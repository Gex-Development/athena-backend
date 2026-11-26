from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATHENA_", env_file=".env", extra="ignore")

    ambiente: str = "local"
    log_level: str = "INFO"
