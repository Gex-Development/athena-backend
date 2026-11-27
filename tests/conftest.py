import os

import pytest
from sqlalchemy.engine import make_url

os.environ.setdefault("ATHENA_DATABASE_URL", "postgresql://teste:teste@localhost:5432/teste")
os.environ.setdefault("ATHENA_AMBIENTE", "local")


def pytest_configure() -> None:
    url = os.environ.get("ATHENA_TEST_DATABASE_URL")
    if url and not (make_url(url).database or "").endswith(("_teste", "_test")):
        raise pytest.UsageError(
            "ATHENA_TEST_DATABASE_URL precisa apontar para um banco descartável, "
            "com nome terminado em _teste ou _test. Os testes apagam e recriam tabelas."
        )
