import os
import sys
import time
import socket
import datetime
import threading

from loguru import logger

from settings import settings
from main_comm import MainComm
from trayer.trayer import Trayer
from down_detecror.detector import DownDetector
from down_detecror.plot_drawer import PlotDrawer
from server_manager import MinecraftServerManager


class AppInitializer:
    """Starts application and init different instances"""

    def __init__(self):
        """Init"""

        self.main_comm: MainComm = MainComm()

    def check_settings(self) -> None:
        """Checks if server-start settings provided as expected

        Raises:
            AssertionError: In case no bat and no min-max mem  provided"""

        logger.info('Checking settings...')

        if settings.paths.START_BAT:
            if not os.path.exists(settings.paths.START_BAT):
                raise AssertionError(f'No bat found at {settings.paths.START_BAT}')
            else:
                logger.info('.bat file ok...')
        else:
            if not settings.MIN_MEM or not settings.MIN_MEM:
                raise AssertionError('You should provide .bat to start server or indicate min and max RAM in settings!')
            else:
                logger.info(f'Using {settings.MIN_MEM=} and {settings.MAX_MEM=}...')

        self._check_backup_time()
        self._check_paths()
        if settings.down_detector.DETECTOR_ON:
            self._check_urls()
        else:
            logger.warning('DownDetector is OFF, you can change this with DD_DETECTOR_ON=true')

        if settings.LOW_CPU and not settings.paths.START_BAT:
            logger.warning('Launching with flags for LOW-END CPU. You can this off with LOW_CPU=false')

        if settings.backups.WORLD_SENDER_ON:
            self._check_receiver()
        else:
            logger.warning('Sending backups if off! You can turn it on with BACKUPS_WORLD_SENDER_ON=true')

        logger.info('Settings checks completed successfully')

    def _check_backup_time(self) -> None:
        """Checks time for backup from settings

        Raises:
            AssertionError: If time for backup from settings is invalid"""

        try:
            # %H is 24-hour clock (00-23)
            # %M is minutes (00-59)
            datetime.datetime.strptime(settings.backups.BACKUP_TIME, '%H:%M')
            logger.info('Backup time ok...')
        except ValueError:
            raise AssertionError('BACKUP_TIME is not valid. Check settings')

    def _check_paths(self) -> None:
        """Checks Paths from settings

        Raises:
            AssertionError: In case Paths are incorrect"""

        all_good = True

        if not os.path.exists(settings.paths.SERVER_DIR):
            logger.error(f'Path in settings.paths.SERVER_DIR ({settings.paths.SERVER_DIR}) is invalid!')
            all_good = False

        for abs_path in settings.paths.TO_BACKUP:
            if not os.path.exists(abs_path):
                logger.error(f'Path in settings.paths.TO_BACKUP ({abs_path}) is invalid!')
                all_good = False

        if not os.path.exists(settings.paths.BACKUP_DIR):
            logger.error(f'Path in settings.paths.BACKUP_DIR ({settings.paths.BACKUP_DIR}) is invalid!')
            all_good = False

        if not os.path.exists(settings.paths.SERVER_JAR):
            logger.error(f'Path in settings.paths.SERVER_JAR ({settings.paths.SERVER_JAR}) is invalid!')
            all_good = False

        if settings.notifications.ACTIVATED:
            if not os.path.exists(settings.paths.MESSAGES):
                logger.warning(f'Path in settings.paths.MESSAGES ({settings.paths.MESSAGES}) is invalid!')

            if not os.path.exists(settings.paths.USERS_DATA):
                logger.warning(f'Path in settings.paths.USERS_DATA ({settings.paths.USERS_DATA}) is invalid!')

        if not all_good:
            raise AssertionError('Some paths are invalid! Check settings')
        logger.info('Paths are ok...')

    def _check_urls(self) -> None:
        """Checks URLs for DownDetector"""

        all_good = True
        for url in settings.down_detector.CONNECTIVITY_URLS:
            result = DownDetector.check_url(url)
            if not result:
                all_good = False
                logger.warning(f'URL {url} is already not available. '
                               f'This may cause wrong data from DownDetector collected later')

        if all_good:
            logger.info('URLs for DownDetector are ok...')

    def _check_receiver(self) -> None:
        """Checks if receiver for backups is available"""

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3)
                # connect_ex returns 0 on success, error code otherwise
                result_code = s.connect_ex((settings.backups.RECEIVER_IP, settings.backups.RECEIVER_PORT))
                result = result_code == 0
        except:
            result = False

        # Usage

        if result:
            logger.info('Receiver for backups available...')
        else:
            logger.warning(f'Receiver for backups is NOT available! '
                           f'Tested: {settings.backups.RECEIVER_IP}:{settings.backups.RECEIVER_PORT}')

    def init_logger(self) -> None:
        """Set up logger"""

        # Make sure the logs folder exists
        os.makedirs("logs", exist_ok=True)

        # Remove the default stderr logger
        logger.remove()

        # Add rotating file handler
        logger.add(
            "logs/server_manager_{time:YYYY-MM-DD}.log",
            rotation="00:00",      # create new log file every day at midnight
            retention="100 days",  # keep logs for 10 days, delete older automatically
            compression="zip",     # compress old logs
            enqueue=True,          # thread-safe
            encoding="utf-8"
        )

        # Optional: also log to console
        logger.add(
            sys.stderr,
            colorize=True,
            enqueue=True,
            backtrace=True,
            diagnose=True
        )
        # logger.add(lambda msg: print(msg, end=""), colorize=True)

    def init_components(self) -> None:
        """Create instances of app's main components"""

        Trayer(self.main_comm)
        server_manager = MinecraftServerManager(self.main_comm)
        threading.Thread(target=server_manager.run,
                         daemon=False).start()

        if settings.down_detector.DETECTOR_ON:
            logger.info('Launching down-detector')
            down_detector  = DownDetector(self.main_comm)
            threading.Thread(target=down_detector.monitor,
                             daemon=True).start()
        else:
            logger.info('Running without down-detector')

    def run_indefinitely(self) -> None:
        """Loop to let app run"""

        while self.main_comm.trayer_running:
            time.sleep(1)
            self._check_plot_trigger()

    def _check_plot_trigger(self) -> None:
        """Checks if trigger to draw plot was activated. Draws plot if trigger is on"""

        if self.main_comm.draw_plot_trigger:
            time.sleep(2)
            self.main_comm.draw_plot_trigger = False
            PlotDrawer.draw_data_24h()
