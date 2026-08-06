import sys

from loguru import logger

from app.core.config import get_settings


def setup_logging() -> None:
    """
    Configure loguru as the sole logging sink.

    - Development: human-readable coloured output to stdout.
    - Production: newline-delimited JSON to stdout (suitable for log aggregators).
    """
    settings = get_settings()

    # Remove the default loguru sink before adding our own.
    logger.remove()

    if settings.is_production:
        logger.add(
            sys.stdout,
            level="INFO",
            serialize=True,  # JSON output
            backtrace=False,
            diagnose=False,
        )
    else:
        logger.add(
            sys.stdout,
            level="DEBUG",
            colorize=True,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
                "<level>{message}</level>"
            ),
            backtrace=True,
            diagnose=True,
        )

    logger.info(
        f"Logging configured | env={settings.app_env} | debug={settings.debug}"
    )
