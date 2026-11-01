"""Coleta e carga da vida de uma lei: tramitacao, autoria e desfecho.

Fica fora de load.py porque tem um ritmo proprio. O resto da carga e por
legislatura ou por ano; esta roda todo dia, sobre uma janela, e cresce para
sempre - em dez anos ela e o acervo mais valioso da plataforma, porque nao da
para reconstruir historico de tramitacao depois.

A coleta e incremental de proposito. A API aceita filtrar proposicoes pela data
de TRAMITACAO, nao so de apresentacao: numa janela de dez dias voltam ~4.400
proposicoes, e entre elas aparece coisa apresentada em 2003 que se mexeu agora.
Sem esse filtro a atualizacao diaria teria que varrer o acervo inteiro.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

from . import bronze, tramitacao as T
from .config import DERIVADO
from .load import _data_br, registra_fonte
from .sources import camara, senado

# Tipos que podem virar norma. O resto (requerimento, recurso, destaque,
# parecer) e instrumento de processo, nao proposta de lei - entra no sistema
# como etapa de outra proposicao, nunca como projeto na aba de leis.
TIPOS_LEI = ("PL", "PEC", "PLP", "MPV", "PDL", "PDC", "PLN", "PLV")

URI_DEP = re.compile(r"/deputados/(\d+)")


# ------------------------------------------------------------------- coleta

def ingest(inicio: str, fim: str, so_tipos: bool = True,
           progresso=None) -> dict:
    """Baixa proposicoes que tramitaram na janela, com trilha e autoria."""
    props = camara.proposicoes_que_tramitaram(inicio, fim)
    if so_tipos:
        props = [p for p in props if p.get("siglaTipo") in TIPOS_LEI]
    ids = sorted({str(p["id"]) for p in props})

    detalhes = camara.proposicoes_por_id(ids)
    trilhas = camara.tramitacoes_em_lote(ids, progresso=progresso)
    autorias = camara.autores_em_lote(ids, progresso=progresso)

    pacote = {"janela": [inicio, fim], "detalhes": detalhes,
              "tramitacoes": trilhas, "autores": autorias}
    bronze.guarda(camara.FONTE_API, f"leis_{inicio}_{fim}.json",
                  json.dumps(pacote, ensure_ascii=False).encode(),
                  f"{camara.API}/proposicoes?dataInicio={inicio}&dataFim={fim}")
    DERIVADO.mkdir(parents=True, exist_ok=True)
    (DERIVADO / f"leis_{inicio}_{fim}.json").write_text(
        json.dumps(pacote, ensure_ascii=False))

    return {"tramitaram": len(props), "proposicoes": len(ids),
            "com_trilha": sum(1 for v in trilhas.values() if v),
            "movimentacoes": sum(len(v) for v in trilhas.values())}


def ingest_senado(ids_camara: list[str], detalhes: dict,
                  progresso=None) -> dict[str, dict]:
    """Busca no Senado as materias que chegaram la.

    So vale a pena para quem passou da casa de origem, ou nasceu no Senado:
    pedir o processo de 4.000 proposicoes que nunca sairam da Camara seria
    gastar requisicao para receber nada.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def um(pid: str):
        d = detalhes.get(pid) or {}
        p = senado.processo(d.get("siglaTipo"), d.get("numero"), d.get("ano"))
        if not p:
            return pid, None
        return pid, senado.detalhe(p["id"])

    saida: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:   # servico mais lento
        fut = [pool.submit(um, i) for i in ids_camara]
        for n, f in enumerate(as_completed(fut), 1):
            try:
                pid, det = f.result()
                if det:
                    saida[pid] = det
            except Exception:
                pass
            if progresso and n % 50 == 0:
                progresso(n, len(ids_camara))
    return saida


# -------------------------------------------------------------------- carga

def _upsert_proposicao(cur, pid: str, d: dict, fonte_id: int) -> int:
    st = d.get("statusProposicao") or {}
    cur.execute(
        """insert into proposicao
             (ente_codigo, id_externo, tipo, numero, ano, ementa,
              data_apresentacao, situacao, cod_situacao, casa_origem, regime,
              apreciacao, url_integra, atualizado_em, fonte_registro_id)
           values ('0',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),%s)
           on conflict (ente_codigo, id_externo) do update set
             ementa       = coalesce(excluded.ementa, proposicao.ementa),
             situacao     = excluded.situacao,
             cod_situacao = excluded.cod_situacao,
             regime       = excluded.regime,
             apreciacao   = excluded.apreciacao,
             url_integra  = coalesce(excluded.url_integra, proposicao.url_integra),
             data_apresentacao = coalesce(excluded.data_apresentacao,
                                          proposicao.data_apresentacao),
             atualizado_em = now()
           returning id""",
        (pid, d.get("siglaTipo"), d.get("numero"), d.get("ano"),
         (d.get("ementa") or "").strip() or None,
         _data_br(d.get("dataApresentacao")),
         st.get("descricaoSituacao"), st.get("codSituacao"),
         st.get("siglaOrgao"), st.get("regime"), st.get("apreciacao"),
         d.get("urlInteiroTeor"), fonte_id))
    return cur.fetchone()[0]


def _grava_etapas(cur, prop_id: int, fonte: str, etapas: list[dict],
                  fonte_id: int) -> None:
    """Regrava a trilha daquela casa.

    Delete + insert em vez de upsert: a sequencia do Senado vem nula e, em
    Postgres, nulo nao conflita com nulo - um upsert duplicaria a trilha a cada
    execucao. A trilha e sempre rebaixada inteira da fonte, entao regravar e
    tao correto quanto e bem mais simples. O id da etapa nao e URL publica,
    logo nao precisa ser estavel.
    """
    cur.execute("delete from etapa where proposicao_id=%s and fonte=%s",
                (prop_id, fonte))
    for e in etapas:
        cur.execute(
            """insert into etapa
                 (proposicao_id, fonte, sequencia, data_hora, orgao, cod_tipo,
                  descricao, despacho, situacao, cod_situacao, url, relator,
                  marco, fase, metodo, fonte_registro_id)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (prop_id, fonte, e.get("sequencia"), e.get("dataHora"),
             e.get("siglaOrgao"), str(e.get("codTipoTramitacao") or "") or None,
             e.get("descricaoTramitacao"), e.get("despacho"),
             e.get("descricaoSituacao"), e.get("codSituacao"),
             e.get("url"), e.get("relator"),
             e.get("marco"), e.get("fase"), e.get("metodo"), fonte_id))


def _etapa_apresentacao(d: dict, esfera: str = "FEDERAL") -> dict | None:
    """A apresentacao vem da propria proposicao, nao do historico.

    Os codigos candidatos no historico (100, 105, 604) disparam tambem para
    parecer, mensagem do Executivo e projeto apensado: na trilha do PL
    1087/2025 produziam tres "Apresentado", nenhum na data certa. A data de
    apresentacao e campo publicado - usar ela e trocar palpite por dado.
    """
    quando = d.get("dataApresentacao")
    if not quando:
        return None
    return {"dataHora": quando, "sequencia": 0,
            "siglaOrgao": (d.get("statusProposicao") or {}).get("siglaOrgao"),
            "codTipoTramitacao": "APRESENTACAO",
            "descricaoTramitacao": "Apresentação da proposição",
            "despacho": None, "url": d.get("urlInteiroTeor"),
            "marco": "APRESENTACAO", "fase": T.fase_de("APRESENTACAO", esfera),
            "metodo": "codigo"}


def _grava_autores(cur, prop_id: int, autores: list[dict],
                   mandato_por_dep: dict[str, int]) -> None:
    cur.execute("delete from autoria_proposicao where proposicao_id=%s and papel='autor'",
                (prop_id,))
    for a in autores:
        nome = (a.get("nome") or "").strip()
        if not nome:
            continue
        m = URI_DEP.search(a.get("uri") or "")
        pessoa = mandato_por_dep.get(m.group(1)) if m else None
        cur.execute(
            """insert into autoria_proposicao
                 (proposicao_id, pessoa_id, nome, tipo, ordem, proponente, papel)
               values (%s,%s,%s,%s,%s,%s,'autor')
               on conflict (proposicao_id, nome, papel) do nothing""",
            (prop_id, pessoa, nome, a.get("tipo"),
             a.get("ordemAssinatura"), bool(a.get("proponente"))))


def _grava_relatores(cur, prop_id: int, etapas: list[dict]) -> int:
    """O relator sai do despacho de designacao.

    Vale mais que o autor em muitos casos: no PL 1087/2025 o autor e o Poder
    Executivo, mas o texto aprovado foi a subemenda substitutiva global do
    relator, que prejudicou a proposicao inicial inteira. Mostrar os dois lado
    a lado e a parte mais educativa da pagina.
    """
    vistos: dict[str, str | None] = {}
    for e in etapas:
        if r := T.relator_de(e.get("despacho")):
            vistos[r[0]] = r[1]
    cur.execute("delete from autoria_proposicao where proposicao_id=%s and papel='relator'",
                (prop_id,))
    for ordem, (nome, sigla) in enumerate(vistos.items(), 1):
        partido, _, uf = (sigla or "").partition("-")
        cur.execute(
            """insert into autoria_proposicao
                 (proposicao_id, nome, tipo, partido, uf, ordem, papel)
               values (%s,%s,'Deputado(a) relator(a)',%s,%s,%s,'relator')
               on conflict (proposicao_id, nome, papel) do nothing""",
            (prop_id, nome, partido.strip() or None, uf.strip() or None, ordem))
    return len(vistos)


def _fecha_proposicao(cur, prop_id: int, etapas: list[dict], cod_situacao,
                      sen: dict | None) -> str | None:
    """Grava o estado atual e a norma gerada; devolve divergencia, se houver."""
    r = T.resumo(etapas)
    norma = None
    for e in reversed(etapas):
        if n := T.norma_gerada(e.get("despacho")):
            norma = (*n, None)
            break
    # O Senado publica a norma estruturada. Quando as duas fontes falam, a dele
    # vence: regex sobre despacho e deducao, campo e fato.
    if sen and (n := senado.norma_de(sen)):
        norma = n

    cur.execute(
        """update proposicao set marco_atual=%s, fase_atual=%s,
             norma_tipo=%s, norma_numero=%s, norma_ano=%s, norma_data=%s,
             tramitando=%s, id_senado=%s, atualizado_em=now()
           where id=%s""",
        (r["marco_atual"], r["fase_atual"],
         norma[0] if norma else None, norma[1] if norma else None,
         (norma[2] or None) if norma else None,
         _data_br(norma[3]) if norma and len(norma) > 3 else None,
         None if r["desfecho"] else True,
         str(sen.get("id")) if sen else None, prop_id))

    falta = T.confere(cod_situacao, etapas)
    # Segunda conferencia, independente: o Senado declara o desfecho em campo
    # proprio. Se ele diz LEI e a trilha nao achou, e regressao - e esse e o
    # cruzamento que a Camara sozinha nao permite fazer.
    if not falta and sen and (d := senado.desfecho_de(sen)):
        if d not in {e.get("marco") for e in etapas}:
            falta = f"{d} (declarado pelo Senado)"

    if falta:
        cur.execute(
            """insert into divergencia_tramitacao
                 (proposicao_id, tipo, esperado, encontrado)
               values (%s,'desfecho_ausente',%s,%s)
               on conflict (proposicao_id, tipo) do update set
                 esperado=excluded.esperado, encontrado=excluded.encontrado,
                 detectado_em=now(), resolvido_em=null""",
            (prop_id, falta, r["marco_atual"]))
    else:
        cur.execute(
            """update divergencia_tramitacao set resolvido_em=now()
                where proposicao_id=%s and resolvido_em is null""", (prop_id,))
    return falta


def carrega(cur, fonte_id: int, inicio: str, fim: str,
            com_senado: bool = True, progresso=None) -> dict:
    pacote = json.loads((DERIVADO / f"leis_{inicio}_{fim}.json").read_text())
    detalhes, trilhas = pacote["detalhes"], pacote["tramitacoes"]
    autorias = pacote.get("autores", {})

    cur.execute("""select ie.id_na_fonte, ie.pessoa_id from identidade_externa ie
                    where ie.fonte='camara'""")
    pessoa_por_dep = {r[0]: r[1] for r in cur.fetchall()}

    # Quem chegou na casa revisora: so esses valem consulta ao Senado.
    classificadas: dict[str, list[dict]] = {}
    alem_da_origem: list[str] = []
    for pid, tr in trilhas.items():
        # Hoje tudo que entra por aqui e federal (ente '0'), mas a esfera e
        # explicita de proposito: quando entrar lei estadual ou municipal, o
        # caminho muda de sete etapas para cinco e a fase tem que acompanhar.
        esfera = T.esfera_de((detalhes.get(pid) or {}).get("ente_codigo") or "0")
        et = T.trilha(tr, esfera)
        if ap := _etapa_apresentacao(detalhes.get(pid) or {}, esfera):
            et.insert(0, ap)
        classificadas[pid] = et
        marcos = {e.get("marco") for e in et}
        if marcos & {"CASA_REVISORA", "PLENARIO_REVISORA", "SANCAO", "LEI",
                     "PROMULGACAO", "VETO_TOTAL"}:
            alem_da_origem.append(pid)

    senados: dict[str, dict] = {}
    if com_senado and alem_da_origem:
        senados = ingest_senado(alem_da_origem, detalhes, progresso)

    n_prop = n_etapa = n_marco = n_rel = n_aut = 0
    divergencias: list[tuple[str, str]] = []
    normas = 0

    for pid, et in classificadas.items():
        d = detalhes.get(pid)
        if not d:
            continue
        prop_id = _upsert_proposicao(cur, pid, d, fonte_id)
        n_prop += 1

        _grava_etapas(cur, prop_id, "camara", et, fonte_id)
        n_etapa += len(et)
        n_marco += sum(1 for e in et if e.get("marco"))

        sen = senados.get(pid)
        todas = list(et)
        if sen:
            mapa = senado.marcos(sen)
            sen_et = []
            for e in senado.trilha(sen):
                m = mapa.get(e["codTipoTramitacao"])
                sen_et.append({**e, "marco": m, "fase": T.fase_de(m, esfera),
                               "metodo": "codigo"})
            _grava_etapas(cur, prop_id, "senado", sen_et, fonte_id)
            n_etapa += len(sen_et)
            n_marco += sum(1 for e in sen_et if e.get("marco"))
            todas += sen_et

        _grava_autores(cur, prop_id, autorias.get(pid, []), pessoa_por_dep)
        n_aut += len(autorias.get(pid, []))
        n_rel += _grava_relatores(cur, prop_id, et)

        falta = _fecha_proposicao(cur, prop_id, todas,
                                  (d.get("statusProposicao") or {}).get("codSituacao"), sen)
        if falta:
            divergencias.append((f"{d.get('siglaTipo')} {d.get('numero')}/{d.get('ano')}", falta))
        cur.execute("select norma_numero from proposicao where id=%s", (prop_id,))
        normas += 1 if cur.fetchone()[0] else 0

    return {"proposicoes": n_prop, "etapas": n_etapa, "marcos": n_marco,
            "ruido_descartado": n_etapa - n_marco,
            "autores": n_aut, "relatores": n_rel,
            "no_senado": len(senados), "viraram_norma": normas,
            "divergencias": divergencias}


# ------------------------------------------------------------------ agenda

def agenda(cur, dias: int = 21) -> dict:
    """O que esta marcado para ser votado, da pauta ja carregada.

    Nao busca nada: le o que ingest-eventos gravou. A aba "vai ser votada" e
    uma consulta, nao uma coleta.
    """
    cur.execute("""
        select count(distinct pi.proposicao_id)
          from pauta_item pi join evento e on e.id = pi.evento_id
         where e.inicio between now() and now() + make_interval(days => %s)""",
                (dias,))
    return {"na_pauta": cur.fetchone()[0]}


def principal(inicio: str | None = None, fim: str | None = None,
              com_senado: bool = True) -> dict:
    """Uma rodada completa. Sem janela, pega os ultimos 7 dias."""
    from .load import conecta

    fim = fim or date.today().isoformat()
    inicio = inicio or (date.fromisoformat(fim) - timedelta(days=7)).isoformat()

    def tick(n, t):
        print(f"  ... {n}/{t}", flush=True)

    print(f"coletando proposicoes que tramitaram entre {inicio} e {fim}")
    r_ing = ingest(inicio, fim, progresso=tick)
    print(json.dumps(r_ing, ensure_ascii=False, indent=1))

    with conecta() as con, con.cursor() as cur:
        fid = registra_fonte(cur, "camara_api",
                             f"{camara.API}/proposicoes?dataInicio={inicio}&dataFim={fim}")
        r = carrega(cur, fid, inicio, fim, com_senado=com_senado, progresso=tick)
        con.commit()
    return {**r_ing, **r}
