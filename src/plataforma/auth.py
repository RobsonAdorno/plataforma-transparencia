"""Autenticacao do painel de administracao.

Nao escrevemos autenticacao: a identidade vem de um provedor externo e aqui so
se decide o que a pessoa pode fazer. Duas implementacoes:

  Firebase  - producao. Valida o ID token e exige o claim de administrador.
  TokenLocal - desenvolvimento. Um segredo longo no ambiente, sem usuario e sem
               senha, porque senha caseira e pior que token caseiro.

A verificacao acontece SEMPRE no servidor. Esconder o botao no cliente nao e
seguranca.
"""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

TAMANHO_MINIMO_TOKEN = 32


@dataclass(frozen=True)
class Ator:
    email: str
    papel: str

    @property
    def pode_escrever(self) -> bool:
        return self.papel in ("editor", "admin")


class Verificador:
    def identifica(self, credencial: str) -> Ator:
        raise NotImplementedError


class TokenLocal(Verificador):
    """Um unico operador, um unico segredo. Só para desenvolvimento."""

    def __init__(self, segredo: str, email: str = "local@dev"):
        if len(segredo) < TAMANHO_MINIMO_TOKEN:
            raise RuntimeError(
                f"ADMIN_TOKEN precisa de pelo menos {TAMANHO_MINIMO_TOKEN} caracteres")
        self.segredo = segredo
        self.email = email

    def identifica(self, credencial: str) -> Ator:
        # compare_digest para nao vazar o segredo pelo tempo de resposta
        if not hmac.compare_digest(credencial, self.segredo):
            raise HTTPException(401, "credencial inválida")
        return Ator(email=self.email, papel="admin")


class Firebase(Verificador):
    """Producao: ID token do Firebase com claim de administrador."""

    def __init__(self, credencial_json: str):
        self.credencial_json = credencial_json

    def identifica(self, credencial: str) -> Ator:
        raise HTTPException(
            501, "verificação Firebase ainda não implementada: faltam as credenciais do projeto")


def verificador() -> Verificador:
    if cred := os.getenv("FIREBASE_CREDENTIALS", ""):
        return Firebase(cred)
    token = os.getenv("ADMIN_TOKEN", "")
    if not token:
        raise HTTPException(503, "painel desabilitado: defina ADMIN_TOKEN ou FIREBASE_CREDENTIALS")
    return TokenLocal(token)


def ator_atual(authorization: str = Header(default="")) -> Ator:
    """Dependencia do FastAPI. Toda rota de escrita passa por aqui."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "envie o cabeçalho Authorization: Bearer <token>")
    return verificador().identifica(authorization[7:])


def exige_escrita(ator: Ator = Depends(ator_atual)) -> Ator:
    if not ator.pode_escrever:
        raise HTTPException(403, "sem permissão de escrita")
    return ator
