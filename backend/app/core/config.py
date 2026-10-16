import yaml
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# Anchor config.yaml to the repository layout rather than the process CWD.
# A bare open("../config.yaml") resolved against whatever directory the
# process was launched from, so starting uvicorn anywhere other than
# backend/ silently fell through to env vars with an empty database_url.
CONFIG_PATH = Path(__file__).resolve().parents[3] / "config.yaml"

class Settings(BaseSettings):
    database_url: str = ""
    redis_url: str = ""
    jwt_secret_key: str = ""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    jwt_access_token_expire_minutes: int = 60
    environment: str = "development"

    enforce_qr_validation: bool = False
    enforce_proximity_check: bool = False
    skip_password_check: bool = False

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    
    # Load from config.yaml if present to override or supplement
    try:
        with open(CONFIG_PATH, "r") as f:
            yaml_data = yaml.safe_load(f)
            if yaml_data:
                db_config = yaml_data.get("database", {})
                if db_config:
                    settings.database_url = f"postgresql://{db_config.get('user')}:{db_config.get('password')}@{db_config.get('host')}:{db_config.get('port')}/{db_config.get('name')}"
                
                redis_config = yaml_data.get("redis", {})
                if redis_config:
                    settings.redis_url = f"redis://{redis_config.get('host')}:{redis_config.get('port')}/{redis_config.get('db')}"
                
                app_config = yaml_data.get("app", {})
                if app_config:
                    settings.jwt_secret_key = app_config.get("jwt_secret_key", settings.jwt_secret_key)
                    settings.jwt_secret = app_config.get("jwt_secret", settings.jwt_secret_key)
                    settings.jwt_algorithm = app_config.get("jwt_algorithm", settings.jwt_algorithm)
                    settings.jwt_expiration_hours = app_config.get("jwt_expiration_hours", settings.jwt_expiration_hours)
                    settings.jwt_access_token_expire_minutes = app_config.get("jwt_access_token_expire_minutes", settings.jwt_access_token_expire_minutes)
                    settings.environment = app_config.get("environment", settings.environment)
                    settings.enforce_qr_validation = app_config.get("enforce_qr_validation", settings.enforce_qr_validation)
                    settings.enforce_proximity_check = app_config.get("enforce_proximity_check", settings.enforce_proximity_check)
                    settings.skip_password_check = app_config.get("skip_password_check", settings.skip_password_check)
    except FileNotFoundError:
        pass # Fallback to env vars if yaml not found

    return settings

settings = get_settings()
