"""Configuracao lida do ambiente. Nada de segredo no codigo."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_a, **_k):
        return False

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")

BRONZE = Path(os.getenv("BRONZE_DIR", RAIZ / "data" / "bronze"))
DERIVADO = Path(os.getenv("DERIVADO_DIR", RAIZ / "data" / "derivado"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
CPF_SALT = os.getenv("CPF_SALT", "")

_SO_DIGITO = re.compile(r"\D")


def normaliza_cpf(valor: str | None) -> str | None:
    """Devolve 11 digitos ou None. CPF do TSE e do CEAP vem sem mascara, mas
    arquivo preenchido a mao vem de tudo que e jeito."""
    if not valor:
        return None
    d = _SO_DIGITO.sub("", str(valor))
    if not d or len(d) > 11:
        return None
    d = d.zfill(11)
    return d if d != "0" * 11 else None


def cpf_valido(cpf: str | None) -> bool:
    """Digito verificador. Barra lixo antes de virar chave de juncao."""
    c = normaliza_cpf(cpf)
    if c is None or len(set(c)) == 1:
        return False
    for pos in (9, 10):
        soma = sum(int(c[i]) * ((pos + 1) - i) for i in range(pos))
        dv = (soma * 10) % 11 % 10
        if dv != int(c[pos]):
            return False
    return True


def hash_cpf(cpf: str | None) -> str | None:
    """Chave de juncao. O numero cru fica no bronze; no banco so entra o hash.

    O sal nunca muda depois do primeiro carregamento: trocar invalida todas as
    ligacoes ja gravadas.
    """
    c = normaliza_cpf(cpf)
    if c is None:
        return None
    if not CPF_SALT:
        raise RuntimeError("CPF_SALT ausente. Copie .env.example para .env e defina um valor.")
    return hashlib.sha256((CPF_SALT + c).encode()).hexdigest()
