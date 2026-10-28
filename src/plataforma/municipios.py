"""Casamento de municipio entre TSE e IBGE.

O TSE identifica municipio por codigo proprio e nome; o resto do mundo usa o
codigo do IBGE. Sem essa ponte nao se carrega vereador nenhum.

Em camadas, da certeza ao palpite - e o que nao alcanca o limiar e relatado,
nunca adivinhado. Atribuir os vereadores a cidade errada e pior que nao ter.
"""
from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher

LIMIAR = 0.88

# Nomes que divergem de propósito entre as duas bases, conferidos um a um.
RENOMEADOS: dict[tuple[str, str], str] = {
    # O TSE manteve o nome antigo; o IBGE usa o oficial.
    ("RN", "BOA SAUDE"): "2405306",   # Januário Cicco
    ("RR", "SAO LUIZ"): "1400605",    # São Luiz do Anauá
}


def normaliza(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return " ".join(s.replace("'", " ").replace("-", " ").split())


class Indice:
    def __init__(self, entes: list[tuple[str, str, str]]):
        """entes: (codigo_ibge, nome, uf)"""
        self.exato: dict[tuple[str, str], str] = {}
        self.por_uf: dict[str, list[tuple[str, str]]] = {}
        for cod, nome, uf in entes:
            n = normaliza(nome)
            self.exato[(uf, n)] = cod
            self.por_uf.setdefault(uf, []).append((n, cod))
        self.nao_resolvidos: dict[tuple[str, str], str] = {}

    def resolve(self, uf: str, nome: str) -> tuple[str | None, str]:
        """Devolve (codigo_ibge, metodo). None quando nao da para afirmar."""
        n = normaliza(nome)
        if cod := RENOMEADOS.get((uf, n)):
            return cod, "renomeado"
        if cod := self.exato.get((uf, n)):
            return cod, "exato"
        melhor, score = None, 0.0
        for cand, cod in self.por_uf.get(uf, []):
            s = SequenceMatcher(None, n, cand).ratio()
            if s > score:
                melhor, score = cod, s
        if melhor and score >= LIMIAR:
            return melhor, f"similaridade {score:.2f}"
        self.nao_resolvidos[(uf, n)] = f"melhor palpite {score:.2f}"
        return None, "nao resolvido"
