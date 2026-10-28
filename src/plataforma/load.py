"""Carga do canonico no Postgres.

Idempotente: pode rodar de novo sem duplicar. Toda linha publicavel ganha um
fonte_registro, que e o que permite a tela dizer de onde veio o numero.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime

import psycopg
import requests

from . import bronze
from .config import DATABASE_URL, DERIVADO, cpf_valido, hash_cpf
from .sources import camara, tse

IBGE_UF = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
LEGISLATURA_ATUAL = "57"


def conecta():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL ausente no .env")
    return psycopg.connect(DATABASE_URL)


def _data_br(v: str | None) -> date | None:
    if not v:
        return None
    for f in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(v[:19], f).date()
        except ValueError:
            continue
    return None


def _num(v: str | None) -> float:
    if not v:
        return 0.0
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return 0.0


def _chave_despesa(d: dict) -> str:
    """Chave estavel para a despesa.

    O CSV da cota nao tem coluna unica: ideDocumento repete '0' em milhares de
    linhas e vem vazio em outras. Entao a chave e o hash dos campos de negocio.
    Duas linhas identicas em todos eles sao indistinguiveis mesmo - e viram uma.
    """
    bruto = "|".join((d.get(c) or "").strip() for c in (
        "ideCadastro", "ideDocumento", "datEmissao", "vlrLiquido",
        "txtCNPJCPF", "numSubCota", "txtNumero", "numMes", "numAno"))
    return hashlib.sha1(bruto.encode()).hexdigest()[:24]


def registra_fonte(cur, fonte: str, url: str, hash_conteudo: str | None = None,
                   tipo: str = "automatico") -> int:
    cur.execute(
        "insert into fonte_registro (fonte, tipo, url_origem, hash_conteudo)"
        " values (%s,%s,%s,%s) returning id",
        (fonte, tipo, url, hash_conteudo))
    return cur.fetchone()[0]


def carrega_entes(cur) -> dict[str, str]:
    """Uniao e os 27 estados. Municipio entra quando a Fase 4 chegar."""
    cur.execute("insert into ente (codigo_ibge, nivel, nome) values ('0','uniao','União')"
                " on conflict (codigo_ibge) do nothing")
    ufs = requests.get(IBGE_UF, timeout=60).json()
    por_sigla = {}
    for u in ufs:
        cod = str(u["id"])
        por_sigla[u["sigla"]] = cod
        cur.execute(
            "insert into ente (codigo_ibge, nivel, nome, uf) values (%s,'estado',%s,%s)"
            " on conflict (codigo_ibge) do update set nome = excluded.nome",
            (cod, u["nome"], u["sigla"]))
    return por_sigla


def carrega_deputados(cur, fonte_id: int, uf_ibge: dict[str, str]) -> dict[str, int]:
    """Pessoa + identidade nas duas fontes + mandato. Devolve id_camara -> mandato_id."""
    deps = {str(d["id"]): d for d in json.loads((DERIVADO / "camara_deputados.json").read_text())}
    vinc = json.loads((DERIVADO / "vinculos_2022.json").read_text())
    man_tse = bronze.ja_baixado_hoje(tse.FONTE, "consulta_cand_2022.zip")
    tse_idx = tse.por_cpf(man_tse) if man_tse else {}

    mandatos: dict[str, int] = {}
    for v in vinc["resolvidos"]:
        dep = deps.get(v["id_camara"])
        if dep is None:
            continue
        reg = tse_idx.get(v["cpf"] or "", {})
        cpf = v["cpf"] if cpf_valido(v["cpf"]) else None

        cur.execute(
            """insert into pessoa (nome_completo, nome_urna, cpf_hash, data_nascimento,
                                   sexo, cor_raca, foto_url)
               values (%s,%s,%s,%s,%s,%s,%s)
               on conflict (cpf_hash) do update set
                 nome_completo = excluded.nome_completo,
                 foto_url      = coalesce(excluded.foto_url, pessoa.foto_url)
               returning id""",
            (reg.get("nome_completo") or v["nome_camara"], dep.get("nome"),
             hash_cpf(cpf), _data_br(reg.get("nascimento")),
             reg.get("sexo"), reg.get("cor_raca"), dep.get("urlFoto")))
        pessoa_id = cur.fetchone()[0]

        cur.execute(
            """insert into identidade_externa
                 (fonte, id_na_fonte, pessoa_id, metodo, confianca, fonte_registro_id)
               values ('camara',%s,%s,%s,%s,%s)
               on conflict (fonte, id_na_fonte) do update set
                 pessoa_id = excluded.pessoa_id, confianca = excluded.confianca""",
            (v["id_camara"], pessoa_id, v["metodo"] if v["metodo"] in ("cpf",) else "nome_nascimento",
             v["confianca"], fonte_id))
        if v.get("sq_candidato"):
            cur.execute(
                """insert into identidade_externa
                     (fonte, id_na_fonte, pessoa_id, metodo, confianca, fonte_registro_id)
                   values ('tse',%s,%s,%s,%s,%s)
                   on conflict (fonte, id_na_fonte) do nothing""",
                (v["sq_candidato"], pessoa_id,
                 "cpf" if v["metodo"] == "cpf" else "nome_nascimento",
                 v["confianca"], fonte_id))

        cur.execute(
            """insert into mandato (pessoa_id, cargo, ente_codigo, partido, legislatura,
                                    situacao, fonte_registro_id)
               values (%s,'DEPUTADO_FEDERAL',%s,%s,%s,'em_exercicio',%s)
               on conflict (pessoa_id, cargo, ente_codigo, legislatura) do update set
                 partido = excluded.partido, situacao = excluded.situacao
               returning id""",
            (pessoa_id, uf_ibge[dep["siglaUf"]], dep.get("siglaPartido"),
             LEGISLATURA_ATUAL, fonte_id))
        mandatos[v["id_camara"]] = cur.fetchone()[0]
    return mandatos


def carrega_despesas(cur, fonte_id: int, mandatos: dict[str, int], ano: int) -> tuple[int, int]:
    man = bronze.ja_baixado_hoje(camara.FONTE_CEAP, f"Ano-{ano}.csv.zip")
    if man is None:
        return (0, 0)
    inseridas = orfas = repetidas = 0
    linhas, vistos = [], set()
    for d in camara.le_ceap(man):
        mid = mandatos.get((d.get("ideCadastro") or "").strip())
        if mid is None:
            orfas += 1          # liderancas e bancadas gastam pela cota sem ter mandato
            continue
        chave = _chave_despesa(d)
        if chave in vistos:
            repetidas += 1
            continue
        vistos.add(chave)
        linhas.append((
            mid, _data_br(d.get("datEmissao")), (d.get("txtDescricao") or "").strip()[:200],
            (d.get("txtDescricaoEspecificacao") or "").strip()[:300] or None,
            (d.get("txtFornecedor") or "").strip()[:200],
            (d.get("txtCNPJCPF") or "").strip()[:30],
            _num(d.get("vlrLiquido")), _num(d.get("vlrGlosa")),
            (d.get("urlDocumento") or "").strip() or None,
            chave, fonte_id))
    with cur.copy(
        "copy despesa (mandato_id, data, categoria, descricao, fornecedor, cnpj_cpf,"
        " valor, valor_glosa, documento_url, id_externo, fonte_registro_id) from stdin"
    ) as cp:
        for l in linhas:
            cp.write_row(l)
            inseridas += 1
    return inseridas, orfas, repetidas




def carrega_historicos(cur, fonte_id: int, uf_ibge: dict[str, str],
                       inicio: str, fim: str) -> int:
    """Quem votou em 2026 mas nao esta entre os 513 de hoje.

    Suplente que assumiu por um periodo e deputado que saiu no meio do mandato
    votaram de verdade. Ignorar esses votos perderia 4% do total e faria o
    placar de votacao nao fechar. Entram com mandato 'encerrado'.
    """
    nominais = json.loads((DERIVADO / f"votos_{inicio}_{fim}.json").read_text())
    ponte = json.loads((DERIVADO / "camara_ponte_cpf.json").read_text())
    cpf_por_ide = {v["ide_cadastro"]: cpf for cpf, v in ponte.items()}

    cur.execute("select id_na_fonte from identidade_externa where fonte='camara'")
    ja_tem = {r[0] for r in cur.fetchall()}

    man_tse = bronze.ja_baixado_hoje(tse.FONTE, "consulta_cand_2022.zip")
    tse_idx = tse.por_cpf(man_tse) if man_tse else {}

    faltantes: dict[str, dict] = {}
    for votos in nominais.values():
        for v in votos:
            d = v.get("deputado_") or {}
            did = str(d.get("id") or "")
            if did and did not in ja_tem:
                faltantes.setdefault(did, d)

    for did, d in faltantes.items():
        cpf = cpf_por_ide.get(did)
        reg = tse_idx.get(cpf or "", {})
        cpf = cpf if cpf_valido(cpf) else None
        cur.execute(
            """insert into pessoa (nome_completo, nome_urna, cpf_hash, data_nascimento,
                                   sexo, cor_raca, foto_url)
               values (%s,%s,%s,%s,%s,%s,%s)
               on conflict (cpf_hash) do update set nome_completo = excluded.nome_completo
               returning id""",
            (reg.get("nome_completo") or d.get("nome"), d.get("nome"), hash_cpf(cpf),
             _data_br(reg.get("nascimento")), reg.get("sexo"), reg.get("cor_raca"),
             d.get("urlFoto")))
        pessoa_id = cur.fetchone()[0]

        cur.execute(
            """insert into identidade_externa
                 (fonte, id_na_fonte, pessoa_id, metodo, confianca, fonte_registro_id)
               values ('camara',%s,%s,%s,%s,%s)
               on conflict (fonte, id_na_fonte) do nothing""",
            (did, pessoa_id, "cpf" if cpf else "manual", 1.0 if cpf else 0.5, fonte_id))

        uf = (d.get("siglaUf") or "").strip()
        if uf in uf_ibge:
            cur.execute(
                """insert into mandato (pessoa_id, cargo, ente_codigo, partido, legislatura,
                                        situacao, fonte_registro_id)
                   values (%s,'DEPUTADO_FEDERAL',%s,%s,%s,'encerrado',%s)
                   on conflict (pessoa_id, cargo, ente_codigo, legislatura) do nothing""",
                (pessoa_id, uf_ibge[uf], d.get("siglaPartido"), LEGISLATURA_ATUAL, fonte_id))
    return len(faltantes)


def carrega_votacoes(cur, fonte_id: int, inicio: str, fim: str) -> dict:
    """Proposicoes, votacoes e votos individuais.

    O campo votacao.tipo separa nominal de simbolica. A maioria das votacoes e
    simbolica e nao tem voto individual: a tela precisa dizer isso em vez de
    sugerir uma cobertura que nao existe.
    """
    import re

    vs = json.loads((DERIVADO / f"votacoes_{inicio}_{fim}.json").read_text())
    nominais = json.loads((DERIVADO / f"votos_{inicio}_{fim}.json").read_text())
    props = json.loads((DERIVADO / f"proposicoes_{inicio}_{fim}.json").read_text())

    # proposicoes
    prop_id: dict[str, int] = {}
    for pid, d in props.items():
        cur.execute(
            """insert into proposicao (ente_codigo, id_externo, tipo, numero, ano,
                                       ementa, data_apresentacao, situacao, fonte_registro_id)
               values ('0',%s,%s,%s,%s,%s,%s,%s,%s)
               on conflict (ente_codigo, id_externo) do update set ementa = excluded.ementa
               returning id""",
            (pid, d.get("siglaTipo"), d.get("numero"), d.get("ano"),
             (d.get("ementa") or "").strip() or None,
             _data_br(d.get("dataApresentacao")),
             ((d.get("statusProposicao") or {}).get("descricaoSituacao")), fonte_id))
        prop_id[pid] = cur.fetchone()[0]

    # mandato por id da Camara, via identidade_externa
    cur.execute("""select ie.id_na_fonte, m.id from identidade_externa ie
                     join mandato m on m.pessoa_id = ie.pessoa_id
                    where ie.fonte='camara' and m.cargo='DEPUTADO_FEDERAL'""")
    mandato_por_dep = {r[0]: r[1] for r in cur.fetchall()}

    n_vot = n_voto = n_orfao = 0
    for v in vs:
        # Primeiro o campo oficial; quando ele vem nulo - o que acontece na
        # maioria das vezes - cai no prefixo do id da votacao, que e o id da
        # propria proposicao.
        m = re.search(r"/proposicoes/(\d+)", v.get("uriProposicaoObjeto") or "")
        pid = prop_id.get(m.group(1)) if m else None
        if pid is None and (pref := str(v.get("id", "")).split("-")[0]).isdigit():
            pid = prop_id.get(pref)
        votos = nominais.get(v["id"], [])
        cur.execute(
            """insert into votacao (ente_codigo, id_externo, proposicao_id, orgao,
                                    descricao, data_hora, aprovada, tipo, fonte_registro_id)
               values ('0',%s,%s,%s,%s,%s,%s,%s,%s)
               on conflict (ente_codigo, id_externo) do update set
                 descricao = excluded.descricao, tipo = excluded.tipo,
                 proposicao_id = coalesce(excluded.proposicao_id, votacao.proposicao_id),
                 aprovada = excluded.aprovada
               returning id""",
            (v["id"], pid, v.get("siglaOrgao"), (v.get("descricao") or "").strip() or None,
             v.get("dataHoraRegistro"),
             None if v.get("aprovacao") is None else bool(v.get("aprovacao")),
             "nominal" if votos else "simbolica", fonte_id))
        vid = cur.fetchone()[0]
        n_vot += 1

        for voto in votos:
            dep = str((voto.get("deputado_") or {}).get("id") or "")
            mid = mandato_por_dep.get(dep)
            if mid is None:
                # suplente que ja saiu, ou deputado de legislatura anterior
                n_orfao += 1
                continue
            cur.execute(
                """insert into voto (votacao_id, mandato_id, tipo_voto) values (%s,%s,%s)
                   on conflict (votacao_id, mandato_id) do nothing""",
                (vid, mid, (voto.get("tipoVoto") or "").strip()))
            n_voto += 1

    return {"proposicoes": len(prop_id), "votacoes": n_vot,
            "votos": n_voto, "votos_sem_mandato": n_orfao,
            "nominais": len(nominais)}



def carrega_eventos(cur, fonte_id: int, inicio: str, fim: str) -> dict:
    """Agenda e pauta. A pauta e o que permite avisar ANTES de a votacao acontecer."""
    evs = json.loads((DERIVADO / f"eventos_{inicio}_{fim}.json").read_text())
    pautas = json.loads((DERIVADO / f"pautas_{inicio}_{fim}.json").read_text())

    evento_id: dict[str, int] = {}
    for e in evs:
        orgao = (e.get("orgaos") or [{}])[0].get("sigla")
        cur.execute(
            """insert into evento (ente_codigo, id_externo, tipo, descricao,
                                   inicio, fim, situacao, fonte_registro_id)
               values ('0',%s,%s,%s,%s,%s,%s,%s)
               on conflict (ente_codigo, id_externo) do update set
                 situacao = excluded.situacao, fim = excluded.fim
               returning id""",
            (str(e["id"]), e.get("descricaoTipo"),
             ((orgao + " · ") if orgao else "") + (e.get("descricao") or "")[:400],
             e.get("dataHoraInicio"), e.get("dataHoraFim"), e.get("situacao"), fonte_id))
        evento_id[str(e["id"])] = cur.fetchone()[0]

    n_itens = 0
    for eid, itens in pautas.items():
        ev = evento_id.get(eid)
        if ev is None:
            continue
        for it in itens:
            # A materia de verdade: quando o item e um parecer (PRL), a
            # proposicao apreciada esta em proposicaoRelacionada_. Ler so
            # proposicao_ faz o alerta anunciar "PRL 1/0" em vez de "PL 6198/2025".
            pr = it.get("proposicaoRelacionada_") or it.get("proposicao_") or {}
            if not pr.get("id"):
                continue
            cur.execute(
                """insert into proposicao (ente_codigo, id_externo, tipo, numero, ano,
                                           ementa, fonte_registro_id)
                   values ('0',%s,%s,%s,%s,%s,%s)
                   on conflict (ente_codigo, id_externo) do update set
                     ementa = coalesce(excluded.ementa, proposicao.ementa)
                   returning id""",
                (str(pr["id"]), pr.get("siglaTipo"), pr.get("numero"), pr.get("ano"),
                 (pr.get("ementa") or "").strip() or None, fonte_id))
            prop = cur.fetchone()[0]
            cur.execute(
                """insert into pauta_item (evento_id, proposicao_id, ordem, regime, topico,
                                          relator, texto_parecer, titulo)
                   values (%s,%s,%s,%s,%s,%s,%s,%s)
                   on conflict (evento_id, proposicao_id) do update set
                     regime = excluded.regime, relator = excluded.relator,
                     texto_parecer = excluded.texto_parecer, titulo = excluded.titulo""",
                (ev, prop, it.get("ordem"), it.get("regime"), (it.get("topico") or "")[:200],
                 ((it.get("relator") or {}).get("nome")),
                 (it.get("textoParecer") or "")[:600] or None,
                 (it.get("titulo") or "")[:120] or None))
            n_itens += 1
    return {"eventos": len(evento_id), "itens_de_pauta": n_itens}


def principal(ano_ceap: int = 2026, periodo: tuple[str, str] | None = None,
              agenda: tuple[str, str] | None = None):
    with conecta() as con, con.cursor() as cur:
        cur.execute("truncate despesa, voto, autoria, presenca,"
                    " mandato, identidade_externa, pessoa restart identity cascade")
        uf_ibge = carrega_entes(cur)
        f_cam = registra_fonte(cur, "camara_api", f"{camara.API}/deputados")
        mandatos = carrega_deputados(cur, f_cam, uf_ibge)
        print(f"pessoas e mandatos: {len(mandatos)}")

        man = bronze.ja_baixado_hoje(camara.FONTE_CEAP, f"Ano-{ano_ceap}.csv.zip")
        f_ceap = registra_fonte(cur, "camara_ceap", man.url if man else "", man.sha256 if man else None)
        ins, orfas, rep = carrega_despesas(cur, f_ceap, mandatos, ano_ceap)
        print(f"despesas: {ins} carregadas, {orfas} sem mandato (liderancas e bancadas),"
              f" {rep} linhas identicas descartadas")
        if periodo:
            f_vot = registra_fonte(cur, "camara_api", f"{camara.API}/votacoes")
            n_hist = carrega_historicos(cur, f_vot, uf_ibge, *periodo)
            print(f"suplentes e ex-deputados que votaram no periodo: {n_hist}")
            r = carrega_votacoes(cur, f_vot, *periodo)
            print("votacoes:", json.dumps(r, ensure_ascii=False))
        if agenda:
            f_ev = registra_fonte(cur, "camara_api", f"{camara.API}/eventos")
            print("agenda:", json.dumps(carrega_eventos(cur, f_ev, *agenda), ensure_ascii=False))
        con.commit()


if __name__ == "__main__":
    import sys
    per = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else None
    age = (sys.argv[3], sys.argv[4]) if len(sys.argv) > 4 else None
    principal(periodo=per, agenda=age)
