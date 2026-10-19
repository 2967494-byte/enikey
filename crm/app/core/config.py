import os

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./brain.db")
    APP_PREFIX: str = os.getenv("APP_PREFIX", "/crm").rstrip("/")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "brain_super_secret_key_change_in_prod")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

settings = Settings()
