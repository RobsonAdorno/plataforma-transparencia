#!/usr/bin/env python3
"""Gera os caminhos SVG dos municipios, um arquivo por estado.

A malha do IBGE em qualidade intermediaria da 1,8 MB so para Minas Gerais -
inviavel para o navegador. Este script reduz isso em uma ordem de grandeza com
tres passos, na ordem:

  1. projeta para um viewBox proprio daquele estado, para o estado preencher a
     tela toda em vez de ficar do tamanho que tem no mapa do Brasil;
  2. simplifica com Douglas-Peucker numa tolerancia calculada em unidades do
     viewBox, nao em graus - tolerancia em grau distorce com a latitude;
  3. arredonda as coordenadas para inteiro. Num viewBox de 1000 unidades o
     inteiro ja e mais fino que um pixel na tela, entao a casa decimal era
     puro peso.

Uma armadilha que custou tempo na primeira versao do mapa do Brasil: anel
fechado tem o primeiro ponto igual ao ultimo, e o Douglas-Peucker sobre um
segmento de comprimento zero descarta o anel inteiro e devolve poligono vazio.
A correcao e partir o anel no ponto mais distante do inicio e simplificar as
duas metades.

  python scripts/gera_malhas.py              # os 27
  python scripts/gera_malhas.py --uf SE,MG   # so alguns
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "web" / "app" / "malhas"
IBGE = ("https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf}"
        "?formato=application/vnd.geo+json&intrarregiao=municipio"
        "&qualidade=intermediaria")

UFS = ("AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
       "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
       "SE", "SP", "TO")

LADO = 1000          # o viewBox e quadrado de 1000 unidades
MARGEM = 8
TOLERANCIA = 0.55    # em unidades do viewBox: abaixo de 1 nao se ve a diferenca


def baixa(uf: str) -> dict:
    """O IBGE responde gzip mesmo sem Accept-Encoding, e urllib nao descomprime."""
    req = urllib.request.Request(IBGE.format(uf=uf),
                                 headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        bruto = r.read()
    if bruto[:2] == b"\x1f\x8b":
        import gzip
        bruto = gzip.decompress(bruto)
    return json.loads(bruto)


# ------------------------------------------------------------------ projecao

def _limites(features: list[dict]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []

    def anda(c):
        if isinstance(c[0], (int, float)):
            xs.append(c[0])
            ys.append(c[1])
        else:
            for x in c:
                anda(x)

    for f in features:
        anda(f["geometry"]["coordinates"])
    return min(xs), min(ys), max(xs), max(ys)


def _projetor(features: list[dict]):
    """Equirretangular com correcao de latitude, suficiente na escala de um estado.

    Sem o cos(lat) o estado aparece esticado na horizontal - visivel a olho nu
    no Amazonas e no Rio Grande do Sul, que estao longe do equador.
    """
    x0, y0, x1, y1 = _limites(features)
    k = math.cos(math.radians((y0 + y1) / 2)) or 1.0
    larg = (x1 - x0) * k
    alt = (y1 - y0)
    escala = (LADO - 2 * MARGEM) / max(larg, alt)
    dx = (LADO - larg * escala) / 2
    dy = (LADO - alt * escala) / 2

    def proj(lon: float, lat: float) -> tuple[float, float]:
        return (dx + (lon - x0) * k * escala,
                dy + (y1 - lat) * escala)       # y cresce para baixo no SVG

    return proj


# --------------------------------------------------------- Douglas-Peucker

def _dist(p, a, b) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _rdp(pontos: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    if len(pontos) < 3:
        return pontos
    a, b = pontos[0], pontos[-1]
    pior, idx = 0.0, 0
    for i in range(1, len(pontos) - 1):
        d = _dist(pontos[i], a, b)
        if d > pior:
            pior, idx = d, i
    if pior <= tol:
        return [a, b]
    return _rdp(pontos[:idx + 1], tol)[:-1] + _rdp(pontos[idx:], tol)


def simplifica_anel(anel: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    """Simplifica um anel fechado sem colapsa-lo.

    Aplicar Douglas-Peucker direto num anel e um bug silencioso: como o
    primeiro ponto e igual ao ultimo, a reta de referencia tem comprimento
    zero, todo ponto fica a distancia zero dela e o anel vira duas copias do
    mesmo ponto. Partir no ponto mais distante do inicio resolve.
    """
    if len(anel) < 4:
        return anel
    fechado = anel[0] == anel[-1]
    pts = anel[:-1] if fechado else anel[:]
    if len(pts) < 4:
        return anel

    o = pts[0]
    corte = max(range(1, len(pts)), key=lambda i: math.hypot(pts[i][0] - o[0],
                                                             pts[i][1] - o[1]))
    metade1 = _rdp(pts[:corte + 1], tol)
    metade2 = _rdp(pts[corte:] + [o], tol)
    saida = metade1[:-1] + metade2
    if len(saida) < 4:                      # degenerou: devolve o original
        return anel
    return saida


# ------------------------------------------------------------------- saida

def _para_d(aneis: list[list[tuple[float, float]]]) -> str:
    partes = []
    for anel in aneis:
        if len(anel) < 3:
            continue
        pontos = [(round(x), round(y)) for x, y in anel]
        # tira pontos repetidos que o arredondamento criou
        limpo = [pontos[0]]
        for p in pontos[1:]:
            if p != limpo[-1]:
                limpo.append(p)
        if len(limpo) < 3:
            continue
        partes.append("M" + "L".join(f"{x} {y}" for x, y in limpo) + "Z")
    return "".join(partes)


def _aneis_de(geom: dict) -> list[list[tuple[float, float]]]:
    t = geom["type"]
    coords = geom["coordinates"]
    if t == "Polygon":
        return [[(p[0], p[1]) for p in anel] for anel in coords]
    if t == "MultiPolygon":
        return [[(p[0], p[1]) for p in anel] for poly in coords for anel in poly]
    return []


def monta(uf: str, geo: dict, nomes: dict[str, str]) -> dict:
    features = geo["features"]
    proj = _projetor(features)
    municipios = []
    for f in features:
        codigo = str((f.get("properties") or {}).get("codarea") or "").strip()
        aneis = []
        for anel in _aneis_de(f["geometry"]):
            projetado = [proj(lon, lat) for lon, lat in anel]
            aneis.append(simplifica_anel(projetado, TOLERANCIA))
        d = _para_d(aneis)
        if not d:
            continue
        # centroide do maior anel, para ancorar o rotulo
        maior = max(aneis, key=len)
        cx = sum(p[0] for p in maior) / len(maior)
        cy = sum(p[1] for p in maior) / len(maior)
        municipios.append({"c": codigo, "n": nomes.get(codigo, ""),
                           "d": d, "x": round(cx), "y": round(cy)})
    municipios.sort(key=lambda m: m["n"])
    return {"uf": uf, "w": LADO, "h": LADO, "municipios": municipios}


def nomes_do_banco() -> dict[str, str]:
    """Os nomes vem do banco, nao do IBGE: a malha so traz o codigo da area."""
    sys.path.insert(0, str(RAIZ / "src"))
    try:
        from plataforma.load import conecta
        with conecta() as con, con.cursor() as cur:
            cur.execute("select codigo_ibge, nome from ente where nivel='municipio'")
            return {r[0]: r[1] for r in cur.fetchall()}
    except Exception as e:
        print(f"  aviso: sem nomes do banco ({e}); os rotulos ficam vazios")
        return {}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--uf", help="lista separada por virgula; vazio = todos")
    a = p.parse_args()
    ufs = [u.strip().upper() for u in a.uf.split(",")] if a.uf else list(UFS)

    DESTINO.mkdir(parents=True, exist_ok=True)
    nomes = nomes_do_banco()
    total_bytes = total_mun = 0

    for uf in ufs:
        geo = baixa(uf)
        dados = monta(uf, geo, nomes)
        alvo = DESTINO / f"{uf}.json"
        alvo.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")))
        n = alvo.stat().st_size
        total_bytes += n
        total_mun += len(dados["municipios"])
        cru = len(json.dumps(geo))
        print(f"  {uf}  {len(dados['municipios']):>4} municipios  "
              f"{cru/1e6:>5.2f} MB cru -> {n/1024:>6.1f} KB  "
              f"({n/max(cru,1):.1%})")

    print(f"\n{len(ufs)} estados, {total_mun} municipios, "
          f"{total_bytes/1024/1024:.2f} MB no total "
          f"(media {total_bytes/len(ufs)/1024:.0f} KB por estado)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
