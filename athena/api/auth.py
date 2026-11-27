from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Annotated, Literal

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel

from athena.config.settings import Settings, get_settings

COOKIE_SESSAO = "athena_sessao"

router = APIRouter(prefix="/v1")


class Usuario(BaseModel):
    id: str
    nome: str
    email: str
    papel: Literal["admin", "analista"]
    nomeAssinatura: str


@cache
def chaves_locais() -> tuple[str, str]:
    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_privada = privada.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    pem_publica = (
        privada.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return pem_privada, pem_publica


def chaves(settings: Settings) -> tuple[str, str]:
    if settings.jwt_chave_privada and settings.jwt_chave_publica:
        return settings.jwt_chave_privada, settings.jwt_chave_publica
    return chaves_locais()


def emitir_sessao(settings: Settings, email: str, nome: str) -> str:
    agora = datetime.now(UTC)
    papel = "admin" if email in settings.emails_admin else "analista"
    privada, _ = chaves(settings)
    claims = {"sub": email, "nome": nome, "papel": papel, "iat": agora}
    claims["exp"] = agora + timedelta(days=settings.sessao_dias)
    return jwt.encode(claims, privada, algorithm="RS256")


def erro(status: int, mensagem: str, codigo: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": mensagem, "code": codigo})


def usuario_atual(
    settings: Annotated[Settings, Depends(get_settings)],
    athena_sessao: Annotated[str | None, Cookie()] = None,
) -> Usuario:
    if not athena_sessao:
        raise erro(401, "Faça login para continuar.", "unauthorized")
    _, publica = chaves(settings)
    try:
        claims = jwt.decode(athena_sessao, publica, algorithms=["RS256"])
    except jwt.PyJWTError as exc:
        raise erro(401, "Sessão expirada. Faça login de novo.", "unauthorized") from exc
    nome = claims.get("nome") or claims["sub"]
    return Usuario(
        id=claims["sub"],
        nome=nome,
        email=claims["sub"],
        papel=claims["papel"],
        nomeAssinatura=nome.split(" ")[0],
    )


@router.get("/me")
def me(usuario: Annotated[Usuario, Depends(usuario_atual)]) -> Usuario:
    return usuario


@router.post("/auth/logout", status_code=204)
def logout() -> Response:
    resposta = Response(status_code=204)
    resposta.delete_cookie(COOKIE_SESSAO)
    return resposta
