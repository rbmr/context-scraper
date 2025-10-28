import logging
from pathlib import Path

from tqdm import tqdm

SRC_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SRC_DIR.parent
ENV_PATH = PROJECT_DIR / ".env"
STATE_FILE = PROJECT_DIR / "state.json"

class TqdmLoggingHandler(logging.StreamHandler):
    def __init__(self):
        super().__init__()

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg, file=self.stream)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"}
    },
    "handlers": {
        "tqdm": {
            "class": TqdmLoggingHandler,
            "formatter": "default",
            "level": logging.INFO,
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": logging.INFO,
        },
    },
    "root": {
        "level": logging.INFO,
        "handlers": ["tqdm"],
    },
}
