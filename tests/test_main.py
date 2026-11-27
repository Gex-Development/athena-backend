import pytest
from fastapi.testclient import TestClient

from athena.api import auth
from athena.config import settings as modulo_settings
from athena.config.settings import Settings
from athena.main import criar_agent_os


@pytest.fixture
def producao(monkeypatch):
    privada, publica = auth.chaves_locais()
    monkeypatch.setenv("ATHENA_AMBIENTE", "producao")
    monkeypatch.setenv("ATHENA_JWT_CHAVE_PRIVADA", privada.replace("\n", "\\n"))
    monkeypatch.setenv("ATHENA_JWT_CHAVE_PUBLICA", publica.replace("\n", "\\n"))
    monkeypatch.setenv("ATHENA_GOOGLE_CLIENT_ID", "cliente-teste")
    monkeypatch.setenv("ATHENA_GOOGLE_CLIENT_SECRET", "segredo-teste")
    modulo_settings.get_settings.cache_clear()
    yield
    modulo_settings.get_settings.cache_clear()


def test_database_url_ganha_driver_psycopg():
    settings = Settings(database_url="postgresql://u:s@host:5432/db")

    assert settings.database_url == "postgresql+psycopg://u:s@host:5432/db"


def test_producao_sem_chaves_nao_sobe(monkeypatch):
    for nome in modulo_settings.OBRIGATORIAS_PRODUCAO:
        monkeypatch.delenv(f"ATHENA_{nome.upper()}", raising=False)

    with pytest.raises(ValueError, match="ATHENA_GOOGLE_CLIENT_SECRET"):
        Settings(ambiente="producao", database_url="postgresql://u:s@h/db")


def test_chave_com_barra_n_vira_quebra_de_linha(producao):
    assert modulo_settings.get_settings().jwt_chave_publica.startswith(
        "-----BEGIN PUBLIC KEY-----\n"
    )


def test_local_health_responde_pela_rota_da_athena():
    cliente = TestClient(criar_agent_os().get_app())

    resposta = cliente.get("/health")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_producao_protege_agno_e_deixa_v1_com_o_login_da_athena(producao):
    cliente = TestClient(criar_agent_os().get_app())
    sessao = auth.emitir_sessao(modulo_settings.get_settings(), "maria@gexcorp.com.br", "Maria")

    assert cliente.get("/health").status_code == 200
    assert cliente.get("/config").status_code == 401
    assert cliente.get("/agents").status_code == 401
    assert cliente.get("/v1/me").json()["code"] == "unauthorized"
    cliente.cookies.set(auth.COOKIE_SESSAO, sessao)
    assert cliente.get("/v1/me").json()["email"] == "maria@gexcorp.com.br"
