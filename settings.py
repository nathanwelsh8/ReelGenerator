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

    # Internal API (worker <-> API communication)
    INTERNAL_API_BASE_URL: str = os.getenv('INTERNAL_API_BASE_URL', 'http://localhost:8000/internal')
    INTERNAL_API_TIMEOUT: float = float(os.getenv('INTERNAL_API_TIMEOUT', '15'))

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
    RABBITMQ_CONNECT_MAX_ATTEMPTS: int = int(os.getenv('RABBITMQ_CONNECT_MAX_ATTEMPTS', '5'))  # 0 = infinite
    RABBITMQ_CONNECT_BASE_DELAY: float = float(os.getenv('RABBITMQ_CONNECT_BASE_DELAY', '1.5'))
    RABBITMQ_CONNECT_MAX_DELAY: float = float(os.getenv('RABBITMQ_CONNECT_MAX_DELAY', '30'))
    # Heartbeat and connection timeout settings
    RABBITMQ_HEARTBEAT: int = int(os.getenv('RABBITMQ_HEARTBEAT', '600'))  # Heartbeat interval in seconds (default 600 = 10 min)
    RABBITMQ_BLOCKED_CONNECTION_TIMEOUT: int = int(os.getenv('RABBITMQ_BLOCKED_CONNECTION_TIMEOUT', '300'))  # Timeout for blocked connections (default 300 = 5 min)
    RABBITMQ_CONNECTION_ATTEMPTS: int = int(os.getenv('RABBITMQ_CONNECTION_ATTEMPTS', '3'))  # Number of connection attempts per retry
    RABBITMQ_RETRY_DELAY: int = int(os.getenv('RABBITMQ_RETRY_DELAY', '2'))  # Delay between connection attempts in seconds

    # Higgs model configuration (Boson Higgs Audio v2)
    # Legacy HIGGS_MODEL_ID/REVISION retained for backward compat but unused in Boson flow
    HIGGS_MODEL_ID: str = os.getenv('HIGGS_MODEL_ID', 'unused')
    HIGGS_MODEL_REVISION: str = os.getenv('HIGGS_MODEL_REVISION', 'unused')
    HIGGS_DEVICE: str = os.getenv('HIGGS_DEVICE', 'cuda:0')
    HIGGS_USE_HALF: bool = os.getenv('HIGGS_USE_HALF', 'true').lower() in ('1','true','yes','on')
    HIGGS_ENABLE_GPU_METRICS: bool = os.getenv('HIGGS_ENABLE_GPU_METRICS', 'true').lower() in ('1','true','yes','on')
    VOICE_MODE: str = os.getenv('VOICE_MODE', 'placeholder')  # placeholder|clone
    VOICE_REF_DIR: str = os.getenv('VOICE_REF_DIR', 'voice_refs')
    VOICE_EMBED_CACHE: str = os.getenv('VOICE_EMBED_CACHE', 'cache/embeddings')

    # Provider selection for clone mode: only 'boson' (Higgs Audio v2) supported
    HIGGS_MODEL_PROVIDER: str = os.getenv('HIGGS_MODEL_PROVIDER', 'boson')
    # Boson (Higgs Audio v2) defaults per README
    HIGGS_BOSON_MODEL: str = os.getenv('HIGGS_BOSON_MODEL', 'bosonai/higgs-audio-v2-generation-3B-base')
    HIGGS_BOSON_TOKENIZER: str = os.getenv('HIGGS_BOSON_TOKENIZER', 'bosonai/higgs-audio-v2-tokenizer')

def get_settings() -> Settings:
    return Settings()
