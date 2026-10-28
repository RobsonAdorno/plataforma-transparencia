"""Camada bronze: o download bruto, intocado, com data e hash.

Fonte publica muda de formato e some sem aviso. Guardar o original e o que
permite reprocessar o historico quando o parser estiver errado - e provar o que
a fonte dizia naquele dia.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from .config import BRONZE

TIMEOUT = 120


@dataclass(frozen=True)
class Manifest:
    fonte: str
    nome: str
    url: str
    coletado_em: str
    sha256: str
    bytes: int
    caminho: str

    @property
    def path(self) -> Path:
        return Path(self.caminho)


def _destino(fonte: str, nome: str, dia: date | None = None) -> Path:
    d = (dia or date.today()).isoformat()
    return BRONZE / fonte / d / nome


def guarda(fonte: str, nome: str, conteudo: bytes, url: str) -> Manifest:
    """Grava o bruto do dia. Se o conteudo ja esta la com o mesmo hash, nao reescreve."""
    alvo = _destino(fonte, nome)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(conteudo).hexdigest()
    man = Manifest(
        fonte=fonte,
        nome=nome,
        url=url,
        coletado_em=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        sha256=sha,
        bytes=len(conteudo),
        caminho=str(alvo),
    )
    mpath = alvo.with_suffix(alvo.suffix + ".manifest.json")
    if alvo.exists() and mpath.exists():
        antigo = json.loads(mpath.read_text())
        if antigo.get("sha256") == sha:
            return Manifest(**antigo)
    alvo.write_bytes(conteudo)
    mpath.write_text(json.dumps(asdict(man), ensure_ascii=False, indent=2))
    return man


def baixa(fonte: str, nome: str, url: str, *, headers: dict | None = None) -> Manifest:
    r = requests.get(url, timeout=TIMEOUT, headers=headers or {})
    r.raise_for_status()
    return guarda(fonte, nome, r.content, url)


def ja_baixado_hoje(fonte: str, nome: str) -> Manifest | None:
    mpath = _destino(fonte, nome).with_suffix(Path(nome).suffix + ".manifest.json")
    if mpath.exists():
        return Manifest(**json.loads(mpath.read_text()))
    return None
