from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    # Example fields, add or modify as needed
    TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN', '')
    DB_PATH: str = os.getenv('DB_PATH', 'stewie_database.db')
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILENAME: str = 'master.log'

    # Proxy settings from .env
    PROXY_USERNAME: str = os.getenv('PROXY_USERNAME', '')
    PROXY_PASSWORD: str = os.getenv('PROXY_PASSWORD', '')
    PROXY_REGION: str = os.getenv('PROXY_REGION', '')
    PROXY_HOST: str = os.getenv('PROXY_HOST', '')
    PROXY_PORT: str = os.getenv('PROXY_PORT', '')

    INSTAGRAM_USERNAME: str = os.getenv('INSTAGRAM_USERNAME', '')
    INSTAGRAM_PASSWORD: str = os.getenv('INSTAGRAM_PASSWORD', '')

    GOOGLE_API_KEY: str = os.getenv('GOOGLE_API_KEY', '')
    GOOGLE_SEARCH_ENGINE_CX: str = os.getenv('GOOGLE_SEARCH_ENGINE_CX', '')

    GEMINI_API_KEY: str = os.getenv('GEMINI_API_KEY', '')

def get_settings() -> Settings:
    return Settings()
