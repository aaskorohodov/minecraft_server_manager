import threading
import subprocess

from loguru import logger
from typing import Optional
from queue import Queue, Empty

from settings import settings
from anti_bot.anti_bot import AntiBot
from notifications.notificator import Notificator
from toxicity_manager.manager import ToxicityManager
from server_communicator.logs_extractor import LogsExtractor


class ServerCommunicator:
    """Communicates with java-server to get logs from it and write commands into it

    Attributes:
        server_proc: Process with Minecraft-Server
        notificator: Instance of Notificator to get notifications for Users from
        _output_queue: Queue to store Minecraft-Server's output
        _stop_event: Thread-communicator"""

    def __init__(self,
                 server_proc: subprocess.Popen,
                 antibot: Optional[AntiBot] = None,
                 toxicity: Optional[ToxicityManager] = None):
        """Init

        Args:
            server_proc: Process with java-server
            antibot: Instance of AntiBot to track bots
            toxicity: Instance of toxicity manager"""

        self.server_proc:  subprocess.Popen  = server_proc
        self.notificator:  Notificator       = Notificator()
        self.antibot:      Optional[AntiBot] = antibot

        self.toxicity: Optional[ToxicityManager] = toxicity

        self._output_queue: Queue           = Queue(maxsize=10000)
        self._stop_event:   threading.Event = threading.Event()

    def start_communication(self):
        """Entry point to launch both threads"""

        # Thread 1: Producer (Reads from process)
        threading.Thread(target=self._reader_loop, daemon=True).start()

        # Thread 2: Consumer (Processes data)
        threading.Thread(target=self._processor_loop, daemon=True).start()

    def _reader_loop(self) -> None:
        """Loop, responsible for reading Server's output and putting it into queue"""

        assert self.server_proc is not None, "Process not started"
        assert self.server_proc.stdout is not None

        try:
            for line_bytes in iter(self.server_proc.stdout.readline, b''):
                self._output_queue.put_nowait(line_bytes)
        except Exception as e:
            logger.error(f"Reader thread error: {e}")
        finally:
            self.server_proc.stdout.close()
            self._stop_event.set()
            logger.warning("Minecraft output reader finished.")

    def _processor_loop(self) -> None:
        """Consumer: Pulls from queue and runs logic"""

        while not self._stop_event.is_set() or not self._output_queue.empty():
            line_bytes = None
            try:
                line_bytes = self._output_queue.get(timeout=1.0)
                line_string = self._read_output_line(line_bytes)
                if line_string:
                    self._process_line(line_string)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Processor thread error: {e}")
            finally:
                if line_bytes is not None:
                    self._output_queue.task_done()

    def _read_output_line(self,
                          line_bytes: bytes) -> str | None:
        """Reads output from server

        Args:
            line_bytes: Output from server
        Returns:
            Output from server, converted into string or None in case of any error"""

        try:
            line = line_bytes.decode('utf-8', errors='replace').strip()
            return line
        except Exception as decode_err:
            logger.error(f"Decoding error: {decode_err}")

    def _process_line(self,
                      line: str) -> None:
        """Process line from server's output

        Args:
            line: Line from server's output"""

        logger.opt(colors=True).info("<green>[MINECRAFT]</green> {}", line)
        if self.notificator.activated:
            self._check_login_event(line)

        if settings.antibot.ON:
            self._check_antibot_events(line)

        if settings.TOXICITY_ON and self.toxicity:
            user_name, message = LogsExtractor.extract_message(line)
            if user_name and message:
                self.toxicity.check_text(message, user_name)

    def _check_antibot_events(self,
                              clean_line: str) -> None:
        """Check logs in search of events, related to antibot specifically

        Args:
            clean_line: Log from server"""

        # clean_line = '[19:25:45 INFO]: Name issued server command: /plugins'

        try:
            if "UUID of player" in clean_line:
                user_uuid, user_name = LogsExtractor.extract_uuid_and_name(clean_line)
                logger.debug(f'Parsed {user_name=}, {user_uuid=}')
                self.antibot.add_user(user_uuid=user_uuid, user_name=user_name)

            if 'Teleported' in clean_line and 'to' in clean_line:
                updated_coords, user_name = LogsExtractor.extract_updated_coords(clean_line)
                logger.debug(f'Parsed {updated_coords=}')
                self.antibot.update_last_know_coords(user_name=user_name, coordinates_str=updated_coords)

            if settings.antibot.AGGRESSIVE_COMMAND in clean_line:
                for root_user in settings.antibot.ACCEPT_FROM_USERS:
                    if root_user in clean_line:
                        self.antibot.become_aggressive()

            if settings.antibot.UNBAN_IPS_COMMAND:
                if settings.antibot.UNBAN_IPS_COMMAND in clean_line:
                    for root_user in settings.antibot.ACCEPT_FROM_USERS:
                        if root_user in clean_line:
                            self.antibot.unban_ips(unban_all=True)

            if ' issued server command: ' in clean_line:
                command, user_name = LogsExtractor.extract_command(clean_line)
                self.antibot.check_forbidden_commands(command, user_name)

        except Exception as e:
            logger.exception(e)

    def _check_login_event(self,
                           clean_line: str) -> None:
        """Checks if Player logged in and initiates login message, and extracts data for antibot

        Args:
            clean_line: Output from server to check if this is a login event"""

        try:
            if "logged in with entity id" in clean_line and "[/ " not in clean_line:
                user_name = LogsExtractor.extract_user_name(clean_line)
                if user_name:
                    logger.info(f"Scheduling welcome message for {user_name} "
                                f"in {settings.notifications.START_MESSAGE_DELAY}s")

                    timer = threading.Timer(
                        interval=settings.notifications.START_MESSAGE_DELAY,
                        function=self._send_login_message,
                        args=[user_name]
                    )
                    timer.start()

                    self._save_login_coords(clean_line, user_name)

        except Exception as e:
            logger.exception(e)

    def _save_login_coords(self,
                           clean_line: str,
                           user_name: str) -> None:
        """Extract initial data for antibot

        Args:
            clean_line: Log from server
            user_name: UserName from log from serve"""

        if settings.antibot.ON:
            login_coords, ip_address = LogsExtractor.extract_login_coords_and_ip(clean_line)
            logger.debug(f'Parsed {login_coords=}, {ip_address=}, {user_name=}')
            self.antibot.save_login_coordinates_and_ip(login_coordinates_str=login_coords,
                                                       ip_address=ip_address,
                                                       user_name=user_name)

    def _send_login_message(self,
                            player_name: str) -> None:
        """Sends a message to a specific player

        Args:
            player_name: Player to send message to"""

        if self.server_proc and self.server_proc.stdin:
            message = self.notificator.get_login_message(player_name)
            if message:
                command = f"tellraw {player_name} {message}\n"
                logger.opt(colors=True).info("<green>[SERVER]</green> {}", command)
                self.send_to_server(command)

    def send_to_server(self,
                       command: str) -> None:
        """Sends commands to server"""

        if self.server_proc and self.server_proc.stdin:
            try:
                if not command.endswith('\n'):
                    command += '\n'
                self.server_proc.stdin.write(command.encode('utf-8'))
                self.server_proc.stdin.flush()
            except Exception as e:
                logger.error(f"Failed to write to server stdin: {e}")
