import pytest
from fastapi.testclient import TestClient

from athena.api import auth
from athena.api.app import app
from athena.config import settings as modulo_settings
from athena.config.banco import get_engine


@pytest.fixture
def cliente():
    app.dependency_overrides[get_engine] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("corpo", "esperado"),
    [
        ({"json": {"email": "nao-e-email"}}, "Dados inválidos: email."),
        ({"json": {}}, "Dados inválidos: email."),
        ({}, "Corpo da requisição ausente ou inválido."),
        (
            {"content": '{"email": "a@', "headers": {"Content-Type": "application/json"}},
            "Corpo da requisição ausente ou inválido.",
        ),
    ],
)
def test_422_sai_no_formato_do_contrato(cliente, corpo, esperado):
    resposta = cliente.post("/v1/auth/magic-link", **corpo)

    assert resposta.status_code == 422
    assert resposta.json() == {"error": esperado, "code": "invalid_request"}


def test_422_de_parametro_de_consulta_cita_o_parametro(cliente, monkeypatch):
    monkeypatch.setenv("ATHENA_ADMINS", "chefe@gexcorp.com.br")
    modulo_settings.get_settings.cache_clear()
    sessao = auth.emitir_sessao(modulo_settings.get_settings(), "chefe@gexcorp.com.br", "Chefe")
    cliente.cookies.set(auth.COOKIE_SESSAO, sessao)

    resposta = cliente.get("/v1/agente/eventos?cursor=abc")
    modulo_settings.get_settings.cache_clear()

    assert resposta.status_code == 422
    assert resposta.json() == {"error": "Dados inválidos: cursor.", "code": "invalid_request"}
