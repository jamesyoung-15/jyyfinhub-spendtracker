"""Logging setup, called once from create_app before anything else runs."""

import logging
from logging.config import dictConfig

from jyyfinhub_spendtracker.core.config import Settings

FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging(settings: Settings) -> None:
    """Send everything to stdout at the configured level."""
    dictConfig(
        {
            "version": 1,
            # uvicorn installs its own handlers before this runs; True (the default) would
            # silently mute them and you would lose startup and access logs
            "disable_existing_loggers": False,
            "formatters": {"default": {"format": FORMAT}},
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "default",
                }
            },
            "root": {"handlers": ["stdout"], "level": settings.app_log_level},
            "loggers": {
                # own code
                "jyyfinhub_spendtracker": {"level": settings.app_log_level},
                # echoes every statement, only wanted while debugging
                "sqlalchemy.engine": {
                    "level": "INFO" if settings.app_debug else "WARNING"
                },
                # naming a logger here REPLACES its config, so uvicorn's own handlers are
                # dropped and must be replaced with ours. propagate stays False so records
                # are not also handled by root, which would print every line twice
                "uvicorn": {
                    "handlers": ["stdout"],
                    "level": settings.app_log_level,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["stdout"],
                    "level": settings.app_log_level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["stdout"],
                    "level": settings.app_log_level,
                    "propagate": False,
                },
            },
        }
    )
    logging.getLogger(__name__).debug("logging configured")
