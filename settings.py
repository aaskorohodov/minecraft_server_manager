import os

from loguru import logger
from pprint import pformat
from pydantic_settings import BaseSettings, SettingsConfigDict

from utils.other import find_my_file


CONFIG_FILE_NAME: str = 'config.env'


class Settings(BaseSettings):
    """Apps main settings

    Attributes:
        SERVER_DIR: ABS-path to the folder with your Minecraft Server
        WORLD_DIR: ABS-path to the folder with your Minecraft World (must start with 'world...')
        BACKUP_DIR: ABS-path to the folder where world-backups will be saved
        START_BAT: Path to start.bat file that launches Minecraft Server
        BACKUP_TIME: Time for backing up world as string  in format HH:mm
        BACK_UP_DAYS: Backups, made more days ago, will be automatically deleted"""

    model_config = SettingsConfigDict(env_file=(find_my_file(CONFIG_FILE_NAME)),
                                      extra='ignore')

    SERVER_DIR:   str = ''
    WORLD_DIR:    str = ''
    BACKUP_DIR:   str = ''
    START_BAT:    str = ''
    BACKUP_TIME:  str = ''
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


logger.info(f'Found config.env at: {find_my_file(CONFIG_FILE_NAME)}')
settings = Settings(
    _env_file=find_my_file(CONFIG_FILE_NAME),
    _env_file_encoding='utf-8'
)
models_representation: dict[str, any] = settings.model_dump()
logger.info(f'Настройки загружены:\n{pformat(models_representation)}')
