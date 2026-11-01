"""Importacao de CSV preenchido a mao.

Para quem opera sozinho, planilha ganha de qualquer tela de cadastro. Entao o
painel nao e um CRUD: e um importador que valida, mostra o diff, espera
confirmacao e grava com numero de lote - reversivel por inteiro, porque dado
digitado a mao vai estar errado alguma hora.

Toda linha importada nasce marcada como manual, com quem inseriu e o link do
documento de onde saiu. Sem esse selo, uma planilha errada contamina a
confianca em tudo que e automatico.
"""
from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import psycopg

from .config import DATABASE_URL, cpf_valido, hash_cpf, normaliza_cpf

CARGOS = {"PRESIDENTE", "GOVERNADOR", "PREFEITO", "SENADOR",
          "DEPUTADO_FEDERAL", "DEPUTADO_ESTADUAL", "VEREADOR"}
SITUACOES = {"eleito", "diplomado", "em_exercicio", "afastado", "encerrado"}
ESFERAS = {"MUNICIPAL", "ESTADUAL", "FEDERAL"}


@dataclass
class Campo:
    nome: str
    obrigatorio: bool = False
    tipo: str = "texto"                 # texto, cpf, ibge, data, numero, enum, url
    valores: set[str] | None = None


@dataclass
class Spec:
    entidade: str
    tabela: str
    campos: list[Campo]
    chave: tuple[str, ...]              # chave natural, para decidir novo x alterado
    upsert: Callable
    sql_existente: str = ""

    @property
    def nomes(self) -> list[str]:
        return [c.nome for c in self.campos]


# ------------------------------------------------------------------ validacao
#
# Um parser so, usado pela validacao e pela gravacao. Quando eram dois, o
# validador recusava "1.250,00" e o gravador aceitava: a planilha era barrada
# por um valor que o banco teria guardado certo.

def _numero(v: str | None) -> float | None:
    """Aceita '1.234,56', '1234.56' e 'R$ 1.234,56'. Devolve None se nao for numero."""
    if v is None or not str(v).strip():
        return None
    s = str(v).strip().replace("R$", "").replace(" ", "").replace("\u00a0", "")
    if "," in s:                      # formato brasileiro: ponto e milhar
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _valida_linha(spec: Spec, linha: dict, n: int, entes: set[str]) -> list[str]:
    erros = []
    for c in spec.campos:
        v = (linha.get(c.nome) or "").strip()
        if c.obrigatorio and not v:
            erros.append(f"linha {n}: '{c.nome}' é obrigatório")
            continue
        if not v:
            continue
        if c.tipo == "cpf" and not cpf_valido(v):
            erros.append(f"linha {n}: CPF '{v}' tem dígito verificador inválido")
        elif c.tipo == "ibge" and v not in entes:
            erros.append(f"linha {n}: código IBGE '{v}' não existe")
        elif c.tipo == "data":
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                erros.append(f"linha {n}: data '{v}' não está em AAAA-MM-DD")
        elif c.tipo == "numero":
            if _numero(v) is None:
                erros.append(f"linha {n}: '{c.nome}' = '{v}' não é número")
        elif c.tipo == "enum" and c.valores and v.upper() not in c.valores \
                and v not in c.valores:
            erros.append(f"linha {n}: '{c.nome}' = '{v}' não é um de {sorted(c.valores)}")
    return erros


# -------------------------------------------------------------------- upserts

def _up_competencia(cur, linha, fonte_id):
    cur.execute("""
        insert into competencia (tema, esfera, cargo_responsavel, descricao,
                                 base_legal, fonte_registro_id)
        values (%s,%s,%s,%s,%s,%s)
        on conflict (lower(tema), esfera, cargo_responsavel) do update set
          descricao = excluded.descricao, base_legal = excluded.base_legal,
          fonte_registro_id = excluded.fonte_registro_id""",
        (linha["tema"], linha["esfera"].upper(), linha["cargo_responsavel"],
         linha.get("descricao") or None, linha.get("base_legal") or None, fonte_id))


def _up_orgao(cur, linha, fonte_id):
    cur.execute("""
        insert into orgao_municipal (ente_codigo, nome_camara, url_portal,
                                     url_transparencia, formato, tem_api, qualidade,
                                     observacao, fonte_registro_id)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        on conflict (ente_codigo) do update set
          nome_camara = excluded.nome_camara, url_portal = excluded.url_portal,
          url_transparencia = excluded.url_transparencia, formato = excluded.formato,
          tem_api = excluded.tem_api, qualidade = excluded.qualidade,
          observacao = excluded.observacao, fonte_registro_id = excluded.fonte_registro_id""",
        (linha["ibge_municipio"], linha.get("nome_camara"), linha.get("url_portal"),
         linha.get("url_transparencia"), linha.get("formato"),
         (linha.get("tem_api") or "").strip().lower() in ("sim", "true", "1"),
         (linha.get("qualidade") or "").upper() or None,
         linha.get("observacao"), fonte_id))


def _up_pessoa(cur, linha, fonte_id):
    cpf = normaliza_cpf(linha.get("cpf"))
    cur.execute("""
        insert into pessoa (nome_completo, nome_urna, cpf_hash, data_nascimento,
                            sexo, foto_url)
        values (%s,%s,%s,%s,%s,%s)
        on conflict (cpf_hash) do update set
          nome_completo = excluded.nome_completo, nome_urna = excluded.nome_urna
        returning id""",
        (linha["nome_completo"], linha.get("nome_urna") or None, hash_cpf(cpf),
         linha.get("data_nascimento") or None, linha.get("sexo") or None,
         linha.get("foto_url") or None))
    return cur.fetchone()[0]


def _up_mandato(cur, linha, fonte_id):
    cpf = normaliza_cpf(linha.get("cpf"))
    cur.execute("select id from pessoa where cpf_hash = %s", (hash_cpf(cpf),))
    r = cur.fetchone()
    if r is None:
        raise ValueError(f"CPF {cpf} não existe em pessoa — importe pessoa.csv antes")
    cur.execute("""
        insert into mandato (pessoa_id, cargo, ente_codigo, partido, legislatura,
                             data_inicio, data_fim, situacao, fonte_registro_id)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        on conflict (pessoa_id, cargo, ente_codigo, legislatura) do update set
          partido = excluded.partido, situacao = excluded.situacao,
          data_fim = excluded.data_fim, fonte_registro_id = excluded.fonte_registro_id""",
        (r[0], linha["cargo"].upper(), linha["ibge_municipio"], linha.get("partido"),
         (linha.get("data_inicio") or "")[:4] or None,
         linha.get("data_inicio") or None, linha.get("data_fim") or None,
         linha.get("situacao") or "em_exercicio", fonte_id))


# ---------------------------------------------- identificar o mandato alvo
#
# Aqui mora o problema mais chato do nivel municipal. O importador de mandato
# acha a pessoa pelo CPF, porque para deputado federal o CPF existe. Para
# vereador NAO existe: o TSE publica '-4' ("nao divulgavel") no CPF de
# candidato municipal, e por isso os 58.174 vereadores do banco estao com
# cpf_hash nulo. Uma planilha de despesa de camara municipal chegaria sem como
# apontar para o eleito.
#
# Entao a chave alternativa e (nome de urna + municipio + cargo), que dentro de
# uma cidade e praticamente unica. Quando for ambigua - dois homonimos na mesma
# camara - a importacao para e diz, em vez de escolher um e gravar errado.

def _resolve_mandato(cur, linha) -> int:
    cpf = normaliza_cpf(linha.get("cpf"))
    if cpf and cpf_valido(cpf):
        cur.execute("""select m.id from mandato m
                         join pessoa p on p.id = m.pessoa_id
                        where p.cpf_hash = %s and m.cargo = %s
                          and m.ente_codigo = %s""",
                    (hash_cpf(cpf), (linha.get("cargo") or "").upper(),
                     linha.get("ibge_municipio")))
        achados = [r[0] for r in cur.fetchall()]
        if achados:
            return achados[0]

    nome = (linha.get("nome_urna") or "").strip()
    if not nome:
        raise ValueError("sem CPF válido no banco e sem nome_urna: "
                         "não há como identificar o mandato")
    cur.execute("""select m.id, p.nome_completo from mandato m
                     join pessoa p on p.id = m.pessoa_id
                    where m.ente_codigo = %s and m.cargo = %s
                      and (upper(p.nome_urna) = upper(%s)
                           or upper(p.nome_completo) = upper(%s))""",
                (linha.get("ibge_municipio"), (linha.get("cargo") or "").upper(),
                 nome, nome))
    achados = cur.fetchall()
    if not achados:
        raise ValueError(f"'{nome}' não é {linha.get('cargo')} em "
                         f"{linha.get('ibge_municipio')} — confira o nome de urna")
    if len(achados) > 1:
        nomes = ", ".join(a[1] for a in achados)
        raise ValueError(f"'{nome}' é ambíguo em {linha.get('ibge_municipio')}: "
                         f"{nomes}. Use a coluna cpf para desempatar")
    return achados[0][0]


def _up_gabinete(cur, linha, fonte_id):
    mid = _resolve_mandato(cur, linha)
    # Sem chave natural na tabela: o par (mandato, assessor, mes) e o que
    # identifica a folha. Apagar e reinserir o mes evita somar duas vezes a
    # mesma planilha, que e o erro mais provavel de quem importa a mao.
    cur.execute("""delete from cargo_gabinete
                    where mandato_id=%s and upper(nome_assessor)=upper(%s)
                      and mes_referencia=%s""",
                (mid, linha["nome_assessor"], linha.get("mes_referencia") or None))
    cur.execute("""
        insert into cargo_gabinete (mandato_id, nome_assessor, cargo, vinculo,
                                    remuneracao_bruta, mes_referencia, fonte_registro_id)
        values (%s,%s,%s,%s,%s,%s,%s)""",
        (mid, linha["nome_assessor"], linha.get("cargo_assessor") or None,
         linha.get("vinculo") or None, _dinheiro(linha.get("remuneracao_bruta")),
         linha.get("mes_referencia") or None, fonte_id))


def _up_despesa(cur, linha, fonte_id):
    mid = _resolve_mandato(cur, linha)
    cur.execute("""
        insert into despesa (mandato_id, data, categoria, descricao, fornecedor,
                             cnpj_cpf, valor, documento_url, id_externo,
                             fonte_registro_id)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        on conflict (id_externo) do nothing""",
        (mid, linha.get("data") or None, linha.get("categoria") or None,
         linha.get("descricao") or None, linha.get("fornecedor") or None,
         linha.get("cnpj_cpf") or None, _dinheiro(linha.get("valor")),
         linha.get("documento_url") or None,
         linha.get("id_documento") or None, fonte_id))


def _up_proposicao(cur, linha, fonte_id):
    """Projeto de lei municipal, que nenhuma API entrega.

    ente_codigo e o municipio, nao '0': a mesma tabela guarda PL federal e
    projeto de camara municipal. Era esse o ponto do modelo canonico - o que
    muda e o ente, nunca a estrutura.
    """
    cur.execute("""
        insert into proposicao (ente_codigo, id_externo, tipo, numero, ano, ementa,
                                data_apresentacao, situacao, tema, url_integra,
                                fonte_registro_id)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        on conflict (ente_codigo, id_externo) do update set
          ementa = excluded.ementa, situacao = excluded.situacao,
          tema = excluded.tema, url_integra = excluded.url_integra,
          fonte_registro_id = excluded.fonte_registro_id""",
        (linha["ibge_municipio"], linha["identificador"], linha.get("tipo") or None,
         _inteiro(linha.get("numero")), _inteiro(linha.get("ano")),
         linha.get("ementa") or None, linha.get("data_apresentacao") or None,
         linha.get("situacao_texto") or None, linha.get("tema") or None,
         linha.get("url_integra") or None, fonte_id))


def _dinheiro(v: str | None) -> float:
    return _numero(v) or 0.0


def _inteiro(v: str | None) -> int | None:
    try:
        return int(str(v).strip())
    except (ValueError, AttributeError):
        return None


ESPECS: dict[str, Spec] = {
    "competencia": Spec(
        "competencia", "competencia",
        [Campo("tema", True), Campo("esfera", True, "enum", ESFERAS),
         Campo("cargo_responsavel", True), Campo("descricao"), Campo("base_legal")],
        ("tema", "esfera", "cargo_responsavel"), _up_competencia,
        "select lower(tema)||'|'||esfera||'|'||cargo_responsavel from competencia"),
    "orgao_municipal": Spec(
        "orgao_municipal", "orgao_municipal",
        [Campo("ibge_municipio", True, "ibge"), Campo("uf"), Campo("nome_camara"),
         Campo("url_portal"), Campo("url_transparencia"), Campo("formato"),
         Campo("tem_api"), Campo("qualidade"), Campo("observacao")],
        ("ibge_municipio",), _up_orgao,
        "select ente_codigo from orgao_municipal"),
    "pessoa": Spec(
        "pessoa", "pessoa",
        [Campo("nome_completo", True), Campo("nome_urna"), Campo("cpf", True, "cpf"),
         Campo("data_nascimento", False, "data"), Campo("sexo"), Campo("foto_url"),
         Campo("fonte_url", True), Campo("observacao")],
        ("cpf",), _up_pessoa, ""),
    "mandato": Spec(
        "mandato", "mandato",
        [Campo("cpf", True, "cpf"), Campo("nome_urna"),
         Campo("cargo", True, "enum", CARGOS),
         Campo("ibge_municipio", True, "ibge"), Campo("uf"), Campo("partido"),
         Campo("data_inicio", False, "data"), Campo("data_fim", False, "data"),
         Campo("situacao", False, "enum", SITUACOES), Campo("fonte_url", True)],
        ("cpf", "cargo", "ibge_municipio"), _up_mandato, ""),
    # As tres abaixo cobrem o nivel municipal, onde nao existe API. Todas
    # aceitam cpf OU nome_urna para apontar o mandato, porque o TSE nao
    # divulga o CPF de candidato municipal.
    "gabinete": Spec(
        "gabinete", "cargo_gabinete",
        [Campo("cpf", False, "cpf"), Campo("nome_urna"),
         Campo("cargo", True, "enum", CARGOS),
         Campo("ibge_municipio", True, "ibge"),
         Campo("nome_assessor", True), Campo("cargo_assessor"), Campo("vinculo"),
         Campo("remuneracao_bruta", False, "numero"),
         Campo("mes_referencia", False, "data"), Campo("fonte_url", True)],
        ("ibge_municipio", "nome_urna", "nome_assessor", "mes_referencia"),
        _up_gabinete, ""),
    "despesa": Spec(
        "despesa", "despesa",
        [Campo("cpf", False, "cpf"), Campo("nome_urna"),
         Campo("cargo", True, "enum", CARGOS),
         Campo("ibge_municipio", True, "ibge"),
         Campo("id_documento", True), Campo("data", False, "data"),
         Campo("categoria"), Campo("descricao"), Campo("fornecedor"),
         Campo("cnpj_cpf"), Campo("valor", True, "numero"),
         Campo("documento_url"), Campo("fonte_url", True)],
        ("id_documento",), _up_despesa,
        "select id_externo from despesa where id_externo is not null"),
    "proposicao": Spec(
        "proposicao", "proposicao",
        [Campo("ibge_municipio", True, "ibge"), Campo("identificador", True),
         Campo("tipo"), Campo("numero", False, "numero"), Campo("ano", False, "numero"),
         Campo("ementa", True), Campo("data_apresentacao", False, "data"),
         Campo("situacao_texto"), Campo("tema"), Campo("url_integra"),
         Campo("fonte_url", True)],
        ("ibge_municipio", "identificador"), _up_proposicao,
        "select ente_codigo||'|'||id_externo from proposicao where id_externo is not null"),
}


# ----------------------------------------------------------------- execucao

def _chave_natural(entidade: str, spec: Spec, linha: dict) -> str:
    """Mesma forma do indice unico no banco, para o diff bater com a realidade."""
    if entidade == "competencia":
        return "|".join([(linha.get("tema") or "").strip().lower(),
                         (linha.get("esfera") or "").strip().upper(),
                         (linha.get("cargo_responsavel") or "").strip()])
    return "|".join((linha.get(k) or "").strip() for k in spec.chave)


@dataclass
class Relatorio:
    entidade: str
    arquivo: str
    total: int = 0
    novos: int = 0
    alterados: int = 0
    erros: list[str] = field(default_factory=list)
    lote_id: str | None = None
    aplicado: bool = False

    def resumo(self) -> dict:
        return {"entidade": self.entidade, "arquivo": self.arquivo, "linhas": self.total,
                "novos": self.novos, "ja_existentes": self.alterados,
                "erros": len(self.erros), "primeiros_erros": self.erros[:8],
                "lote_id": self.lote_id, "aplicado": self.aplicado}


def processa(entidade: str, caminho: str, ator: str, *, confirmar: bool = False) -> Relatorio:
    spec = ESPECS.get(entidade)
    if spec is None:
        raise ValueError(f"entidade '{entidade}' desconhecida. "
                         f"Disponíveis: {', '.join(sorted(ESPECS))}")

    with open(caminho, encoding="utf-8-sig") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    rel = Relatorio(entidade, caminho, total=len(linhas))

    faltando = set(c.nome for c in spec.campos if c.obrigatorio) - set(linhas[0] if linhas else [])
    if faltando:
        rel.erros.append(f"colunas obrigatórias ausentes no arquivo: {sorted(faltando)}")
        return rel

    with psycopg.connect(DATABASE_URL) as con, con.cursor() as cur:
        cur.execute("select codigo_ibge from ente")
        entes = {r[0] for r in cur.fetchall()}

        existentes: set[str] = set()
        if spec.sql_existente:
            cur.execute(spec.sql_existente)
            existentes = {r[0] for r in cur.fetchall()}

        for i, linha in enumerate(linhas, start=2):   # 1 e o cabecalho
            rel.erros.extend(_valida_linha(spec, linha, i, entes))
            if spec.sql_existente:
                chave = _chave_natural(entidade, spec, linha)
                if chave in existentes:
                    rel.alterados += 1
                else:
                    rel.novos += 1
            else:
                rel.novos += 1

        if rel.erros:
            return rel

        if not confirmar:
            # Simulacao de verdade: executa os upserts e desfaz. Conferir so o
            # formato das colunas nao prova nada - o erro caro e referencial
            # ("esse nome nao e vereador nessa cidade"), e ele so aparece
            # quando o insert roda. Antes disso a simulacao dizia "3 novos" e
            # a gravacao estourava na terceira linha.
            cur.execute("""insert into fonte_registro (fonte, tipo, url_origem,
                             inserido_por, observacao)
                           values (%s,'manual',%s,%s,'simulação') returning id""",
                        (f"import_{entidade}",
                         (linhas[0].get("fonte_url") if linhas else None), ator))
            ensaio = cur.fetchone()[0]
            for i, linha in enumerate(linhas, start=2):
                try:
                    cur.execute("savepoint ensaio")
                    spec.upsert(cur, linha, ensaio)
                    cur.execute("release savepoint ensaio")
                except Exception as e:
                    cur.execute("rollback to savepoint ensaio")
                    rel.erros.append(f"linha {i}: {e}")
            con.rollback()
            return rel

        lote = str(uuid.uuid4())
        rel.lote_id = lote
        cur.execute("""insert into importacao_lote (id, arquivo, entidade, inserido_por)
                       values (%s,%s,%s,%s)""", (lote, caminho, entidade, ator))
        cur.execute("""insert into fonte_registro
                         (fonte, tipo, url_origem, lote_id, inserido_por, observacao)
                       values (%s,'manual',%s,%s,%s,%s) returning id""",
                    (f"import_{entidade}",
                     (linhas[0].get("fonte_url") if linhas else None),
                     lote, ator, f"importação de {caminho}"))
        fonte_id = cur.fetchone()[0]

        for linha in linhas:
            spec.upsert(cur, linha, fonte_id)
        cur.execute("update importacao_lote set linhas_ok=%s where id=%s",
                    (len(linhas), lote))
        cur.execute("""insert into auditoria (ator, acao, entidade, entidade_id, valor_depois)
                       values (%s,'importar',%s,%s,%s)""",
                    (ator, entidade, lote, psycopg.types.json.Json(rel.resumo())))
        con.commit()
        rel.aplicado = True
    return rel


EXEMPLOS = {
    "gabinete": ["", "JOAO DA SILVA", "VEREADOR", "2910800", "Maria Souza",
                 "Assessor Parlamentar I", "comissionado", "3500,00",
                 "2026-09-01", "https://camara.exemplo.gov.br/folha/2026-09.pdf"],
    "despesa": ["", "JOAO DA SILVA", "VEREADOR", "2910800", "NF-2026-0042",
                "2026-09-15", "Combustivel", "Abastecimento do veiculo oficial",
                "Posto Central Ltda", "12345678000199", "412,90",
                "https://camara.exemplo.gov.br/notas/42.pdf",
                "https://camara.exemplo.gov.br/transparencia"],
    "proposicao": ["2910800", "PL-2026-17", "PL", "17", "2026",
                   "Institui o programa municipal de hortas comunitarias.",
                   "2026-03-12", "Aprovado em primeira discussao", "meio ambiente",
                   "https://camara.exemplo.gov.br/pl/17-2026.pdf",
                   "https://camara.exemplo.gov.br/proposicoes"],
}


def gera_templates(destino: str = "templates") -> list[str]:
    """Escreve um CSV de exemplo por entidade, a partir das proprias Specs.

    Template escrito a mao desencontra do codigo na primeira mudanca de campo,
    e quem descobre e a pessoa que passou a tarde preenchendo a planilha.
    """
    import csv as _csv
    from pathlib import Path as _Path

    pasta = _Path(destino)
    pasta.mkdir(parents=True, exist_ok=True)
    escritos = []
    for nome, spec in ESPECS.items():
        alvo = pasta / f"{nome}.csv"
        with alvo.open("w", newline="", encoding="utf-8") as f:
            w = _csv.writer(f, delimiter=";")
            w.writerow(spec.nomes)
            if exemplo := EXEMPLOS.get(nome):
                w.writerow(exemplo)
        escritos.append(str(alvo))
    return escritos


def reverte(lote_id: str, ator: str) -> dict:
    """Desfaz um lote inteiro. E por isso que cada linha carrega o lote."""
    with psycopg.connect(DATABASE_URL) as con, con.cursor() as cur:
        cur.execute("select entidade, revertido_em from importacao_lote where id=%s", (lote_id,))
        r = cur.fetchone()
        if r is None:
            return {"erro": "lote inexistente"}
        entidade, revertido = r
        if revertido:
            return {"erro": "lote já revertido"}
        tabela = ESPECS[entidade].tabela
        cur.execute(f"""delete from {tabela} where fonte_registro_id in
                        (select id from fonte_registro where lote_id = %s)""", (lote_id,))
        apagadas = cur.rowcount
        cur.execute("update importacao_lote set revertido_em = now() where id=%s", (lote_id,))
        cur.execute("""insert into auditoria (ator, acao, entidade, entidade_id)
                       values (%s,'reverter_importacao',%s,%s)""", (ator, entidade, lote_id))
        con.commit()
    return {"lote": lote_id, "entidade": entidade, "linhas_removidas": apagadas}
