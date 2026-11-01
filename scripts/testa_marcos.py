#!/usr/bin/env python3
"""Casos reais que o modelo de etapas ja errou. Nao roda rede.

Cada linha aqui e um despacho que existe de verdade na API e que, em algum
momento, foi classificado errado. Mantê-los fixos e o que impede o conserto de
um caso de quebrar outro - no PL 1087/2025 e no PLP 186/2026 foi exatamente o
que aconteceu duas vezes.

  python scripts/testa_marcos.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plataforma import tramitacao as T   # noqa: E402

# (codigo, orgao, descricao, despacho, marco esperado, por que importa)
CASOS: list[tuple[str, str | None, str, str, str | None, str]] = [
    ("1240", "PLEN", "Prejudicialidade (Plenário)",
     "Em consequência, ficam prejudicados o Substitutivo, a proposição inicial, "
     "a apensada e a emenda apresentada.",
     None,
     "adotar substitutivo prejudica o texto original, nao mata o projeto - o PLP "
     "186/2026 virou Lei Complementar 238/2026 com este despacho na trilha"),

    ("200", "MESA", "Retirada pelo(a) Autor(a)",
     "Retirado o PDL n. 18/2023, em razão do deferimento do Requerimento n. "
     "REQ 868/2024, nos termos do artigo 104, caput.",
     "RETIRADO",
     "a palavra 'Requerimento' esta na justificativa; o objeto e o projeto"),

    ("1241", "PLEN", "Retirada pelo Autor(a) (Plenário)",
     "Retirado o DTQ 3 (SOLIDARI): Destaque de Emenda de Plenário nº 71/2025 (161, II).",
     None,
     "morreu o destaque, nao o projeto - isto gerava seis 'Retirado' no PL 1087/2025"),

    ("1236", "PLEN", "Rejeição de Proposição (Plenário)",
     "Rejeitado o Recurso. Fica prejudicada a tramitação da Emenda de Plenário nº 94.",
     None,
     "recurso rejeitado nao e projeto rejeitado"),

    ("197", "PLEN", "Rejeição de Proposicao",
     "Rejeitado o Projeto de Lei n. 123, de 2025.",
     "REJEITADO",
     "rejeicao de verdade tem que passar"),

    ("1235", "PLEN", "Aprovação de Proposição (Plenário)",
     "Aprovado o Requerimento.",
     None,
     "1235 dispara para requerimento dentro da sessao"),

    ("1235", "PLEN", "Aprovação de Proposição (Plenário)",
     "Aprovada a Subemenda Substitutiva Global ao Projeto de Lei nº 1.087, de 2025, "
     "adotada pelo relator. Sim: 493; Total: 493.",
     "PLENARIO_ORIGEM",
     "a aprovacao da materia tem que passar"),

    ("190", "MESA", "Expedição de Documento",
     "Remessa ao Senado Federal por meio do Of. nº 222/2025/SGM-P.",
     "CASA_REVISORA",
     "a ida ao Senado veio no codigo generico 190, nao no 128 que existe para isso"),

    ("100", "MESA", "Apresentação de Proposição",
     "Recebimento do Ofício nº 1.088/2025 (SF) comunicando remessa da matéria à sanção.",
     "SANCAO",
     "a remessa a sancao veio no codigo 100; sem a regra de texto a etapa se perde"),

    ("251", "MESA", "Transformação em Norma Jurídica",
     "Transformado na Lei Ordinária 15270/2025. DOU 27/11/2025 PÁG 03 COL 02.",
     "LEI",
     "o desfecho"),

    ("190", "MESA", "Expedição de Documento",
     "Apresentação do Autógrafo.",
     None,
     "autografo e o texto fechado para ir a casa revisora, nao sancao - tratar como "
     "sancao punha o PL 1087/2025 na sancao antes de ir ao Senado"),

    ("110", "MESA", "Distribuição",
     "Às Comissões de Trabalho; Finanças e Tributação e Constituição e Justiça.",
     "COMISSOES",
     "distribuir e registrado na Mesa; filtrar por orgao apagava 107 distribuicoes "
     "numa amostra de 180 proposicoes"),

    ("322", "PLEN", "Parecer do(a) Relator(a)",
     "Parecer às Emendas de Plenário proferido pelo Relator.",
     None,
     "parecer lido em Plenario nao e 'nas comissoes' - aparecia intercalado no meio "
     "da votacao e dava a impressao de que o projeto voltou atras"),

    ("503", "MESA", "Desarquivamento",
     "Desarquivada a proposição nos termos do art. 105 do RICD.",
     "DESARQUIVADO",
     "desarquivamento tem que vencer o 'arquiv' da regra de arquivamento"),
]

NORMAS = [
    ("Transformado na Lei Ordinária 15270/2025. DOU 27/11/2025.", ("LEI", "15270", 2025)),
    ("Transformado na Lei Complementar 214/2025.", ("LEI_COMPLEMENTAR", "214", 2025)),
    ("Transformado na Emenda Constitucional 135/2025.", ("EMENDA_CONSTITUCIONAL", "135", 2025)),
    ("Aprovado o requerimento nº 3382/2025.", None),
]

RELATORES = [
    ("Designado Relator, Dep. Arthur Lira (PP-AL).", ("Arthur Lira", "PP-AL")),
    ("Designado Relator, Dep. Rubens Pereira Júnior (PT-MA).", ("Rubens Pereira Júnior", "PT-MA")),
    ("Apresentação do REQ n. 2/2025, pelo Deputado Pedro Paulo (PSD/RJ).", None),
]


def main() -> int:
    falhas = 0

    print("marcos:")
    for cod, orgao, desc, despacho, esperado, porque in CASOS:
        obtido = T.classifica(cod, despacho, desc, orgao).nome
        if obtido == esperado:
            print(f"  ok      cod {cod:<5} -> {str(obtido)}")
        else:
            falhas += 1
            print(f"  FALHOU  cod {cod:<5} -> {str(obtido)} (esperado {esperado})")
            print(f"          {porque}")

    print("\nnorma gerada:")
    for despacho, esperado in NORMAS:
        obtido = T.norma_gerada(despacho)
        if obtido == esperado:
            print(f"  ok      {str(obtido)}")
        else:
            falhas += 1
            print(f"  FALHOU  {obtido} (esperado {esperado}) em: {despacho[:50]}")

    print("\nrelator:")
    for despacho, esperado in RELATORES:
        obtido = T.relator_de(despacho)
        if obtido == esperado:
            print(f"  ok      {str(obtido)}")
        else:
            falhas += 1
            print(f"  FALHOU  {obtido} (esperado {esperado}) em: {despacho[:50]}")

    print(f"\n{'='*62}")
    print("tudo ok" if not falhas else f"{falhas} falha(s)")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
