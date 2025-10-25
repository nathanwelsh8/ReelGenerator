import os
from pathlib import Path
from typing import Optional

from loguru import logger as _logger
from settings import get_settings

settings = get_settings()


class LoggerService:
    """Provide a shared Loguru logger and ensure a master.log sink exists for scripts."""

    _configured: bool = False

    @staticmethod
    def _ensure_master_sink(filename: Optional[str] = None) -> None:
        log_dir = Path("runtime_logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        fname = filename or settings.LOG_FILENAME or "master.log"
        path = log_dir / fname
        # Add a sink for master log (rotation 5 MB, keep 10 files)
        _logger.add(str(path), level=settings.LOG_LEVEL.upper(), rotation="5 MB", retention=10, encoding="utf-8", enqueue=True)

    @staticmethod
    def get_logger():
        if not LoggerService._configured:
            # Minimal default sink for standalone scripts that don't call configure_logging()
            try:
                LoggerService._ensure_master_sink()
            except Exception:
                pass
            LoggerService._configured = True
        return _logger


def get_logger():
    return LoggerService.get_logger()

# Public module-level logger alias for convenience imports
# Enables: from services.logger import logger
logger = LoggerService.get_logger()
