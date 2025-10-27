import os
import time
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

        if settings.START_BAT:
            if not os.path.exists(settings.START_BAT):
                raise AssertionError(f'No bat found at {settings.START_BAT}')
        else:
            if not settings.MIN_MEM or not settings.MIN_MEM:
                raise AssertionError('You should provide .bat to start server or indicate min and max RAM in settings!')

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
        logger.add(lambda msg: print(msg, end=""), colorize=True)

    def init_components(self) -> None:
        """Create instances of app's main components"""

        Trayer(self.main_comm)
        server_manager = MinecraftServerManager(self.main_comm)
        threading.Thread(target=server_manager.run,
                         daemon=True).start()

        if settings.DETECTOR_ON:
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

        time.sleep(5)
        quit()

    def _check_plot_trigger(self) -> None:
        """Checks if trigger to draw plot was activated. Draws plot if trigger is on"""

        if self.main_comm.draw_plot_trigger:
            time.sleep(2)
            self.main_comm.draw_plot_trigger = False
            PlotDrawer.draw_data_24h()
