from loguru import logger
from pprint import pformat

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from utils.other import find_my_file


CONFIG_FILE_NAME: str = 'config.env'


class NotificationsSettings(BaseSettings):
    """Settings for notifications

    Attributes:
        ACTIVATED: If notificator should be activated, direct flag
        START_MESSAGE_DELAY: Delay in seconds to show login notification, after Player logged in"""

    model_config = SettingsConfigDict(
        env_prefix='NOTIFICATION_',
        env_file=(find_my_file(CONFIG_FILE_NAME)),
        extra='ignore'
    )

    ACTIVATED:           bool = True
    START_MESSAGE_DELAY: int  = 5


class PathsSettings(BaseSettings):
    """Paths to different files

    Attributes:
        SERVER_DIR: ABS-path to the folder with your Minecraft Server
        TO_BACKUP: ABS-path to folders and files to back up
        BACKUP_DIR: ABS-path to the folder where world-backups will be saved
        START_BAT: ABS-Path to start.bat file that launches Minecraft Server
        SERVER_JAR: ABS-Path to .jar with server, if START_BAT not set
        DB: ABS-Path to DB that will be created locally for app's data
        MESSAGES: ABS-path to JSON with messages-data
        USERS_DATA: ABS-path to JSON with Users' data"""

    model_config = SettingsConfigDict(
        env_prefix='PATH_',
        env_file=(find_my_file(CONFIG_FILE_NAME)),
        extra='ignore'
    )

    SERVER_DIR: str       = ''
    TO_BACKUP:  list[str] = ''
    BACKUP_DIR: str       = ''
    START_BAT:  str       = ''
    SERVER_JAR: str       = ''
    DB:         str       = 'my_shiny.db'
    MESSAGES:   str       = ''
    USERS_DATA: str       = ''


class BackupSettings(BaseSettings):
    """Settings for backing up world

    Attributes:
        BACKUP_TIME: Time for backing up world as string in format HH:mm
        BACK_UP_DAYS: Backups, made more days ago, will be automatically deleted
        BACKUP_INTERVAL_DAYS: Interval between each backup in days (back up every x day)
        WAIT_BEFORE_BACKUP: Seconds to wait before zipping and sending backup, to let server restart

        WORLD_SENDER_ON: True, if world backup should be sent over HTTP somewhere (you need to launch receiver there)
        SEND_ATTEMPTS: Number of attempts to send world backup

        RECEIVER_IP: IP where to send world backup
        RECEIVER_PORT: Port where to send world backup
        RECEIVER_TOKEN: Token for authentication in receiver
        RECEIVER_DIR: Folder to save file into when it will be received over HTTP"""

    model_config = SettingsConfigDict(
        env_prefix='BACKUPS_',
        env_file=(find_my_file(CONFIG_FILE_NAME)),
        extra='ignore'
    )

    BACKUP_TIME:          str = '07:00'
    BACK_UP_DAYS:         int = 5
    BACKUP_INTERVAL_DAYS: int = 3
    WAIT_BEFORE_BACKUP:   int = 180

    WORLD_SENDER_ON: bool = True
    SEND_ATTEMPTS:   int  = 5

    RECEIVER_IP:    str       = '127.0.0.1'
    RECEIVER_PORT:  int       = '8123'
    RECEIVER_TOKEN: SecretStr = SecretStr('')
    RECEIVER_DIR:   str       = ''


class DownDetectorSettings(BaseSettings):
    """Settings for DownDetector

    Attributes:
        CONNECTIVITY_URLS: URLS to check network with (will be pinged)
        DETECTOR_ON: If down-detector should be launched"""

    model_config = SettingsConfigDict(
        env_prefix='DD_',
        env_file=(find_my_file(CONFIG_FILE_NAME)),
        extra='ignore'
    )

    CONNECTIVITY_URLS: list[str] = [
        "https://www.google.com",
        "https://1.1.1.1",
        "https://example.com",
        "https://www.wikipedia.org",
        "https://www.python.org/",
        "https://www.bing.com/",
        "https://duckduckgo.com/",
        "https://www.amazon.com/",
        "https://www.wikipedia.org/",
        "https://pingmydomain.blogspot.com/"
    ]
    DETECTOR_ON: bool = True


class Settings(BaseSettings):
    """Apps main settings

    Attributes:
        MIN_MEM: In case no START_BAT provided, will be used to set as minimum RAM for server
        MAX_MEM: In case no START_BAT provided, will be used to set as maximum RAM for server
        LOW_CPU: If set to True, will run java with optimizations flags

        paths: Paths to different files
        notifications: Settings for notifications
        backups: Settings for backing up world
        down_detector: Settings for DownDetector"""

    model_config = SettingsConfigDict(env_file=(find_my_file(CONFIG_FILE_NAME)),
                                      extra='ignore')

    MIN_MEM: int | None = 6
    MAX_MEM: int | None = 6
    LOW_CPU: bool       = True

    paths:         PathsSettings         = PathsSettings()
    notifications: NotificationsSettings = NotificationsSettings()
    backups:       BackupSettings        = BackupSettings()
    down_detector: DownDetectorSettings  = DownDetectorSettings()


logger.info(f'Found config.env at: {find_my_file(CONFIG_FILE_NAME)}')
settings = Settings(
    _env_file=find_my_file(CONFIG_FILE_NAME),
    _env_file_encoding='utf-8'
)
models_representation: dict[str, any] = settings.model_dump()
logger.info(f'Settings loaded:\n{pformat(models_representation)}')
