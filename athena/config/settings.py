from functools import cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROTAS_PUBLICAS_AGENTOS = ["/", "/health", "/info", "/v1/*"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATHENA_", env_file=".env", extra="ignore")

    ambiente: str = "local"
    log_level: str = "INFO"
    database_url: str
    jwt_chave_publica: str | None = None

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
        if self.producao and not self.jwt_chave_publica:
            raise ValueError("ATHENA_JWT_CHAVE_PUBLICA é obrigatória fora do ambiente local")
        return self


@cache
def get_settings() -> Settings:
    return Settings()
