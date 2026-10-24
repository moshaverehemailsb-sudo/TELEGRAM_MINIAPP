from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_ids(raw: str) -> frozenset[int]:
    return frozenset(int(x) for x in raw.split(",") if x.strip())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"  # development | production
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/konkur"
    telegram_bot_token: str = ""
    telegram_init_data_max_age: int = 86400
    admin_telegram_ids: str = ""  # comma-separated; only these users are admins
    allow_dev_auth: bool = False
    invite_code_ttl_days: int = 7

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def admin_ids(self) -> frozenset[int]:
        return _parse_ids(self.admin_telegram_ids)


@lru_cache
def get_settings() -> Settings:
    return Settings()