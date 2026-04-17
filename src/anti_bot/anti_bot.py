import threading

from loguru import logger
from typing import TYPE_CHECKING

from settings import settings
from anti_bot.cycler import Cycler
from anti_bot.kicker import Kicker
from anti_bot.storage import STORAGE
from anti_bot.detector import Detector
from anti_bot.teleporter import Teleporter
from anti_bot.logins_manager import LoginsManager
from server_communicator.logs_extractor import LogsExtractor

if TYPE_CHECKING:
    from server_communicator.communicator import ServerCommunicator

from anti_bot.models import Coordinates


class AntiBot:
    """Logic of kicking and banning bots

    Attributes:
        _server_comm: Communicator to send command to server
        _kicker: Kicks, bans and unbans users
        _login_manager: Logic of logins for Users (what to do on login)
        _teleporter: Teleports Users
        _cycler: Checks cycles and aggressive runs
        _detector: Detects User-events"""

    def __init__(self,
                 server_comm: 'ServerCommunicator'):
        """Init

        Args:
            server_comm: Communicator to send commands to server with"""

        self._server_comm:  'ServerCommunicator' = server_comm
        self._kicker:        Kicker              = Kicker(server_comm)
        self._login_manager: LoginsManager       = LoginsManager()
        self._teleporter:    Teleporter          = Teleporter(server_comm)
        self._cycler:        Cycler              = Cycler(server_comm)
        self._detector:      Detector            = Detector()

    def check_players(self) -> None:
        """Entrypoint into logic

        Performs tracking of any players, to determine if they logged in spawn area and if they stay there for long
        enough to be considered bots """

        try:
            if not self._cycler.check_cycles():
                return

            if STORAGE.get_tracked_users_count() == 0:
                return

            self.unban_ips(unban_all=False)
            self._request_current_coordinates()

            self._protect_from_login_bursts()

            self._untrack_moved_users()
            self._detector.check_movements()

            self._protect_from_static_users()
            self._protect_from_disconnected_users()
            self._protect_by_ips()

            if self._cycler.is_aggressive():
                self._protect_aggressively()
        except Exception as e:
            logger.exception(e)

    def _request_current_coordinates(self) -> None:
        """Requests current User's coordinates by executing fake teleport with command to server

        Result of this teleportation will be a log with Player's coordinates, which will be picked later

        Notes:
            This command does not make player actually teleport, it seems to have affect even if player is running"""

        tracked_users = STORAGE.get_tracked_users()

        for user in tracked_users:
            command = f'execute at {user.name} run tp {user.name} ~ ~ ~\n'
            self._server_comm.send_to_server(command)

    def _protect_from_login_bursts(self) -> None:
        """Detects and kicks users, logged in a small time-window"""

        users_to_kick = self._detector.detect_login_bursts()
        if len(users_to_kick) > 0:
            threading.Thread(target=self._kicker.kick_due_to_login_bursts, args=(users_to_kick,)).start()

    def _protect_from_static_users(self) -> None:
        """Protects from static Users, which don't want to leave spawn or move at all"""

        static_in_spawn_point, static_in_spawn_area = self._detector.get_static_users()
        self._kicker.kick_due_to_static(static_in_spawn_point=static_in_spawn_point,
                                        static_in_spawn_area=static_in_spawn_area)

    def _protect_from_disconnected_users(self) -> None:
        """Kicks Users, for which we were unable to get coordinates (most likely disconnected shortly)"""

        users_to_kick = self._detector.get_disconnected_users()
        self._kicker.kick_due_to_disconnected(users_to_kick)

    def _protect_aggressively(self) -> None:
        """Logic for aggressive antibot protection"""

        ips_to_ban = self._detector.collect_ips_with_lots_of_kicks()

        if len(ips_to_ban) > 0:
            logger.warning(f'Banning IPs due to aggressive antibot mode! {ips_to_ban}')
        else:
            logger.warning('No IPs to ban (aggressive mode is on)')

        self._kicker.ban_ips(ips_to_ban)

    def _protect_by_ips(self) -> None:
        """Searches for IPs to ban them by different criteria, and bans them"""

        if STORAGE.get_tracked_ips_count() == 0:
            return

        ips_to_ban = self._detector.collect_ips_with_lots_of_kicked_users()
        ips_to_ban = ips_to_ban + self._detector.collect_ips_with_lots_of_kicks_for_single_user()
        if len(ips_to_ban) > 0:
            logger.warning(f'Collected IPs to ban: {ips_to_ban}')
        self._kicker.ban_ips(ips_to_ban)

    def unban_ips(self,
                  unban_all: bool = True) -> None:
        """Unbans IPs

        Args:
            unban_all: If all IPs should be unbanned now, without checking time"""

        if unban_all:
            ips_to_unban = STORAGE.get_tracked_ips()
        else:
            ips_to_unban = self._detector.get_ips_to_unban()

        self._kicker.unban_ips(ips_to_unban)

    def add_user(self,
                 user_uuid: str | None,
                 user_name: str):
        """Saves User for later tracking

        Args:
            user_uuid: UUID of a User
            user_name: User's name"""

        if not user_name:
            logger.error(f'Skipping adding new user {user_name=}, {user_uuid=}, as no user_name is present!')
            return

        STORAGE.add_user(user_name=user_name, user_uuid=user_uuid)

    def save_login_coordinates_and_ip(self,
                                      login_coordinates_str: str,
                                      ip_address: str,
                                      user_name: str):
        """Saves login coordinates and IP for a User, after login event

        Args:
            login_coordinates_str: Login coordinates received from log from server
            ip_address: IP of a User
            user_name: Name of a User"""

        login_coords = self._parse_coords(login_coordinates_str)
        logger.info(f'Parsed on login for {user_name=}: {login_coords=}, {ip_address=}')
        if not login_coords:
            logger.warning('Was not able to parse login coords!')
            self._kicker.kick_by_user_name(user_name)
            return

        self._log_spawn_info(coords=login_coords, user_name=user_name)
        user = STORAGE.get_user(user_name)
        if user:
            user.save_login_data(login_coords, ip_address)

            if not self._login_manager.is_login_allowed(user):
                self._kicker.kick_due_to_login_sanctions(user)
                return

            if self._login_manager.check_same_ip_login(user):
                self._kicker.kick_due_to_same_ip_sanctions(user)
                return

            if self._login_manager.is_too_many_logins(user):
                self._teleporter.teleport_to_spawn(user)
                return

            logger.info(f'User {user.name} is allowed to login initially')

        else:
            logger.warning(f'user {user_name=} is not tracked!')
            self._kicker.kick_by_user_name(user_name)

    def _log_spawn_info(self,
                        coords: Coordinates,
                        user_name: str) -> None:
        """Logs where had User logged in

        Args:
            coords: Coordinates of login
            user_name: Name of a User"""

        try:
            user_in_spawn_area  = self._detector.check_if_coords_are_in_spawn_area(coords)
            user_in_spawn_point = self._detector.check_if_coords_in_spawn_point(coords)
            if not user_in_spawn_area:
                logger.info(f'User {user_name} spawned Outside spawn area')
                return
            if not user_in_spawn_point:
                logger.info(f'User {user_name} spawned in spawn Area')
                return
            else:
                logger.info(f'User {user_name} spawned in spawn Point')
        except Exception as e:
            logger.exception(e)

    def update_last_know_coords(self,
                                user_name: str,
                                coordinates_str: str) -> None:
        """Updates current coordinates for tracked User

        Args:
            user_name: Name of a User
            coordinates_str: Current coordinates of a User"""

        coords = self._parse_coords(coordinates_str)
        logger.debug(f'Parsed coords for {user_name=}: {coords}')
        if not coords:
            logger.warning('Was not able to parse coords!')
            return

        user = STORAGE.get_user(user_name)
        if not user:
            logger.error(f'{user_name=} is not found! Kicking')
            self._kicker.kick_by_user_name(user_name)

        user.last_know_coords = coords

    def become_aggressive(self) -> None:
        """Sets antibot to be aggressive for some period of time"""

        self._cycler.become_aggressive()

    def _parse_coords(self,
                      coords_str) -> Coordinates | None:
        """Parses coordinates into Model

        Args:
            coords_str: Coordinates (x,y,z) a single string
        Returns:
            Coordinates as model"""

        try:
            x, y, z = LogsExtractor.parse_coordinates(coords_str)
            coords  = Coordinates(x, y, z)
            return coords

        except Exception as e:
            logger.error('Error during parsing coordinates!')
            if settings.LOGS_DEPTH != 'INFO':
                logger.exception(e)

    def _untrack_moved_users(self) -> None:
        """Forgets User, who moved or were spawned outside spawn area"""

        tracked_users = STORAGE.get_tracked_users()
        users_to_untrack = []
        for user in tracked_users:
            if user.initial_coordinates:
                if not self._detector.check_if_coords_are_in_spawn_area(user.initial_coordinates):
                    logger.info(f'User {user.name} spawned outside spawn area')
                    users_to_untrack.append(user)
                    continue

            if user.left_spawn:
                logger.info(f'User {user.name} left spawn')
                users_to_untrack.append(user)

        for user in users_to_untrack:
            STORAGE.untrack_user(user)
