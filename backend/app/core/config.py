from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    APP_NAME: str = "Food Spot API"
    APP_ENV: str = "development"

    # Database configuration
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 5432
    DB_NAME: str = "foodspot_db"

    # Security & JWT
    JWT_SECRET_KEY: str = "foodspot_dev_secret_key_change_in_production_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Redis Queue & Cache
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    # External AI Service
    AI_SERVER_EXTRACT_URL: str = "https://excess-dom-upper-ranch.trycloudflare.com/api/v1/extract"
    AI_REQUEST_TIMEOUT: int = 180

    # ArcGIS Geocoding Service
    ARCGIS_GEOCODE_URL: str = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
    ARCGIS_REVERSE_GEOCODE_URL: str = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/reverseGeocode"

    @property
    def database_url(self) -> str:
        return f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()