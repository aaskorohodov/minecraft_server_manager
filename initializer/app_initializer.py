import os
import random
import time
import threading

from loguru import logger

from initializer.start_logos import START_LOGOS
from main_comm import MainComm
from settings import settings
from trayer.trayer import Trayer
from server_manager import MinecraftServerManager


class AppInitializer:
    """Starts application and init different instances"""

    def __init__(self):
        """Init"""

        self.main_comm: MainComm = MainComm()
        self._print_logo()

    def _print_logo(self) -> None:
        """Print start logo"""

        start_logo = random.choice(START_LOGOS)

        for line in start_logo.splitlines():
            # Print the line
            print(line)

            # Pause the program
            time.sleep(0.05)

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

    def run_indefinitely(self) -> None:
        """Loop to let app run"""

        while self.main_comm.trayer_running:
            time.sleep(1)
