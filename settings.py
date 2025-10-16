import os
from pprint import pformat

from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict

from utils.other import find_my_file


CONFIG_FILE_PATH: str = 'config.env'


class Settings(BaseSettings):
    """"""

    model_config = SettingsConfigDict(env_file=(find_my_file(CONFIG_FILE_PATH)),
                                      extra='ignore')

    SERVER_DIR:   str = ''
    WORLD_DIR:    str = ''
    BACKUP_DIR:   str = ''
    START_BAT:    str = ''
    STOP_TIME:    str = ''
    BACK_UP_DAYS: int = 5


# Make sure the logs folder exists
os.makedirs("logs", exist_ok=True)

# Remove the default stderr logger
logger.remove()

# Add rotating file handler
logger.add(
    "logs/server_manager_{time:YYYY-MM-DD}.log",
    rotation="00:00",       # create new log file every day at midnight
    retention="100 days",    # keep logs for 10 days, delete older automatically
    compression="zip",      # compress old logs
    enqueue=True,           # thread-safe
    encoding="utf-8"
)

# Optional: also log to console
logger.add(lambda msg: print(msg, end=""), colorize=True)


print(find_my_file(CONFIG_FILE_PATH))
settings = Settings(
    _env_file=find_my_file(CONFIG_FILE_PATH),
    _env_file_encoding='utf-8'
)
models_representation: dict[str, any] = settings.model_dump()
logger.info(f'Настройки загружены:\n{pformat(models_representation)}')
