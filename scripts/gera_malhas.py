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
DESTINO = RAIZ / "web" / "public" / "malhas"
IBGE = ("https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf}"
        "?formato=application/vnd.geo+json&intrarregiao=municipio"
        "&qualidade=intermediaria")

UFS = ("AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
       "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
       "SE", "SP", "TO")

MAIOR_LADO = 1000    # a maior dimensao do estado; a outra sai proporcional
MARGEM = 8
TOLERANCIA = 0.55    # em unidades do viewBox: abaixo de 1 nao se ve a diferenca
IBGE_MUNICIPIOS = ("https://servicodados.ibge.gov.br/api/v1/localidades/"
                   "estados/{uf}/municipios")

# Quatro preenchimentos, aplicados por coloracao de grafo: regiao vizinha nunca
# recebe a mesma cor. Isso e coloracao cartografica, nao codificacao de dado -
# duas regioes distantes podem repetir a cor sem confundir ninguem, porque o
# nome esta escrito em cima e a identidade nunca depende so da cor.
#
# Sao tres matizes porque o validador da paleta so aprova tres em --pairs all,
# que e o criterio de mapa. Testei a quarta posicao com violeta, magenta e
# amarelo: todas reprovam no piso de visao normal, e esse piso e falha dura
# que codificacao secundaria nao desculpa. O quarto slot e neutro, usado so
# quando tres nao bastam.
#
# Os valores sao os tres slots validados compostos a 75% sobre a superficie -
# abaixo disso o par verde/azul cai para delta-E 14,1 e reprova. O apuramento
# esta no commit que introduziu este arquivo.
HUES = ("a", "b", "c")   # o CSS resolve cada letra nos dois temas
HACHURA = "h"            # mesma matiz 'a', com textura: canal extra, nao 4a cor


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

    O viewBox segue a proporcao real do estado, nao um quadrado fixo. Com o
    quadrado, estado alongado como o Amazonas ou o Rio Grande do Sul ficava
    pequeno no meio de duas faixas vazias, e o usuario reclamou disso olhando
    a Bahia: o mapa ocupava metade do espaco que tinha.
    """
    x0, y0, x1, y1 = _limites(features)
    k = math.cos(math.radians((y0 + y1) / 2)) or 1.0
    larg = (x1 - x0) * k
    alt = (y1 - y0)
    escala = (MAIOR_LADO - 2 * MARGEM) / max(larg, alt)
    w = larg * escala + 2 * MARGEM
    h = alt * escala + 2 * MARGEM

    def proj(lon: float, lat: float) -> tuple[float, float]:
        return (MARGEM + (lon - x0) * k * escala,
                MARGEM + (y1 - lat) * escala)   # y cresce para baixo no SVG

    return proj, round(w), round(h)


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


def regioes_do_estado(uf: str) -> dict[str, tuple[str, str]]:
    """Regiao intermediaria de cada municipio: (id, nome).

    E a divisao oficial vigente do IBGE, que substituiu a mesorregiao. Da de 5
    a 13 regioes por estado - granularidade certa para agrupar o mapa sem
    virar um borrao nem virar 400 pedacos.
    """
    import unicodedata
    req = urllib.request.Request(IBGE_MUNICIPIOS.format(uf=uf),
                                 headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        bruto = r.read()
    if bruto[:2] == b"\x1f\x8b":
        import gzip
        bruto = gzip.decompress(bruto)
    saida: dict[str, tuple[str, str]] = {}
    for m in json.loads(bruto):
        ri = (m.get("regiao-imediata") or {}).get("regiao-intermediaria") or {}
        nome = (ri.get("nome") or "").strip()
        # O servico devolve o travessao como caractere invalido em alguns nomes
        # ("Ilheus ? Itabuna"): e ruido de codificacao e sai feio na tela.
        for ruim in ("\ufffd", "\xbf", "\u00bf"):
            nome = nome.replace(ruim, "\u2013")
        saida[str(m["id"])] = (str(ri.get("id") or ""), unicodedata.normalize("NFC", nome))
    return saida


def adjacencia(geo: dict) -> dict[str, set[str]]:
    """Quais municipios se tocam, pelos vertices que compartilham.

    A malha do IBGE e topologica: 85% dos vertices pertencem a mais de um
    poligono. Calcular isso ANTES de simplificar e essencial - depois cada
    contorno e simplificado por conta propria e as fronteiras deixam de bater.
    """
    from collections import defaultdict

    dono: dict[tuple[float, float], set[str]] = defaultdict(set)

    def pontos(c):
        if isinstance(c[0], (int, float)):
            yield (round(c[0], 6), round(c[1], 6))
        else:
            for x in c:
                yield from pontos(x)

    for f in geo["features"]:
        cod = str((f.get("properties") or {}).get("codarea") or "")
        for p in pontos(f["geometry"]["coordinates"]):
            dono[p].add(cod)

    viz: dict[str, set[str]] = defaultdict(set)
    for ms in dono.values():
        if len(ms) > 1:
            for a in ms:
                viz[a] |= ms - {a}
    return viz


def colore_regioes(regioes: dict[str, tuple[str, str]],
                   viz: dict[str, set[str]]) -> dict[str, str]:
    """Coloracao de grafo: regiao vizinha nunca recebe a mesma cor.

    Busca exata com retrocesso, nao heuristica gulosa - e a diferenca entre
    precisar de tres cores ou de quatro, e quatro nao esta disponivel.
    O validador da paleta reprova qualquer quarta cor em --pairs all, que e o
    criterio de mapa: testei violeta, magenta, amarelo e seis cinzas, e todos
    caem abaixo do piso de visao normal, que e falha dura.

    Com no maximo treze regioes por estado o espaco de busca e pequeno e a
    resposta sai instantanea. Se ainda assim tres nao bastarem, o excedente
    recebe a primeira matiz com hachura - textura e outro canal de
    codificacao, nao uma quarta cor.
    """
    from collections import defaultdict

    entre: dict[str, set[str]] = defaultdict(set)
    for mun, vizinhos in viz.items():
        ra = regioes.get(mun, ("", ""))[0]
        if not ra:
            continue
        for v in vizinhos:
            rb = regioes.get(v, ("", ""))[0]
            if rb and rb != ra:
                entre[ra].add(rb)
                entre[rb].add(ra)

    # Grau decrescente: o no mais travado primeiro, que e o que poda mais cedo.
    ordem = sorted({r for r, _n in regioes.values() if r},
                   key=lambda r: (-len(entre.get(r, ())), r))
    cor: dict[str, str] = {}

    def tenta(i: int) -> bool:
        if i == len(ordem):
            return True
        r = ordem[i]
        usadas = {cor[v] for v in entre.get(r, ()) if v in cor}
        for c in HUES:
            if c in usadas:
                continue
            cor[r] = c
            if tenta(i + 1):
                return True
            del cor[r]
        return False

    if tenta(0):
        return cor

    # Nao deu com tres: guloso, e quem sobrar vai de hachura.
    cor.clear()
    for r in ordem:
        usadas = {cor[v] for v in entre.get(r, ()) if v in cor}
        cor[r] = next((c for c in HUES if c not in usadas), HACHURA)
    return cor


def monta(uf: str, geo: dict, dados: dict[str, tuple[str, int, int]]) -> dict:
    features = geo["features"]
    proj, w, h = _projetor(features)
    regioes = regioes_do_estado(uf)
    cor_regiao = colore_regioes(regioes, adjacencia(geo))

    municipios = []
    vistas: dict[str, dict] = {}
    for f in features:
        codigo = str((f.get("properties") or {}).get("codarea") or "").strip()
        aneis = []
        for anel in _aneis_de(f["geometry"]):
            projetado = [proj(lon, lat) for lon, lat in anel]
            aneis.append(simplifica_anel(projetado, TOLERANCIA))
        d = _para_d(aneis)
        if not d:
            continue
        maior = max(aneis, key=len)       # centroide do maior anel, para o rotulo
        cx = sum(p[0] for p in maior) / len(maior)
        cy = sum(p[1] for p in maior) / len(maior)
        nome, pop, ver = dados.get(codigo, ("", 0, 0))
        rid, rnome = regioes.get(codigo, ("", ""))
        municipios.append({"c": codigo, "n": nome, "d": d,
                           "x": round(cx), "y": round(cy), "p": pop, "v": ver,
                           "r": rid, "k": cor_regiao.get(rid, "n")})
        if rid:
            vistas.setdefault(rid, {"id": rid, "n": rnome,
                                    "k": cor_regiao.get(rid, "n"), "q": 0})
            vistas[rid]["q"] += 1

    municipios.sort(key=lambda m: m["n"])
    return {"uf": uf, "w": w, "h": h, "municipios": municipios,
            "regioes": sorted(vistas.values(), key=lambda r: -r["q"])}

def dados_do_banco() -> dict[str, tuple[str, int, int]]:
    """Nome, populacao e numero de vereadores. A malha do IBGE so traz o codigo.

    A populacao nao e enfeite: e ela que decide quais nomes aparecem no mapa.
    Sao 853 municipios em Minas e nenhuma tela comporta 853 rotulos, entao o
    algoritmo escreve os maiores primeiro e vai descendo ate nao caber mais.
    """
    sys.path.insert(0, str(RAIZ / "src"))
    try:
        from plataforma.load import conecta
        with conecta() as con, con.cursor() as cur:
            cur.execute("""select e.codigo_ibge, e.nome, coalesce(e.populacao,0),
                                  count(*) filter (where m.cargo='VEREADOR')
                             from ente e
                             left join mandato m on m.ente_codigo = e.codigo_ibge
                            where e.nivel='municipio' group by 1,2,3""")
            return {r[0]: (r[1], r[2], r[3]) for r in cur.fetchall()}
    except Exception as e:
        print(f"  aviso: sem dados do banco ({e}); os rotulos ficam vazios")
        return {}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--uf", help="lista separada por virgula; vazio = todos")
    a = p.parse_args()
    ufs = [u.strip().upper() for u in a.uf.split(",")] if a.uf else list(UFS)

    DESTINO.mkdir(parents=True, exist_ok=True)
    dados = dados_do_banco()
    total_bytes = total_mun = 0

    for uf in ufs:
        geo = baixa(uf)
        saida = monta(uf, geo, dados)
        alvo = DESTINO / f"{uf}.json"
        alvo.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")))
        n = alvo.stat().st_size
        total_bytes += n
        total_mun += len(saida["municipios"])
        cru = len(json.dumps(geo))
        cores = {m["k"] for m in saida["municipios"]}
        print(f"  {uf}  {len(saida['municipios']):>4} mun  "
              f"{len(saida['regioes']):>2} regioes  {len(cores)} cores  "
              f"{saida['w']}x{saida['h']}  "
              f"{cru/1e6:>5.2f} MB -> {n/1024:>6.1f} KB")

    print(f"\n{len(ufs)} estados, {total_mun} municipios, "
          f"{total_bytes/1024/1024:.2f} MB no total "
          f"(media {total_bytes/len(ufs)/1024:.0f} KB por estado)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
