"""Canal de reclamacao: roteia, conta o prazo e torna o silencio visivel.

O servico que a plataforma presta aqui nao e hospedar texto - e responder "de
quem e isso". O cidadao descreve um poste queimado; descobrir que poste e da
prefeitura, que energia e da concessionaria regulada pela ANEEL e que as duas
coisas moram na mesma conta de luz e o trabalho.

O roteamento sai da tabela `competencia`, a mesma que alimenta o conteudo
educativo sobre o limite de cada cargo. Isso nao e economia de tabela: e a
garantia de que a plataforma roteia pelo mesmo critério que ensina. Se um dia
ela mandar reclamacao de poste para o deputado federal, a pagina do deputado
federal tambem estara errada, e os dois se consertam de uma vez.

Sobre o prazo: nao e nosso. A Lei 13.460/2017 da a reclamacao o status de
manifestacao (art. 2, V) e obriga a ouvidoria a enviar a decisao administrativa
final em 30 dias, prorrogaveis uma vez por igual periodo com justificativa
(art. 16). Contamos esse prazo e mostramos quando estoura - mas tambem
registramos a prorrogacao, porque acusar de omissa uma prefeitura que usou um
direito legal seria o mesmo tipo de erro que acusar camara dentro do teto.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import date, timedelta

from .config import CPF_SALT

# Este modulo espera cursor com row_factory=dict_row, como o da API. Indexar
# por posicao quebrou na primeira chamada real, e misturar os dois estilos no
# mesmo arquivo seria pior - acesso por nome em tudo.

PRAZO_DIAS = 30                 # Lei 13.460/2017, art. 16
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sem I, O, 0, 1


def protocolo() -> str:
    """Codigo curto que a pessoa anota. Sem caracteres que se confundem a mao."""
    corpo = "".join(secrets.choice(ALFABETO) for _ in range(6))
    return f"{date.today().year}-{corpo}"


def hash_autor(contato: str | None) -> str | None:
    """Identifica repeticao sem guardar quem e.

    Mesma politica do CPF: o identificador cru nao entra no banco. Reclamacao
    revela onde a pessoa mora e do que ela reclama - e dado sensivel, nao
    cadastro.
    """
    if not contato:
        return None
    base = (CPF_SALT or "sem-sal") + contato.strip().lower()
    return hashlib.sha256(base.encode()).hexdigest()[:32]


# ---------------------------------------------------------------- roteamento

def temas(cur) -> list[dict]:
    """Os temas disponiveis, com a esfera responsavel de cada um."""
    cur.execute("""
        select tema, esfera, cargo_responsavel, descricao, base_legal
          from competencia order by esfera, tema""")
    return cur.fetchall()


def roteia(cur, tema: str, ente_codigo: str) -> dict:
    """De quem e o problema, e quem ocupa esse cargo nesta cidade.

    Devolve uma LISTA de responsaveis, nao um. Saude de media complexidade e
    competencia comum (CF art. 23, II): o estado e a Uniao dividem, e dizer
    "e do estado" mandaria metade das pessoas ao lugar errado.
    """
    cur.execute("""
        select tema, esfera, cargo_responsavel, descricao, base_legal
          from competencia where lower(tema) = lower(%s)
         order by case esfera when 'MUNICIPAL' then 1
                              when 'ESTADUAL' then 2 else 3 end""", (tema,))
    achados = cur.fetchall()
    if not achados:
        return {"tema": tema, "responsaveis": [], "indefinido": True}

    # O ente do estado e o codigo do IBGE ('29'), nao a sigla ('BA'). Usar a
    # sigla fazia o governador aparecer vazio em toda reclamacao estadual,
    # porque nenhum mandato aponta para 'BA'.
    estado = None
    if len(ente_codigo) >= 7:
        cur.execute("""select est.codigo_ibge from ente mun
                         join ente est on est.nivel='estado' and est.uf = mun.uf
                        where mun.codigo_ibge = %s""", (ente_codigo,))
        linha = cur.fetchone()
        estado = linha["codigo_ibge"] if linha else None
    elif ente_codigo != "0":
        estado = ente_codigo

    for a in achados:
        a["ente_destino"] = _ente_da_esfera(a["esfera"], ente_codigo, estado)
        a["ocupante"] = _ocupante(cur, a["cargo_responsavel"], a["ente_destino"])
        a["canais"] = _canais(cur, a["ente_destino"])
    return {"tema": tema, "responsaveis": achados, "indefinido": False}


def _ente_da_esfera(esfera: str, ente_codigo: str, estado: str | None) -> str:
    """Qual ente responde por aquela esfera, a partir de onde esta o problema."""
    if esfera == "FEDERAL":
        return "0"
    if esfera == "ESTADUAL":
        return estado or "0"
    return ente_codigo


def _ocupante(cur, cargo: str, ente_destino: str) -> dict | None:
    """Quem ocupa o cargo hoje. None nao e erro: pode nao estar carregado."""
    cur.execute("""
        select p.id, p.nome_urna, p.nome_completo, m.partido
          from mandato m join pessoa p on p.id = m.pessoa_id
         where m.cargo = %s and m.ente_codigo = %s and m.situacao <> 'encerrado'
         order by m.data_inicio desc nulls last limit 1""", (cargo, ente_destino))
    return cur.fetchone()


def _canais(cur, ente_destino: str) -> list[dict]:
    cur.execute("""select tipo, valor, orgao, observacao, verificado_em
                     from canal_atendimento where ente_codigo=%s
                    order by case tipo when 'ouvidoria' then 1 when 'lai' then 2
                                       when 'email' then 3 else 4 end""",
                (ente_destino,))
    return cur.fetchall()


def escalonamento(cur, esfera: str) -> list[dict]:
    """O que fazer quando nao respondem, do mais simples ao mais pesado.

    A ordem importa: mandar o cidadao direto ao Ministerio Publico por um poste
    queimado desperdica o instrumento e desgasta o canal.
    """
    cur.execute("""
        select ordem, orgao, o_que_fazer, prazo, base_legal, quando_usar
          from escalonamento where esfera = %s order by ordem""", (esfera,))
    return cur.fetchall()


# ------------------------------------------------------------------ abertura

def abre(cur, *, ente_codigo: str, tema: str, titulo: str, descricao: str,
         local_referencia: str | None = None, autor_nome: str | None = None,
         autor_email: str | None = None, exibir_autor: bool = False) -> dict:
    """Registra a reclamacao, ja roteada, com o prazo contado.

    Nasce no estado 'recebida' e NAO no 'encaminhada': encaminhar depende de
    existir canal conhecido para aquele ente, e prometer encaminhamento que
    nao aconteceu seria pior que nao ter o canal.
    """
    rota = roteia(cur, tema, ente_codigo)
    principal = rota["responsaveis"][0] if rota["responsaveis"] else None
    canais = (principal or {}).get("canais") or []
    canal = canais[0] if canais else None
    ocupante = (principal or {}).get("ocupante") or {}

    cur.execute(
        """insert into reclamacao
             (protocolo, ente_codigo, tema, esfera_responsavel, cargo_destino,
              destino_nome, destino_orgao, destino_email, destino_metodo,
              titulo, descricao, local_referencia, autor_hash, autor_nome,
              autor_email, exibir_autor, estado)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'recebida')
           returning id, protocolo, criado_em""",
        (protocolo(), ente_codigo, tema,
         (principal or {}).get("esfera"), (principal or {}).get("cargo_responsavel"),
         ocupante.get("nome_urna"),
         (canal or {}).get("orgao"),
         (canal or {}).get("valor") if (canal or {}).get("tipo") == "email" else None,
         "email" if (canal or {}).get("tipo") == "email"
         else ("ouvidoria" if canal else "indefinido"),
         titulo.strip(), descricao.strip(), local_referencia,
         hash_autor(autor_email), autor_nome if exibir_autor else None,
         autor_email, exibir_autor))
    criada = cur.fetchone()
    rid, proto, criado = criada["id"], criada["protocolo"], criada["criado_em"]

    _evento(cur, rid, "recebida",
            f"Reclamação registrada e classificada como «{tema}», de competência "
            f"{(principal or {}).get('esfera', 'indefinida').lower()}.")
    if not canal:
        _evento(cur, rid, "sem_canal",
                "Ainda não temos o canal oficial de atendimento deste órgão "
                "cadastrado, então não há para onde encaminhar automaticamente. "
                "A reclamação fica pública e o passo a passo abaixo diz como "
                "protocolá-la você mesmo.")
    return {"id": rid, "protocolo": proto, "criado_em": criado,
            "roteamento": rota, "encaminhavel": bool(canal)}


def _evento(cur, reclamacao_id: int, tipo: str, descricao: str,
            ator: str = "plataforma") -> None:
    cur.execute("""insert into reclamacao_evento (reclamacao_id, tipo, descricao, ator)
                   values (%s,%s,%s,%s)""", (reclamacao_id, tipo, descricao, ator))


def encaminha(cur, reclamacao_id: int, ator: str, como: str) -> dict:
    """Marca como encaminhada e abre a contagem do prazo de 30 dias."""
    prazo = date.today() + timedelta(days=PRAZO_DIAS)
    cur.execute(
        """update reclamacao set estado='encaminhada', encaminhado_em=now(),
             prazo_resposta=%s where id=%s and estado='recebida'
           returning protocolo""", (prazo, reclamacao_id))
    r = cur.fetchone()
    if r is None:
        return {"erro": "reclamação não está em estado 'recebida'"}
    _evento(cur, reclamacao_id, "encaminhada",
            f"Encaminhada ao órgão responsável por {como}. O prazo legal para a "
            f"decisão administrativa final é {PRAZO_DIAS} dias "
            f"(Lei 13.460/2017, art. 16), vencendo em "
            f"{prazo.strftime('%d/%m/%Y')}.", ator)
    return {"protocolo": r["protocolo"], "prazo_resposta": prazo.isoformat()}


def responde(cur, reclamacao_id: int, resposta: str, autor: str) -> dict:
    cur.execute(
        """update reclamacao set estado='respondida', respondido_em=now(),
             resposta=%s, resposta_autor=%s where id=%s returning protocolo""",
        (resposta.strip(), autor, reclamacao_id))
    r = cur.fetchone()
    if r is None:
        return {"erro": "reclamação inexistente"}
    _evento(cur, reclamacao_id, "respondida",
            "O órgão respondeu. A resposta está publicada abaixo, no texto "
            "em que foi enviada.", autor)
    return {"protocolo": r["protocolo"]}


def prorroga(cur, reclamacao_id: int, justificativa: str, ator: str) -> dict:
    """A lei permite prorrogar uma vez. Registrar isso evita acusacao injusta."""
    cur.execute("select prazo_resposta, prorrogado from reclamacao where id=%s",
                (reclamacao_id,))
    r = cur.fetchone()
    if r is None:
        return {"erro": "reclamação inexistente"}
    if r["prorrogado"]:
        return {"erro": "a lei permite uma única prorrogação (art. 16)"}
    novo = (r["prazo_resposta"] or date.today()) + timedelta(days=PRAZO_DIAS)
    cur.execute("""update reclamacao set prorrogado=true, prorrogado_ate=%s
                    where id=%s""", (novo, reclamacao_id))
    _evento(cur, reclamacao_id, "prorrogada",
            f"O órgão prorrogou o prazo por mais {PRAZO_DIAS} dias, como a lei "
            f"permite uma única vez, até {novo.strftime('%d/%m/%Y')}. "
            f"Justificativa: {justificativa}", ator)
    return {"prorrogado_ate": novo.isoformat()}


def vence_prazos(cur) -> dict:
    """Passa para 'sem_resposta' o que estourou o prazo legal.

    Este e o coracao do canal. Reclamacao sem resposta nao e dado faltando: e
    o achado, e precisa virar estado explicito para a tela poder dizer "o
    prazo legal venceu em tal dia e nao houve resposta" em vez de deixar a
    reclamacao parada parecendo esquecida pela plataforma.
    """
    cur.execute("""
        update reclamacao
           set estado = 'sem_resposta'
         where estado = 'encaminhada'
           and coalesce(prorrogado_ate, prazo_resposta) < current_date
        returning id, protocolo,
                  coalesce(prorrogado_ate, prazo_resposta) as prazo""")
    venceram = cur.fetchall()
    for v in venceram:
        rid, prazo = v["id"], v["prazo"]
        _evento(cur, rid, "sem_resposta",
                f"O prazo legal venceu em {prazo.strftime('%d/%m/%Y')} sem "
                f"resposta do órgão. Pela Lei 13.460/2017 a ouvidoria deveria "
                f"ter enviado a decisão administrativa final. O silêncio fica "
                f"registrado aqui, e abaixo estão os próximos passos.")
    return {"venceram": len(venceram),
            "protocolos": [v["protocolo"] for v in venceram]}
