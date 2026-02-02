import os
import sys
import time
import threading
import subprocess

from loguru import logger
from datetime import datetime

from settings import settings
from main_comm import MainComm
from file_transfer.backuper import FileBackuper
from file_transfer.sender import HttpFileSender
from file_transfer.cleaner import BackupsCleaner
from initializer.logo_printer import LogoPrinter


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

    def run(self) -> None:
        """Main loop"""

        self._running = True
        self._start_server()

        while self._running and not self.main_comm.stop_server:
            if self._check_backup_triggers():
                self._backup_world()
                self._restart_server()
                self.main_comm.backup_now_trigger = False
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
                logger.info('Backup trigger activated, creating world backup and restarting server...')
            self.main_comm.record_net_stat_trigger = True
            return True
        return False

    def _backup_world(self) -> None:
        """Stops server, zips world and triggers sending it to remote, if configured"""

        try:
            self.main_comm.backup_now_trigger = True
            self._stop_server()

            backuper    = FileBackuper()
            backup_path = backuper.backup_world(settings.WORLD_DIRS)

            BackupsCleaner.cleanup_old_backups(settings.BACK_UP_DAYS, settings.BACKUP_DIR)
            if settings.WORLD_SENDER_ON:
                threading.Thread(target=self._send_backup, args=(backup_path,)).start()
            logger.info("Backup completed")
        except Exception as e:
            self.main_comm.set_error(e.__str__())
            logger.error(f"Error during world backup: {e}")
            logger.exception(e)

    def _restart_server(self) -> None:
        """Restarts server after backing up world"""

        try:
            self._start_server()
        except Exception as e:
            logger.error(f'Fatal error on server restart: {e}')
            logger.exception(e)
            self._stop()
            time.sleep(10)
            quit()

    def _start_server(self) -> None:
        """Start Minecraft server"""

        LogoPrinter.print_logo()

        os.chdir(settings.SERVER_DIR)

        common_params = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": False,
            "bufsize": 0
        }

        if settings.START_BAT:
            logger.info("Starting server via .bat file...")
            self.proc = subprocess.Popen([settings.START_BAT], **common_params)
        else:
            self.proc = subprocess.Popen(
                ["java", f"-Xmx{settings.MAX_MEM}G", "-jar", "server.jar"],
                **common_params
            )
        time.sleep(10)
        threading.Thread(target=self._read_server_output, daemon=True).start()
        logger.info("Server started")

    def _stop_server(self) -> None:
        """Gracefully stop the server"""

        if self.proc and self.proc.stdin:
            logger.info("Sending stop command...")
            try:
                # .encode() converts the string to bytes which the pipe now requires
                self.proc.stdin.write("stop\n".encode('utf-8'))
                self.proc.stdin.flush()

                # Wait for the process to actually exit instead of just sleeping
                logger.info("Waiting for server to shut down...")
                self.proc.wait(timeout=30)

                logger.info("Server stopped.")
            except subprocess.TimeoutExpired:
                logger.warning("Server took too long to stop, forcing termination...")
                self.proc.terminate()
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
        else:
            logger.info("Server process not running.")

    def _send_backup(self,
                     file_path: str) -> None:
        """Send world backup over HTTP"""

        logger.info('Backup sending initiated...')
        time.sleep(180)
        attempt = 0
        sent    = False
        sender  = HttpFileSender(file_path)
        while attempt < settings.SEND_ATTEMPTS + 1 and not sent:
            sent = sender.send()
            attempt += 1

        if sent:
            logger.info(f'World was sent successfully on attempt #{attempt}')
        else:
            logger.warning('Was not able to send world backup copy over HTTP!')

    def _stop(self) -> None:
        """Stop the manager thread and server"""

        logger.info("Stopping manager...")
        self._running = False
        self._stop_server()
        logger.info("Manager stopped")

    def _read_server_output(self) -> None:
        """Continuously read Minecraft server output with safe decoding"""

        assert self.proc is not None, "Process not started"
        assert self.proc.stdout is not None

        # Read line-by-line from the binary stream
        with self.proc.stdout as pipe:
            for line_bytes in iter(pipe.readline, b''):
                # Check if process died unexpectedly
                if self.proc.poll() is not None:
                    break

                try:
                    line = line_bytes.decode('utf-8', errors='replace').strip()
                    if line:
                        # Pass 'line' as a separate argument.
                        # This prevents Loguru from parsing 'line' for <tags>.
                        logger.opt(colors=True).info("<green>[MINECRAFT]</green> {}", line)
                except Exception as e:
                    # Use sys.__stderr__ to bypass Loguru if Loguru itself is the issue
                    print(f"CRITICAL: Reader thread error: {e}", file=sys.stderr)

        logger.info("Minecraft output reader finished.")
