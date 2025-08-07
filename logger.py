import logging
from logging import Logger
from settings import get_settings
import os

settings = get_settings()

# Centralized logger service
class LoggerService:
    _loggers = {}
    logs_dir = 'runtime_logs'

    @staticmethod
    def get_logger() -> Logger:
        if settings.LOG_FILENAME in LoggerService._loggers:
            return LoggerService._loggers[settings.LOG_FILENAME]
        if not os.path.exists(LoggerService.logs_dir):
            os.makedirs(LoggerService.logs_dir)
        logger = logging.getLogger(f'{LoggerService.logs_dir}/{settings.LOG_FILENAME}')
        logger.setLevel(settings.LOG_LEVEL.upper())
        if not logger.handlers:
            handler = logging.FileHandler(f'{LoggerService.logs_dir}/{settings.LOG_FILENAME}')
            handler.setLevel(settings.LOG_LEVEL.upper())
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        LoggerService._loggers[settings.LOG_FILENAME] = logger
        return logger
    
def get_logger() -> Logger: 
    return LoggerService.get_logger()