import threading
import subprocess

from loguru import logger
from queue import Queue, Empty

from settings import settings
from notifications.notificator import Notificator


class ServerCommunicator:
    """Communicates with java-server to get logs from it and write commands into it"""

    def __init__(self,
                 server_proc: subprocess.Popen):
        """Init

        Args:
            server_proc: Process with java-server"""

        self._server_proc: subprocess.Popen = server_proc
        self.notificator:  Notificator      = Notificator()

        self._output_queue: Queue           = Queue(maxsize=10000)
        self._stop_event:   threading.Event = threading.Event()

    def start_communication(self):
        """Entry point to launch both threads"""

        # Thread 1: Producer (Reads from process)
        threading.Thread(target=self._reader_loop, daemon=True).start()

        # Thread 2: Consumer (Processes data)
        threading.Thread(target=self._processor_loop, daemon=True).start()

    def _reader_loop(self) -> None:
        """"""

        assert self._server_proc is not None, "Process not started"
        assert self._server_proc.stdout is not None

        try:
            for line_bytes in iter(self._server_proc.stdout.readline, b''):
                self._output_queue.put(line_bytes)
        except Exception as e:
            logger.error(f"Reader thread error: {e}")
        finally:
            self._server_proc.stdout.close()
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

    def _check_login_event(self,
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
                        function=self._send_login_message,
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

    def _send_login_message(self,
                            player_name: str) -> None:
        """Sends a message to a specific player

        Args:
            player_name: Player to send message to"""

        if self._server_proc and self._server_proc.stdin:
            message = self.notificator.get_login_message(player_name)
            if message:
                command = f"tellraw {player_name} {message}\n"
                logger.opt(colors=True).info("<green>[SERVER]</green> {}", command)
                self.send_to_server(command)

    def send_to_server(self,
                       command: str) -> None:
        """Sends commands to server"""

        if self._server_proc and self._server_proc.stdin:
            try:
                self._server_proc.stdin.write(command.encode('utf-8'))
                self._server_proc.stdin.flush()
            except Exception as e:
                logger.error(f"Failed to write to server stdin: {e}")
