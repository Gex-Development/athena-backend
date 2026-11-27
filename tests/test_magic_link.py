import os
from urllib.parse import parse_qs, urlparse

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from athena.api import auth, magic_link
from athena.api.app import app
from athena.config import settings as modulo_settings
from athena.config.banco import get_engine

URL_TESTE = os.environ.get("ATHENA_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL_TESTE, reason="sem Postgres de teste")


@pytest.fixture
def enviados(monkeypatch):
    caixa: list[tuple[str, str]] = []
    monkeypatch.setattr(
        magic_link, "enviar_email", lambda settings, para, link: caixa.append((para, link))
    )
    return caixa


@pytest.fixture
def cliente():
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", URL_TESTE)
    command.upgrade(config, "head")
    motor = create_engine(URL_TESTE)
    with motor.begin() as conexao:
        conexao.execute(text("TRUNCATE athena.links_magicos"))
    modulo_settings.get_settings.cache_clear()
    app.dependency_overrides[get_engine] = lambda: motor
    yield TestClient(app)
    app.dependency_overrides.clear()
    motor.dispose()


def token_do(link: str) -> str:
    return parse_qs(urlparse(link).query)["token"][0]


def test_link_entra_uma_vez_so_e_cria_sessao(cliente, enviados):
    resposta = cliente.post("/v1/auth/magic-link", json={"email": "Maria@GexCorp.com.br"})

    assert resposta.status_code == 204
    para, link = enviados[0]
    assert para == "maria@gexcorp.com.br"
    assert link.startswith("http://localhost:5173/v1/auth/magic-link/entrar?token=")
    entrada = cliente.get(
        f"/v1/auth/magic-link/entrar?token={token_do(link)}", follow_redirects=False
    )
    assert entrada.headers["location"] == "http://localhost:5173/"
    assert auth.COOKIE_SESSAO in entrada.cookies
    assert cliente.get("/v1/me").json()["email"] == "maria@gexcorp.com.br"
    de_novo = cliente.get(
        f"/v1/auth/magic-link/entrar?token={token_do(link)}", follow_redirects=False
    )
    assert de_novo.headers["location"] == "http://localhost:5173/login?erro=link"


def test_email_de_fora_responde_igual_e_nao_recebe(cliente, enviados):
    resposta = cliente.post("/v1/auth/magic-link", json={"email": "alguem@gmail.com"})

    assert resposta.status_code == 204
    assert enviados == []


def test_link_vencido_e_token_falso_voltam_para_o_login(cliente, enviados):
    cliente.post("/v1/auth/magic-link", json={"email": "joao@gexcorp.com.br"})
    motor = app.dependency_overrides[get_engine]()
    with motor.begin() as conexao:
        conexao.execute(
            text("UPDATE athena.links_magicos SET expira_em = now() - interval '1 minute'")
        )

    vencido = cliente.get(
        f"/v1/auth/magic-link/entrar?token={token_do(enviados[0][1])}", follow_redirects=False
    )
    falso = cliente.get("/v1/auth/magic-link/entrar?token=inventado", follow_redirects=False)

    assert vencido.headers["location"].endswith("/login?erro=link")
    assert falso.headers["location"].endswith("/login?erro=link")


def test_limite_de_tentativas_e_email_invalido(cliente, enviados):
    for _ in range(3):
        assert (
            cliente.post("/v1/auth/magic-link", json={"email": "ana@gexcorp.com.br"}).status_code
            == 204
        )

    quarta = cliente.post("/v1/auth/magic-link", json={"email": "ana@gexcorp.com.br"})

    assert quarta.status_code == 429
    assert quarta.json()["code"] == "rate_limited"
    assert cliente.post("/v1/auth/magic-link", json={"email": "nao-e-email"}).status_code == 422
    with create_engine(URL_TESTE).connect() as conexao:
        guardado = conexao.execute(
            text("SELECT token_hash FROM athena.links_magicos LIMIT 1")
        ).scalar_one()
    assert len(guardado) == 64
