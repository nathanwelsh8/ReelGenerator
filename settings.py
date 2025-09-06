from dataclasses import dataclass
import os
from dotenv import load_dotenv

# Load environment from current working directory and also alongside this file
# Do NOT override pre-set environment variables; prefer container/devcontainer env
load_dotenv(override=False)
try:
    import os as _os
    _here = _os.path.dirname(__file__)
    load_dotenv(_os.path.join(_here, '.env'), override=False)
except Exception:
    pass

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

    # Auth / Session settings
    GOOGLE_CLIENT_ID: str = os.getenv('GOOGLE_CLIENT_ID', '816675945395-baf59ejmlutui561htohnn8hq6655o4j.apps.googleusercontent.com')
    SESSION_SECRET: str = os.getenv('GOOGLE_CLIENT_SECRET', 'change-me')
    SESSION_ALG: str = os.getenv('SESSION_ALG', 'HS256')
    SESSION_TTL: int = int(os.getenv('SESSION_TTL', str(8 * 3600)))  # seconds

    # Frontend origins for CORS (comma-separated)
    FRONTEND_ORIGINS: list[str] = tuple(o.strip() for o in os.getenv('FRONTEND_ORIGINS', 'FRONTEND_ORIGINS=http://localhost:5280,http://localhost:5173').split(',') if o.strip())

    # Messaging configuration
    # Default to RabbitMQ service name used in devcontainer compose
    MESSAGING_BACKEND: str = os.getenv('MESSAGING_BACKEND', 'rabbitmq')
    RABBITMQ_URL: str = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/%2F')

def get_settings() -> Settings:
    return Settings()
