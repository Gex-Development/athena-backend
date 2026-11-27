import os

import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

os.environ.setdefault("ATHENA_DATABASE_URL", "postgresql://teste:teste@localhost:5432/teste")
os.environ.setdefault("ATHENA_AMBIENTE", "local")
if url_do_env := dotenv_values(".env").get("ATHENA_TEST_DATABASE_URL"):
    os.environ.setdefault("ATHENA_TEST_DATABASE_URL", url_do_env)


def banco_descartavel(url: str) -> bool:
    return (make_url(url).database or "").endswith(("_teste", "_test"))


def pytest_configure() -> None:
    url = os.environ.get("ATHENA_TEST_DATABASE_URL")
    if url and not banco_descartavel(url):
        raise pytest.UsageError(
            "ATHENA_TEST_DATABASE_URL precisa apontar para um banco descartável, "
            "com nome terminado em _teste ou _test. Os testes apagam e recriam tabelas."
        )
