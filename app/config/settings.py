from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    LOG_LEVEL: str = "INFO"

    # --- REDIS CONFIG ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB_MAIN: int = 15

    # --- INPUT SOURCES CONFIG ---
    WORKERS_INPUT_SOURCE: Dict[str, Dict[str, str]] = {
       "mt02": {"module_path": "app.src.input.mt02.worker", "func_name": "worker"},
    }

    # MT02 Input Source Config
    MT02_API_BASE_URL: str = "..."
    MT02_API_KEY: str = "..."

    # --- OUTPUT PROTOCOLS CONFIG ---
    # GT06
    GT06_LOCATION_PACKET_PROTOCOL_NUMBER: int = 0xA0 # Can be: 0x22, 0x32, 0xA0. For more informations consult the protocol guide.

settings = Settings()