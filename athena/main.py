import logging

from agno.db.postgres import PostgresDb
from agno.os import AgentOS
from agno.os.authz import Authorization

from athena.api.app import app as base_app
from athena.config.settings import ROTAS_PUBLICAS_AGENTOS, get_settings


def configurar_logs(nivel: str) -> None:
    raiz = logging.getLogger("athena")
    nome = nivel.strip().upper()
    raiz.setLevel(nome if nome in logging.getLevelNamesMapping() else logging.INFO)
    if not raiz.handlers:
        manipulador = logging.StreamHandler()
        manipulador.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
        raiz.addHandler(manipulador)


def criar_agent_os() -> AgentOS:
    settings = get_settings()
    configurar_logs(settings.log_level)
    autorizacao: Authorization | bool = False
    if settings.producao:
        autorizacao = Authorization(
            verification_keys=[settings.jwt_chave_publica],
            algorithm="RS256",
            excluded_route_paths=ROTAS_PUBLICAS_AGENTOS,
        )
    return AgentOS(
        id="athena",
        name="Athena",
        db=PostgresDb(id="athena-db", db_url=settings.database_url),
        base_app=base_app,
        on_route_conflict="preserve_base_app",
        authorization=autorizacao,
    )


agent_os = criar_agent_os()
app = agent_os.get_app()
