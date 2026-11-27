import pytest
from fastapi.testclient import TestClient

from athena.api import auth
from athena.api.app import app
from athena.config import settings as modulo_settings


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("ATHENA_ADMINS", "chefe@gexcorp.com.br")
    modulo_settings.get_settings.cache_clear()
    yield TestClient(app)
    modulo_settings.get_settings.cache_clear()


def entrar(cliente, email, nome="Maria Souza"):
    sessao = auth.emitir_sessao(modulo_settings.get_settings(), email, nome)
    cliente.cookies.set(auth.COOKIE_SESSAO, sessao)


def test_me_sem_sessao_devolve_401_no_formato_do_contrato(cliente):
    resposta = cliente.get("/v1/me")

    assert resposta.status_code == 401
    assert resposta.json() == {"error": "Faça login para continuar.", "code": "unauthorized"}


def test_me_com_sessao_invalida_devolve_401(cliente):
    cliente.cookies.set(auth.COOKIE_SESSAO, "token-falso")

    assert cliente.get("/v1/me").json()["code"] == "unauthorized"


def test_me_devolve_analista_no_schema_do_contrato(cliente):
    entrar(cliente, "maria@gexcorp.com.br")

    assert cliente.get("/v1/me").json() == {
        "id": "maria@gexcorp.com.br",
        "nome": "Maria Souza",
        "email": "maria@gexcorp.com.br",
        "papel": "analista",
        "nomeAssinatura": "Maria",
    }


def test_email_de_admins_ganha_papel_admin(cliente):
    entrar(cliente, "chefe@gexcorp.com.br")

    assert cliente.get("/v1/me").json()["papel"] == "admin"


def test_logout_encerra_a_sessao(cliente):
    entrar(cliente, "maria@gexcorp.com.br")

    resposta = cliente.post("/v1/auth/logout")

    assert resposta.status_code == 204
    assert auth.COOKIE_SESSAO in resposta.headers["set-cookie"]
    assert 'athena_sessao=""' in resposta.headers["set-cookie"]
