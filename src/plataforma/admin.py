"""Painel de administracao: rotas protegidas e a mesa de alertas.

Tres superficies, nao uma. O importador cobre dado em massa e vive na CLI e
numa rota de upload. As duas telas aqui existem porque sao decisao rapida e
repetitiva, coisa que planilha nao resolve:

  mesa de alertas    - as votacoes do dia com um botao de notificar
  fila de identidade - comparacao lado a lado, aprovar ou rejeitar
  divergencias       - proposicoes cuja situacao declarada pela fonte nao
                       aparece na trilha: o alarme de que o mapeamento de
                       etapas regrediu em silencio
  atribuicoes        - o texto sobre o limite de cada cargo, que e a unica
                       coisa aqui escrita por gente e por isso a unica que
                       precisa de aprovacao antes de contar como conferida
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


# ------------------------------------------------- divergencias de tramitacao

@router.get("/divergencias")
def fila_divergencias(limite: int = 50, ator: Ator = Depends(exige_escrita)):
    """A fila que denuncia regressao do modelo de etapas.

    Cada linha aqui e uma proposicao cuja situacao declarada pela fonte nao
    aparece na trilha que o mapeamento montou. Fila vazia e o estado normal;
    fila crescendo de repente significa que a Camara mudou a redacao de algum
    despacho e as regras de texto pararam de reconhecer a etapa.
    """
    with cursor() as cur:
        cur.execute("""
            select d.id, d.tipo, d.esperado, d.encontrado, d.detectado_em,
                   p.id as proposicao_id, p.tipo as sigla, p.numero, p.ano,
                   p.situacao, p.cod_situacao, p.ementa
              from divergencia_tramitacao d
              join proposicao p on p.id = d.proposicao_id
             where d.resolvido_em is null
             order by d.detectado_em desc limit %s""", (limite,))
        itens = cur.fetchall()
        # O total por 'esperado' diz se e caso isolado ou regra quebrada.
        cur.execute("""select esperado, count(*) as total
                         from divergencia_tramitacao where resolvido_em is null
                        group by 1 order by 2 desc""")
        return {"itens": itens, "por_marco": cur.fetchall()}


@router.post("/divergencias/{divergencia_id}/dispensar")
def dispensa_divergencia(divergencia_id: int, motivo: str = "",
                         ator: Ator = Depends(exige_escrita)):
    """Marca como analisada. Nao conserta o mapeamento - so para de cobrar."""
    with psycopg.connect(DATABASE_URL) as con, con.cursor() as cur:
        cur.execute("""update divergencia_tramitacao set resolvido_em=now()
                        where id=%s and resolvido_em is null returning proposicao_id""",
                    (divergencia_id,))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(409, "divergência já resolvida ou inexistente")
        _audita(cur, ator.email, "dispensar_divergencia", "divergencia_tramitacao",
                str(divergencia_id), {"motivo": motivo})
        con.commit()
    return {"id": divergencia_id, "dispensada": True}


# ------------------------------------------- revisao do conteudo editorial

@router.get("/atribuicoes")
def fila_atribuicoes(cargo: str | None = None, pendentes: bool = True,
                     ator: Ator = Depends(exige_escrita)):
    """O conteudo sobre o limite de cada cargo, para conferencia.

    Este e o unico conteudo da plataforma que nao vem de API: foi redigido a
    partir dos artigos citados. Ate alguem aprovar, a pagina publica mostra o
    aviso de 'em revisao' - o que e mais honesto do que esperar a revisao para
    publicar, e mais honesto do que publicar sem avisar.
    """
    with cursor() as cur:
        cur.execute(f"""
            select a.id, a.cargo, c.nome as cargo_nome, a.natureza, a.ordem,
                   a.texto, a.base_legal, a.abrangencia, a.revisado,
                   a.revisado_por, a.revisado_em
              from atribuicao_cargo a
              join cargo c on c.codigo = a.cargo
             where (%s::text is null or a.cargo = upper(%s))
               {"and a.revisado = false" if pendentes else ""}
             order by c.ordem, a.natureza, a.ordem""", (cargo, cargo))
        itens = cur.fetchall()
        cur.execute("""select cargo, count(*) filter (where revisado) as revisados,
                              count(*) as total
                         from atribuicao_cargo group by 1""")
        return {"itens": itens, "progresso": cur.fetchall()}


@router.post("/atribuicoes/{atribuicao_id}/{decisao}")
def decide_atribuicao(atribuicao_id: int, decisao: str, texto: str | None = None,
                      base_legal: str | None = None,
                      ator: Ator = Depends(exige_escrita)):
    """Aprovar, corrigir o texto, ou remover a linha."""
    if decisao not in ("aprovar", "corrigir", "remover"):
        raise HTTPException(400, "decisão inválida")
    with psycopg.connect(DATABASE_URL) as con, con.cursor() as cur:
        if decisao == "remover":
            cur.execute("delete from atribuicao_cargo where id=%s returning cargo",
                        (atribuicao_id,))
            if cur.fetchone() is None:
                raise HTTPException(404, "atribuição inexistente")
        else:
            cur.execute("""update atribuicao_cargo
                              set texto = coalesce(%s, texto),
                                  base_legal = coalesce(%s, base_legal),
                                  revisado = true, revisado_por = %s, revisado_em = now()
                            where id=%s returning cargo""",
                        (texto, base_legal, ator.email, atribuicao_id))
            if cur.fetchone() is None:
                raise HTTPException(404, "atribuição inexistente")
        _audita(cur, ator.email, f"{decisao}_atribuicao", "atribuicao_cargo",
                str(atribuicao_id), {"texto": texto, "base_legal": base_legal})
        con.commit()
    return {"id": atribuicao_id, "decisao": decisao}


@router.get("/pendencias")
def pendencias(ator: Ator = Depends(exige_escrita)):
    """Uma chamada que responde 'o que precisa de mim agora'.

    Existe porque o painel tem quatro filas e ninguem abre quatro telas para
    descobrir que tres estao vazias.
    """
    with cursor() as cur:
        cur.execute("""
            select
              (select count(*) from alerta where estado='rascunho')                  as alertas,
              (select count(*) from identidade_pendente where resolvido_em is null)  as identidades,
              (select count(*) from divergencia_tramitacao where resolvido_em is null) as divergencias,
              (select count(*) from atribuicao_cargo where revisado = false)         as atribuicoes,
              (select count(*) from ente where nivel='municipio'
                 and not exists (select 1 from mandato m
                                  where m.ente_codigo = ente.codigo_ibge
                                    and m.cargo='VEREADOR'))                         as camaras_sem_vereador
            """)
        return cur.fetchone()


PAGINA = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Painel</title>
<style>
 :root{--bg:#f6f8f7;--fg:#15201d;--muted:#5b6b66;--line:#dce3e0;--accent:#0d6356;--card:#fff;--risk:#a8394a}
 @media(prefers-color-scheme:dark){:root{--bg:#0d1413;--fg:#e7eeeb;--muted:#93a49f;--line:#27322f;--accent:#49c9ae;--card:#141e1b;--risk:#e2788a}}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,sans-serif}
 .wrap{max-width:920px;margin:0 auto;padding:24px 16px 60px}
 h1{font-size:22px;margin:0 0 4px}
 .sub{color:var(--muted);font-size:13.5px;margin:0 0 18px}
 .barra{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
 input,select,button,textarea{font:inherit;padding:7px 10px;border:1px solid var(--line);
   border-radius:5px;background:var(--card);color:var(--fg)}
 input{flex:1;min-width:200px}
 button{cursor:pointer}
 button.p{background:var(--accent);color:#fff;border-color:var(--accent)}
 button.d{color:var(--risk);border-color:var(--risk)}
 nav{display:flex;gap:4px;flex-wrap:wrap;border-bottom:1px solid var(--line);margin-bottom:16px}
 nav button{border:0;border-bottom:2px solid transparent;border-radius:0;background:0;
   color:var(--muted);padding:9px 12px;font-size:13px}
 nav button[aria-current]{color:var(--fg);border-bottom-color:var(--accent)}
 nav .n{display:inline-block;min-width:17px;margin-left:5px;padding:0 4px;border-radius:9px;
   background:var(--accent);color:#fff;font-size:11px;font-family:ui-monospace,monospace}
 nav .n[data-zero]{background:var(--line);color:var(--muted)}
 .item{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);
   border-radius:0 6px 6px 0;padding:13px 15px;margin-bottom:10px}
 .item[data-alerta]{border-left-color:var(--risk)}
 .item h3{font-size:15px;margin:0 0 5px}
 .item p{margin:0 0 9px;font-size:13.5px;color:var(--muted)}
 .tags{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
 .tag{font-size:11px;font-family:ui-monospace,Menlo,monospace;background:var(--bg);
   border:1px solid var(--line);border-radius:3px;padding:2px 6px;color:var(--muted)}
 .pri{float:right;font-family:ui-monospace,monospace;font-size:12px;color:var(--accent)}
 .acoes{display:flex;gap:7px;flex-wrap:wrap}
 .vazio{color:var(--muted);font-style:italic;padding:22px 0}
 .nota{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--risk);
   border-radius:0 5px 5px 0;padding:11px 14px;font-size:13px;color:var(--muted);margin-bottom:14px}
 textarea{width:100%;min-height:62px;margin-bottom:7px}
 #msg{font-size:13px;color:var(--muted);margin-left:auto}
</style></head><body><div class="wrap">
<h1>Painel</h1>
<p class="sub">Nada sai sozinho. Toda decisão fica registrada em auditoria, com quem decidiu e quando.</p>
<div class="barra">
  <input id="tok" type="password" placeholder="token de administrador" autocomplete="off">
  <button class="p" id="carregar">Entrar</button><span id="msg"></span>
</div>
<nav id="abas"></nav>
<div id="corpo"></div>
</div>
<script>
const $=s=>document.querySelector(s);
const tok=()=>{try{return sessionStorage.getItem('tok')||''}catch(e){return ''}};
try{ $('#tok').value=tok() }catch(e){}
$('#tok').addEventListener('change',e=>{try{sessionStorage.setItem('tok',e.target.value)}catch(_){}});

const FILAS=[
 ['alertas','Alertas'],['divergencias','Divergências'],
 ['atribuicoes','Textos em revisão'],['identidades','Identidades']];
let aba='alertas', contagem={};

async function api(url,metodo='GET'){
  const r=await fetch(url,{method:metodo,headers:{'Authorization':'Bearer '+$('#tok').value}});
  if(!r.ok) throw new Error((await r.json().catch(()=>({detail:r.status}))).detail);
  return r.json();
}
function esc(s){const d=document.createElement('div');d.textContent=s==null?'':s;return d.innerHTML}

function abas(){
  $('#abas').innerHTML=FILAS.map(([k,r])=>{
    const n=contagem[k]??0;
    return `<button data-aba="${k}" ${k===aba?'aria-current="page"':''}>${r}`+
           `<span class="n" ${n?'':'data-zero'}>${n}</span></button>`;
  }).join('');
  document.querySelectorAll('[data-aba]').forEach(b=>b.onclick=()=>{aba=b.dataset.aba;abas();desenha()});
}

async function carregar(){
  $('#msg').textContent='carregando...';
  try{
    const p=await api('/admin/pendencias');
    contagem=p; $('#msg').textContent=
      p.camaras_sem_vereador+' câmaras sem vereador publicado';
    abas(); await desenha();
  }catch(e){ $('#msg').textContent='erro: '+e.message; }
}

async function desenha(){
  $('#corpo').innerHTML='<p class="vazio">carregando...</p>';
  try{
    if(aba==='alertas')      return pinta(await api('/admin/alertas?estado=rascunho'),rAlerta);
    if(aba==='divergencias') return pinta(await api('/admin/divergencias'),rDiv,notaDiv);
    if(aba==='atribuicoes')  return pinta(await api('/admin/atribuicoes'),rAtrib,notaAtrib);
    if(aba==='identidades')  return pinta(await api('/admin/identidades'),rIdent);
  }catch(e){ $('#corpo').innerHTML='<p class="vazio">erro: '+esc(e.message)+'</p>'; }
}
function pinta(d,render,nota){
  const itens=d.itens||[];
  $('#corpo').innerHTML=(nota?nota(d):'')+(itens.length?itens.map(render).join('')
    :'<p class="vazio">Nada nesta fila — e isso é o estado normal.</p>');
  document.querySelectorAll('[data-url]').forEach(b=>b.onclick=()=>agir(b));
}
async function agir(b){
  b.disabled=true;
  try{ await api(b.dataset.url,'POST');
       const el=document.getElementById(b.dataset.alvo); if(el) el.remove();
       const p=await api('/admin/pendencias'); contagem=p; abas();
  }catch(e){ $('#msg').textContent='erro: '+e.message; b.disabled=false; }
}

function rAlerta(a){
  const q=a.evento_inicio?new Date(a.evento_inicio).toLocaleString('pt-BR'):'';
  return `<div class="item" id="al${a.id}"><span class="pri">prio ${a.prioridade}</span>
    <h3>${esc(a.titulo)}</h3><p>${esc(a.corpo||'')}${q?' · '+q:''}</p>
    <div class="tags">${(a.topicos||[]).map(t=>'<span class="tag">'+esc(t)+'</span>').join('')}</div>
    <div class="acoes">
      <button class="p" data-url="/admin/alertas/${a.id}/enviar" data-alvo="al${a.id}">Notificar</button>
      <button data-url="/admin/alertas/${a.id}/aprovar" data-alvo="al${a.id}">Aprovar</button>
      <button class="d" data-url="/admin/alertas/${a.id}/descartar" data-alvo="al${a.id}">Descartar</button>
    </div></div>`;
}
function notaDiv(d){
  return `<div class="nota"><strong>O que esta fila significa.</strong> Cada linha é uma
    proposição cuja situação declarada pela fonte não aparece na trilha que o modelo montou.
    Fila vazia é o normal. Fila crescendo de repente quer dizer que a Câmara mudou a redação
    de algum despacho e as regras de texto pararam de reconhecer a etapa — a plataforma
    passaria a mostrar “em tramitação” para lei que já está em vigor.
    ${(d.por_marco||[]).map(m=>'<span class="tag">'+esc(m.esperado)+': '+m.total+'</span>').join(' ')}</div>`;
}
function rDiv(x){
  return `<div class="item" data-alerta id="dv${x.id}">
    <h3>${esc(x.sigla)} ${x.numero}/${x.ano}</h3>
    <p>${esc((x.ementa||'').slice(0,180))}</p>
    <div class="tags">
      <span class="tag">fonte diz: ${esc(x.situacao)} (${x.cod_situacao})</span>
      <span class="tag">esperava a etapa: ${esc(x.esperado)}</span>
      <span class="tag">trilha terminou em: ${esc(x.encontrado||'nada')}</span></div>
    <div class="acoes">
      <a href="/leis/${x.proposicao_id}" target="_blank"><button>Ver na API</button></a>
      <button class="d" data-url="/admin/divergencias/${x.id}/dispensar" data-alvo="dv${x.id}">Dispensar</button>
    </div></div>`;
}
function notaAtrib(d){
  const feito=(d.progresso||[]).reduce((a,c)=>a+Number(c.revisados),0);
  const tot=(d.progresso||[]).reduce((a,c)=>a+Number(c.total),0);
  return `<div class="nota"><strong>Este é o único conteúdo escrito por gente.</strong>
    Todo o resto da plataforma vem de API. Estes textos foram redigidos a partir dos artigos
    citados e, até alguém aprovar, a página pública mostra o aviso de “em revisão”.
    Progresso: ${feito} de ${tot} conferidos.</div>`;
}
function rAtrib(a){
  const cor=a.natureza==='nao_pode'?'d':'';
  return `<div class="item" id="at${a.id}">
    <div class="tags"><span class="tag">${esc(a.cargo_nome)}</span>
      <span class="tag">${esc(a.natureza)}</span>
      <span class="tag">${esc(a.abrangencia)}</span></div>
    <textarea id="tx${a.id}">${esc(a.texto)}</textarea>
    <textarea id="bl${a.id}" style="min-height:34px">${esc(a.base_legal)}</textarea>
    <div class="acoes">
      <button class="p" onclick="aprovar(${a.id})">Aprovar como está</button>
      <button onclick="corrigir(${a.id})">Salvar correção e aprovar</button>
      <button class="${cor||'d'}" data-url="/admin/atribuicoes/${a.id}/remover" data-alvo="at${a.id}">Remover</button>
    </div></div>`;
}
async function aprovar(id){ await mandar(id,'aprovar',{}); }
async function corrigir(id){
  await mandar(id,'corrigir',{texto:$('#tx'+id).value, base_legal:$('#bl'+id).value});
}
async function mandar(id,decisao,corpo){
  const q=new URLSearchParams(corpo).toString();
  try{ await api(`/admin/atribuicoes/${id}/${decisao}`+(q?'?'+q:''),'POST');
       const el=document.getElementById('at'+id); if(el) el.remove();
       contagem=await api('/admin/pendencias'); abas();
  }catch(e){ $('#msg').textContent='erro: '+e.message; }
}
function rIdent(i){
  return `<div class="item" id="id${i.id}">
    <h3>${esc(i.fonte)} · ${esc(i.id_na_fonte)}</h3>
    <p>${esc(i.motivo||'')} · score ${i.score ?? '—'}</p>
    <div class="acoes">
      <button class="d" data-url="/admin/identidades/${i.id}/rejeitado" data-alvo="id${i.id}">Rejeitar</button>
    </div></div>`;
}
$('#carregar').onclick=carregar;
if(tok()) carregar();
</script></body></html>"""


@router.get("", response_class=HTMLResponse)
def pagina():
    """A pagina em si e publica; os dados atras dela nao. Toda chamada
    carrega o token e e verificada no servidor."""
    return HTMLResponse(PAGINA)
