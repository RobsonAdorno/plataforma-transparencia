"""API publica, sem autenticacao e cacheavel.

Era so de leitura, e o comentario aqui dizia isso. Deixou de ser por um motivo
que nao tem contorno: reclamacao de cidadao e escrita publica por natureza. Ou
a pessoa escreve sem conta, ou o canal nao existe - e exigir cadastro para
reclamar do poste da rua seria filtrar justamente quem mais precisa do canal.

Entao ha exatamente UMA rota de escrita publica, POST /reclamacoes, e ela e
tratada como superficie hostil:

  - valida tamanho e formato antes de tocar o banco (modelo Pydantic);
  - nao aceita HTML, so texto;
  - grava sempre no mesmo estado inicial, sem deixar o cliente escolher
    estado, protocolo, prazo nem destino;
  - nao devolve nada que nao seja do proprio registro criado.

O que FALTA e precisa existir antes de abrir para a internet: limite de taxa
por origem e prova de humanidade. O contador em memoria aqui embaixo segura
abuso acidental e nada mais - com dois processos de uvicorn ele ja nao conta
certo. Isso e trabalho de CDN e de captcha, nao de codigo de aplicacao, e esta
anotado como pendencia no README.

Escrita administrativa continua fora daqui, no painel, com credencial propria.
"""
from __future__ import annotations

import re
import time
from collections import deque
from contextlib import contextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, field_validator

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


# ------------------------------------------------------------- reclamacoes

MAX_POR_HORA = 5
_recentes: dict[str, deque] = {}
_HTML = re.compile(r"<[^>]*>")


def _trava(request: Request) -> None:
    """Limite de taxa por origem, em memoria. Mitigacao, nao protecao.

    Existe para que um script distraido nao enche o banco. Nao substitui
    limite no CDN: reinicia com o processo e nao e compartilhado entre
    trabalhadores do uvicorn. Documentado como pendencia de proposito.
    """
    origem = (request.client.host if request.client else "?")
    agora = time.time()
    fila = _recentes.setdefault(origem, deque())
    while fila and agora - fila[0] > 3600:
        fila.popleft()
    if len(fila) >= MAX_POR_HORA:
        raise HTTPException(429, "muitas reclamações da mesma origem em uma hora")
    fila.append(agora)


class NovaReclamacao(BaseModel):
    ente_codigo: str = Field(min_length=1, max_length=7)
    tema: str = Field(min_length=3, max_length=120)
    titulo: str = Field(min_length=6, max_length=140)
    descricao: str = Field(min_length=20, max_length=4000)
    local_referencia: str | None = Field(default=None, max_length=200)
    autor_nome: str | None = Field(default=None, max_length=120)
    autor_email: str | None = Field(default=None, max_length=160)
    exibir_autor: bool = False

    @field_validator("titulo", "descricao", "local_referencia", "autor_nome")
    @classmethod
    def sem_marcacao(cls, v: str | None) -> str | None:
        """Texto e texto. A reclamacao vai para uma pagina publica e para o
        corpo de um e-mail: aceitar marcacao aqui seria convidar injecao."""
        if v is None:
            return v
        limpo = _HTML.sub("", v).strip()
        if not limpo:
            raise ValueError("texto vazio depois de remover marcação")
        return limpo


@app.get("/reclamacoes/temas")
def reclamacao_temas():
    """Os temas pelos quais a reclamação é roteada, com a esfera de cada um."""
    from . import reclamacoes as R

    with cursor() as cur:
        return R.temas(cur)


@app.get("/reclamacoes/rota")
def reclamacao_rota(tema: str, ente: str = Query(..., min_length=1, max_length=7)):
    """De quem é o problema, antes de a pessoa escrever.

    Serve para a tela já dizer "isso é da prefeitura, e o prefeito hoje é X"
    enquanto a pessoa digita — que é o momento em que a informação ensina.
    """
    from . import reclamacoes as R

    with cursor() as cur:
        rota = R.roteia(cur, tema, ente)
        if rota["responsaveis"]:
            rota["escalonamento"] = R.escalonamento(
                cur, rota["responsaveis"][0]["esfera"])
        return rota


@app.get("/reclamacoes/escalonamento/{esfera}")
def reclamacao_escalonamento(esfera: str):
    """O que fazer quando não respondem. Cada passo com base legal e prazo."""
    from . import reclamacoes as R

    e = esfera.upper()
    if e not in ("MUNICIPAL", "ESTADUAL", "FEDERAL"):
        raise HTTPException(404, "esfera inválida")
    with cursor() as cur:
        return {"esfera": e, "passos": R.escalonamento(cur, e)}


@app.get("/reclamacoes")
def reclamacao_lista(ente: str | None = None, estado: str | None = None,
                     limite: int = Query(30, le=100)):
    """As reclamações públicas. Inclui as sem resposta — são o achado."""
    with cursor() as cur:
        cur.execute("""
            select r.protocolo, r.titulo, r.tema, r.estado, r.criado_em,
                   r.prazo_resposta, r.prorrogado_ate, r.respondido_em,
                   r.esfera_responsavel, r.cargo_destino, r.destino_nome,
                   r.resolvido, e.nome as municipio, e.uf,
                   case when r.exibir_autor then r.autor_nome end as autor
              from reclamacao r join ente e on e.codigo_ibge = r.ente_codigo
             where r.publica
               and (%s::text is null or r.ente_codigo = %s)
               and (%s::text is null or r.estado = %s)
             order by r.criado_em desc limit %s""",
                    (ente, ente, estado, estado, limite))
        return cur.fetchall()


@app.get("/reclamacoes/{protocolo}")
def reclamacao(protocolo: str):
    from . import reclamacoes as R

    with cursor() as cur:
        cur.execute("""
            select r.protocolo, r.titulo, r.descricao, r.tema, r.estado,
                   r.local_referencia, r.criado_em, r.encaminhado_em,
                   r.prazo_resposta, r.prorrogado, r.prorrogado_ate,
                   r.respondido_em, r.resposta, r.resposta_autor, r.resolvido,
                   r.esfera_responsavel, r.cargo_destino, r.destino_nome,
                   r.destino_orgao, r.destino_metodo, r.ente_codigo,
                   e.nome as municipio, e.uf,
                   case when r.exibir_autor then r.autor_nome end as autor
              from reclamacao r join ente e on e.codigo_ibge = r.ente_codigo
             where r.protocolo = upper(%s) and r.publica""", (protocolo,))
        base = cur.fetchone()
        if base is None:
            raise HTTPException(404, "protocolo não encontrado")
        cur.execute("""select tipo, descricao, ator, criado_em
                         from reclamacao_evento
                        where reclamacao_id = (select id from reclamacao
                                                where protocolo = upper(%s))
                        order by criado_em""", (protocolo,))
        base["linha_do_tempo"] = cur.fetchall()
        if base["esfera_responsavel"]:
            base["escalonamento"] = R.escalonamento(cur, base["esfera_responsavel"])
        # Dias de atraso, calculado aqui para a tela nao ter que saber a regra.
        from datetime import date as _d
        limite = base["prorrogado_ate"] or base["prazo_resposta"]
        base["dias_de_atraso"] = (
            (_d.today() - limite).days
            if limite and base["estado"] in ("encaminhada", "sem_resposta")
               and limite < _d.today() else 0)
        return base


@app.post("/reclamacoes", status_code=201)
def abre_reclamacao(nova: NovaReclamacao, request: Request):
    """A única escrita pública da API. Ver a explicação no topo do arquivo."""
    from . import reclamacoes as R

    _trava(request)
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as con, con.cursor() as cur:
        cur.execute("select 1 from ente where codigo_ibge=%s", (nova.ente_codigo,))
        if cur.fetchone() is None:
            raise HTTPException(400, "município ou estado inexistente")
        r = R.abre(cur, ente_codigo=nova.ente_codigo, tema=nova.tema,
                   titulo=nova.titulo, descricao=nova.descricao,
                   local_referencia=nova.local_referencia,
                   autor_nome=nova.autor_nome, autor_email=nova.autor_email,
                   exibir_autor=nova.exibir_autor)
        con.commit()
    return {"protocolo": r["protocolo"], "encaminhavel": r["encaminhavel"],
            "roteamento": r["roteamento"]}


@app.get("/fontes")
def fontes():
    """O que está coberto e o que não está, por esfera.

    Página de credibilidade. O federal tem API boa; acima disso o Brasil não
    tem padrão, e esconder isso seria pior que não ter a seção — quem consulta
    precisa saber que "nenhuma lei estadual aqui" significa "ainda não
    coletamos", não "o estado não legislou".
    """
    with cursor() as cur:
        cur.execute("""
            select e.nivel, f.escopo, f.tipo, f.verificacao, f.tem_tramitacao,
                   count(*) as entes
              from fonte_legislativa f join ente e on e.codigo_ibge = f.ente_codigo
             group by 1,2,3,4,5 order by 1, 6 desc""")
        resumo = cur.fetchall()
        cur.execute("""
            select e.uf, e.nome, e.nivel, f.escopo, f.tipo, f.url, f.formato,
                   f.verificacao, f.tem_tramitacao, f.observacao, f.verificado_em
              from fonte_legislativa f join ente e on e.codigo_ibge = f.ente_codigo
             where e.nivel in ('uniao','estado') and f.verificacao <> 'ausente'
             order by f.verificacao, e.nivel desc, e.uf nulls first""")
        detalhe = cur.fetchall()
        cur.execute("""
            select count(*) filter (where f.verificacao = 'testado')  as com_gazeta,
                   count(*) filter (where f.verificacao = 'ausente')  as sem_gazeta
              from fonte_legislativa f join ente e on e.codigo_ibge = f.ente_codigo
             where e.nivel = 'municipio' and f.escopo = 'gazeta'""")
        municipal = cur.fetchone()
    return {"resumo": resumo, "estaduais_e_federal": detalhe, "municipal": municipal}


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
                   p.data_apresentacao, p.marco_atual, p.fase_atual, p.ente_codigo,
                   p.norma_tipo, p.norma_numero, p.norma_ano, p.norma_data,
                   e.nome as ente_nome, e.uf as ente_uf, e.nivel as ente_nivel
              from proposicao p
              join ente e on e.codigo_ibge = p.ente_codigo
             where p.id = %s""", (proposicao_id,))
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
    esfera = T.esfera_de(base["ente_codigo"])
    blocos = T.agrupa([{**e, "dataHora": (e["data_hora"].isoformat()
                                          if e["data_hora"] else None)}
                       for e in etapas], esfera)
    base["trilha"] = [{k: v for k, v in b.items() if k != "itens"} | {
        "itens": [{"data_hora": i.get("dataHora"), "orgao": i.get("orgao"),
                   "descricao": i.get("descricao"), "despacho": i.get("despacho"),
                   "url": i.get("url"), "fonte": i.get("fonte"),
                   "metodo": i.get("metodo")} for i in b["itens"]]}
        for b in blocos]
    base["movimentacoes_totais"] = len(etapas)
    # O caminho depende da esfera: sete etapas no Congresso, cinco numa
    # assembleia ou camara municipal, que sao unicamerais. Desenhar sempre
    # sete faria uma lei estadual parecer ter duas etapas pendentes que nao
    # existem.
    base["esfera"] = esfera
    base["caminho"] = T.caminho_de(esfera)
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
