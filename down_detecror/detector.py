import os
import time
import sqlite3
import datetime
import requests
import pandas as pd
import matplotlib.pyplot as plt

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

    def _init_db(self) -> None:
        """Creates a table for internet stability test"""

        self._cursor.execute("""
            CREATE TABLE IF NOT EXISTS connectivity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('online', 'offline'))
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

        for url in settings.CONNECTIVITY_URLS:
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
        logger.info(f"Recorded status: {status}")

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
                        logger.warning(f"Offline for {downtime:.1f} seconds")

                    # Record the status change
                    self._record_status(status)
                    last_change_time = datetime.datetime.now()
                    last_status = status

                time.sleep(interval)

            except Exception as e:
                logger.exception(e)
                time.sleep(interval)
            finally:
                if status:
                    self._record_status(status)

        self._conn.close()

    def _get_status(self) -> str:
        """Makes HTTP-request and returns status as string

        Returns:
            Status as string"""

        status = "online" if self._is_online() else "offline"
        return status


def draw_data() -> None:
    """Draws collected downtime"""

    root_folder = os.path.dirname(os.path.dirname(__file__))
    os.chdir(root_folder)
    df = pd.read_sql_query(
        "SELECT * FROM connectivity ORDER BY timestamp",
        sqlite3.connect(settings.DB_PATH)
    )
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    if len(df) < 2:
        print("Not enough data to plot.")
        return

    # Calculate uptime %
    uptime = (df['status'] == 'online').sum() / len(df)
    print(f"Uptime: {uptime:.2%}")

    # Plot timeline with colored segments
    plt.figure(figsize=(10, 2))
    for i in range(1, len(df)):
        color = 'green' if df.loc[i - 1, 'status'] == 'online' else 'red'
        plt.plot(df['timestamp'].iloc[i-1:i+1], [1, 1], color=color, linewidth=3)

    plt.yticks([])
    plt.title("Internet Connectivity Timeline")
    plt.xlabel("Time")
    plt.tight_layout()
    plt.show()


if __name__ == '__main__':
    draw_data()
