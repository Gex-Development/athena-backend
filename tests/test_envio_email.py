import logging
import smtplib

import pytest

from athena.api import magic_link
from athena.config.settings import Settings


class SmtpFalso:
    def __init__(self, host, porta, **_):
        self.passos = [("conectar", host, porta)]
        SmtpFalso.ultimo = self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.passos.append(("fechar",))

    def starttls(self, **_):
        self.passos.append(("starttls",))

    def login(self, usuario, _senha):
        self.passos.append(("login", usuario))

    def send_message(self, mensagem):
        self.passos.append(("enviar", mensagem["To"]))


class SmtpSslFalso(SmtpFalso, smtplib.SMTP_SSL):
    pass


@pytest.fixture
def smtp(monkeypatch):
    monkeypatch.setattr(magic_link.smtplib, "SMTP", SmtpFalso)
    monkeypatch.setattr(magic_link.smtplib, "SMTP_SSL", SmtpSslFalso)


def configuracao(porta: int) -> Settings:
    return Settings(smtp_porta=porta, smtp_usuario="athena@gexcorp.com.br", smtp_senha="x")


def test_porta_587_usa_starttls_antes_do_login(smtp, caplog):
    caplog.set_level(logging.INFO, logger="athena")

    magic_link.enviar_email(configuracao(587), "ana@gexcorp.com.br", "https://link")

    assert [p[0] for p in SmtpFalso.ultimo.passos] == [
        "conectar",
        "starttls",
        "login",
        "enviar",
        "fechar",
    ]
    assert "domínio gexcorp.com.br" in caplog.text
    assert "ana@" not in caplog.text


def test_porta_465_usa_ssl_direto(smtp):
    magic_link.enviar_email(configuracao(465), "ana@gexcorp.com.br", "https://link")

    assert isinstance(SmtpFalso.ultimo, SmtpSslFalso)
    assert "starttls" not in [p[0] for p in SmtpFalso.ultimo.passos]


def test_falha_no_envio_vira_log_sem_derrubar(monkeypatch, caplog):
    def recusar(*_, **__):
        raise TimeoutError("timed out")

    monkeypatch.setattr(magic_link.smtplib, "SMTP_SSL", recusar)

    magic_link.enviar_email(configuracao(465), "ana@gexcorp.com.br", "https://link")

    assert "Falha ao enviar o link de acesso por mail.gexcorp.com.br:465" in caplog.text
    assert "ana@" not in caplog.text
