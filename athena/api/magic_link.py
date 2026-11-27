import hashlib
import logging
import secrets
import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import Engine, text

from athena.api.auth import COOKIE_SESSAO, emitir_sessao, erro
from athena.config.banco import get_engine
from athena.config.settings import Settings, get_settings

router = APIRouter(prefix="/v1/auth/magic-link")
logger = logging.getLogger("athena.magic_link")


class PedidoLink(BaseModel):
    email: str = Field(pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$", max_length=254)


def hash_do_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def enviar_email(settings: Settings, para: str, link: str) -> None:
    mensagem = EmailMessage()
    mensagem["Subject"] = "Seu link de acesso à Athena"
    mensagem["From"] = f"Athena · GEX <{settings.smtp_usuario}>"
    mensagem["To"] = para
    minutos = settings.magic_link_minutos
    mensagem.set_content(
        f"Olá,\n\nUse o link abaixo para entrar na Athena. Ele vale por {minutos} minutos "
        f"e funciona uma vez só.\n\n{link}\n\nSe você não pediu este acesso, ignore este e-mail.\n"
    )
    mensagem.add_alternative(
        f"<p>Olá,</p><p>Use o botão abaixo para entrar na Athena. O link vale por {minutos} "
        f'minutos e funciona uma vez só.</p><p><a href="{link}" style="background:#1e6fd9;'
        "color:#ffffff;padding:12px 20px;border-radius:10px;text-decoration:none;"
        'font-family:Arial,sans-serif;display:inline-block">Entrar na Athena</a></p>'
        "<p>Se você não pediu este acesso, ignore este e-mail.</p>",
        subtype="html",
    )
    try:
        with abrir_smtp(settings) as s:
            if not isinstance(s, smtplib.SMTP_SSL):
                s.starttls(context=ssl.create_default_context())
            s.login(settings.smtp_usuario or "", settings.smtp_senha or "")
            s.send_message(mensagem)
    except (OSError, smtplib.SMTPException) as falha:
        logger.error(
            "Falha ao enviar o link de acesso por %s:%s (%s)",
            settings.smtp_host,
            settings.smtp_porta,
            type(falha).__name__,
        )
        return
    logger.info("Link de acesso enviado para o domínio %s", para.rsplit("@", 1)[-1])


def abrir_smtp(settings: Settings) -> smtplib.SMTP:
    if settings.smtp_porta == 465:
        return smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_porta,
            context=ssl.create_default_context(),
            timeout=20,
        )
    return smtplib.SMTP(settings.smtp_host, settings.smtp_porta, timeout=20)


@router.post("", status_code=204)
def pedir_link(
    pedido: PedidoLink,
    tarefas: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> Response:
    email = pedido.email.lower()
    agora = datetime.now(UTC)
    with engine.begin() as conexao:
        recentes = conexao.execute(
            text(
                "SELECT count(*) FROM athena.links_magicos WHERE email = :e AND criado_em > :desde"
            ),
            {"e": email, "desde": agora - timedelta(minutes=15)},
        ).scalar_one()
        if recentes >= settings.magic_link_limite:
            raise erro(429, "Muitas tentativas. Espere alguns minutos.", "rate_limited")
        token = secrets.token_urlsafe(32)
        conexao.execute(
            text(
                "INSERT INTO athena.links_magicos (token_hash, email, expira_em) "
                "VALUES (:h, :e, :expira)"
            ),
            {
                "h": hash_do_token(token),
                "e": email,
                "expira": agora + timedelta(minutes=settings.magic_link_minutos),
            },
        )
    if email.rsplit("@", 1)[-1] in settings.dominios:
        link = f"{settings.url_publica.rstrip('/')}/v1/auth/magic-link/entrar?token={token}"
        tarefas.add_task(enviar_email, settings, email, link)
    return Response(status_code=204)


@router.get("/entrar")
def entrar(
    token: str,
    settings: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> RedirectResponse:
    destino = settings.url_publica.rstrip("/")
    with engine.begin() as conexao:
        email = conexao.execute(
            text(
                "UPDATE athena.links_magicos SET usado_em = now() "
                "WHERE token_hash = :h AND usado_em IS NULL AND expira_em > now() RETURNING email"
            ),
            {"h": hash_do_token(token)},
        ).scalar_one_or_none()
    if not email or email.rsplit("@", 1)[-1] not in settings.dominios:
        return RedirectResponse(f"{destino}/login?erro=link", status_code=302)
    resposta = RedirectResponse(f"{destino}/", status_code=302)
    resposta.set_cookie(
        COOKIE_SESSAO,
        emitir_sessao(settings, email, email.split("@")[0].replace(".", " ").title()),
        max_age=settings.sessao_dias * 86400,
        httponly=True,
        secure=settings.producao,
        samesite="lax",
    )
    return resposta
