import sys
from loguru import logger

def setup_logger() -> None:
    """Setup loguru logger with stdout and a rotating file handler."""
    logger.remove()  # Remove default logger
    
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    # Log to stdout
    logger.add(
        sys.stdout,
        format=log_format,
        level="INFO",
        enqueue=True,
    )
    
    # Log to rotating file at /app/temp/bot.log
    logger.add(
        "/app/temp/bot.log",
        format=log_format,
        level="INFO",
        rotation="10 MB",
        retention="10 days",
        enqueue=True,
    )
