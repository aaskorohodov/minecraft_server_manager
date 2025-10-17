import os
import threading
import time
import shutil
import zipfile
import subprocess

from loguru import logger
from datetime import datetime, timedelta

from settings import settings
from main_comm import MainComm


class MinecraftServerManager:
    """Manager for Minecraft Server"""

    def __init__(self,
                 main_comm: MainComm):
        """Init

        Args:
            main_comm: Instance of thread-communicator"""

        self.main_comm: MainComm                = main_comm
        self.proc:      subprocess.Popen | None = None
        self._running:  bool                    = False

    def run(self):
        """Main loop"""

        self._running = True
        self._start_server()

        while self._running and not self.main_comm.stop_server:
            if self._check_backup_triggers():
                try:
                    self._stop_server()
                    self._backup_world()
                    self._cleanup_old_backups()
                    logger.info("Backup completed")
                except Exception as e:
                    self.main_comm.set_error(e.__str__())
                    logger.error(f"Error during world backup: {e}")
                    logger.exception(e)

                try:
                    self._start_server()
                except Exception as e:
                    logger.error(f'Fatal error on server restart: {e}')
                    logger.exception(e)
                    quit()
            time.sleep(1)
        self._stop()

    def _check_backup_triggers(self) -> bool:
        """Checks if any triggers for backing up world are present

        Returns:
            True if back up should be executed"""

        now = datetime.now().strftime("%H:%M")
        its_time_to_backup = now == settings.BACKUP_TIME
        if its_time_to_backup or self.main_comm.backup_now_trigger:
            if its_time_to_backup:
                logger.info(f"Reached stop time {settings.BACKUP_TIME}, creating world backup and restarting server...")
            else:
                logger.info(f'Backup trigger activated, creating world backup and restarting server...')
            self.main_comm.backup_now_trigger = False
            return True
        return False

    def _start_server(self):
        """Start Minecraft server"""

        os.chdir(settings.SERVER_DIR)
        if settings.START_BAT:
            logger.info("Starting server via .bat file...")
            self.proc = subprocess.Popen([settings.START_BAT],
                                         stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT,
                                         text=True)
        else:
            logger.info("Starting server directly...")
            self.proc = subprocess.Popen(
                ["java",
                 f"-Xmx{settings.MAX_MEM}G",
                 f"-Xms{settings.MIN_MEM}G",
                 "-jar",
                 "server.jar"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
        time.sleep(10)
        threading.Thread(target=self._read_server_output, daemon=True).start()
        logger.info("Server started")

    def _stop_server(self):
        """Gracefully stop the server"""

        if self.proc and self.proc.stdin:
            logger.info("Sending stop command...")
            self.proc.stdin.write("stop\n")
            self.proc.stdin.flush()
            time.sleep(10)
            logger.info("Server stopped.")
        else:
            logger.info("Server process not running.")

    def _backup_world(self):
        """Copy and zip the world folder"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_copy = os.path.join(settings.BACKUP_DIR, f"world_{timestamp}")
        zip_path  = os.path.join(settings.BACKUP_DIR, f"world_{timestamp}.zip")

        logger.info(f"Copying world folder to {temp_copy}...")
        shutil.copytree(settings.WORLD_DIR, temp_copy)
        logger.info("Zipping backup...")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_copy):
                for file in files:
                    abs_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_path, temp_copy)
                    zipf.write(abs_path, rel_path)
        shutil.rmtree(temp_copy)
        logger.info(f"Backup completed: {zip_path}")

    def _cleanup_old_backups(self):
        """Remove .zip backups older than given number of days"""

        now = datetime.now()
        cutoff = now - timedelta(days=settings.BACK_UP_DAYS)

        deleted = 0
        for filename in os.listdir(settings.BACKUP_DIR):
            if not filename.startswith("world_") or not filename.endswith(".zip"):
                continue

            file_path = os.path.join(settings.BACKUP_DIR, filename)
            try:
                # Parse timestamp from filename: world_YYYYMMDD_HHMMSS.zip
                time_part = filename[len("world_"):-4]  # remove prefix + ".zip"
                file_time = datetime.strptime(time_part, "%Y%m%d_%H%M%S")

                if file_time < cutoff:
                    os.remove(file_path)
                    deleted += 1
            except Exception as e:
                logger.warning(f"[WARN] Skipped file {filename}: {e}")

        if deleted:
            logger.info(f"[{datetime.now()}] Deleted {deleted} old backup(s) older than {settings.BACK_UP_DAYS} days.")
        else:
            logger.info(f"[{datetime.now()}] No old backups found for deletion.")

    def _stop(self):
        """Stop the manager thread and server"""

        logger.info("Stopping manager...")
        self._running = False
        self._stop_server()
        logger.info("Manager stopped")

    def _read_server_output(self):
        """Continuously read Minecraft server output"""

        assert self.proc is not None, "Process not started"
        for line in self.proc.stdout:
            if line.strip():  # skip empty lines
                try:
                    safe_line = line.replace("<", "\\<").replace(">", "\\>")
                    # Add your colored prefix
                    logger.opt(colors=True).info(f"<green>[MINECRAFT]</green> {safe_line.strip()}")
                except Exception as e:
                    logger.exception(e)
        logger.info("Minecraft output reader finished (process closed).")
