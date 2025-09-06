from logging.config import dictConfig
import sys

# Define the logging configuration
log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "default",
            "filename": "runtime_logs/fastapi.log",
            "mode": "a",
            "maxBytes": 1024 * 1024 * 5,  # 5 MB
            "backupCount": 10,
        },
        "worker_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "default",
            "filename": "runtime_logs/worker.log",
            "mode": "a",
            "maxBytes": 1024 * 1024 * 5,  # 5 MB
            "backupCount": 10,
        }
    },
    "loggers": {
        "app": {"level": "INFO", "propagate": False},
        "pika": { "level": "WARNING", "propagate": False},
        "Worker": {"handlers": ["worker_file"], "lsevel": "DEBUG", "propagate": False},
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
}

# Apply the configuration
def configure_logging():
    dictConfig(log_config)
