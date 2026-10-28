"""Deteccao e despacho de alertas de votacao.

O gargalo aqui nunca foi tecnico. Sao 7.436 votacoes por ano e a pauta vive
tomada por requerimento: empurrar tudo garante desinstalacao no primeiro dia.
Entao o filtro e a peca central - e ele registra por que decidiu cada coisa,
porque num projeto de transparencia a regra tambem precisa ser auditavel.

Nada sai sozinho. Todo alerta nasce rascunho e espera alguem aprovar.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from .api import cursor
from .config import DATABASE_URL

import psycopg

# Materias que movem a vida das pessoas.
PESO_TIPO = {
    "PEC": 50,   # emenda constitucional
    "MPV": 40,   # medida provisoria, tem prazo e tranca a pauta
    "PLP": 35,   # lei complementar
    "PL": 25,    # lei ordinaria
    "PDL": 12,   # decreto legislativo
    "MSC": 10,   # mensagem
}

# Ruido de tramitacao. Importa para quem acompanha o rito, nao para o cidadao
# que quer saber o que mudou na vida dele.
RUIDO = {"REQ", "RIC", "INC", "PFC", "EMC", "EMP", "SBT", "SBE", "DVT", "DTQ"}

CORTE = 40          # abaixo disso nem vira rascunho
CORTE_DESTAQUE = 65  # acima disso entra no topico geral


def _pontua(tipo: str | None, *, orgao: str | None = None, watchlist: bool = False,
            nominal: bool = False, placar: tuple[int, int] | None = None
            ) -> tuple[int, list[str]]:
    t = (tipo or "").upper()
    motivos: list[str] = []

    if t in RUIDO and not watchlist:
        return 0, [f"{t} e ruido de tramitacao"]

    score = PESO_TIPO.get(t, 0)
    if score:
        motivos.append(f"{t} vale {score}")
    elif not watchlist:
        return 0, [f"tipo {t or '?'} fora da lista relevante"]

    if watchlist:
        score += 25
        motivos.append("esta na watchlist (+25)")
    if orgao == "PLEN":
        score += 20
        motivos.append("plenario (+20)")
    if nominal:
        score += 15
        motivos.append("votacao nominal, da para dizer quem votou o que (+15)")
    if placar:
        sim, nao = placar
        total = sim + nao
        if total and abs(sim - nao) / total < 0.12:
            score += 10
            motivos.append(f"placar apertado {sim}x{nao} (+10)")
    return score, motivos


def _topicos(tipo: str | None, prop_id: int | None, orgao: str | None, score: int) -> list[str]:
    t = [f"materia_{(tipo or 'outros').lower()}"]
    if prop_id:
        t.append(f"prop_{prop_id}")
    if orgao == "PLEN":
        t.append("plenario")
    if score >= CORTE_DESTAQUE:
        t.append("destaques")
    return t


def detectar() -> dict:
    """Varre o que ha de novo e cria rascunhos. Idempotente pela chave de dedup."""
    criados = descartados = 0
    exemplos_descartados: list[str] = []

    with psycopg.connect(DATABASE_URL) as con, con.cursor() as cur:
        cur.execute("select proposicao_id from watchlist")
        wl = {r[0] for r in cur.fetchall()}

        # --- 1. o que vai acontecer: pauta de evento futuro ainda nao realizado
        cur.execute("""
            select e.id, e.inicio, e.descricao, pr.id, pr.tipo, pr.numero, pr.ano, pr.ementa
              from pauta_item pi
              join evento e     on e.id = pi.evento_id
              join proposicao pr on pr.id = pi.proposicao_id
             where e.inicio > now()
               and e.situacao in ('Convocada','Agendada')""")
        for eid, inicio, edesc, pid, tipo, num, ano, ementa in cur.fetchall():
            orgao = (edesc or "").split(" · ")[0]
            score, motivos = _pontua(tipo, orgao=orgao, watchlist=pid in wl)
            chave = f"pauta:{eid}:{pid}"
            if score < CORTE:
                descartados += 1
                if len(exemplos_descartados) < 4:
                    exemplos_descartados.append(f"{tipo} {num}/{ano} — {motivos[0]}")
                continue
            quando = inicio.strftime("%d/%m às %Hh%M")
            cur.execute("""
                insert into alerta (chave_dedup, tipo, titulo, corpo, prioridade,
                                    topicos, proposicao_id, evento_id)
                values (%s,'pauta_futura',%s,%s,%s,%s,%s,%s)
                on conflict (chave_dedup) do nothing""",
                (chave, f"{tipo} {num}/{ano} entra em pauta {quando}",
                 (ementa or "")[:280], score,
                 _topicos(tipo, pid, orgao, score), pid, eid))
            criados += cur.rowcount

        # --- 2. o que acabou de acontecer: votacao nominal com placar
        # Uma materia rende varias votacoes no mesmo dia: destaque, emenda,
        # primeiro turno, segundo turno. O cidadao quer saber que a PEC foi
        # votada, nao receber cinco avisos sobre a mesma PEC. Entao agrupamos
        # por materia e dia, e anunciamos a votacao mais cheia - que e a
        # decisiva, nao um destaque lateral.
        cur.execute("""
            with por_votacao as (
              select vo.id, vo.orgao, vo.descricao, vo.data_hora::date as dia,
                     pr.id as pid, pr.tipo, pr.numero, pr.ano,
                     count(*) filter (where v.tipo_voto='Sim') as sim,
                     count(*) filter (where v.tipo_voto='Não') as nao,
                     count(*) as total
                from votacao vo
                join voto v        on v.votacao_id = vo.id
                join proposicao pr on pr.id = vo.proposicao_id
               where vo.tipo = 'nominal'
               group by vo.id, vo.orgao, vo.descricao, vo.data_hora, pr.id,
                        pr.tipo, pr.numero, pr.ano
            ), ranqueada as (
              select *, row_number() over (partition by pid, dia order by total desc, id) as rn,
                     count(*) over (partition by pid, dia) as votacoes_no_dia
                from por_votacao
            )
            select id, orgao, descricao, pid, tipo, numero, ano, sim, nao, dia, votacoes_no_dia
              from ranqueada where rn = 1""")
        for (vid, orgao, desc, pid, tipo, num, ano, sim, nao,
             dia, no_dia) in cur.fetchall():
            score, motivos = _pontua(tipo, orgao=orgao, watchlist=pid in wl,
                                     nominal=True, placar=(sim, nao))
            chave = f"votacao:{pid}:{dia}"      # uma materia, um dia, um alerta
            if score < CORTE:
                descartados += 1
                continue
            extra = (f" (e mais {no_dia - 1} votacoes dessa materia no mesmo dia)"
                     if no_dia > 1 else "")
            cur.execute("""
                insert into alerta (chave_dedup, tipo, titulo, corpo, prioridade,
                                    topicos, proposicao_id, votacao_id)
                values (%s,'votacao_ocorrida',%s,%s,%s,%s,%s,%s)
                on conflict (chave_dedup) do nothing""",
                (chave, f"{tipo} {num}/{ano}: {sim} a favor, {nao} contra",
                 ((desc or "")[:240] + extra), score,
                 _topicos(tipo, pid, orgao, score), pid, vid))
            criados += cur.rowcount
        con.commit()

    return {"rascunhos_criados": criados, "descartados_pelo_filtro": descartados,
            "exemplos_descartados": exemplos_descartados}


def imprime_fila(estado: str = "rascunho", limite: int = 15) -> None:
    with cursor() as cur:
        cur.execute("""
            select id, prioridade, tipo, titulo, topicos, estado
              from alerta where estado = %s
             order by prioridade desc, criado_em desc limit %s""", (estado, limite))
        linhas = cur.fetchall()
        cur.execute("select estado, count(*) from alerta group by estado")
        resumo = {r["estado"]: r["count"] for r in cur.fetchall()}
    print("fila:", json.dumps(resumo, ensure_ascii=False))
    for a in linhas:
        print(f"  [{a['id']:>4}] {a['prioridade']:>3}  {a['tipo']:<16} {a['titulo'][:62]}")
        print(f"         topicos: {' '.join(a['topicos'])}")


# ----------------------------------------------------------------- despacho

class Despachante:
    nome = "base"

    def envia(self, titulo: str, corpo: str, topicos: list[str]) -> dict:
        raise NotImplementedError


class Console(Despachante):
    """Padrao em desenvolvimento: imprime em vez de notificar ninguem."""
    nome = "console"

    def envia(self, titulo, corpo, topicos):
        print(f"  >> [{','.join(topicos)}] {titulo}\n     {corpo[:120]}")
        return {"despachante": self.nome, "topicos": topicos}


class FCM(Despachante):
    """Firebase Cloud Messaging, por topico.

    Topico em vez de lista de dispositivos: sem tabela de tokens, sem fan-out e
    sem guardar quem segue o que - o que tambem e uma decisao de privacidade.
    """
    nome = "fcm"

    def __init__(self, credencial: str):
        self.credencial = credencial

    def envia(self, titulo, corpo, topicos):
        raise NotImplementedError(
            "despacho real exige o projeto Firebase configurado; "
            "defina FIREBASE_CREDENTIALS e implemente o envio por topico")


def despachante() -> Despachante:
    cred = os.getenv("FIREBASE_CREDENTIALS", "")
    return FCM(cred) if cred else Console()


def enviar(alerta_id: int, ator: str = "cli") -> dict:
    d = despachante()
    with psycopg.connect(DATABASE_URL) as con, con.cursor() as cur:
        cur.execute("select titulo, corpo, topicos, estado from alerta where id=%s", (alerta_id,))
        row = cur.fetchone()
        if row is None:
            return {"erro": "alerta inexistente"}
        titulo, corpo, topicos, estado = row
        if estado == "enviado":
            return {"erro": "ja enviado", "id": alerta_id}
        r = d.envia(titulo, corpo, topicos)
        cur.execute("""update alerta set estado='enviado', enviado_em=now(),
                         decidido_em=now(), decidido_por=%s where id=%s""", (ator, alerta_id))
        cur.execute("""insert into auditoria (ator, acao, entidade, entidade_id, valor_depois)
                       values (%s,'enviar_alerta','alerta',%s,%s)""",
                    (ator, str(alerta_id), json.dumps(r, ensure_ascii=False)))
        con.commit()
    return {"id": alerta_id, "titulo": titulo, **r}
