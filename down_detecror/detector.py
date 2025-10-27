import time
import copy
import random
import sqlite3
import datetime
import requests
import threading

from loguru import logger

from settings import settings
from main_comm import MainComm


class DownDetector:
    """Checks network and writes down results"""

    def __init__(self,
                 main_comm: MainComm):
        """Init

        Args:
            main_comm: Thread-communicator object"""

        self.main_comm: MainComm = main_comm

        self._conn   = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
        self._cursor = self._conn.cursor()

        self._init_db()
        threading.Thread(target=self._check_triggers_loop, daemon=True).start()

    def _init_db(self) -> None:
        """Creates a table for internet stability test"""

        self._cursor.execute("""
            CREATE TABLE IF NOT EXISTS connectivity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('online', 'offline', 'off'))
            )
        """)
        self._conn.commit()

    def _is_online(self,
                   timeout=3) -> bool:
        """Makes requests to check internet connection

        Args:
            timeout: Timeout for requests
        Returns:
            True, in case internet works"""

        urls = copy.copy(settings.CONNECTIVITY_URLS)
        random.shuffle(urls)
        for url in urls:
            try:
                requests.get(url, timeout=timeout)
                return True
            except Exception:
                pass
        return False

    def _record_status(self,
                       status: str) -> None:
        """Saves status into DB

        Args:
            status: Status of connection to save into DB"""

        self._cursor.execute(
            "INSERT INTO connectivity (timestamp, status) VALUES (?, ?)",
            (datetime.datetime.now().isoformat(), status)
        )
        self._conn.commit()
        logger.opt(colors=True).info(
            f"<yellow>[DOWN DETECTOR]</yellow> Recorded status: {status}"
        )

    def monitor(self,
                interval=10) -> None:
        """Check connectivity every N seconds.

        Args:
            interval: Interval for making HTTP request to check network"""

        time.sleep(10)

        status = None
        last_status = self._get_status()
        self._record_status(last_status)

        last_change_time = datetime.datetime.now()

        while self.main_comm.trayer_running:
            try:
                status = self._get_status()

                # Detect status change
                if status != last_status:
                    # If we are coming back online, calculate downtime
                    if last_status == "offline" and status == "online":
                        downtime = (datetime.datetime.now() - last_change_time).total_seconds()
                        logger.opt(colors=True).warning(
                            f"<yellow>[DOWN DETECTOR]</yellow> Offline for {downtime:.1f} seconds"
                        )

                    # Record the status change
                    self._record_status(status)
                    last_change_time = datetime.datetime.now()
                    last_status = status

                time.sleep(interval)

            except Exception as e:
                logger.exception(e)
                time.sleep(interval)

        self._conn.close()

    def _check_triggers_loop(self) -> None:
        """Checks if User pressed button in tray and requested plot, or if status should be recorded now"""

        while self.main_comm.trayer_running:
            if self.main_comm.draw_plot_trigger:
                self._record_status(self._get_status())
            if self.main_comm.record_net_stat_trigger:
                self._record_status(self._get_status())
                self.main_comm.record_net_stat_trigger = False
            if self.main_comm.backup_now_trigger:
                self._record_status('off')
                while self.main_comm.backup_now_trigger:
                    time.sleep(1)
                self._record_status(self._get_status())
            time.sleep(1)

        self._record_status('off')

    def _get_status(self) -> str:
        """Makes HTTP-request and returns status as string

        Returns:
            Status as string"""

        status = "online" if self._is_online() else "offline"
        return status
