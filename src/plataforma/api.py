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
            with federal as (
              select e.uf,
                     count(distinct m.id)                     as deputados,
                     coalesce(sum(d.valor), 0)::numeric(14,2) as gasto_cota
                from ente e
                left join mandato m on m.ente_codigo = e.codigo_ibge
                                   and m.cargo = 'DEPUTADO_FEDERAL'
                                   and m.situacao = 'em_exercicio'
                left join despesa d on d.mandato_id = m.id
               where e.nivel = 'estado'
               group by e.uf
            ), municipal as (
              select e.uf,
                     count(*) filter (where m.cargo = 'VEREADOR') as vereadores,
                     count(*) filter (where m.cargo = 'PREFEITO') as prefeitos,
                     count(distinct e.codigo_ibge)                as municipios
                from ente e
                left join mandato m on m.ente_codigo = e.codigo_ibge
               where e.nivel = 'municipio'
               group by e.uf
            )
            select e.uf, e.nome, e.codigo_ibge,
                   f.deputados, f.gasto_cota,
                   coalesce(mu.vereadores, 0) as vereadores,
                   coalesce(mu.prefeitos, 0)  as prefeitos,
                   coalesce(mu.municipios, 0) as municipios
              from ente e
              join federal f    on f.uf = e.uf
              left join municipal mu on mu.uf = e.uf
             where e.nivel = 'estado'
             order by e.uf""")
        return cur.fetchall()


@app.get("/municipios")
def municipios(uf: str = Query(..., min_length=2, max_length=2)):
    """Lista enxuta para navegar do estado ate a cidade."""
    with cursor() as cur:
        cur.execute("""
            select e.codigo_ibge, e.nome, e.populacao,
                   count(*) filter (where m.cargo='VEREADOR') as vereadores,
                   count(*) filter (where m.cargo='PREFEITO')  as prefeitos
              from ente e
              left join mandato m on m.ente_codigo = e.codigo_ibge
             where e.nivel='municipio' and e.uf = upper(%s)
             group by 1,2,3
             order by e.populacao desc nulls last, e.nome""", (uf,))
        return cur.fetchall()


@app.get("/municipio/{codigo_ibge}")
def municipio(codigo_ibge: str):
    """A cidade da pessoa: quem governa, quem legisla, e o que a fonte nao disse."""
    with cursor() as cur:
        cur.execute("""
            select e.codigo_ibge, e.nome, e.uf, e.populacao, e.populacao_ano,
                   e.populacao_referencia, e.populacao_referencia_ano,
                   eu.nome as estado
              from ente e
              left join ente eu on eu.nivel='estado' and eu.uf = e.uf
             where e.codigo_ibge = %s and e.nivel='municipio'""", (codigo_ibge,))
        base = cur.fetchone()
        if base is None:
            raise HTTPException(404, "município não encontrado")

        cur.execute("""
            select p.id, p.nome_urna, p.nome_completo, m.cargo, m.partido, m.situacao
              from mandato m join pessoa p on p.id = m.pessoa_id
             where m.ente_codigo = %s and m.cargo in ('PREFEITO','VEREADOR')
             order by m.cargo, p.nome_urna""", (codigo_ibge,))
        eleitos = cur.fetchall()
        base["prefeito"] = next((e for e in eleitos if e["cargo"] == "PREFEITO"), None)
        base["vereadores"] = [e for e in eleitos if e["cargo"] == "VEREADOR"]

        # A cobertura e o que impede a tela de afirmar "nenhum vereador" quando
        # o que houve foi a fonte nao publicar.
        cur.execute("""select cargo, situacao, eleitos, candidaturas, sem_resultado,
                              motivo, fonte, ano_eleicao
                         from cobertura where ente_codigo = %s
                        order by cargo""", (codigo_ibge,))
        base["cobertura"] = {c["cargo"]: c for c in cur.fetchall()}

        # Teto de cadeiras do art. 29, IV para esta cidade, pelas duas
        # referencias de populacao.
        cur.execute("""
            select f.letra, f.max_vereadores, f.pop_min, f.pop_max
              from faixa_vereador f
             where %s::bigint >= f.pop_min and (f.pop_max is null or %s::bigint <= f.pop_max)""",
                    (base["populacao"], base["populacao"]))
        base["faixa_censo"] = cur.fetchone()
        cur.execute("""
            select f.letra, f.max_vereadores
              from faixa_vereador f
             where %s::bigint >= f.pop_min and (f.pop_max is null or %s::bigint <= f.pop_max)""",
                    (base["populacao_referencia"], base["populacao_referencia"]))
        base["faixa_referencia"] = cur.fetchone()
        return base


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


@app.get("/congresso")
def congresso():
    """Composicao por partido, para o hemiciclo."""
    with cursor() as cur:
        cur.execute("""
            select m.partido, count(*) as cadeiras
              from mandato m
             where m.cargo = 'DEPUTADO_FEDERAL' and m.situacao = 'em_exercicio'
             group by m.partido order by count(*) desc, m.partido""")
        partidos = cur.fetchall()
    total = sum(p["cadeiras"] for p in partidos)
    return {"casa": "Câmara dos Deputados", "total": total, "partidos": partidos}


@app.get("/votacoes/{votacao_id}")
def votacao_detalhe(votacao_id: int):
    with cursor() as cur:
        cur.execute("""
            select vo.id, vo.data_hora, vo.orgao, vo.descricao, vo.aprovada, vo.tipo,
                   pr.tipo as prop_tipo, pr.numero as prop_numero,
                   pr.ano as prop_ano, pr.ementa
              from votacao vo left join proposicao pr on pr.id = vo.proposicao_id
             where vo.id = %s""", (votacao_id,))
        v = cur.fetchone()
        if v is None:
            raise HTTPException(404, "votação não encontrada")
        cur.execute("""
            select v.tipo_voto, p.nome_urna, m.partido, e.uf
              from voto v
              join mandato m on m.id = v.mandato_id
              join pessoa p  on p.id = m.pessoa_id
              join ente e    on e.codigo_ibge = m.ente_codigo
             where v.votacao_id = %s order by p.nome_urna""", (votacao_id,))
        v["votos"] = cur.fetchall()
        return v


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


# ------------------------------------------------------------------- leis
#
# Tres estados, tres consultas. A separacao vem do que o cidadao pergunta -
# "o que vao votar?", "o que estao votando agora?", "o que ja virou lei?" -
# e nao da estrutura das tabelas.

@app.get("/leis/agenda")
def leis_agenda(dias: int = Query(21, ge=1, le=90), limite: int = Query(40, le=120)):
    """Vai ser votada: materia marcada em evento que ainda nao comecou."""
    with cursor() as cur:
        cur.execute("""
            select p.id, p.tipo, p.numero, p.ano, p.ementa, p.marco_atual, p.fase_atual,
                   e.inicio, e.tipo as evento_tipo, e.descricao as evento,
                   pi.regime, pi.relator, pi.titulo,
                   (select count(*) from etapa et where et.proposicao_id = p.id) as etapas
              from pauta_item pi
              join evento e     on e.id = pi.evento_id
              join proposicao p on p.id = pi.proposicao_id
             where e.inicio between now() and now() + make_interval(days => %s)
               and coalesce(e.situacao,'') not in ('Cancelada','Encerrada')
             order by e.inicio, pi.ordem nulls last
             limit %s""", (dias, limite))
        return cur.fetchall()


@app.get("/leis/agora")
def leis_agora():
    """Esta sendo votada: sessao em andamento, com a pauta dela.

    Honestidade que a tela precisa repetir: so 2% das votacoes sao nominais.
    Estar em pauta numa sessao em andamento nao garante que havera voto
    individual registrado no fim.
    """
    with cursor() as cur:
        cur.execute("""
            select e.id as evento_id, e.descricao as evento, e.tipo as evento_tipo,
                   e.inicio, e.situacao,
                   p.id, p.tipo, p.numero, p.ano, p.ementa, p.marco_atual, p.fase_atual
              from evento e
              left join pauta_item pi on pi.evento_id = e.id
              left join proposicao p  on p.id = pi.proposicao_id
             where e.situacao = 'Em Andamento'
             order by e.inicio desc, pi.ordem nulls last""")
        return cur.fetchall()


@app.get("/leis/votadas")
def leis_votadas(limite: int = Query(40, le=120), virou_lei: bool = False):
    """Ja foi votada. Com virou_lei=true, so o que chegou ao Diario Oficial."""
    with cursor() as cur:
        cur.execute("""
            select p.id, p.tipo, p.numero, p.ano, p.ementa,
                   p.marco_atual, p.fase_atual, p.situacao,
                   p.norma_tipo, p.norma_numero, p.norma_ano, p.norma_data,
                   (select max(et.data_hora) from etapa et
                     where et.proposicao_id = p.id and et.marco is not null) as ultimo_passo
              from proposicao p
             where (%s = false or p.norma_numero is not null)
               and (%s = true  or p.fase_atual >= 3)
             order by coalesce(p.norma_data, p.atualizado_em) desc nulls last
             limit %s""", (virou_lei, virou_lei, limite))
        return cur.fetchall()


@app.get("/leis/{proposicao_id}")
def lei(proposicao_id: int):
    """Tudo de um projeto: trilha agrupada, autores, relator e desfecho."""
    from . import tramitacao as T

    with cursor() as cur:
        cur.execute("""
            select p.id, p.tipo, p.numero, p.ano, p.ementa, p.situacao, p.cod_situacao,
                   p.regime, p.apreciacao, p.casa_origem, p.url_integra, p.tramitando,
                   p.data_apresentacao, p.marco_atual, p.fase_atual,
                   p.norma_tipo, p.norma_numero, p.norma_ano, p.norma_data
              from proposicao p where p.id = %s""", (proposicao_id,))
        base = cur.fetchone()
        if base is None:
            raise HTTPException(404, "proposição não encontrada")

        cur.execute("""select nome, tipo, partido, uf, ordem, proponente, papel, pessoa_id
                         from autoria_proposicao where proposicao_id=%s
                        order by papel, ordem nulls last""", (proposicao_id,))
        pessoas = cur.fetchall()
        base["autores"] = [a for a in pessoas if a["papel"] == "autor"]
        base["relatores"] = [a for a in pessoas if a["papel"] == "relator"]

        cur.execute("""select fonte, sequencia, data_hora, orgao, cod_tipo, descricao,
                              despacho, url, marco, fase, metodo
                         from etapa where proposicao_id=%s
                        order by data_hora, sequencia nulls last""", (proposicao_id,))
        etapas = cur.fetchall()

    # Agrupar aqui, e nao no front: a regra de "o que e a mesma etapa" e
    # conhecimento do dominio e tem que valer igual na web e no app.
    blocos = T.agrupa([{**e, "dataHora": (e["data_hora"].isoformat()
                                          if e["data_hora"] else None)}
                       for e in etapas])
    base["trilha"] = [{k: v for k, v in b.items() if k != "itens"} | {
        "itens": [{"data_hora": i.get("dataHora"), "orgao": i.get("orgao"),
                   "descricao": i.get("descricao"), "despacho": i.get("despacho"),
                   "url": i.get("url"), "fonte": i.get("fonte"),
                   "metodo": i.get("metodo")} for i in b["itens"]]}
        for b in blocos]
    base["movimentacoes_totais"] = len(etapas)
    base["caminho"] = [{"marco": m, "fase": T.FASES[m], "rotulo": T.ROTULOS[m],
                        "explicacao": T.EXPLICACOES.get(m)}
                       for m in ("APRESENTACAO", "COMISSOES", "PLENARIO_ORIGEM",
                                 "CASA_REVISORA", "PLENARIO_REVISORA", "SANCAO", "LEI")]
    return base


# ------------------------------------------------------------------ cargos
#
# O objetivo central da plataforma: o limite de cada cargo publico.

@app.get("/cargos")
def cargos():
    with cursor() as cur:
        cur.execute("""select codigo, nome, plural, esfera, poder, mandato_anos, resumo
                         from cargo order by ordem""")
        return cur.fetchall()


@app.get("/cargos/{codigo}")
def cargo(codigo: str):
    with cursor() as cur:
        cur.execute("""select codigo, nome, plural, esfera, poder, mandato_anos, resumo
                         from cargo where codigo = upper(%s)""", (codigo,))
        base = cur.fetchone()
        if base is None:
            raise HTTPException(404, "cargo não encontrado")
        cur.execute("""select natureza, texto, base_legal, abrangencia, ordem, revisado
                         from atribuicao_cargo where cargo = upper(%s)
                        order by natureza, ordem""", (codigo,))
        itens = cur.fetchall()
        for n in ("pode", "nao_pode", "limite"):
            base[n] = [i for i in itens if i["natureza"] == n]
        # Quantos existem hoje no Brasil, do proprio banco. Numero concreto
        # ancora o texto: "57.000 vereadores" e mais util que "os vereadores".
        cur.execute("""select count(*) from mandato
                        where cargo = upper(%s) and situacao <> 'encerrado'""", (codigo,))
        base["em_exercicio"] = cur.fetchone()["count"]
        base["revisado"] = all(i["revisado"] for i in itens) if itens else False
        return base


@app.get("/cargos/vereador/camaras")
def camaras_art29(limite: int = Query(60, le=200)):
    """Conferencia das camaras contra o teto do art. 29, IV.

    Devolve a contagem por estado e so a lista do que nao fecha por nenhuma
    referencia de populacao. Nao e laudo de irregularidade: a divergencia pode
    estar na fonte, e a tela precisa dizer isso.
    """
    from .cargos import CONFERE_ART29

    with cursor() as cur:
        cur.execute(f"select estado, count(*) as total from ({CONFERE_ART29}) t"
                    " group by 1 order by 2 desc")
        estados = cur.fetchall()
        cur.execute(f"""select nome, uf, codigo_ibge, populacao, populacao_referencia,
                               cadeiras, teto_censo, teto_estimativa, teto_aplicavel
                          from ({CONFERE_ART29}) t where estado='a_conferir'
                         order by cadeiras - teto_aplicavel desc limit %s""", (limite,))
        return {"por_estado": estados, "a_conferir": cur.fetchall(),
                "base_legal": "CF/88, art. 29, IV (redação da EC 58/2009)"}


# A pagina do deputado agora e do Next.js, em web/. Aqui fica so a API e o
# painel: dois renderizadores do mesmo HTML divergem com o tempo.
from .admin import router as _admin  # noqa: E402  (evita import circular)
app.include_router(_admin)
