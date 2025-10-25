import os
import sys
import logging
from pathlib import Path
from typing import Optional

from loguru import logger


class InterceptHandler(logging.Handler):
    """Forward stdlib logging records to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        # Preserve the original stdlib logger name in Loguru's record.extra
        logger.bind(stdlib_logger_name=record.name).opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _ensure_log_dir() -> Path:
    log_dir = Path("runtime_logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def configure_logging(level: Optional[str] = None) -> None:
    """Configure Loguru sinks and intercept stdlib logging.

    - Console sink (INFO+)
    - FastAPI file sink (everything except Worker logger)
    - Worker file sink (only Worker logger)
    - Intercepts `logging` to route to Loguru
    """

    _ensure_log_dir()

    # Determine log level
    level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()

    # Reset Loguru default handlers
    logger.remove()

    # Console sink
    logger.add(sys.stdout, level=level, enqueue=True, backtrace=False, diagnose=False,
               format="{time:YYYY-MM-DD HH:mm:ss} [{level}] {name}: {message}")

    # File sinks with rotation and retention
    logger.add("runtime_logs/fastapi.log",
               level=level,  # Use configured level instead of DEBUG
               rotation="5 MB",
               retention=10,
               encoding="utf-8",
               enqueue=True,
               filter=lambda r: r.get("extra", {}).get("stdlib_logger_name") != "Worker",
               format="{time:YYYY-MM-DD HH:mm:ss} [{level}] {name}: {message}")

    logger.add("runtime_logs/worker.log",
               level=level,  # Use configured level instead of DEBUG
               rotation="5 MB",
               retention=10,
               encoding="utf-8",
               enqueue=True,
               filter=lambda r: r.get("extra", {}).get("stdlib_logger_name") == "Worker",
               format="{time:YYYY-MM-DD HH:mm:ss} [{level}] {name}: {message}")

    # Intercept stdlib logging
    logging.basicConfig(handlers=[InterceptHandler()], level=getattr(logging, level, logging.INFO), force=True)

    for noisy in ("uvicorn", "uvicorn.access", "uvicorn.error", "pika"):
        logging.getLogger(noisy).handlers = [InterceptHandler()]
        logging.getLogger(noisy).propagate = False
