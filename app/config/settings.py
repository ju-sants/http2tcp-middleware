from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    WORKERS_INPUT_SOURCE: Dict[str, Dict[str, str]] = {
       "mt02": {"module_path": "app.src.input.mt02.worker", "func_name": "worker"},
    }

settings = Settings()