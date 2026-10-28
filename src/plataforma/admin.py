"""Painel de administracao: rotas protegidas e a mesa de alertas.

Tres superficies, nao uma. O importador cobre dado em massa e vive na CLI e
numa rota de upload. As duas telas aqui existem porque sao decisao rapida e
repetitiva, coisa que planilha nao resolve:

  mesa de alertas  - as votacoes do dia com um botao de notificar
  fila de identidade - comparacao lado a lado, aprovar ou rejeitar
"""
from __future__ import annotations

import json

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from . import alertas as mod_alertas
from .api import cursor
from .auth import Ator, exige_escrita
from .config import DATABASE_URL

router = APIRouter(prefix="/admin")


def _audita(cur, ator: str, acao: str, entidade: str, eid: str, depois=None):
    cur.execute("""insert into auditoria (ator, acao, entidade, entidade_id, valor_depois)
                   values (%s,%s,%s,%s,%s)""",
                (ator, acao, entidade, eid,
                 psycopg.types.json.Json(depois) if depois else None))


@router.get("/alertas")
def fila_alertas(estado: str = "rascunho", limite: int = 50,
                 ator: Ator = Depends(exige_escrita)):
    with cursor() as cur:
        cur.execute("""
            select a.id, a.prioridade, a.tipo, a.titulo, a.corpo, a.topicos, a.estado,
                   a.criado_em, pr.tipo as materia_tipo, pr.numero, pr.ano,
                   e.inicio as evento_inicio
              from alerta a
              left join proposicao pr on pr.id = a.proposicao_id
              left join evento e      on e.id = a.evento_id
             where a.estado = %s
             order by a.prioridade desc, a.criado_em desc limit %s""", (estado, limite))
        itens = cur.fetchall()
        cur.execute("select estado, count(*) from alerta group by estado")
        return {"resumo": {r["estado"]: r["count"] for r in cur.fetchall()}, "itens": itens}


@router.post("/alertas/{alerta_id}/{decisao}")
def decide_alerta(alerta_id: int, decisao: str, ator: Ator = Depends(exige_escrita)):
    if decisao not in ("aprovar", "descartar", "enviar"):
        raise HTTPException(400, "decisão deve ser aprovar, descartar ou enviar")
    if decisao == "enviar":
        r = mod_alertas.enviar(alerta_id, ator.email)
        if "erro" in r:
            raise HTTPException(409, r["erro"])
        return r
    novo = {"aprovar": "aprovado", "descartar": "descartado"}[decisao]
    with psycopg.connect(DATABASE_URL) as con, con.cursor() as cur:
        cur.execute("""update alerta set estado=%s, decidido_em=now(), decidido_por=%s
                        where id=%s and estado in ('rascunho','aprovado')
                        returning titulo""", (novo, ator.email, alerta_id))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(409, "alerta já decidido ou inexistente")
        _audita(cur, ator.email, f"alerta_{decisao}", "alerta", str(alerta_id),
                {"estado": novo})
        con.commit()
    return {"id": alerta_id, "estado": novo, "titulo": row[0]}


@router.get("/identidades")
def fila_identidades(limite: int = 50, ator: Ator = Depends(exige_escrita)):
    """Vazia significa que a ponte do CPF resolveu tudo - nao que esteja quebrada."""
    with cursor() as cur:
        cur.execute("""
            select id, fonte, id_na_fonte, candidatos, score, motivo, criado_em
              from identidade_pendente
             where resolvido_em is null
             order by score desc nulls last limit %s""", (limite,))
        return {"itens": cur.fetchall()}


@router.post("/identidades/{pendente_id}/{decisao}")
def decide_identidade(pendente_id: int, decisao: str, pessoa_id: int | None = None,
                      ator: Ator = Depends(exige_escrita)):
    if decisao not in ("aprovado", "rejeitado", "novo_registro"):
        raise HTTPException(400, "decisão inválida")
    with psycopg.connect(DATABASE_URL) as con, con.cursor() as cur:
        cur.execute("""select fonte, id_na_fonte from identidade_pendente
                        where id=%s and resolvido_em is null""", (pendente_id,))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(409, "pendência já resolvida ou inexistente")
        fonte, id_fonte = row
        if decisao == "aprovado":
            if pessoa_id is None:
                raise HTTPException(400, "aprovar exige pessoa_id")
            cur.execute("""insert into identidade_externa
                             (fonte, id_na_fonte, pessoa_id, metodo, confianca)
                           values (%s,%s,%s,'manual',1.0)
                           on conflict (fonte, id_na_fonte) do update set
                             pessoa_id = excluded.pessoa_id""",
                        (fonte, id_fonte, pessoa_id))
        cur.execute("""update identidade_pendente
                          set resolvido_em=now(), resolvido_por=%s, decisao=%s,
                              pessoa_id=coalesce(%s, pessoa_id)
                        where id=%s""", (ator.email, decisao, pessoa_id, pendente_id))
        _audita(cur, ator.email, "decidir_identidade", "identidade_pendente",
                str(pendente_id), {"decisao": decisao, "pessoa_id": pessoa_id})
        con.commit()
    return {"id": pendente_id, "decisao": decisao}


PAGINA = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Mesa de alertas</title>
<style>
 :root{--bg:#f6f8f7;--fg:#15201d;--muted:#5b6b66;--line:#dce3e0;--accent:#0d6356;--card:#fff;--risk:#a8394a}
 @media(prefers-color-scheme:dark){:root{--bg:#0d1413;--fg:#e7eeeb;--muted:#93a49f;--line:#27322f;--accent:#49c9ae;--card:#141e1b;--risk:#e2788a}}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,sans-serif}
 .wrap{max-width:880px;margin:0 auto;padding:24px 16px 60px}
 h1{font-size:22px;margin:0 0 4px}
 .sub{color:var(--muted);font-size:13.5px;margin:0 0 20px}
 .barra{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:18px}
 input,select,button{font:inherit;padding:7px 10px;border:1px solid var(--line);
   border-radius:5px;background:var(--card);color:var(--fg)}
 input{flex:1;min-width:220px}
 button{cursor:pointer}
 button.p{background:var(--accent);color:#fff;border-color:var(--accent)}
 button.d{color:var(--risk);border-color:var(--risk)}
 .item{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);
   border-radius:0 6px 6px 0;padding:13px 15px;margin-bottom:10px}
 .item h3{font-size:15.5px;margin:0 0 5px}
 .item p{margin:0 0 9px;font-size:13.5px;color:var(--muted)}
 .tags{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
 .tag{font-size:11px;font-family:ui-monospace,Menlo,monospace;background:var(--bg);
   border:1px solid var(--line);border-radius:3px;padding:2px 6px;color:var(--muted)}
 .pri{float:right;font-family:ui-monospace,monospace;font-size:12px;color:var(--accent)}
 .acoes{display:flex;gap:7px}
 .vazio{color:var(--muted);font-style:italic;padding:22px 0}
 #msg{font-size:13px;color:var(--muted);margin-left:auto}
</style></head><body><div class="wrap">
<h1>Mesa de alertas</h1>
<p class="sub">Nada sai sozinho. Todo alerta espera uma decisão sua, e ela fica registrada.</p>
<div class="barra">
  <input id="tok" type="password" placeholder="token de administrador" autocomplete="off">
  <select id="est">
    <option value="rascunho">rascunhos</option>
    <option value="aprovado">aprovados</option>
    <option value="enviado">enviados</option>
    <option value="descartado">descartados</option>
  </select>
  <button class="p" id="carregar">Carregar</button><span id="msg"></span>
</div>
<div id="lista"></div>
</div>
<script>
const $=s=>document.querySelector(s);
const tok=()=>{try{return sessionStorage.getItem('tok')||''}catch(e){return ''}};
try{ $('#tok').value=tok() }catch(e){}
$('#tok').addEventListener('change',e=>{try{sessionStorage.setItem('tok',e.target.value)}catch(_){}});

async function api(url,metodo='GET'){
  const r=await fetch(url,{method:metodo,headers:{'Authorization':'Bearer '+$('#tok').value}});
  if(!r.ok) throw new Error((await r.json().catch(()=>({detail:r.status}))).detail);
  return r.json();
}
async function carregar(){
  $('#msg').textContent='carregando...';
  try{
    const d=await api('/admin/alertas?estado='+$('#est').value);
    $('#msg').textContent=Object.entries(d.resumo).map(([k,v])=>k+': '+v).join(' · ');
    $('#lista').innerHTML = d.itens.length ? d.itens.map(render).join('')
      : '<p class="vazio">Nada nesta fila.</p>';
    document.querySelectorAll('[data-acao]').forEach(b=>b.onclick=()=>decidir(b));
  }catch(e){ $('#msg').textContent='erro: '+e.message; }
}
function render(a){
  const quando = a.evento_inicio ? new Date(a.evento_inicio).toLocaleString('pt-BR') : '';
  return `<div class="item" id="a${a.id}">
    <span class="pri">prio ${a.prioridade}</span>
    <h3>${esc(a.titulo)}</h3>
    <p>${esc(a.corpo||'')}${quando?' · '+quando:''}</p>
    <div class="tags">${(a.topicos||[]).map(t=>'<span class="tag">'+esc(t)+'</span>').join('')}</div>
    <div class="acoes">
      <button class="p" data-acao="enviar" data-id="${a.id}">Notificar</button>
      <button data-acao="aprovar" data-id="${a.id}">Aprovar</button>
      <button class="d" data-acao="descartar" data-id="${a.id}">Descartar</button>
    </div></div>`;
}
function esc(s){const d=document.createElement('div');d.textContent=s==null?'':s;return d.innerHTML}
async function decidir(b){
  b.disabled=true;
  try{
    await api(`/admin/alertas/${b.dataset.id}/${b.dataset.acao}`,'POST');
    const el=document.getElementById('a'+b.dataset.id); if(el) el.remove();
  }catch(e){ $('#msg').textContent='erro: '+e.message; b.disabled=false; }
}
$('#carregar').onclick=carregar;
if(tok()) carregar();
</script></body></html>"""


@router.get("", response_class=HTMLResponse)
def pagina():
    """A pagina em si e publica; os dados atras dela nao. Toda chamada
    carrega o token e e verificada no servidor."""
    return HTMLResponse(PAGINA)
