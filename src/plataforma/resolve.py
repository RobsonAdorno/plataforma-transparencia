"""Identificacao de pessoas entre as fontes.

O componente que decide se a plataforma funciona. Em camadas, da certeza ao
palpite - e o que nao alcanca o limiar vai para revisao humana, nunca para o
banco. Um merge errado atribui o gasto do deputado A ao deputado B.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

LIMIAR_AUTOMATICO = 0.93   # acima disso entra sozinho
LIMIAR_SUGESTAO = 0.80     # entre os dois, vai para a fila com sugestao


def normaliza_nome(n: str) -> str:
    s = unicodedata.normalize("NFKD", n or "").encode("ascii", "ignore").decode().upper()
    return " ".join(s.replace(".", " ").split())


def similaridade(a: str, b: str) -> float:
    return SequenceMatcher(None, normaliza_nome(a), normaliza_nome(b)).ratio()


@dataclass
class Vinculo:
    id_camara: str
    nome_camara: str
    uf: str
    partido: str
    cpf: str | None = None
    sq_candidato: str | None = None
    metodo: str = "nao_resolvido"
    confianca: float = 0.0
    nome_tse: str | None = None


@dataclass
class Resultado:
    resolvidos: list[Vinculo] = field(default_factory=list)
    pendentes: list[Vinculo] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.resolvidos) + len(self.pendentes)

    def resumo(self) -> dict:
        from collections import Counter
        return {
            "total": self.total,
            "resolvidos": len(self.resolvidos),
            "pendentes": len(self.pendentes),
            "por_metodo": dict(Counter(v.metodo for v in self.resolvidos)),
        }


def liga_camara_tse(deputados: list[dict], ponte: dict[str, dict],
                    tse_por_cpf: dict[str, dict]) -> Resultado:
    """Camara -> TSE, passando pelo CPF que so existe no CSV da cota.

    deputados     : saida de camara.deputados_em_exercicio()
    ponte         : saida de camara.ponte_cpf()  -> cpf: {ide_cadastro, ...}
    tse_por_cpf   : saida de tse.por_cpf()       -> cpf: {...}
    """
    por_ide = {v["ide_cadastro"]: cpf for cpf, v in ponte.items()}
    res = Resultado()

    for dep in deputados:
        v = Vinculo(
            id_camara=str(dep["id"]),
            nome_camara=dep.get("nome", ""),
            uf=dep.get("siglaUf", ""),
            partido=dep.get("siglaPartido", ""),
        )
        cpf = por_ide.get(str(dep["id"]))

        # camada 1: CPF, deterministico
        if cpf and cpf in tse_por_cpf:
            reg = tse_por_cpf[cpf]
            v.cpf = cpf
            v.sq_candidato = reg["sq_candidato"]
            v.nome_tse = reg["nome_completo"]
            v.metodo = "cpf"
            v.confianca = 1.0
            res.resolvidos.append(v)
            continue

        # camada 2: nome, so dentro da mesma UF, para encolher o espaco de busca
        melhor, melhor_score = None, 0.0
        for reg in tse_por_cpf.values():
            if reg["uf"] != v.uf or reg["cargo"] != "DEPUTADO_FEDERAL":
                continue
            s = max(similaridade(dep.get("nome", ""), reg["nome_completo"]),
                    similaridade(dep.get("nome", ""), reg["nome_urna"]))
            if s > melhor_score:
                melhor, melhor_score = reg, s

        if melhor and melhor_score >= LIMIAR_AUTOMATICO:
            v.cpf = melhor["cpf"]
            v.sq_candidato = melhor["sq_candidato"]
            v.nome_tse = melhor["nome_completo"]
            v.metodo = "nome_uf"
            v.confianca = round(melhor_score, 3)
            res.resolvidos.append(v)
        else:
            if melhor and melhor_score >= LIMIAR_SUGESTAO:
                v.nome_tse = melhor["nome_completo"]
                v.sq_candidato = melhor["sq_candidato"]
                v.confianca = round(melhor_score, 3)
                v.metodo = "sugestao"
            res.pendentes.append(v)

    return res
