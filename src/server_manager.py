import os
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
from notifications.notificator import Notificator
from server_communicator.communicator import ServerCommunicator


class MinecraftServerManager:
    """Manager for Minecraft Server"""

    def __init__(self,
                 main_comm: MainComm):
        """Init

        Args:
            main_comm: Instance of thread-communicator"""

        self.notificator:  Notificator               = Notificator()
        self.main_comm:    MainComm                  = main_comm
        self._server_proc: subprocess.Popen | None   = None
        self._running:     bool                      = False
        self._server_comm: ServerCommunicator | None = None

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
        its_time_to_backup = now == settings.backups.BACKUP_TIME
        if its_time_to_backup or self.main_comm.backup_now_trigger:
            if its_time_to_backup:
                logger.info(
                    f"Reached stop time {settings.backups.BACKUP_TIME}, creating world backup and restarting server..."
                )
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

            backuper = FileBackuper()
            backuper.copy_world_to_temp_folder(settings.paths.WORLD_DIRS)
            logger.info("Main backup sequence completed")
            threading.Thread(target=self._zip_and_send_world, args=(backuper,)).start()
        except Exception as e:
            self.main_comm.set_error(e.__str__())
            logger.error(f"Error during world backup: {e}")
            logger.exception(e)

    def _start_server(self) -> None:
        """Start Minecraft server"""

        LogoPrinter.print_logo()

        os.chdir(settings.paths.SERVER_DIR)

        aikar_flags = [
            "-XX:+UseCriticalJavaThreadPriority",
            "-XX:+UseG1GC",
            "-XX:+ParallelRefProcEnabled",
            "-XX:MaxGCPauseMillis=200",
            "-XX:+UnlockExperimentalVMOptions",
            "-XX:+DisableExplicitGC",
            "-XX:+AlwaysPreTouch",
            "-XX:G1NewSizePercent=30",
            "-XX:G1MaxNewSizePercent=40",
            "-XX:G1HeapRegionSize=8M",
            "-XX:G1ReservePercent=20",
            "-XX:G1HeapWastePercent=5",
            "-XX:G1MixedGCCountTarget=4",
            "-XX:InitiatingHeapOccupancyPercent=15",
            "-XX:G1MixedGCLiveThresholdPercent=90",
            "-XX:G1RSetUpdatingPauseTimePercent=5",
            "-XX:SurvivorRatio=32",
            "-XX:+PerfDisableSharedMem",
            "-XX:MaxTenuringThreshold=1",
        ]

        encoding_flags = [
            "-Dfile.encoding=UTF-8",
            "-Dsun.stdout.encoding=UTF-8",
            "-Dsun.stderr.encoding=UTF-8",
        ]

        common_params = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "bufsize": 0,          # Line buffered: Much faster than 0
        }

        if settings.paths.START_BAT:
            logger.info("Starting server via .bat file...")
            self._server_proc = subprocess.Popen([settings.paths.START_BAT], **common_params)
        else:
            self._server_proc = subprocess.Popen(
                [
                    "java",
                    *encoding_flags,
                    *(aikar_flags if settings.LOW_CPU else []),
                    f"-Xms{settings.MIN_MEM}G",
                    f"-Xmx{settings.MAX_MEM}G",
                    "-jar", f"{settings.paths.SERVER_JAR}",
                    "nogui"
                ],
                **common_params
            )

        self._server_comm = ServerCommunicator(self._server_proc)
        self._server_comm.start_communication()
        logger.info("Server started")

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

    def _stop_server(self) -> None:
        """Gracefully stop the server"""

        if self._server_proc and self._server_proc.stdin:
            try:
                command = "say Server is restarting, 5 minutes max...\n"
                self._server_comm.send_to_server(command)
                time.sleep(10)

                logger.info("Sending stop command...")
                self._server_comm.send_to_server(command="stop\n")

                # Wait for the process to actually exit instead of just sleeping
                logger.info("Waiting for server to shut down...")
                self._server_proc.wait(timeout=60)

                logger.info("Server stopped.")
            except subprocess.TimeoutExpired:
                logger.warning("Server took too long to stop, forcing termination...")
                self._server_proc.kill()
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
            finally:
                self._server_proc = None
                logger.info("Server handle cleared.")
        else:
            logger.info("Server process not running.")

    def _zip_and_send_world(self,
                            backuper: FileBackuper) -> None:
        """Zips world-copy, send it to remote storage (if configured), deletes world-copy and cleans old backups

        Notes:
            Intended to be run in background
        Args:
            backuper: Initiated backuper"""

        logger.info(
            f'Backup post-sequence initiated. '
            f'Waiting {settings.backups.WAIT_BEFORE_BACKUP} seconds to let server start...'
        )
        time.sleep(settings.backups.WAIT_BEFORE_BACKUP)

        try:
            zip_world_path = backuper.zip_world()
            if zip_world_path:
                logger.info('Deleting temp-copy')
                backuper.delete_temp_folder()
            else:
                logger.error('Was not able to create zip! Skipping deletion of world-copy as it it the only backup '
                             'we have')

            if zip_world_path and settings.backups.WORLD_SENDER_ON:
                BackupsCleaner.cleanup_old_backups(settings.backups.BACK_UP_DAYS, settings.paths.BACKUP_DIR)
                self._send_backup(file_path=zip_world_path)
            elif zip_world_path and not settings.backups.WORLD_SENDER_ON:
                logger.warning('WORLD_SENDER_ON set to False in settings. Skipping sending')
            elif not zip_world_path and settings.backups.WORLD_SENDER_ON:
                logger.error('Zipping process failed, skipping sending')
        finally:
            self.main_comm.backup_now_trigger = False
            logger.info('Backup post-sequence completed')

    def _send_backup(self,
                     file_path: str) -> None:
        """Send world backup over HTTP"""

        logger.info('Backup sending initiated...')
        attempt = 0
        sent    = False
        sender  = HttpFileSender(file_path)
        while attempt < settings.backups.SEND_ATTEMPTS + 1 and not sent:
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
