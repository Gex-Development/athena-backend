import secrets
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Annotated, Literal
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from athena.config.settings import Settings, get_settings

COOKIE_SESSAO = "athena_sessao"
COOKIE_STATE = "athena_oauth_state"
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
EMISSORES_GOOGLE = {"https://accounts.google.com", "accounts.google.com"}

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


def callback_url(settings: Settings) -> str:
    return f"{settings.url_publica.rstrip('/')}/v1/auth/google/callback"


def trocar_codigo(settings: Settings, codigo: str) -> dict:
    resposta = httpx.post(
        GOOGLE_TOKEN,
        data={
            "code": codigo,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": callback_url(settings),
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    resposta.raise_for_status()
    return jwt.decode(
        resposta.json()["id_token"],
        options={"verify_signature": False},
        audience=settings.google_client_id,
    )


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


@router.get("/auth/google/start")
def google_start(settings: Annotated[Settings, Depends(get_settings)]) -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    parametros = {
        "client_id": settings.google_client_id,
        "redirect_uri": callback_url(settings),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    resposta = RedirectResponse(f"{GOOGLE_AUTH}?{urlencode(parametros)}", status_code=302)
    resposta.set_cookie(
        COOKIE_STATE, state, max_age=600, httponly=True, secure=settings.producao, samesite="lax"
    )
    return resposta


@router.get("/auth/google/callback")
def google_callback(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    code: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    esperado = request.cookies.get(COOKIE_STATE)
    if not code or not state or not esperado or not secrets.compare_digest(state, esperado):
        raise erro(400, "Login inválido. Tente entrar de novo.", "bad_request")
    claims = trocar_codigo(settings, code)
    email = str(claims.get("email", "")).lower()
    dominio = email.rsplit("@", 1)[-1]
    destino = settings.url_publica.rstrip("/")
    valido = claims.get("iss") in EMISSORES_GOOGLE and claims.get("email_verified")
    if not valido or dominio not in settings.dominios:
        resposta = RedirectResponse(f"{destino}/login?erro=dominio", status_code=302)
    else:
        resposta = RedirectResponse(f"{destino}/", status_code=302)
        resposta.set_cookie(
            COOKIE_SESSAO,
            emitir_sessao(settings, email, claims.get("name") or email),
            max_age=settings.sessao_dias * 86400,
            httponly=True,
            secure=settings.producao,
            samesite="lax",
        )
    resposta.delete_cookie(COOKIE_STATE)
    return resposta


@router.get("/me")
def me(usuario: Annotated[Usuario, Depends(usuario_atual)]) -> Usuario:
    return usuario


@router.post("/auth/logout", status_code=204)
def logout() -> Response:
    resposta = Response(status_code=204)
    resposta.delete_cookie(COOKIE_SESSAO)
    return resposta
