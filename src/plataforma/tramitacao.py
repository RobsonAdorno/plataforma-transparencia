"""O caminho de um projeto ate virar lei, traduzido.

A Camara publica 235 tipos de movimentacao. Uma cidada entende umas 12. Este
modulo faz essa reducao - e e o ponto mais fragil do projeto inteiro, por um
motivo que vale explicar.

Eu esperava que cada etapa importante tivesse seu proprio codigo. Nao tem.
Conferi no PL 1087/2025, que virou a Lei 15.270/2025:

  - "Remessa ao Senado Federal"            veio no codigo 190 (Expedicao de Documento)
  - "remessa da materia a sancao"          veio no codigo 100 (Apresentacao de Proposicao)

Existe um codigo 128 = "Remessa ao Senado Federal" no catalogo oficial. Aquele
PL nao usou. Ou seja: um mapeamento so por codigo perde as duas etapas que mais
importam para explicar como uma lei nasce.

Dai o desenho em duas camadas, na ordem:

  1. CODIGO - deterministico, e o que se confia.
  2. TEXTO  - regra sobre o despacho, para os codigos genericos. Cada etapa
     reconhecida assim fica marcada com metodo='texto' no banco, porque e
     exatamente ela que para de funcionar em silencio se a Camara reescrever a
     frase.

E dai tambem a necessidade do `confere()` no fim do arquivo: se a Camara diz
que a proposicao virou norma juridica e a trilha nao achou a etapa de lei, o
mapeamento regrediu. Sem esse teste a plataforma passaria a mentir sem avisar.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# ----------------------------------------------------------------- os marcos
#
# `fase` desenha a barra de progresso. Nulo = anda no processo mas nao avanca o
# projeto (urgencia muda o rito, desarquivamento ressuscita, nenhum dos dois
# aproxima da sancao).

FASES = {
    "APRESENTACAO":       1,
    "COMISSOES":          2,
    "PLENARIO_ORIGEM":    3,
    "CASA_REVISORA":      4,
    "PLENARIO_REVISORA":  5,
    "SANCAO":             6,
    "PROMULGACAO":        6,   # caminho da PEC e do decreto legislativo: nao ha sancao
    "LEI":                7,
}

# Fim de linha. O projeto parou aqui e nao vai virar lei por este caminho.
DESFECHOS = {"LEI", "REJEITADO", "ARQUIVADO", "RETIRADO", "PREJUDICADO", "VETO_TOTAL"}

ROTULOS = {
    "APRESENTACAO":      "Apresentado",
    "COMISSOES":         "Nas comissões",
    "URGENCIA":          "Urgência aprovada",
    "PLENARIO_ORIGEM":   "Aprovado na casa de origem",
    "CASA_REVISORA":     "Enviado à casa revisora",
    "PLENARIO_REVISORA": "Aprovado na casa revisora",
    "SANCAO":            "Enviado à sanção presidencial",
    "PROMULGACAO":       "Enviado à promulgação",
    "LEI":               "Virou lei",
    "VETO_TOTAL":        "Vetado integralmente",
    "REJEITADO":         "Rejeitado",
    "ARQUIVADO":         "Arquivado",
    "DESARQUIVADO":      "Desarquivado",
    "RETIRADO":          "Retirado pelo autor",
    "PREJUDICADO":       "Prejudicado",
}

# O que cada marco significa, em portugues de gente. Vai direto para a tela:
# o objetivo da plataforma e ensinar, e etapa sem explicacao nao ensina nada.
EXPLICACOES = {
    "APRESENTACAO": (
        "Alguém protocolou o texto. Pode ser um parlamentar, o Presidente da "
        "República, o STF, uma comissão ou os próprios cidadãos por iniciativa "
        "popular. Nessa hora o projeto ainda não vale nada — é só uma proposta."
    ),
    "COMISSOES": (
        "As comissões temáticas analisam o mérito e a constitucionalidade. Um "
        "relator é designado e escreve um parecer. É aqui que a maioria dos "
        "projetos morre, sem nunca ser votada."
    ),
    "URGENCIA": (
        "O Plenário decidiu atropelar o rito das comissões para votar logo. "
        "Acelera a tramitação e reduz o tempo de debate público."
    ),
    "PLENARIO_ORIGEM": (
        "A casa onde o projeto nasceu aprovou o texto. Metade do caminho: "
        "no Brasil uma lei precisa passar pelas duas casas do Congresso."
    ),
    "CASA_REVISORA": (
        "O projeto foi para a outra casa. Se nasceu na Câmara vai ao Senado, e "
        "vice-versa. A casa revisora pode aprovar, rejeitar ou emendar — e se "
        "emendar, o texto volta para a casa de origem decidir sobre as mudanças."
    ),
    "PLENARIO_REVISORA": (
        "As duas casas aprovaram. O texto do Congresso está fechado e segue "
        "para o Presidente da República."
    ),
    "SANCAO": (
        "O Presidente tem 15 dias úteis para sancionar ou vetar. Se ficar "
        "calado, vira lei do mesmo jeito — é a sanção tácita (art. 66, §3º da "
        "Constituição)."
    ),
    "PROMULGACAO": (
        "Emenda constitucional e decreto legislativo não vão à sanção do "
        "Presidente: o próprio Congresso promulga."
    ),
    "LEI": (
        "Sancionada e publicada no Diário Oficial. Agora é lei e vale para "
        "todos. Um veto parcial significa que partes do texto aprovado pelo "
        "Congresso foram cortadas pelo Presidente."
    ),
    "VETO_TOTAL": (
        "O Presidente rejeitou o texto inteiro. O veto volta ao Congresso, que "
        "pode derrubá-lo por maioria absoluta das duas casas em sessão conjunta."
    ),
    "REJEITADO": "Votado e derrotado. O projeto não vira lei.",
    "ARQUIVADO": (
        "Saiu de tramitação. O motivo mais comum é o fim da legislatura: pelo "
        "art. 105 do Regimento da Câmara, projeto não votado em quatro anos é "
        "arquivado em bloco. Pode ser desarquivado no início da legislatura "
        "seguinte, a pedido do autor."
    ),
    "DESARQUIVADO": "Voltou a tramitar, do ponto onde havia parado.",
    "RETIRADO": "O próprio autor desistiu e pediu a retirada.",
    "PREJUDICADO": (
        "Perdeu o objeto: outro texto sobre o mesmo assunto foi aprovado antes, "
        "ou a matéria já foi resolvida. Encerra sem votação de mérito."
    ),
}

# ------------------------------------------------- camada 1: marco por codigo
#
# Lista de permissao, nao de bloqueio. Codigo que nao esta aqui e ruido por
# padrao - e e a escolha certa, porque a Camara cria codigo novo e uma lista de
# bloqueio deixaria o ruido novo entrar sozinho na trilha da cidada. O custo
# dessa escolha e perder marco novo em silencio, e e para isso que serve o
# confere() no fim do arquivo.

POR_CODIGO: dict[str, str] = {}


def _reg(marco: str, *codigos: int) -> None:
    for c in codigos:
        POR_CODIGO[str(c)] = marco


# APRESENTACAO nao sai da trilha, de proposito. Os codigos candidatos (105
# "Leitura e publicacao", 604 "Publicacao de Proposicao", 100 "Apresentacao de
# Proposicao") disparam tambem para parecer, mensagem do Executivo e projeto
# apensado - na trilha do PL 1087/2025 eles produziam tres "Apresentado",
# nenhum na data certa. A data de apresentacao e propriedade publicada da
# propria proposicao, entao o carregador sintetiza essa etapa a partir dela.
# Minerar do historico seria trocar um dado exato por um palpite.

_reg("COMISSOES",
     110, 112,                       # distribuicao as comissoes
     120, 121, 122,                  # comissao especial criada / instalada
     319, 320, 321, 327, 328, 329,   # relator designado
     322, 323, 324, 325, 326, 330,   # parecer do relator
     335, 336, 337, 338, 340, 1040,  # parecer votado na comissao
     1027, 1028, 1029, 1030,         # conclusao dos pareceres
     210, 214, 215, 606,             # leitura de parecer
     501, 508)                       # recebimento pelo relator

_reg("URGENCIA", 196, 151)

# Aprovacao na casa de origem. 1235 ("Aprovacao de Proposicao (Plenario)")
# dispara tambem para requerimento dentro da sessao, entao sozinho ele nao
# serve - a desambiguacao esta em APROVACAO_MATERIA, logo abaixo.
_reg("PLENARIO_ORIGEM",
     240, 244, 241,                  # aprovacao
     237, 238,                       # aprovacao em 1o turno (PEC)
     239, 211, 506, 510, 113, 125)   # redacao final aprovada = texto fechado

_reg("CASA_REVISORA", 128, 1041)
_reg("PLENARIO_REVISORA", 1518, 1519)
_reg("SANCAO", 127, 609, 607, 137)
_reg("PROMULGACAO", 126, 608)
_reg("LEI", 251, 1012)
_reg("VETO_TOTAL", 1013)
_reg("REJEITADO", 197, 1236)
_reg("ARQUIVADO", 502, 134, 1024, 630, 131, 1034, 1035)
_reg("DESARQUIVADO", 503, 135, 140, 640, 650)
_reg("RETIRADO", 200, 1241, 1025, 201, 133, 1020, 132)
_reg("PREJUDICADO", 198, 1240, 435, 620)
_reg("TRANSFORMADO_EM_OUTRO", 469)

# Codigos de desfecho que valem tambem para os acessorios da sessao, e por isso
# nao podem ser lidos sozinhos. Na trilha do PL 1087/2025 eles produziam seis
# "Retirado pelo autor", um "Rejeitado" e um "Prejudicado" - e todos eram
# destaques, recursos e emendas sendo retirados, nao o projeto. Um projeto vivo
# apareceria como morto na tela. Para estes o despacho tem que falar da materia.
EXIGE_MATERIA = {"1241", "1236", "1240", "197", "198", "200", "1025", "435",
                 "1242", "260", "263", "362", "193"}

# Marcadores de acessorio: se aparecem no OBJETO do despacho, o desfecho e do
# acessorio, nao do projeto.
ACESSORIO = re.compile(
    r"\b(dtq|destaque|req\b|requerimento|recurso|emenda|subemenda\s+(?!substitutiva\s+global)"
    r"|parecer|prl\b|prle\b|rdf\b|oficio|of\.|msc\b|relatorio|vista)")

# O despacho tem duas partes: o que foi feito e por que. "Retirado o PDL n.
# 18/2023, EM RAZAO DO DEFERIMENTO DO REQUERIMENTO n. 868/2024" retira o
# projeto - a palavra "requerimento" esta na justificativa. Testar o texto
# inteiro fazia o filtro de acessorio engolir retiradas reais, e o
# confere() flagrou isso em dois PDLs da amostra. So o objeto e testado.
JUSTIFICATIVA = re.compile(
    r",?\s*(em\s+raz[ãa]o|em\s+face|em\s+virtude|em\s+decorr[êe]ncia|"
    r"em\s+consequ[êe]ncia|nos\s+termos|na\s+forma|conforme)\b")


def _objeto(texto: str) -> str:
    """So o que foi feito, sem a justificativa que vem depois.

    Quando o despacho COMECA pela justificativa - "Em consequencia, ficam
    prejudicados o Substitutivo, a proposicao inicial e as emendas" - o corte
    devolveria string vazia e o filtro de acessorio viraria um nada, deixando
    passar um "Prejudicado" no meio de um projeto que virou lei. Foi o que
    aconteceu com o PLP 186/2026. Sem objeto proprio, vale o texto todo.
    """
    m = JUSTIFICATIVA.search(texto)
    cabeca = texto[:m.start()].strip() if m else texto
    return cabeca if len(cabeca) > 12 else texto

# Codigos genericos: o tipo nao diz nada, o despacho diz tudo. So estes passam
# pela camada de texto, para uma frase solta num despacho de requerimento nao
# inventar uma etapa que nao houve.
GENERICOS = {"100", "190", "1243", "1510", "1515", "1005", "1023", "180",
             "1001", "611", "603", "1007", "5", "999"}

# 1235 precisa olhar o texto mesmo nao sendo generico: ele aprova tanto a
# materia quanto os requerimentos da sessao.
AMBIGUOS = {"1235", "231", "1231"}


# -------------------------------------------------- camada 2: marco por texto

def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s or "")
                   if not unicodedata.combining(c)).lower()


# A ordem importa e e deliberada:
#   - desarquivamento antes de arquivamento, senao "desarquivado" casa com
#     "arquiv" e o projeto ressuscitado aparece como morto;
#   - lei antes de sancao, porque "transformado na lei X" tambem fala de sancao;
#   - veto total antes de veto parcial, que e desfecho oposto.
REGRAS_TEXTO: list[tuple[str, re.Pattern[str]]] = [
    ("LEI",               re.compile(r"transformad[oa]\s+n[ao]s?\s+(lei|decreto|emenda|norma)")),
    ("LEI",               re.compile(r"transformad[oa]\s+em\s+norma\s+juridica")),
    ("VETO_TOTAL",        re.compile(r"vetad[oa]\s+(totalmente|integralmente)")),
    ("VETO_TOTAL",        re.compile(r"veto\s+total")),
    ("PROMULGACAO",       re.compile(r"(remessa|despacho|envi\w+)\s+(a|à)\s+promulga")),
    ("PROMULGACAO",       re.compile(r"promulgad[oa]")),
    ("SANCAO",            re.compile(r"(remessa|envi\w+|encaminh\w+)\s+(a|à)\s+sanca")),
    ("SANCAO",            re.compile(r"materia\s+(a|à)\s+sanca")),
    ("SANCAO",            re.compile(r"(a|à)\s+sancao\s+presidencial")),
    ("SANCAO",            re.compile(r"remessa\s+(a|à)\s+presidencia\s+da\s+republica")),
    # "Apresentacao do Autografo" NAO e sancao: o autografo e o texto oficial que
    # a casa de origem fecha para mandar a casa revisora. Tratar como sancao
    # fazia a trilha do PL 1087/2025 ir a sancao antes de ir ao Senado. O
    # autografo que importa chega pelo codigo 607, do lado de quem recebe.
    ("PLENARIO_REVISORA", re.compile(r"aprova\w*\s+(no|pelo|d[oa])\s+senado\s+federal")),
    ("PLENARIO_REVISORA", re.compile(r"aprova\w*\s+(na|pela|d[oa])\s+camara\s+dos\s+deputados")),
    ("CASA_REVISORA",     re.compile(r"(remessa|vai|envi\w+|encaminh\w+)\s+ao\s+senado\s+federal")),
    ("CASA_REVISORA",     re.compile(r"materia\s+vai\s+ao\s+senado")),
    ("CASA_REVISORA",     re.compile(r"(remessa|vai|envi\w+)\s+(a|à)\s+camara\s+dos\s+deputados")),
    ("CASA_REVISORA",     re.compile(r"remessa\s+ao\s+congresso\s+nacional")),
    ("DESARQUIVADO",      re.compile(r"desarquiv")),
    ("ARQUIVADO",         re.compile(r"arquiv")),
    ("PLENARIO_ORIGEM",   re.compile(r"aprovad[oa]\s+a\s+redacao\s+final")),
    ("PLENARIO_ORIGEM",   re.compile(r"aprovad[oa]\s+(o|a)\s+(projeto|proposta|substitutivo|subemenda)")),
    ("REJEITADO",         re.compile(r"rejeitad[oa]\s+(o|a)\s+(projeto|proposta)")),
]

# Dentro dos AMBIGUOS, so estas frases contam: elas falam da materia, nao do
# requerimento procedimental que passou na mesma sessao.
MATERIA = re.compile(
    r"aprovad[oa]\s+(a\s+redacao\s+final|o\s+projeto|a\s+proposta|"
    r"a\s+subemenda|o\s+substitutivo|a\s+emenda\s+constitucional)")

# "Transformado na Lei Ordinaria 15270/2025. DOU 27/11/2025" -> a norma gerada.
NORMA = re.compile(
    r"transformad[oa]\s+n[ao]s?\s+"
    r"(lei\s+complementar|lei\s+ordinaria|lei|emenda\s+constitucional|"
    r"decreto\s+legislativo|resolucao)"
    r"\s*n?[oº°.\s]*([\d.]+)\s*[/,\s-]\s*(\d{4})")

TIPO_NORMA = {
    "lei": "LEI",
    "lei ordinaria": "LEI",
    "lei complementar": "LEI_COMPLEMENTAR",
    "emenda constitucional": "EMENDA_CONSTITUCIONAL",
    "decreto legislativo": "DECRETO_LEGISLATIVO",
    "resolucao": "RESOLUCAO",
}

RELATOR = re.compile(r"designad[oa]\s+relator[a(]*[,:\s]+(?:dep\.?|deputad[oa])?\s*"
                     r"([^.(]{3,60}?)\s*\(([^)]+)\)", re.IGNORECASE)


@dataclass(frozen=True)
class Marco:
    nome: str | None
    fase: int | None
    metodo: str | None       # 'codigo' | 'texto' | None quando e ruido


RUIDO = Marco(None, None, None)


# Orgaos que nao sao comissao. Parecer e designacao de relator acontecem
# tambem em Plenario, durante a sessao de votacao - e "Nas comissoes" no meio
# do Plenario e contradicao: aparecia intercalado entre as duas aprovacoes do
# PL 1087/2025 e dava a impressao de que o projeto tinha voltado atras.
NAO_COMISSAO = {"PLEN", "MESA", "CD", "SF", "CN", "PR"}

# Mas o filtro acima so vale para o que depende de ONDE aconteceu. Distribuir
# as comissoes e criar comissao especial sao atos registrados na Mesa cujo
# conteudo E a ida as comissoes: filtra-los apagava 107 distribuicoes numa
# amostra de 180 proposicoes, justamente a etapa que explica para onde o
# projeto foi depois de apresentado.
COMISSAO_SEMPRE = {"110", "112", "120", "121", "122"}


def classifica(cod_tipo: str | int | None, despacho: str | None = None,
               descricao: str | None = None, orgao: str | None = None) -> Marco:
    """Traduz uma movimentacao em marco, ou diz que e ruido processual.

    Codigo primeiro. Texto so para os genericos e para os ambiguos, onde o
    codigo sozinho enganaria.
    """
    cod = str(cod_tipo or "").strip()
    texto = _sem_acento(f"{descricao or ''} {despacho or ''}")
    # O objeto do ato esta no despacho. A descricao e o TIPO do evento
    # ("Prejudicialidade (Plenario)") e, concatenada na frente, virava a cabeca
    # da frase e desarmava o filtro de acessorio: era por isso que o PLP
    # 186/2026 aparecia como prejudicado depois de ter virado lei.
    ato = _objeto(_sem_acento(despacho or ""))

    if cod in AMBIGUOS:
        if not MATERIA.search(texto):
            return RUIDO           # aprovou requerimento, nao a materia
        return Marco("PLENARIO_ORIGEM", FASES["PLENARIO_ORIGEM"], "texto")

    if cod in EXIGE_MATERIA:
        if ACESSORIO.search(ato):
            return RUIDO           # morreu o destaque, nao o projeto
        nome = POR_CODIGO.get(cod)
        return Marco(nome, FASES.get(nome), "texto") if nome else RUIDO

    if cod in POR_CODIGO:
        nome = POR_CODIGO[cod]
        if (nome == "COMISSOES" and cod not in COMISSAO_SEMPRE
                and (orgao or "").strip().upper() in NAO_COMISSAO):
            return RUIDO
        return Marco(nome, FASES.get(nome), "codigo")

    if cod in GENERICOS or not cod:
        for nome, padrao in REGRAS_TEXTO:
            if padrao.search(texto):
                return Marco(nome, FASES.get(nome), "texto")

    return RUIDO


def norma_gerada(despacho: str | None) -> tuple[str, str, int] | None:
    """Extrai "Lei Ordinaria 15270/2025" do despacho de transformacao."""
    m = NORMA.search(_sem_acento(despacho or ""))
    if not m:
        return None
    tipo = TIPO_NORMA.get(m.group(1).strip(), "LEI")
    return tipo, m.group(2).replace(".", ""), int(m.group(3))


def relator_de(despacho: str | None) -> tuple[str, str] | None:
    """"Designado Relator, Dep. Arthur Lira (PP-AL)" -> ('Arthur Lira', 'PP-AL')."""
    m = RELATOR.search(despacho or "")
    if not m:
        return None
    return m.group(1).strip(" ,-"), m.group(2).strip()


# ------------------------------------------------------------------- trilha

def trilha(tramitacoes: list[dict]) -> list[dict]:
    """Classifica a lista crua e devolve na ordem cronologica.

    Nao deduplica: tres pareceres do relator em dias diferentes sao tres
    etapas reais. Deduplicar aqui esconderia o vai-e-vem, que e justamente o
    que explica por que uma lei leva tres anos.
    """
    saida = []
    for t in tramitacoes:
        m = classifica(t.get("codTipoTramitacao"), t.get("despacho"),
                       t.get("descricaoTramitacao"), t.get("siglaOrgao"))
        saida.append({**t, "marco": m.nome, "fase": m.fase, "metodo": m.metodo})
    saida.sort(key=lambda t: (t.get("dataHora") or "", t.get("sequencia") or 0))
    return saida


def agrupa(etapas: list[dict]) -> list[dict]:
    """Colapsa marcos iguais e seguidos num bloco com contagem.

    O PL 1087/2025 passa catorze vezes por "Nas comissoes" - sao catorze
    eventos reais (distribuicao, relator, cinco pareceres, recebimentos), mas
    quatorze linhas iguais na tela nao ensinam nada. Vira um bloco:
    "Nas comissoes - 14 movimentacoes, de 04/04 a 01/10". As etapas originais
    continuam dentro, para quem abrir.
    """
    blocos: list[dict] = []
    for e in (x for x in etapas if x.get("marco")):
        if blocos and blocos[-1]["marco"] == e["marco"]:
            blocos[-1]["itens"].append(e)
        else:
            blocos.append({"marco": e["marco"], "fase": e.get("fase"),
                           "rotulo": ROTULOS.get(e["marco"], e["marco"]),
                           "explicacao": EXPLICACOES.get(e["marco"]),
                           "itens": [e]})
    for b in blocos:
        b["inicio"] = b["itens"][0].get("dataHora")
        b["fim"] = b["itens"][-1].get("dataHora")
        b["total"] = len(b["itens"])
    return blocos


def resumo(etapas: list[dict]) -> dict:
    """O estado do projeto hoje: fase alcancada, marco mais recente, desfecho."""
    marcos = [e for e in etapas if e.get("marco")]
    fases = [e["fase"] for e in marcos if e.get("fase")]
    desfecho = next((e["marco"] for e in reversed(marcos)
                     if e["marco"] in DESFECHOS), None)
    return {
        "fase_atual": max(fases) if fases else None,
        "marco_atual": desfecho or (marcos[-1]["marco"] if marcos else None),
        "desfecho": desfecho,
        "etapas": len(etapas),
        "marcos": len(marcos),
        "por_texto": sum(1 for e in marcos if e.get("metodo") == "texto"),
    }


# -------------------------------------------------------- teste de sanidade
#
# Situacoes finais que a Camara publica, e o marco que a trilha TEM que ter
# encontrado quando a proposicao esta numa delas.
# Cada situacao final aceita um conjunto de marcos, nao um so. "Arquivada" e
# frequentemente a consequencia contabil de outro desfecho: o PDL 19/2025 foi
# declarado prejudicado em Plenario e so depois arquivado. Exigir exatamente
# ARQUIVADO ali acusaria um erro que nao existe - e teste que grita a toa
# acaba ignorado, que e pior do que nao ter teste.
SITUACAO_EXIGE: dict[int, set[str]] = {
    1140: {"LEI"},                   # Transformado em Norma Juridica
    937:  {"VETO_TOTAL"},            # Vetado totalmente
    923:  {"ARQUIVADO", "PREJUDICADO", "RETIRADO", "REJEITADO"},
    950:  {"RETIRADO", "ARQUIVADO"},
    1222: {"PREJUDICADO", "ARQUIVADO"},
    1292: {"PREJUDICADO", "ARQUIVADO"},
}


def confere(cod_situacao: int | None, etapas: list[dict]) -> str | None:
    """Denuncia regressao silenciosa do mapeamento.

    Se a Camara diz que a proposicao virou norma juridica e a trilha nao achou
    nenhuma etapa compativel, o mapeamento parou de funcionar - provavelmente
    porque a redacao do despacho mudou. Devolve o que se esperava achar.

    Este e o unico mecanismo que impede a plataforma de exibir "em tramitacao"
    para uma lei que ja esta em vigor. Na primeira rodada ele acusou tres
    divergencias em setenta proposicoes, e as tres eram defeito meu.
    """
    exigidos = SITUACAO_EXIGE.get(cod_situacao or 0)
    if not exigidos:
        return None
    achados = {e.get("marco") for e in etapas}
    return None if achados & exigidos else "|".join(sorted(exigidos))
