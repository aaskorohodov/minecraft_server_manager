import atexit
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


class MinecraftServerManager:
    """Manager for Minecraft Server"""

    def __init__(self,
                 main_comm: MainComm):
        """Init

        Args:
            main_comm: Instance of thread-communicator"""

        self.notificator: Notificator             = Notificator()
        self.main_comm:   MainComm                = main_comm
        self.proc:        subprocess.Popen | None = None
        self._running:    bool                    = False

    def run(self) -> None:
        """Main loop"""

        atexit.register(self._stop_server)
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

        os.chdir(settings.paths.SERVER_DIR)

        common_params = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,         # Let Python handle string conversion
            "encoding": "utf-8",  # Force UTF-8 to avoid encoding errors
            "bufsize": 1,         # Line buffered: Much faster than 0
            "errors": "replace"   # Don't crash on weird characters
        }

        if settings.paths.START_BAT:
            logger.info("Starting server via .bat file...")
            self.proc = subprocess.Popen([settings.paths.START_BAT], **common_params)
        else:
            self.proc = subprocess.Popen(
                [
                    "java",
                    "-Dfile.encoding=UTF-8",
                    "-Dsun.stdout.encoding=UTF-8",
                    "-Dsun.stderr.encoding=UTF-8",
                    f"-Xms{settings.MIN_MEM}G",
                    f"-Xmx{settings.MAX_MEM}G",
                    "-jar", f"{settings.paths.SERVER_JAR}",
                    "nogui"
                ],
                **common_params
            )
            # self.proc = subprocess.Popen(
            #     ["java", f"-Xmx{settings.MAX_MEM}G", "-jar", "server.jar"],
            #     **common_params
            # )
        threading.Thread(target=self._read_server_output, daemon=True).start()
        logger.info("Server started")

    def _stop_server(self) -> None:
        """Gracefully stop the server"""

        if self.proc and self.proc.stdin:
            command = "say Server is restarting, 5 minutes max...\n"
            self.proc.stdin.write(command)
            self.proc.stdin.flush()
            time.sleep(10)
            logger.info("Sending stop command...")
            try:
                # .encode() converts the string to bytes which the pipe now requires
                self.proc.stdin.write("stop\n")
                self.proc.stdin.flush()

                # Wait for the process to actually exit instead of just sleeping
                logger.info("Waiting for server to shut down...")
                self.proc.wait(timeout=60)

                logger.info("Server stopped.")
            except subprocess.TimeoutExpired:
                logger.warning("Server took too long to stop, forcing termination...")
                self.proc.kill()
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
            finally:
                self.proc = None
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

    def _read_server_output(self) -> None:
        """Continuously read Minecraft server output with safe decoding"""

        assert self.proc is not None, "Process not started"
        assert self.proc.stdout is not None

        try:
            for line in iter(self.proc.stdout.readline, ''):
                clean_line = line.strip()
                if clean_line:
                    logger.opt(colors=True).info("<green>[MINECRAFT]</green> {}", clean_line)
                    if self.notificator.activated:
                        self._check_if_this_is_login_event(clean_line)
        except Exception as e:
            logger.error(f"Reader thread error: {e}")
        finally:
            # If we reach here, the process has closed because we hit the '' sentinel
            self.proc.stdout.close()
            logger.warning("Minecraft output reader finished.")

    def _check_if_this_is_login_event(self,
                                      clean_line: str) -> None:
        """Checks if Player logged in and initiates login message if so

        Args:
            clean_line: Output from server to check if this is a login event"""

        try:
            if "logged in with entity id" in clean_line and "[/ " not in clean_line:
                user_name = self._extract_user_name(clean_line)
                if user_name:
                    logger.info(f"Scheduling welcome message for {user_name} "
                                f"in {settings.notifications.START_MESSAGE_DELAY}s")

                    timer = threading.Timer(
                        interval=settings.notifications.START_MESSAGE_DELAY,
                        function=self.send_private_message,
                        args=[user_name]
                    )
                    timer.start()
        except Exception as e:
            logger.exception(e)

    def _extract_user_name(self,
                           clean_line: str) -> str:
        """Extracts UserName from server's output

        Args:
            clean_line: Output from server
        Returns:
            UserName"""

        # Step A: Get everything after the Minecraft log prefix "]: "
        # This leaves us with: "Name[/188.126.89.172:58488] logged in..."
        after_prefix = clean_line.split("]: ")[-1]

        # Step B: Get everything before the IP bracket "[/"
        # This leaves us with: "Name"
        username = after_prefix.split("[/")[0]

        # Step C: Clean any accidental whitespace
        username = username.strip()

        return username

    def send_private_message(self,
                             player_name: str) -> None:
        """Sends a message to a specific player

        Args:
            player_name: Player to send message to"""

        if self.proc and self.proc.stdin:
            message = self.notificator.get_login_message(player_name)
            if message:
                command = f"tellraw {player_name} {message}\n"
                logger.opt(colors=True).info("<green>[SERVER]</green> {}", command)
                self.proc.stdin.write(command)
                self.proc.stdin.flush()
