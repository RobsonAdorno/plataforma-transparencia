"""Conector do Senado Federal.

Existe por um motivo especifico: a Camara registra QUE o Senado aprovou, mas
nao registra o que aconteceu dentro do Senado. Sem esta fonte, metade do
caminho de uma lei fica em branco - e para projeto que nasce no Senado, como o
PL 2628/2022 (ECA Digital), a Camara so conhece a parte final.

Atencao a um risco de manutencao: o servico antigo /dadosabertos/materia foi
marcado para desativacao completa em 01/02/2026 e o substituto e /processo.
Na data em que este codigo foi escrito o antigo ainda respondia, o que torna
facil construir em cima dele por engano e quebrar sem aviso depois. Este modulo
usa /processo de proposito.

A vantagem e que /processo entrega estruturado o que na Camara so existe como
texto livre no despacho:

    "situacaoAtual":  "TRANSFORMADA EM NORMA JURIDICA"
    "normaGerada":    {"siglaTipo": "LEI", "numero": "15270", ...}
    "objetivo":       "Revisora"

Cruzar as duas casas e o que permite confiar no desfecho em vez de confiar numa
expressao regular.
"""
from __future__ import annotations

from typing import Iterator

import requests

API = "https://legis.senado.leg.br/dadosabertos"
HEADERS = {"accept": "application/json"}
FONTE = "senado_processo"


def _get(caminho: str, **params):
    r = requests.get(f"{API}/{caminho}", params=params, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


def _lista(resposta) -> list[dict]:
    """O servico devolve lista no topo, mas as vezes um objeto so."""
    if isinstance(resposta, list):
        return resposta
    return [resposta] if isinstance(resposta, dict) else []


def processo(sigla: str, numero: int | str, ano: int) -> dict | None:
    """Acha a materia no Senado pela identificacao da Camara.

    Vale para os dois sentidos: um PL que nasceu na Camara chega ao Senado com
    o mesmo numero/ano, e um que nasceu no Senado tambem.
    """
    achados = _lista(_get("processo", sigla=sigla, numero=numero, ano=ano))
    return achados[0] if achados else None


def detalhe(id_processo: str | int) -> dict | None:
    """O processo inteiro: despachos, ordens do dia, deliberacao, norma gerada."""
    achados = _lista(_get(f"processo/{id_processo}"))
    return achados[0] if achados else None


# O Senado abrevia o tipo da norma no vocabulario dele. Sem traduzir, o banco
# guardaria 'LEI-N' onde a Camara guarda 'LEI' e a mesma lei apareceria como
# duas coisas diferentes.
TIPO_NORMA = {
    "LEI-N": "LEI", "LEI": "LEI", "LEI ORDINARIA": "LEI",
    "LCP": "LEI_COMPLEMENTAR", "LEI COMPLEMENTAR": "LEI_COMPLEMENTAR",
    "EMC": "EMENDA_CONSTITUCIONAL", "EMENDA CONSTITUCIONAL": "EMENDA_CONSTITUCIONAL",
    "DLG": "DECRETO_LEGISLATIVO", "DECRETO LEGISLATIVO": "DECRETO_LEGISLATIVO",
    "RSF": "RESOLUCAO", "RCN": "RESOLUCAO", "RESOLUCAO": "RESOLUCAO",
    "MPV": "MEDIDA_PROVISORIA",
}


def norma_de(det: dict) -> tuple[str, str, int, str | None] | None:
    """A norma gerada, ja estruturada - sem regex, diferente da Camara."""
    n = det.get("normaGerada") or {}
    if not isinstance(n, dict) or not n.get("numero"):
        return None
    ano = n.get("anoAssinatura") or (n.get("dataAssinatura") or "")[:4]
    sigla = (n.get("siglaTipo") or "LEI").upper().strip()
    # O Senado sufixa o tipo com '-N' (numerada): LEI-N, EMC-N. Sem tirar o
    # sufixo antes de traduzir, duas emendas constitucionais entraram no banco
    # como 'EMC_N' enquanto as leis entravam certo - porque 'LEI-N' estava no
    # mapa e 'EMC-N' nao.
    if sigla.endswith("-N"):
        sigla = sigla[:-2]
    return (
        TIPO_NORMA.get(sigla, sigla.replace(" ", "_").replace("-", "_")),
        str(n["numero"]).replace(".", ""),
        int(ano) if str(ano).isdigit() else 0,
        n.get("dataAssinatura"),
    )


def _texto(v) -> str:
    if isinstance(v, dict):
        for k in ("descricao", "nome", "texto", "sigla", "identificacao"):
            if v.get(k):
                return str(v[k])
        return ""
    return str(v or "")


def trilha(det: dict) -> Iterator[dict]:
    """Normaliza o processo do Senado no mesmo formato da trilha da Camara.

    Nao existe um /tramitacoes equivalente: o historico vem espalhado em
    `autuacoes`, `despachos`, `ordensDoDia` e `deliberacao`. Esta funcao junta
    os quatro num fluxo unico para o carregador tratar as duas casas igual.
    """
    casa = det.get("siglaCasaIniciadora") or "SF"

    for a in det.get("autuacoes") or []:
        yield {"dataHora": a.get("data") or det.get("dataInicioEfetivo"),
               "siglaOrgao": casa, "codTipoTramitacao": "SF_AUTUACAO",
               "descricaoTramitacao": "Autuação no Senado",
               "despacho": _texto(a.get("ementa") or a.get("descricao")),
               "sequencia": a.get("numeroAutuacao") or 1}

    for d in det.get("despachos") or []:
        yield {"dataHora": d.get("data"), "siglaOrgao": casa,
               "codTipoTramitacao": "SF_DESPACHO",
               "descricaoTramitacao": "Despacho às comissões no Senado",
               "despacho": _texto(d.get("descricao") or d.get("despacho")),
               "sequencia": None}

    for o in det.get("ordensDoDia") or []:
        yield {"dataHora": o.get("data") or o.get("dataSessao"), "siglaOrgao": "PLEN",
               "codTipoTramitacao": "SF_ORDEM_DIA",
               "descricaoTramitacao": "Incluído na ordem do dia do Senado",
               "despacho": _texto(o.get("descricao") or o.get("resultado")),
               "sequencia": None}

    delib = det.get("deliberacao") or {}
    if delib.get("data"):
        yield {"dataHora": delib["data"], "siglaOrgao": "PLEN",
               "codTipoTramitacao": "SF_DELIBERACAO",
               "descricaoTramitacao": _texto(delib.get("tipoDeliberacao")) or "Deliberação do Senado",
               "despacho": (f"{_texto(delib.get('tipoDeliberacao'))}. "
                            f"Destino: {_texto(delib.get('destino'))}"),
               "sequencia": None}

    n = norma_de(det)
    if n:
        tipo, numero, ano, data = n
        yield {"dataHora": data, "siglaOrgao": "PR",
               "codTipoTramitacao": "SF_NORMA",
               "descricaoTramitacao": "Transformado em norma jurídica",
               "despacho": f"Transformado na {tipo.replace('_',' ').title()} {numero}/{ano}.",
               "sequencia": None}


# Marcos do Senado, no vocabulario de tramitacao.py. Nao ha ambiguidade de
# texto aqui - cada chave e sintetica, criada por trilha() acima - mas ha uma
# ambiguidade de papel: o mesmo evento significa coisas diferentes conforme o
# Senado seja a casa onde o projeto nasceu ou a que revisa.
#
# O PL 2628/2022 nasceu no Senado: a autuacao de 2022 e a APRESENTACAO dele, e
# a deliberacao de 2024 e a aprovacao na casa de ORIGEM. Ja o PL 1087/2025
# nasceu na Camara: ali a autuacao e a chegada a casa revisora. Usar um mapa so
# inverteria a historia de metade dos projetos.
_MARCOS_INICIADORA = {
    "SF_AUTUACAO":    "APRESENTACAO",
    "SF_DESPACHO":    "COMISSOES",
    "SF_ORDEM_DIA":   None,
    "SF_DELIBERACAO": "PLENARIO_ORIGEM",
    "SF_NORMA":       "LEI",
}
_MARCOS_REVISORA = {
    "SF_AUTUACAO":    "CASA_REVISORA",
    "SF_DESPACHO":    "COMISSOES",
    "SF_ORDEM_DIA":   None,
    "SF_DELIBERACAO": "PLENARIO_REVISORA",
    "SF_NORMA":       "LEI",
}


def marcos(det: dict) -> dict[str, str | None]:
    """O mapa certo para este processo, conforme o papel do Senado nele."""
    iniciadora = (det.get("objetivo") or "").strip().lower().startswith("inicia")
    return _MARCOS_INICIADORA if iniciadora else _MARCOS_REVISORA

# "TRANSFORMADA EM NORMA JURIDICA" e afins: a situacao final declarada pelo
# Senado, usada para conferir o desfecho que a regex da Camara deduziu.
SITUACAO_DESFECHO = {
    "TNJR": "LEI",
    "TRANSFORMADA EM NORMA JURÍDICA": "LEI",
    "REJEITADA": "REJEITADO",
    "ARQUIVADA": "ARQUIVADO",
    "PREJUDICADA": "PREJUDICADO",
    "RETIRADA PELO AUTOR": "RETIRADO",
    "VETADA TOTALMENTE": "VETO_TOTAL",
}


def desfecho_de(det: dict) -> str | None:
    s = (det.get("siglaSituacaoAtual") or "").strip().upper()
    a = (det.get("situacaoAtual") or "").strip().upper()
    return SITUACAO_DESFECHO.get(s) or SITUACAO_DESFECHO.get(a)
