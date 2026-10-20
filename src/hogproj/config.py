"""Settings loaded from environment / .env. Every key is optional: the app must run without them."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"
CACHE_DIR = DATA_DIR / "cache"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    usda_mmn_api_key: str = ""  # USDA AMS MyMarketNews (free key)
    nass_api_key: str = ""  # USDA NASS Quick Stats (free key)
    fas_api_key: str = ""  # USDA FAS Open Data via api.data.gov (free key): weekly export sales
    offline: bool = False  # force sample data, never hit the network
    prepared_by: str = ""  # optional name shown in every page footer and the Excel report


def get_settings() -> Settings:
    return Settings()
