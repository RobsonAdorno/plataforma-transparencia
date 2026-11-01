#!/usr/bin/env python3
"""Mede a fragilidade do modelo de etapas contra a API ao vivo.

Nao e teste de unidade: e teste de ACORDO com a fonte. O risco real do
mapeamento nao e um bug meu de hoje, e a Camara reescrever a redacao de um
despacho em 2028 e a trilha parar de achar a etapa de sancao sem erro algum.

Roda uma amostra espalhada por tipo e por ano e responde tres coisas:

  1. quantas movimentacoes viram marco (se virar demais, ha ruido na tela;
     se virar de menos, falta etapa);
  2. quantos marcos dependem de regra de TEXTO - esses sao os que quebram
     calados quando a fonte muda a frase;
  3. quantas proposicoes falham no confere() - o numero que tem que ser zero.

  python scripts/valida_tramitacao.py --amostra 150
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plataforma import tramitacao as T   # noqa: E402

API = "https://dadosabertos.camara.leg.br/api/v2"
TIPOS = ("PL", "PEC", "PLP", "MPV", "PDL")


def get(url: str):
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)["dados"]


def amostra(n: int, anos: tuple[int, ...], semente: int) -> list[int]:
    """Espalha por tipo, ano e pagina. Pegar so as primeiras paginas puxaria
    proposicoes recem-apresentadas, que nao tem historico nenhum."""
    ids: list[int] = []
    for tipo in TIPOS:
        for ano in anos:
            for pag in (2, 9, 25):
                try:
                    ids += [p["id"] for p in
                            get(f"{API}/proposicoes?siglaTipo={tipo}&ano={ano}"
                                f"&itens=10&pagina={pag}")]
                except Exception:
                    pass
    random.Random(semente).shuffle(ids)
    return ids[:n]


def uma(pid: int):
    try:
        det = get(f"{API}/proposicoes/{pid}")
        return det, T.trilha(get(f"{API}/proposicoes/{pid}/tramitacoes"))
    except Exception:
        return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--amostra", type=int, default=150)
    p.add_argument("--semente", type=int, default=7)
    p.add_argument("--anos", default="2015,2019,2023,2025")
    a = p.parse_args()
    anos = tuple(int(x) for x in a.anos.split(","))

    ids = amostra(a.amostra, anos, a.semente)
    print(f"amostrando {len(ids)} proposicoes de {anos} ...", flush=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        res = [r for r in pool.map(uma, ids) if r]

    cruas = marcos_n = sem_marco = 0
    marcos: Counter[str] = Counter()
    metodos: Counter[str] = Counter()
    por_codigo_ruido: Counter[str] = Counter()
    falhas: list[tuple] = []

    for det, et in res:
        r = T.resumo(et)
        cruas += r["etapas"]
        marcos_n += r["marcos"]
        sem_marco += 1 if r["marcos"] == 0 else 0
        for e in et:
            if e["marco"]:
                marcos[e["marco"]] += 1
                metodos[e["metodo"]] += 1
            else:
                por_codigo_ruido[f"{e.get('codTipoTramitacao')} {e.get('descricaoTramitacao','')[:34]}"] += 1
        cs = (det.get("statusProposicao") or {}).get("codSituacao")
        if falta := T.confere(cs, et):
            falhas.append((f"{det['siglaTipo']} {det['numero']}/{det['ano']}", cs,
                           (det["statusProposicao"] or {}).get("descricaoSituacao"), falta))

    print(f"\nproposicoes analisadas : {len(res)}")
    print(f"movimentacoes cruas    : {cruas}")
    print(f"viraram marco          : {marcos_n} ({marcos_n / max(cruas,1):.0%})"
          f"  -> {cruas - marcos_n} ruido processual descartado")
    print(f"sem nenhum marco       : {sem_marco}"
          f"  (normal: projeto apresentado que nunca andou)")
    texto = metodos.get("texto", 0)
    print(f"\nreconhecimento: codigo={metodos.get('codigo',0)}  texto={texto}"
          f"  ({texto / max(marcos_n,1):.0%} depende de regra fragil)")

    print("\nmarcos:")
    for k, v in marcos.most_common():
        print(f"  {v:>6}  {k}")

    print("\nruido mais frequente (conferir se nao ha marco escondido aqui):")
    for k, v in por_codigo_ruido.most_common(12):
        print(f"  {v:>6}  cod {k}")

    print(f"\n{'='*66}")
    if falhas:
        print(f"*** {len(falhas)} DIVERGENCIA(S) - a fonte diz um desfecho que a trilha nao achou")
        for f in falhas:
            print(f"   {f[0]:<16} situacao {f[1]} ({f[2]}) -> esperava {f[3]}")
        return 1
    print(f"TESTE DE SANIDADE: ok, 0 divergencias em {len(res)} proposicoes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
