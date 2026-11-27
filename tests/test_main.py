import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from athena.config import settings as modulo_settings
from athena.config.settings import Settings
from athena.main import criar_agent_os


def chave_publica() -> str:
    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        privada.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


@pytest.fixture
def producao(monkeypatch):
    monkeypatch.setenv("ATHENA_AMBIENTE", "producao")
    monkeypatch.setenv("ATHENA_JWT_CHAVE_PUBLICA", chave_publica())
    modulo_settings.get_settings.cache_clear()
    yield
    modulo_settings.get_settings.cache_clear()


def test_database_url_ganha_driver_psycopg():
    settings = Settings(database_url="postgresql://u:s@host:5432/db")

    assert settings.database_url == "postgresql+psycopg://u:s@host:5432/db"


def test_producao_sem_chave_jwt_nao_sobe(monkeypatch):
    monkeypatch.delenv("ATHENA_JWT_CHAVE_PUBLICA", raising=False)

    with pytest.raises(ValueError, match="ATHENA_JWT_CHAVE_PUBLICA"):
        Settings(ambiente="producao", database_url="postgresql://u:s@h/db")


def test_local_health_responde_pela_rota_da_athena():
    cliente = TestClient(criar_agent_os().get_app())

    resposta = cliente.get("/health")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_producao_protege_rotas_do_agno_e_libera_health(producao):
    cliente = TestClient(criar_agent_os().get_app())

    assert cliente.get("/health").status_code == 200
    assert cliente.get("/config").status_code == 401
    assert cliente.get("/agents").status_code == 401
