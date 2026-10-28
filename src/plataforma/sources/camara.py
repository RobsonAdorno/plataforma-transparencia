"""Conector da Camara dos Deputados.

Duas fontes com naturezas diferentes:
  - API v2, boa e paginada, para deputados / proposicoes / votacoes / eventos;
  - CSV anual da cota parlamentar (CEAP), porque o endpoint /despesas da API
    responde vazio. O CSV ainda traz o link do PDF de cada nota.
"""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import date, timedelta
from typing import Iterator

import requests

from .. import bronze

API = "https://dadosabertos.camara.leg.br/api/v2"
CEAP_URL = "https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip"
HEADERS = {"accept": "application/json"}
FONTE_API = "camara_api"
FONTE_CEAP = "camara_ceap"


def _get(caminho: str, **params) -> dict:
    r = requests.get(f"{API}/{caminho}", params=params, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


def _paginado(caminho: str, **params) -> Iterator[dict]:
    """Segue o link 'next' em vez de chutar numero de paginas."""
    url = f"{API}/{caminho}"
    primeiro = True
    while url:
        r = requests.get(url, params=params if primeiro else None, headers=HEADERS, timeout=60)
        r.raise_for_status()
        corpo = r.json()
        yield from corpo.get("dados", [])
        url = next((l["href"] for l in corpo.get("links", []) if l.get("rel") == "next"), None)
        primeiro = False


def deputados_em_exercicio() -> list[dict]:
    """Os 513 da legislatura corrente."""
    return list(_paginado("deputados", itens=100, ordem="ASC", ordenarPor="nome"))


def mesa_diretora() -> list[dict]:
    return _get("orgaos/4/membros")["dados"]


def _janelas(inicio: str, fim: str, dias: int = 85) -> Iterator[tuple[str, str]]:
    """Fatia o periodo. O endpoint de votacoes recusa intervalo maior que 3 meses
    com HTTP 400, entao o conector fatia em vez de deixar o chamador se virar."""
    a = date.fromisoformat(inicio)
    b = date.fromisoformat(fim)
    while a <= b:
        c = min(a + timedelta(days=dias), b)
        yield a.isoformat(), c.isoformat()
        a = c + timedelta(days=1)


def votacoes(data_inicio: str, data_fim: str) -> list[dict]:
    saida: list[dict] = []
    for ini, fim in _janelas(data_inicio, data_fim):
        saida.extend(_paginado("votacoes", dataInicio=ini, dataFim=fim,
                               ordem="DESC", ordenarPor="dataHoraRegistro", itens=100))
    return saida


def votos(id_votacao: str) -> list[dict]:
    """Lista vazia significa votacao simbolica, nao erro."""
    return _get(f"votacoes/{id_votacao}/votos")["dados"]


def eventos(data_inicio: str, data_fim: str) -> list[dict]:
    saida: list[dict] = []
    for ini, fim in _janelas(data_inicio, data_fim):
        saida.extend(_paginado("eventos", dataInicio=ini, dataFim=fim, itens=100))
    return saida


def baixa_ceap(ano: int) -> bronze.Manifest:
    url = CEAP_URL.format(ano=ano)
    return bronze.baixa(FONTE_CEAP, f"Ano-{ano}.csv.zip", url)


def le_ceap(man: bronze.Manifest) -> Iterator[dict]:
    """Le o CSV de dentro do zip. utf-8-sig porque o arquivo vem com BOM."""
    with zipfile.ZipFile(man.path) as z:
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(nome) as f:
            yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"), delimiter=";")


def ponte_cpf(man: bronze.Manifest) -> dict[str, dict]:
    """O achado que liga TSE e Camara.

    O CSV da cota e o unico arquivo oficial onde o CPF do parlamentar e o
    ideCadastro (o id da API) aparecem na mesma linha.
    """
    ponte: dict[str, dict] = {}
    for linha in le_ceap(man):
        cpf = (linha.get("cpf") or "").strip()
        ide = (linha.get("ideCadastro") or "").strip()
        if not cpf or not ide:
            continue  # liderancas e bancadas gastam pela cota sem ter CPF
        ponte.setdefault(cpf, {
            "ide_cadastro": ide,
            "nome": (linha.get("txNomeParlamentar") or "").strip(),
            "uf": (linha.get("sgUF") or "").strip(),
            "partido": (linha.get("sgPartido") or "").strip(),
        })
    return ponte


def votos_em_lote(ids: list[str], trabalhadores: int = 6,
                  progresso=None) -> dict[str, list[dict]]:
    """Busca os votos de muitas votacoes em paralelo.

    Lista vazia significa votacao simbolica, nao erro - e a maioria das
    votacoes e simbolica. O paralelismo fica baixo de proposito: a API e
    publica e gratuita, nao ha motivo para martelar.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    saida: dict[str, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=trabalhadores) as pool:
        futuros = {pool.submit(votos, i): i for i in ids}
        for n, fut in enumerate(as_completed(futuros), 1):
            vid = futuros[fut]
            try:
                saida[vid] = fut.result()
            except Exception:
                saida[vid] = []          # falha pontual nao derruba o lote
            if progresso and n % 500 == 0:
                progresso(n, len(ids))
    return saida


def proposicoes_por_id(ids: list[str], trabalhadores: int = 6) -> dict[str, dict]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def uma(pid: str):
        return pid, _get(f"proposicoes/{pid}")["dados"]

    saida: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=trabalhadores) as pool:
        for fut in as_completed([pool.submit(uma, i) for i in ids]):
            try:
                pid, dados = fut.result()
                saida[pid] = dados
            except Exception:
                continue
    return saida


def pauta(id_evento: str) -> list[dict]:
    """Materias marcadas para o evento. Vazio e comum: muito evento nao delibera."""
    return _get(f"eventos/{id_evento}/pauta")["dados"]


def presentes(id_evento: str) -> list[dict]:
    return _get(f"eventos/{id_evento}/deputados")["dados"]


def pautas_em_lote(ids: list[str], trabalhadores: int = 6) -> dict[str, list[dict]]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    saida: dict[str, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=trabalhadores) as pool:
        fut = {pool.submit(pauta, i): i for i in ids}
        for f in as_completed(fut):
            try:
                saida[fut[f]] = f.result()
            except Exception:
                saida[fut[f]] = []
    return saida
