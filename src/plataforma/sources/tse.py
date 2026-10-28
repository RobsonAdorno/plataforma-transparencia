"""Conector do TSE: base de candidatos por ano de eleicao.

Dois cuidados que so aparecem rodando:
  - deduplicar por SQ_CANDIDATO, senao a contagem sai dobrada (SP aparece com
    140 deputados federais quando a bancada e 70);
  - validar contra os totais que a lei ja fixa, antes de confiar no numero.
"""
from __future__ import annotations

import csv
import io
import zipfile
from typing import Iterator

from .. import bronze

URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{ano}.zip"
FONTE = "tse_cand"

SITUACOES_ELEITO = {"ELEITO", "ELEITO POR QP", "ELEITO POR MÉDIA"}

CARGO_TSE = {
    "PRESIDENTE": "PRESIDENTE",
    "GOVERNADOR": "GOVERNADOR",
    "SENADOR": "SENADOR",
    "DEPUTADO FEDERAL": "DEPUTADO_FEDERAL",
    "DEPUTADO ESTADUAL": "DEPUTADO_ESTADUAL",
    "DEPUTADO DISTRITAL": "DEPUTADO_ESTADUAL",
    "PREFEITO": "PREFEITO",
    "VEREADOR": "VEREADOR",
}

# Totais fixados por lei ou pela estrutura da eleicao. Servem de teste de sanidade.
ESPERADO = {
    2022: {"DEPUTADO_FEDERAL": 513, "SENADOR": 27, "GOVERNADOR": 27},
    2026: {"DEPUTADO_FEDERAL": 513, "SENADOR": 54},
}


def baixa(ano: int) -> bronze.Manifest:
    return bronze.baixa(FONTE, f"consulta_cand_{ano}.zip", URL.format(ano=ano))


def _linhas(man: bronze.Manifest) -> Iterator[dict]:
    with zipfile.ZipFile(man.path) as z:
        for nome in sorted({n for n in z.namelist() if n.lower().endswith(".csv")}):
            with z.open(nome) as f:
                yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";")


def _unicos(man: bronze.Manifest) -> Iterator[dict]:
    """Uma linha por candidato, ficando com o turno mais alto.

    Em eleicao com segundo turno o mesmo SQ_CANDIDATO aparece duas vezes: a
    linha do 1o turno diz "2o TURNO" e so a do 2o turno diz "ELEITO". Guardar a
    primeira que aparece perde justamente quem venceu - em 2022 isso derrubava
    a contagem de governadores de 27 para 21.
    """
    melhor: dict[str, dict] = {}
    for d in _linhas(man):
        sq = d.get("SQ_CANDIDATO")
        if not sq:
            continue
        try:
            turno = int(d.get("NR_TURNO") or 1)
        except ValueError:
            turno = 1
        atual = melhor.get(sq)
        if atual is None or turno > atual["_turno"]:
            d["_turno"] = turno
            melhor[sq] = d
    return iter(melhor.values())


def eleitos(man: bronze.Manifest, cargos: set[str] | None = None) -> list[dict]:
    """So quem foi eleito, uma linha por pessoa."""
    saida: list[dict] = []
    for d in _unicos(man):
        sq = d["SQ_CANDIDATO"]
        if (d.get("DS_SIT_TOT_TURNO") or "").strip() not in SITUACOES_ELEITO:
            continue
        cargo = CARGO_TSE.get((d.get("DS_CARGO") or "").strip())
        if cargo is None or (cargos and cargo not in cargos):
            continue
        saida.append({
            "sq_candidato": sq,
            "cpf": (d.get("NR_CPF_CANDIDATO") or "").strip(),
            "nome_completo": (d.get("NM_CANDIDATO") or "").strip(),
            "nome_urna": (d.get("NM_URNA_CANDIDATO") or "").strip(),
            "cargo": cargo,
            "uf": (d.get("SG_UF") or "").strip(),
            "municipio": (d.get("NM_UE") or "").strip(),
            "sq_ue": (d.get("SG_UE") or "").strip(),
            "partido": (d.get("SG_PARTIDO") or "").strip(),
            "nascimento": (d.get("DT_NASCIMENTO") or "").strip(),
            "sexo": (d.get("DS_GENERO") or "").strip(),
            "cor_raca": (d.get("DS_COR_RACA") or "").strip(),
            "ocupacao": (d.get("DS_OCUPACAO") or "").strip(),
            "situacao_turno": (d.get("DS_SIT_TOT_TURNO") or "").strip(),
        })
    return saida


def confere(ano: int, registros: list[dict]) -> list[str]:
    """Compara com os totais conhecidos. Devolve a lista de divergencias."""
    from collections import Counter
    c = Counter(r["cargo"] for r in registros)
    problemas = []
    for cargo, esperado in ESPERADO.get(ano, {}).items():
        obtido = c.get(cargo, 0)
        if obtido != esperado:
            problemas.append(f"{cargo}: {obtido} (esperado {esperado})")
    return problemas


def por_cpf(man: bronze.Manifest) -> dict[str, dict]:
    """Indexa TODOS os candidatos do ano por CPF, nao so os eleitos.

    Deputado que assumiu como suplente aparece no TSE como SUPLENTE. Filtrar por
    eleito aqui faria a ponte perder justamente esses.
    """
    idx: dict[str, dict] = {}
    for d in _unicos(man):
        sq = d["SQ_CANDIDATO"]
        cpf = (d.get("NR_CPF_CANDIDATO") or "").strip()
        if not cpf:
            continue
        idx.setdefault(cpf, {
            "sq_candidato": sq,
            "cpf": cpf,
            "nome_completo": (d.get("NM_CANDIDATO") or "").strip(),
            "nome_urna": (d.get("NM_URNA_CANDIDATO") or "").strip(),
            "cargo": CARGO_TSE.get((d.get("DS_CARGO") or "").strip(), ""),
            "uf": (d.get("SG_UF") or "").strip(),
            "partido": (d.get("SG_PARTIDO") or "").strip(),
            "nascimento": (d.get("DT_NASCIMENTO") or "").strip(),
            "sexo": (d.get("DS_GENERO") or "").strip(),
            "cor_raca": (d.get("DS_COR_RACA") or "").strip(),
            "situacao_turno": (d.get("DS_SIT_TOT_TURNO") or "").strip(),
        })
    return idx
