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
            try:
                float(v.replace(",", "."))
            except ValueError:
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

        if rel.erros or not confirmar:
            return rel        # simulacao: nada e gravado

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
