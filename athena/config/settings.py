from functools import cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROTAS_PUBLICAS_AGENTOS = ["/", "/health", "/info", "/v1/*"]
OBRIGATORIAS_PRODUCAO = (
    "jwt_chave_publica",
    "jwt_chave_privada",
    "google_client_id",
    "google_client_secret",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATHENA_", env_file=".env", extra="ignore")

    ambiente: str = "local"
    log_level: str = "INFO"
    database_url: str
    jwt_chave_publica: str | None = None
    jwt_chave_privada: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    url_publica: str = "http://localhost:5173"
    dominios_permitidos: str = "gexcorp.com.br,institutoexperience.com.br"
    admins: str = ""
    sessao_dias: int = 30

    @field_validator("jwt_chave_publica", "jwt_chave_privada")
    @classmethod
    def restaurar_quebras_de_linha(cls, valor: str | None) -> str | None:
        return valor.replace("\\n", "\n") if valor else valor

    @property
    def dominios(self) -> set[str]:
        return {d.strip().lower() for d in self.dominios_permitidos.split(",") if d.strip()}

    @property
    def emails_admin(self) -> set[str]:
        return {e.strip().lower() for e in self.admins.split(",") if e.strip()}

    @field_validator("database_url")
    @classmethod
    def usar_driver_psycopg(cls, valor: str) -> str:
        for prefixo in ("postgres://", "postgresql://"):
            if valor.startswith(prefixo):
                return "postgresql+psycopg://" + valor.removeprefix(prefixo)
        return valor

    @property
    def producao(self) -> bool:
        return self.ambiente != "local"

    @model_validator(mode="after")
    def exigir_chave_fora_do_local(self) -> Settings:
        if self.producao:
            faltando = [
                f"ATHENA_{nome.upper()}"
                for nome in OBRIGATORIAS_PRODUCAO
                if not getattr(self, nome)
            ]
            if faltando:
                raise ValueError(f"Obrigatórias fora do ambiente local: {', '.join(faltando)}")
        return self


@cache
def get_settings() -> Settings:
    return Settings()
