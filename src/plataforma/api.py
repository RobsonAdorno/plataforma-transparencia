"""API de leitura. Publica, sem autenticacao e cacheavel.

Nada aqui escreve. Escrita e coisa do importador e do painel de administracao,
que vivem em outro processo com outra credencial.
"""
from __future__ import annotations

from contextlib import contextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Query
from psycopg.rows import dict_row

from .config import DATABASE_URL

app = FastAPI(title="Plataforma de Transparência", version="0.1.0")

CACHE = "public, max-age=900, stale-while-revalidate=3600"


@contextmanager
def cursor():
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as con, con.cursor() as cur:
        yield cur


@app.middleware("http")
async def cacheavel(request, call_next):
    """Dado publico e 100% cacheavel. O CDN na frente faz o trabalho pesado."""
    resp = await call_next(request)
    if request.method == "GET" and resp.status_code == 200:
        resp.headers["Cache-Control"] = CACHE
    return resp


@app.get("/ufs")
def ufs():
    """Alimenta o mapa: uma leitura por clique no estado."""
    with cursor() as cur:
        cur.execute("""
            select e.uf, e.nome, e.codigo_ibge,
                   count(distinct m.id)                     as deputados,
                   coalesce(sum(d.valor), 0)::numeric(14,2) as gasto_cota
              from ente e
              left join mandato m on m.ente_codigo = e.codigo_ibge
                                 and m.cargo = 'DEPUTADO_FEDERAL'
                                 and m.situacao = 'em_exercicio'
              left join despesa d on d.mandato_id = m.id
             where e.nivel = 'estado'
             group by e.uf, e.nome, e.codigo_ibge
             order by e.uf""")
        return cur.fetchall()


@app.get("/deputados")
def deputados(uf: str | None = Query(None, min_length=2, max_length=2),
              partido: str | None = None):
    with cursor() as cur:
        cur.execute("""
            select p.id, p.nome_urna, p.nome_completo, p.foto_url,
                   m.partido, e.uf, m.id as mandato_id
              from pessoa p
              join mandato m on m.pessoa_id = p.id and m.cargo = 'DEPUTADO_FEDERAL'
              join ente e on e.codigo_ibge = m.ente_codigo
             where (%s::text is null or e.uf = upper(%s))
               and (%s::text is null or m.partido = upper(%s))
             order by p.nome_urna""", (uf, uf, partido, partido))
        return cur.fetchall()


@app.get("/deputados/{pessoa_id}")
def deputado(pessoa_id: int):
    """Tudo que a pagina de um deputado precisa, em uma chamada."""
    with cursor() as cur:
        cur.execute("""
            select p.id, p.nome_completo, p.nome_urna, p.foto_url, p.data_nascimento,
                   p.sexo, p.cor_raca, m.id as mandato_id, m.partido, m.situacao,
                   e.uf, e.nome as estado
              from pessoa p
              join mandato m on m.pessoa_id = p.id and m.cargo = 'DEPUTADO_FEDERAL'
              join ente e on e.codigo_ibge = m.ente_codigo
             where p.id = %s""", (pessoa_id,))
        base = cur.fetchone()
        if base is None:
            raise HTTPException(404, "deputado não encontrado")

        cur.execute("""select fonte, id_na_fonte, metodo, confianca
                         from identidade_externa where pessoa_id = %s""", (pessoa_id,))
        base["identidades"] = cur.fetchall()

        cur.execute("""
            select categoria, count(*) as notas, sum(valor)::numeric(14,2) as total
              from despesa where mandato_id = %s
             group by categoria order by sum(valor) desc""", (base["mandato_id"],))
        base["gastos_por_categoria"] = cur.fetchall()

        cur.execute("""
            select d.data, d.fornecedor, d.cnpj_cpf, d.valor, d.documento_url,
                   f.fonte, f.coletado_em
              from despesa d join fonte_registro f on f.id = d.fonte_registro_id
             where d.mandato_id = %s order by d.data desc nulls last limit 20""",
                    (base["mandato_id"],))
        base["despesas_recentes"] = cur.fetchall()

        # Só votação nominal tem voto individual. O resumo diz quantas ficaram
        # de fora para a tela não sugerir cobertura que não existe.
        cur.execute("""
            select v.tipo_voto, count(*) as total
              from voto v where v.mandato_id = %s group by v.tipo_voto""",
                    (base["mandato_id"],))
        base["votos_por_tipo"] = cur.fetchall()

        cur.execute("""
            select vo.data_hora, vo.orgao, vo.descricao, v.tipo_voto,
                   pr.tipo as prop_tipo, pr.numero as prop_numero, pr.ano as prop_ano
              from voto v
              join votacao vo on vo.id = v.votacao_id
              left join proposicao pr on pr.id = vo.proposicao_id
             where v.mandato_id = %s
             order by vo.data_hora desc limit 10""", (base["mandato_id"],))
        base["votos_recentes"] = cur.fetchall()
        return base


@app.get("/votacoes")
def votacoes(limite: int = Query(20, le=100), apenas_nominais: bool = False):
    with cursor() as cur:
        cur.execute("""
            select vo.id, vo.data_hora, vo.orgao, vo.descricao, vo.aprovada, vo.tipo,
                   pr.tipo as prop_tipo, pr.numero as prop_numero, pr.ano as prop_ano,
                   pr.ementa,
                   (select count(*) from voto v where v.votacao_id = vo.id) as votos
              from votacao vo
              left join proposicao pr on pr.id = vo.proposicao_id
             where (%s = false or vo.tipo = 'nominal')
             order by vo.data_hora desc limit %s""", (apenas_nominais, limite))
        return cur.fetchall()


@app.get("/saude")
def saude():
    """Status das fontes. Vira pagina publica de credibilidade."""
    with cursor() as cur:
        cur.execute("""
            select fonte, max(coletado_em) as ultima_coleta, count(*) as coletas
              from fonte_registro group by fonte order by fonte""")
        fontes = cur.fetchall()
        cur.execute("""select
            (select count(*) from pessoa)    as pessoas,
            (select count(*) from mandato)   as mandatos,
            (select count(*) from despesa)   as despesas,
            (select count(*) from votacao)   as votacoes,
            (select count(*) from voto)      as votos""")
        return {"fontes": fontes, "volumes": cur.fetchone()}


from .web import router as _web   # noqa: E402  (evita import circular)
app.include_router(_web)
