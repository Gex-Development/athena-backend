from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from athena.api import auth
from athena.api.app import app
from athena.config import settings as modulo_settings


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("ATHENA_ADMINS", "chefe@gexcorp.com.br")
    monkeypatch.setenv("ATHENA_GOOGLE_CLIENT_ID", "cliente-teste")
    monkeypatch.setenv("ATHENA_GOOGLE_CLIENT_SECRET", "segredo-teste")
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


def login_google(cliente, monkeypatch, email, verificado=True):
    claims = {
        "iss": "https://accounts.google.com",
        "email": email,
        "email_verified": verificado,
        "name": "Maria Souza",
    }
    monkeypatch.setattr(auth, "trocar_codigo", lambda settings, codigo: claims)
    inicio = cliente.get("/v1/auth/google/start", follow_redirects=False)
    state = parse_qs(urlparse(inicio.headers["location"]).query)["state"][0]
    return cliente.get(f"/v1/auth/google/callback?code=abc&state={state}", follow_redirects=False)


def test_start_leva_ao_google_com_callback_e_state(cliente):
    resposta = cliente.get("/v1/auth/google/start", follow_redirects=False)

    destino = urlparse(resposta.headers["location"])
    parametros = parse_qs(destino.query)
    assert resposta.status_code == 302
    assert destino.netloc == "accounts.google.com"
    assert parametros["redirect_uri"] == ["http://localhost:5173/v1/auth/google/callback"]
    assert parametros["state"][0] == resposta.cookies[auth.COOKIE_STATE]


def test_callback_com_state_errado_recusa(cliente):
    cliente.get("/v1/auth/google/start", follow_redirects=False)

    resposta = cliente.get("/v1/auth/google/callback?code=abc&state=outro")

    assert resposta.status_code == 400
    assert resposta.json()["code"] == "bad_request"


def test_login_google_gex_cria_sessao(cliente, monkeypatch):
    resposta = login_google(cliente, monkeypatch, "Maria@GexCorp.com.br")

    assert resposta.headers["location"] == "http://localhost:5173/"
    assert cliente.get("/v1/me").json()["email"] == "maria@gexcorp.com.br"


@pytest.mark.parametrize(
    ("email", "verificado"),
    [("alguem@gmail.com", True), ("maria@gexcorp.com.br", False)],
)
def test_email_fora_da_gex_ou_nao_verificado_e_recusado(cliente, monkeypatch, email, verificado):
    resposta = login_google(cliente, monkeypatch, email, verificado)

    assert resposta.headers["location"] == "http://localhost:5173/login?erro=dominio"
    assert auth.COOKIE_SESSAO not in resposta.cookies
    assert cliente.get("/v1/me").status_code == 401
