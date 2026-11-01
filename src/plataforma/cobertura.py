"""Quanto de cada municipio a fonte realmente publicou.

Existe porque ausencia nao e informacao. Antes desta tabela, um municipio sem
vereador no banco podia significar tres coisas incompativeis - a cidade nao
elege vereador, o TSE nao divulgou, ou a carga falhou - e a tela nao tinha como
distinguir. Dizer "nenhum vereador" para Ananindeua, que tem 478 mil habitantes
e uma camara funcionando, seria publicar uma afirmacao falsa com cara de dado
oficial.

A classificacao nao e deduzida da ausencia: e contada no proprio arquivo do
TSE. Para cada municipio e cargo olhamos quantas candidaturas existem e quantas
voltaram com resultado '#NULO'. Se ha candidatura e nenhum resultado, o buraco
e da fonte e a plataforma diz isso com o numero do lado.

As duas excecoes legais - Distrito Federal e Fernando de Noronha - sao as
unicas coisas fixas aqui, porque sao regra constitucional e nao dado.
"""
from __future__ import annotations

import json
from collections import defaultdict

from . import bronze
from .municipios import Indice
from .sources import tse

# Resultado que o TSE usa quando nao ha o que divulgar.
SEM_RESULTADO = {"#NULO", "#NE", "", "#NULO#"}

# Nao elegem vereador nem prefeito, e isso e lei, nao falha de coleta.
NAO_SE_APLICA = {
    "5300108": ("Brasília", "O Distrito Federal não tem vereadores nem prefeito. "
                            "É regido por 24 deputados distritais e um governador "
                            "(CF/88, art. 32)."),
    "2605459": ("Fernando de Noronha",
                "É um distrito estadual de Pernambuco, não um município com "
                "câmara própria (ADCT, art. 15)."),
}

CARGOS = ("PREFEITO", "VEREADOR")


def apura(cur, man, ano: int = 2024) -> dict[tuple[str, str], dict]:
    """Conta, por municipio e cargo, candidaturas e resultados em branco."""
    cur.execute("""select codigo_ibge, nome, uf from ente where nivel='municipio'""")
    idx = Indice(cur.fetchall())
    contagem: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"candidaturas": 0, "eleitos": 0, "sem_resultado": 0})
    nao_resolvidos: set[str] = set()

    for linha in tse.linhas(man):
        cargo = (linha.get("DS_CARGO") or "").strip().upper()
        if cargo not in CARGOS:
            continue
        uf = (linha.get("SG_UF") or "").strip().upper()
        nome = (linha.get("NM_UE") or "").strip()
        codigo, _ = idx.resolve(uf, nome)
        if not codigo:
            nao_resolvidos.add(f"{uf}/{nome}")
            continue
        sit = (linha.get("DS_SIT_TOT_TURNO") or "").strip().upper()
        c = contagem[(codigo, cargo)]
        c["candidaturas"] += 1
        if sit in SEM_RESULTADO:
            c["sem_resultado"] += 1
        elif sit.startswith("ELEITO"):
            c["eleitos"] += 1

    if nao_resolvidos:
        print(f"  aviso: {len(nao_resolvidos)} unidades eleitorais nao resolvidas")
    return contagem


def carrega(cur, ano: int = 2024) -> dict:
    man = bronze.ja_baixado_hoje(tse.FONTE, f"consulta_cand_{ano}.zip")
    if man is None:
        man = tse.baixa(ano)
    contagem = apura(cur, man, ano)

    cur.execute("select codigo_ibge from ente where nivel='municipio'")
    municipios = [r[0] for r in cur.fetchall()]

    resumo = {"publicado": 0, "nao_publicado": 0, "nao_se_aplica": 0}
    for codigo in municipios:
        for cargo in CARGOS:
            c = contagem.get((codigo, cargo),
                             {"candidaturas": 0, "eleitos": 0, "sem_resultado": 0})
            if codigo in NAO_SE_APLICA:
                situacao, motivo = "nao_se_aplica", NAO_SE_APLICA[codigo][1]
            elif c["eleitos"] > 0:
                situacao, motivo = "publicado", None
            elif c["candidaturas"] > 0:
                situacao = "nao_publicado"
                motivo = (f"O TSE registrou {c['candidaturas']} candidaturas a "
                          f"{cargo.lower()} nesta cidade, mas não divulgou o "
                          f"resultado de {c['sem_resultado']} delas no arquivo "
                          f"oficial de {ano}.")
            else:
                situacao = "nao_publicado"
                motivo = (f"Nenhuma candidatura a {cargo.lower()} consta no "
                          f"arquivo do TSE de {ano} para esta cidade.")
            resumo[situacao] += 1
            cur.execute(
                """insert into cobertura (ente_codigo, cargo, ano_eleicao, situacao,
                     eleitos, candidaturas, sem_resultado, motivo, fonte, verificado_em)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                   on conflict (ente_codigo, cargo, ano_eleicao) do update set
                     situacao=excluded.situacao, eleitos=excluded.eleitos,
                     candidaturas=excluded.candidaturas,
                     sem_resultado=excluded.sem_resultado, motivo=excluded.motivo,
                     verificado_em=now()""",
                (codigo, cargo, ano, situacao, c["eleitos"], c["candidaturas"],
                 c["sem_resultado"], motivo, f"TSE consulta_cand_{ano}"))
    return resumo


def principal(ano: int = 2024) -> dict:
    from .load import conecta

    with conecta() as con, con.cursor() as cur:
        r = carrega(cur, ano)
        con.commit()
        cur.execute("""
            select c.cargo, c.situacao, count(*)
              from cobertura c where c.ano_eleicao=%s
             group by 1,2 order by 1,3 desc""", (ano,))
        print(json.dumps(r, ensure_ascii=False, indent=1))
        print("\npor cargo:")
        for cargo, situacao, n in cur.fetchall():
            print(f"  {cargo:<9} {situacao:<15} {n:>6}")
        cur.execute("""
            select e.nome, e.uf, c.cargo, c.candidaturas, c.sem_resultado
              from cobertura c join ente e on e.codigo_ibge=c.ente_codigo
             where c.situacao='nao_publicado' and c.ano_eleicao=%s
               and c.candidaturas > 0
             order by c.candidaturas desc limit 15""", (ano,))
        faltando = cur.fetchall()
        if faltando:
            print(f"\nmaiores buracos na fonte:")
            for nome, uf, cargo, cand, sem in faltando:
                print(f"  {nome}/{uf:<3} {cargo:<9} {cand:>4} candidaturas, "
                      f"{sem:>4} sem resultado")
    return r
