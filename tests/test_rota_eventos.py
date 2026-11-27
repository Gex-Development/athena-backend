import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from athena.api import auth
from athena.api.app import app
from athena.config import settings as modulo_settings
from athena.config.banco import get_engine
from athena.eventos.registro import TipoEvento, registrar

URL_TESTE = os.environ.get("ATHENA_TEST_DATABASE_URL")


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("ATHENA_ADMINS", "chefe@gexcorp.com.br")
    modulo_settings.get_settings.cache_clear()
    yield TestClient(app)
    modulo_settings.get_settings.cache_clear()
    app.dependency_overrides.clear()


def entrar(cliente, email):
    sessao = auth.emitir_sessao(modulo_settings.get_settings(), email, "Pessoa Teste")
    cliente.cookies.set(auth.COOKIE_SESSAO, sessao)


def test_eventos_sem_login_401_e_analista_403(cliente):
    app.dependency_overrides[get_engine] = lambda: None
    assert cliente.get("/v1/agente/eventos").status_code == 401
    entrar(cliente, "maria@gexcorp.com.br")

    resposta = cliente.get("/v1/agente/eventos")

    assert resposta.status_code == 403
    assert resposta.json() == {
        "error": "Só administradores acessam esta área.",
        "code": "forbidden",
    }


@pytest.mark.skipif(not URL_TESTE, reason="sem Postgres de teste")
def test_admin_ve_a_trilha_da_conversa(cliente):
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", URL_TESTE)
    command.upgrade(config, "head")
    motor = create_engine(URL_TESTE)
    with motor.begin() as conexao:
        conexao.execute(text("TRUNCATE athena.eventos"))
    registrar(motor, 77, TipoEvento.RECEBIDA)
    registrar(motor, 77, TipoEvento.CLASSIFICADA, versao_catalogo="v3.4")
    registrar(motor, 99, TipoEvento.RECEBIDA)
    app.dependency_overrides[get_engine] = lambda: motor
    entrar(cliente, "chefe@gexcorp.com.br")

    resposta = cliente.get("/v1/agente/eventos?conversa=77")

    corpo = resposta.json()
    assert resposta.status_code == 200
    assert [i["tipo"] for i in corpo["itens"]] == ["classificada", "recebida"]
    assert corpo["itens"][0]["conversaId"] == 77
    assert corpo["proximoCursor"] is None
    assert cliente.get("/v1/agente/eventos?cursor=abc").status_code == 422
    motor.dispose()
