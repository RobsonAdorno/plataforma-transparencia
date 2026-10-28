"""Paginas renderizadas no servidor.

Renderizar no servidor nao e preferencia: o trafego desse tipo de site vem de
alguem buscando o nome de um politico no Google. Pagina que so monta no
navegador nao e achada. Por isso HTML pronto, URL estavel e dados estruturados.
"""
from __future__ import annotations

from html import escape

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from .api import cursor

router = APIRouter()


def brl(v) -> str:
    return f"R$ {v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _slug(s: str) -> str:
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


PAGINA = """<!doctype html>
<html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titulo}</title>
<meta name="description" content="{descricao}">
<link rel="canonical" href="{canonical}">
<script type="application/ld+json">{jsonld}</script>
<style>
 :root{{--bg:#f6f8f7;--fg:#15201d;--muted:#5b6b66;--line:#dce3e0;--accent:#0d6356;--card:#fff}}
 @media(prefers-color-scheme:dark){{:root{{--bg:#0d1413;--fg:#e7eeeb;--muted:#93a49f;--line:#27322f;--accent:#49c9ae;--card:#141e1b}}}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}}
 .wrap{{max-width:860px;margin:0 auto;padding:28px 16px 56px}}
 header{{display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin-bottom:8px}}
 img.foto{{width:84px;height:112px;object-fit:cover;border-radius:5px;border:1px solid var(--line)}}
 h1{{font-size:30px;margin:0 0 4px;letter-spacing:-.02em}}
 .meta{{color:var(--muted);font-size:14px;margin:0}}
 .selo{{display:inline-block;font-size:11px;letter-spacing:.06em;text-transform:uppercase;
        border:1px solid var(--accent);color:var(--accent);border-radius:3px;padding:2px 7px;margin-left:6px}}
 h2{{font-size:17px;margin:34px 0 10px;letter-spacing:-.01em}}
 table{{border-collapse:collapse;width:100%;font-size:14px;background:var(--card);
        border:1px solid var(--line);border-radius:5px;overflow:hidden}}
 th{{text-align:left;font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);
     padding:9px 11px;border-bottom:1px solid var(--line)}}
 td{{padding:9px 11px;border-bottom:1px solid var(--line);vertical-align:top}}
 tr:last-child td{{border-bottom:0}}
 td.n{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
 a{{color:var(--accent)}}
 .fonte{{margin-top:34px;padding-top:14px;border-top:1px solid var(--line);font-size:12.5px;color:var(--muted)}}
 .vazio{{color:var(--muted);font-size:14px;font-style:italic}}
</style></head><body><div class="wrap">{corpo}</div></body></html>"""


@router.get("/deputado/{pessoa_id}", response_class=HTMLResponse)
@router.get("/deputado/{pessoa_id}/{slug}", response_class=HTMLResponse)
def pagina_deputado(pessoa_id: int, slug: str | None = None):
    from .api import deputado as dados_deputado
    try:
        d = dados_deputado(pessoa_id)
    except HTTPException:
        raise

    nome = d["nome_urna"] or d["nome_completo"]
    uf, partido = d["uf"], d["partido"]
    total = sum(float(g["total"]) for g in d["gastos_por_categoria"])
    canonical = f"/deputado/{pessoa_id}/{_slug(nome)}"

    cab = [
        '<header>',
        f'<img class="foto" src="{escape(d["foto_url"] or "")}" alt="{escape(nome)}" loading="lazy">'
        if d["foto_url"] else "",
        "<div>",
        f'<h1>{escape(nome)}</h1>',
        f'<p class="meta">{escape(d["nome_completo"])}</p>',
        f'<p class="meta">Deputado federal · {escape(partido or "sem partido")} · '
        f'{escape(d["estado"])}<span class="selo">{escape(d["situacao"].replace("_"," "))}</span></p>',
        "</div></header>",
    ]

    cat = "".join(
        f'<tr><td>{escape(g["categoria"] or "—")}</td><td class="n">{g["notas"]}</td>'
        f'<td class="n">{brl(float(g["total"]))}</td></tr>'
        for g in d["gastos_por_categoria"])
    gastos = (f'<h2>Cota parlamentar · {brl(total)} no período</h2>'
              f'<table><tr><th>Categoria</th><th>Notas</th><th>Total</th></tr>{cat}</table>'
              if cat else '<h2>Cota parlamentar</h2><p class="vazio">Sem despesas no período coletado.</p>')

    notas = "".join(
        f'<tr><td>{(x["data"].strftime("%d/%m/%Y") if x["data"] else "—")}</td>'
        f'<td>{escape((x["fornecedor"] or "")[:46])}</td>'
        f'<td class="n">{brl(float(x["valor"]))}</td>'
        f'<td>{f"<a href=\'{escape(x["documento_url"])}\' rel=\'nofollow\'>nota</a>" if x["documento_url"] else "—"}</td></tr>'
        for x in d["despesas_recentes"])
    recentes = (f'<h2>Notas mais recentes</h2><table>'
                f'<tr><th>Data</th><th>Fornecedor</th><th>Valor</th><th>Documento</th></tr>{notas}</table>')

    if d["votos_recentes"]:
        vl = "".join(
            f'<tr><td>{v["data_hora"].strftime("%d/%m/%Y") if v["data_hora"] else "—"}</td>'
            f'<td>{escape(v["orgao"] or "")}</td>'
            f'<td>{escape((v["prop_tipo"] or "") + " " + str(v["prop_numero"] or "") + "/" + str(v["prop_ano"] or "")) if v["prop_tipo"] else escape((v["descricao"] or "")[:60])}</td>'
            f'<td><strong>{escape(v["tipo_voto"])}</strong></td></tr>'
            for v in d["votos_recentes"])
        votos = (f'<h2>Votos nominais recentes</h2><table>'
                 f'<tr><th>Data</th><th>Órgão</th><th>Matéria</th><th>Voto</th></tr>{vl}</table>'
                 '<p class="meta" style="margin-top:8px">A maior parte das votações é simbólica '
                 'e não registra voto individual. Só o que foi nominal aparece aqui.</p>')
    else:
        votos = ('<h2>Votos nominais</h2><p class="vazio">Nenhum voto nominal registrado no '
                 'período coletado. A maior parte das votações é simbólica e não identifica '
                 'quem votou o quê.</p>')

    ids = " · ".join(f'{i["fonte"]}: {i["id_na_fonte"]} ({i["metodo"]})' for i in d["identidades"])
    fonte = (f'<div class="fonte">Dados da API da Câmara dos Deputados e da base de candidatos '
             f'do TSE. Identificação cruzada — {escape(ids)}. '
             f'Cada nota fiscal aponta para o documento original no portal da Câmara.</div>')

    jsonld = ('{"@context":"https://schema.org","@type":"Person","name":"%s",'
              '"jobTitle":"Deputado Federal","affiliation":"%s","address":'
              '{"@type":"PostalAddress","addressRegion":"%s","addressCountry":"BR"}}'
              % (escape(d["nome_completo"]), escape(partido or ""), escape(uf)))

    return HTMLResponse(PAGINA.format(
        titulo=f"{nome} ({partido}-{uf}) — gastos e votos",
        descricao=f"Quanto gasta e como vota {nome}, deputado federal por {d['estado']}. "
                  f"Dados oficiais da Câmara e do TSE.",
        canonical=canonical, jsonld=jsonld,
        corpo="".join(cab) + gastos + recentes + votos + fonte))
