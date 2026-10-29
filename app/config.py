from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    admin_api_key: str = Field(min_length=16)  # no default: fail closed

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()