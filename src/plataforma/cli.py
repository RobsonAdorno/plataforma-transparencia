"""Linha de comando da ingestao.

  python -m plataforma.cli ingest-camara --ano 2026
  python -m plataforma.cli ingest-tse --ano 2022
  python -m plataforma.cli resolve --ano 2022
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from . import bronze, resolve
from .config import DERIVADO
from .sources import camara, tse


def _grava(nome: str, obj) -> str:
    DERIVADO.mkdir(parents=True, exist_ok=True)
    alvo = DERIVADO / nome
    alvo.write_text(json.dumps(obj, ensure_ascii=False, indent=1))
    return str(alvo)


def cmd_ingest_camara(args):
    deps = camara.deputados_em_exercicio()
    bronze.guarda(camara.FONTE_API, "deputados.json",
                  json.dumps(deps, ensure_ascii=False).encode(),
                  f"{camara.API}/deputados")
    print(f"deputados em exercicio: {len(deps)}")

    man = camara.baixa_ceap(args.ano)
    print(f"CEAP {args.ano}: {man.bytes/1e6:.1f} MB  sha {man.sha256[:12]}")
    ponte = camara.ponte_cpf(man)
    print(f"ponte CPF->ideCadastro: {len(ponte)} parlamentares")

    _grava("camara_deputados.json", deps)
    _grava("camara_ponte_cpf.json", ponte)
    cobertura = sum(1 for d in deps if str(d["id"]) in {v["ide_cadastro"] for v in ponte.values()})
    print(f"cobertura da ponte sobre os em exercicio: {cobertura}/{len(deps)}")


def cmd_ingest_tse(args):
    man = tse.baixa(args.ano)
    print(f"TSE {args.ano}: {man.bytes/1e6:.1f} MB  sha {man.sha256[:12]}")
    els = tse.eleitos(man)
    problemas = tse.confere(args.ano, els)
    print(f"eleitos: {len(els)}")
    if problemas:
        print("DIVERGENCIA contra os totais conhecidos:")
        for p in problemas:
            print("   -", p)
    else:
        print("conferencia contra os totais fixados por lei: ok")
    _grava(f"tse_eleitos_{args.ano}.json", els)


def cmd_resolve(args):
    deps = json.loads((DERIVADO / "camara_deputados.json").read_text())
    ponte = json.loads((DERIVADO / "camara_ponte_cpf.json").read_text())
    man = bronze.ja_baixado_hoje(tse.FONTE, f"consulta_cand_{args.ano}.zip")
    if man is None:
        sys.exit(f"rode antes: ingest-tse --ano {args.ano}")
    idx = tse.por_cpf(man)
    print(f"TSE {args.ano} indexado por CPF: {len(idx)} candidatos")

    r = resolve.liga_camara_tse(deps, ponte, idx)
    print(json.dumps(r.resumo(), ensure_ascii=False, indent=1))
    _grava(f"vinculos_{args.ano}.json",
           {"resolvidos": [v.__dict__ for v in r.resolvidos],
            "pendentes": [v.__dict__ for v in r.pendentes]})
    if r.pendentes:
        print(f"\nfila de revisao humana ({len(r.pendentes)}):")
        for v in r.pendentes[:12]:
            alvo = f"  ~ {v.nome_tse} ({v.confianca})" if v.nome_tse else "  sem candidato"
            print(f"  {v.nome_camara:<26} {v.partido:<14} {v.uf}{alvo}")



def cmd_ingest_votacoes(args):
    import re
    ini, fim = args.inicio, args.fim
    vs = camara.votacoes(ini, fim)
    print(f"votacoes {ini}..{fim}: {len(vs)}")
    bronze.guarda(camara.FONTE_API, f"votacoes_{ini}_{fim}.json",
                  json.dumps(vs, ensure_ascii=False).encode(), f"{camara.API}/votacoes")

    ids = [v["id"] for v in vs]
    def tick(n, t): print(f"  votos {n}/{t}", flush=True)
    votos = camara.votos_em_lote(ids, progresso=tick)
    nominais = {k: v for k, v in votos.items() if v}
    print(f"nominais: {len(nominais)}  |  simbolicas: {len(votos)-len(nominais)}")
    bronze.guarda(camara.FONTE_API, f"votos_{ini}_{fim}.json",
                  json.dumps(nominais, ensure_ascii=False).encode(), f"{camara.API}/votacoes/votos")

    # O id da votacao e "<id da proposicao>-<sequencia>". O campo oficial
    # uriProposicaoObjeto vem nulo na maioria das vezes, mas o prefixo resolve e
    # leva o vinculo com a materia de ~24% para perto de 100%.
    pids: set[str] = set()
    for v in vs:
        if m := re.search(r"/proposicoes/(\d+)", v.get("uriProposicaoObjeto") or ""):
            pids.add(m.group(1))
        if (pref := str(v.get("id", "")).split("-")[0]).isdigit():
            pids.add(pref)
    pids = sorted(pids)
    print(f"proposicoes distintas vinculadas: {len(pids)}")
    props = camara.proposicoes_por_id(pids)
    bronze.guarda(camara.FONTE_API, f"proposicoes_{ini}_{fim}.json",
                  json.dumps(props, ensure_ascii=False).encode(), f"{camara.API}/proposicoes")

    _grava(f"votacoes_{ini}_{fim}.json", vs)
    _grava(f"votos_{ini}_{fim}.json", nominais)
    _grava(f"proposicoes_{ini}_{fim}.json", props)
    print(f"proposicoes carregadas: {len(props)}")



def cmd_ingest_eventos(args):
    ini, fim = args.inicio, args.fim
    evs = camara.eventos(ini, fim)
    print(f"eventos {ini}..{fim}: {len(evs)}")

    # Pauta so interessa em evento que delibera. Puxar de todos seria desperdicio.
    delib = [e for e in evs if "Deliberativa" in (e.get("descricaoTipo") or "")
             or (e.get("descricaoTipo") or "").startswith("Sessão Deliberativa")]
    print(f"  deliberativos: {len(delib)}")
    pautas = camara.pautas_em_lote([str(e["id"]) for e in delib])
    com = sum(1 for v in pautas.values() if v)
    print(f"  com pauta publicada: {com}")

    for nome, obj in (("eventos", evs), ("pautas", pautas)):
        bronze.guarda(camara.FONTE_API, f"{nome}_{ini}_{fim}.json",
                      json.dumps(obj, ensure_ascii=False).encode(), f"{camara.API}/eventos")
        _grava(f"{nome}_{ini}_{fim}.json", obj)


def cmd_alertas(args):
    from . import alertas
    if args.acao == "detectar":
        r = alertas.detectar()
        print(json.dumps(r, ensure_ascii=False, indent=1))
    elif args.acao == "fila":
        alertas.imprime_fila(args.estado)
    elif args.acao == "enviar":
        print(json.dumps(alertas.enviar(args.id), ensure_ascii=False, indent=1))


def main(argv=None):
    p = argparse.ArgumentParser(prog="plataforma")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("ingest-camara"); a.add_argument("--ano", type=int, default=date.today().year)
    a.set_defaults(func=cmd_ingest_camara)
    b = sub.add_parser("ingest-tse"); b.add_argument("--ano", type=int, required=True)
    b.set_defaults(func=cmd_ingest_tse)
    v = sub.add_parser("ingest-votacoes")
    v.add_argument("--inicio", required=True); v.add_argument("--fim", required=True)
    v.set_defaults(func=cmd_ingest_votacoes)
    ev = sub.add_parser("ingest-eventos")
    ev.add_argument("--inicio", required=True); ev.add_argument("--fim", required=True)
    ev.set_defaults(func=cmd_ingest_eventos)
    al = sub.add_parser("alertas")
    al.add_argument("acao", choices=["detectar", "fila", "enviar"])
    al.add_argument("--estado", default="rascunho")
    al.add_argument("--id", type=int)
    al.set_defaults(func=cmd_alertas)
    c = sub.add_parser("resolve"); c.add_argument("--ano", type=int, default=2022)
    c.set_defaults(func=cmd_resolve)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
