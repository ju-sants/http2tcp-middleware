from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    LOG_LEVEL: str = "INFO"

    # --- INPUT SOURCES CONFIG ---
    WORKERS_INPUT_SOURCE: Dict[str, Dict[str, str]] = {
       "mt02": {"module_path": "app.src.input.mt02.worker", "func_name": "worker"},
    }


    # --- OUTPUT PROTOCOLS CONFIG ---
    # GT06
    GT06_LOCATION_PACKET_PROTOCOL_NUMBER: int = 0xA0 # Can be: 0x22, 0x32, 0xA0. For more informations consult the protocol guide.

settings = Settings()