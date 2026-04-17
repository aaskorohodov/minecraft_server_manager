import datetime

from loguru import logger
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from server_communicator.communicator import ServerCommunicator

from settings import settings


class Cycler:
    """Responsible for managing cycles for AntiBot

    Attributes:
        _server_comm: Communicator to send command to server

        _run_every: every N cycle to execute AntiBot logic (every other cycles will be skipped)
        _current_cycle: Current cycle to track when to execute AntiBot logic

        _aggressive: If sett to True, AntiBot will get to aggressive mode, which will cause it bans
        _aggressive_start_at: Timestamp of when aggressive mode was started (it will default to normal after time)"""

    def __init__(self,
                 server_comm: 'ServerCommunicator'):
        """Init"""

        self._server_comm: 'ServerCommunicator' = server_comm

        self._run_every:     int = settings.antibot.RUN_EVERY
        self._current_cycle: int = 0

        self._aggressive:          bool            = False
        self._aggressive_start_at: Optional[float] = None

    def check_cycles(self) -> bool:
        """Checks if it is time to run logic or skipp it, and if aggressive mode time is over

        Returns:
            True if current cycle is the one to execute logic in"""

        if self._aggressive is True:
            self._check_aggressive_cycle_timeout()

        self._current_cycle += 1
        if self._current_cycle < self._run_every:
            return False
        else:
            self._current_cycle = 0
            return True

    def _check_aggressive_cycle_timeout(self) -> None:
        """Checks if we can turn off aggressive mode"""

        try:
            current_time                = datetime.datetime.now().timestamp()
            time_since_aggressive_start = abs(current_time - self._aggressive_start_at)
            aggressive_mode_over        = time_since_aggressive_start > settings.antibot.AGGRESSIVE_LENGTH_SEC
            if aggressive_mode_over:
                self._turn_aggressive_mode_off()
                command = 'say Aggressive antibot mode is off\n'
                self._server_comm.send_to_server(command)
        except Exception as e:
            self._turn_aggressive_mode_off()
            logger.exception(e)

    def become_aggressive(self) -> None:
        """Sets antibot to be aggressive for some period of time"""

        self._aggressive          = True
        self._run_every           = settings.antibot.AGGRESSIVE_RUN_EVERY
        self._aggressive_start_at = datetime.datetime.now().timestamp()

        command = 'say Antibot is now in aggressive mode! Try not to login for a few minutes not to get banned\n'
        self._server_comm.send_to_server(command)

    def _turn_aggressive_mode_off(self) -> None:
        """Turns off aggressive mode"""

        self._aggressive          = False
        self._aggressive_start_at = None
        self._run_every           = settings.antibot.RUN_EVERY

    def is_aggressive(self) -> bool:
        """Checks if aggressive mode is on

        Returns:
            True, in case aggressive mode is on"""

        return self._aggressive
