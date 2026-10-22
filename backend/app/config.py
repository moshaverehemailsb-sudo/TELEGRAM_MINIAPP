from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"  # development | production
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/konkur"
    telegram_bot_token: str = ""
    telegram_init_data_max_age: int = 86400
    advisor_telegram_ids: str = ""
    allow_dev_auth: bool = False

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def advisor_ids(self) -> frozenset[int]:
        return frozenset(int(x) for x in self.advisor_telegram_ids.split(",") if x.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()