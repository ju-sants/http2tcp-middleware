import sys
from loguru import logger
from app.config.settings import settings

# Removes the old handler to avoid duplicates
logger.remove()

# Adds a new "sink" to stdout with a more rich and colorful format
logger.add(
    sys.stdout,
    level=settings.LOG_LEVEL.upper(),
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
           "<level>{level}</level> | "
           "<yellow>[{extra[log_label]}]</yellow> |"
           "<cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>",
    colorize=True,
    backtrace=True,
    diagnose=True
)

def get_logger(name: str):
    """
    returns a instance of logger Loguru with the module name associated.
    """
    return logger.bind(name=name)