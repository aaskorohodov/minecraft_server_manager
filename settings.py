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
        BACK_UP_DAYS: Backups, made more days ago, will be automatically deleted

        MIN_MEM: In case no START_BAT provided, will be used to set as minimum RAM for server
        MAX_MEM: In case no START_BAT provided, will be used to set as maximum RAM for server

        DB_PATH: ABS-Path to DB that will be created locally for app's data

        CONNECTIVITY_URLS: URLS to check network with (will be pinged)
        DETECTOR_ON: If down-detector should be launched"""

    model_config = SettingsConfigDict(env_file=(find_my_file(CONFIG_FILE_NAME)),
                                      extra='ignore')

    SERVER_DIR:   str = ''
    WORLD_DIR:    str = ''
    BACKUP_DIR:   str = ''
    START_BAT:    str = ''
    BACKUP_TIME:  str = ''
    BACK_UP_DAYS: int = 5

    MIN_MEM: int | None = None
    MAX_MEM: int | None = None

    DB_PATH: str = "my_shiny.db"

    CONNECTIVITY_URLS: list[str] = [
        "https://www.google.com",
        "https://1.1.1.1",
        "https://example.com",
        "https://www.wikipedia.org"
    ]
    DETECTOR_ON: bool = True


logger.info(f'Found config.env at: {find_my_file(CONFIG_FILE_NAME)}')
settings = Settings(
    _env_file=find_my_file(CONFIG_FILE_NAME),
    _env_file_encoding='utf-8'
)
models_representation: dict[str, any] = settings.model_dump()
logger.info(f'Settings loaded:\n{pformat(models_representation)}')
