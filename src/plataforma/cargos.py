"""Populacao por ente e a conferencia dos tetos constitucionais.

O conteudo sobre o limite de cada cargo e texto escrito por gente. Dois desses
limites, porem, sao numero: o art. 29, IV fixa quantas cadeiras cada camara
municipal pode ter por faixa de populacao, e o art. 29-A fixa o teto de gasto.
Com a populacao do IBGE do lado dos eleitos que ja estao no banco, da para
conferir as 5.571 camaras do pais contra o limite constitucional.

E aqui esta a licao mais importante deste modulo, aprendida errando:

A primeira versao comparava as cadeiras contra o Censo 2022 e acusava 34
camaras de estarem acima do teto. Estava errada. O numero de vagas e fixado
ANTES da eleicao, com a populacao que valia naquele momento - e entre a
estimativa de 2021 e o Censo 2022 muitos municipios encolheram. Trinta das 34
tinham teto maior pela populacao vigente quando as vagas foram definidas:
Rio Preto da Eva/AM caiu de 34.856 para 24.936 habitantes, o que muda o teto
de 13 para 11 sem que ninguem tenha feito nada de errado.

Publicar aquela lista teria sido acusar trinta camaras legitimas de
irregularidade. Numa plataforma de transparencia esse erro e pior que nao ter
a funcionalidade, porque vem com a autoridade de um dado oficial.

Dai as tres regras que este modulo segue:

  1. compara contra TODAS as referencias de populacao disponiveis e so marca o
     que excede por todas elas;
  2. nunca chama o resultado de irregularidade - e 'a_conferir', porque a
     causa pode estar na fonte. Em Braga/RS o proprio arquivo do TSE lista 10
     vereadores eleitos (9 por quociente, 1 por media) numa cidade de 3.268
     habitantes, cujo teto e 9. Dez e numero par, e nenhuma faixa do art. 29 e
     par: o dado da fonte nao fecha, e isso nao e algo que eu resolva por
     dedução;
  3. guarda as duas populacoes na tela, para quem le poder julgar sozinho.
"""
from __future__ import annotations

import json

import requests

from . import bronze

AGREGADO_CENSO = ("https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/"
                  "2022/variaveis/93?localidades={nivel}")
AGREGADO_ESTIMATIVA = ("https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/"
                       "{ano}/variaveis/9324?localidades={nivel}")
# Os colchetes precisam ir percent-encoded: com '[' literal o servidor do IBGE
# derruba a conexao em vez de responder erro.
NIVEIS = ("N6%5Ball%5D", "N3%5Ball%5D")   # municipios, estados
FONTE = "ibge_censo"
CENSO_ANO = 2022
# Ultima estimativa anterior a definicao das vagas da eleicao municipal de
# 2024. E a referencia que explica a maioria das divergencias contra o Censo.
ESTIMATIVA_ANO = 2021


def _serie(url: str, ano: int, rotulo: str) -> dict[str, int]:
    pop: dict[str, int] = {}
    for nivel in NIVEIS:
        alvo = url.format(nivel=nivel, ano=ano)
        r = requests.get(alvo, timeout=180)
        r.raise_for_status()
        bronze.guarda(FONTE, f"{rotulo}_{'uf' if 'N3' in nivel else 'mun'}.json",
                      r.content, alvo)
        corpo = r.json()
        if not corpo:          # o agregado nao cobre esse ano
            continue
        for s in corpo[0]["resultados"][0]["series"]:
            valor = (s.get("serie") or {}).get(str(ano))
            if valor and str(valor).isdigit():
                pop[s["localidade"]["id"]] = int(valor)
    return pop


def carrega_populacao(cur) -> dict:
    """Grava as duas referencias. Guardar so uma era a causa do erro anterior."""
    censo = _serie(AGREGADO_CENSO, CENSO_ANO, f"censo{CENSO_ANO}")
    estim = _serie(AGREGADO_ESTIMATIVA, ESTIMATIVA_ANO, f"estimativa{ESTIMATIVA_ANO}")

    for codigo, n in censo.items():
        cur.execute(
            """update ente set populacao=%s, populacao_ano=%s, populacao_fonte=%s
                where codigo_ibge=%s""",
            (n, CENSO_ANO, f"IBGE Censo {CENSO_ANO}", codigo))
    for codigo, n in estim.items():
        cur.execute(
            """update ente set populacao_referencia=%s, populacao_referencia_ano=%s
                where codigo_ibge=%s""", (n, ESTIMATIVA_ANO, codigo))

    cur.execute("""select count(*) filter (where populacao is null),
                          count(*) filter (where populacao_referencia is null)
                     from ente where nivel='municipio'""")
    sem_censo, sem_ref = cur.fetchone()
    return {f"censo_{CENSO_ANO}": len(censo),
            f"estimativa_{ESTIMATIVA_ANO}": len(estim),
            "municipios_sem_censo": sem_censo,
            "municipios_sem_estimativa": sem_ref}


# ---------------------------------------------------- conferencia do art. 29
#
# O teto aplicavel e o MAIOR entre as referencias: se por qualquer populacao
# publicada a camara cabe no limite, ela esta conforme. So sobra o que nao
# cabe de jeito nenhum.
CONFERE_ART29 = """
with base as (
  select e.codigo_ibge, e.nome, e.uf, e.populacao, e.populacao_referencia,
         count(*) filter (where m.cargo = 'VEREADOR') as cadeiras
    from ente e
    left join mandato m on m.ente_codigo = e.codigo_ibge
   where e.nivel = 'municipio'
   group by 1,2,3,4,5
), tetos as (
  select b.*,
         (select f.max_vereadores from faixa_vereador f
           where b.populacao >= f.pop_min
             and (f.pop_max is null or b.populacao <= f.pop_max)) as teto_censo,
         (select f.max_vereadores from faixa_vereador f
           where b.populacao_referencia >= f.pop_min
             and (f.pop_max is null or b.populacao_referencia <= f.pop_max)) as teto_estimativa
    from base b
)
select *, greatest(coalesce(teto_censo,0), coalesce(teto_estimativa,0)) as teto_aplicavel,
       case
         when cadeiras = 0 then 'sem_vereador_publicado'
         when populacao is null and populacao_referencia is null then 'sem_populacao'
         when cadeiras <= greatest(coalesce(teto_censo,0), coalesce(teto_estimativa,0))
              then case when cadeiras > coalesce(teto_censo, 99)
                        then 'conforme_pela_estimativa' else 'conforme' end
         else 'a_conferir'
       end as estado
  from tetos
"""


def confere_camaras(cur) -> dict:
    """Compara cada camara municipal com o teto do art. 29, IV.

    Devolve contagem por estado e so a lista do que nao fecha por nenhuma
    referencia - que e a unica coisa que merece ir para revisao humana.
    """
    cur.execute(f"select estado, count(*) from ({CONFERE_ART29}) t group by 1 order by 2 desc")
    estados = {r[0]: r[1] for r in cur.fetchall()}

    cur.execute(f"""select nome, uf, populacao, populacao_referencia, cadeiras,
                           teto_censo, teto_estimativa, teto_aplicavel
                      from ({CONFERE_ART29}) t
                     where estado = 'a_conferir'
                     order by cadeiras - teto_aplicavel desc, populacao desc""")
    colunas = [c.name for c in cur.description]
    return {"por_estado": estados,
            "a_conferir": [dict(zip(colunas, r)) for r in cur.fetchall()]}


def principal() -> dict:
    from .load import conecta

    with conecta() as con, con.cursor() as cur:
        r = carrega_populacao(cur)
        con.commit()
        c = confere_camaras(cur)

    print(json.dumps(r, ensure_ascii=False, indent=1))
    print("\nconferencia do art. 29, IV (teto de cadeiras por populacao):")
    rotulos = {
        "conforme": "dentro do teto",
        "conforme_pela_estimativa": "dentro do teto pela populacao vigente na eleicao "
                                    "(fora se usar o Censo 2022)",
        "a_conferir": "acima do teto por qualquer referencia - vai para revisao",
        "sem_vereador_publicado": "o TSE nao publicou resultado de vereador",
        "sem_populacao": "sem populacao do IBGE",
    }
    for estado, n in c["por_estado"].items():
        print(f"  {n:>5}  {rotulos.get(estado, estado)}")

    if c["a_conferir"]:
        print(f"\n{len(c['a_conferir'])} camara(s) para conferir na fonte:")
        for x in c["a_conferir"]:
            print(f"  {x['nome']}/{x['uf']:<3} censo {x['populacao'] or 0:>8,} "
                  f"| estimativa {x['populacao_referencia'] or 0:>8,} "
                  f"| tem {x['cadeiras']:>2} cadeiras, teto {x['teto_aplicavel']:>2}")
        print("\n  Isto NAO e laudo de irregularidade: a divergencia pode estar na fonte."
              "\n  Em Braga/RS o proprio arquivo do TSE lista 10 eleitos, e nenhuma faixa"
              "\n  do art. 29 e par.")
    return {**r, **c}
