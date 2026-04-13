import time
import datetime
import threading

from loguru import logger
from collections import defaultdict
from typing import TYPE_CHECKING, Optional

from server_communicator.logs_extractor import LogsExtractor

if TYPE_CHECKING:
    from server_communicator.communicator import ServerCommunicator

from settings import settings
from anti_bot.models import UserToCheck, Coordinates, KickedIp


class AntiBot:
    """Logic of kicking and banning bots

    Attributes:
        _kicked_users: user_name and User-model for users, that were kicked
        _kicked_ips: IPs of kicked users
        _tracked_users: user_name and User-model for Users, that AntiBot is currently tracking

        _server_comm: Communicator to send command to server

        _run_every: every N cycle to execute AntiBot logic (every other cycles will be skipped)
        _current_cycle: Current cycle to track when to execute AntiBot logic

        _aggressive: If sett to True, AntiBot will get to aggressive mode, which will cause it bans
        _aggressive_start_at: Timestamp of when aggressive mode was started (it will default to normal after time)"""

    def __init__(self,
                 server_comm: 'ServerCommunicator'):
        """Init

        Args:
            server_comm: Communicator to send comands to server with"""

        self._kicked_users:  dict[str, UserToCheck] = {}
        self._kicked_ips:    dict[str, KickedIp]   = {}
        self._tracked_users: dict[str, UserToCheck] = {}

        self._server_comm:  'ServerCommunicator' = server_comm

        self._run_every:     int = settings.antibot.RUN_EVERY
        self._current_cycle: int = 0

        self._aggressive:          bool            = False
        self._aggressive_start_at: Optional[float] = None

    def check_players(self) -> None:
        """Entrypoint into logic

        Performs tracking of any players, to determine if they logged in spawn area and if they stay there for long
        enough to be considered bots """

        if not self._check_cycles():
            return

        if len(self._tracked_users) == 0:
            return

        self._request_current_coordinates()

        self._protect_from_login_bursts()

        self._untrack_moved_users()
        self._check_movements()

        self._protect_from_static_users()
        self._protect_from_disconnected_users()
        self._protect_by_ips()

        if self._aggressive:
            self._protect_aggressively()

    def _check_cycles(self) -> bool:
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

    def _turn_aggressive_mode_off(self) -> None:
        """Turns off aggressive mode"""

        self._aggressive          = False
        self._aggressive_start_at = None
        self._run_every           = settings.antibot.RUN_EVERY

    def _request_current_coordinates(self) -> None:
        """Requests current User's coordinates by executing fake teleport with command to server

        Result of this teleportation will be a log with Player's coordinates, which will be picked later

        Notes:
            This command does not make player actually teleport, it seems to have affect even if player is running"""

        for user in self._tracked_users.values():
            command = f'execute at {user.name} run tp {user.name} ~ ~ ~\n'
            self._server_comm.send_to_server(command)

    def _protect_from_login_bursts(self) -> None:
        """Detects and kicks users, logged in a small time-window"""

        suspicious_login_groups = self._detect_login_bursts()
        if len(suspicious_login_groups) > 0:
            threading.Thread(target=self._kick_with_delay, args=(suspicious_login_groups,)).start()

    def _detect_login_bursts(self) -> dict[float, list[UserToCheck]]:
        """Detects logins in a small time-window. Window is fixed

        Method automatically groups Users, that were logged in a small time-widow, based on LOGINS_THRESHOLD and
        WINDOW_SIZE_SECONDS, so returned Users are intended to be kicked

        Returns:
            dict[login_time_stamp: list[UserToCheck, UserToCheck]]"""

        buckets = defaultdict(list)

        for user in self._tracked_users.values():
            # Get the 'bucket' ID (integer division of timestamp)
            # This groups users into fixed blocks (e.g., 0-3s, 3-6s, 6-9s)
            timestamp_key = int(user.login_time.timestamp() // settings.antibot.WINDOW_SIZE_SECONDS)
            buckets[timestamp_key].append(user)

        # Filter for groups that meet your 'Bot Attack' threshold
        suspicious_groups: dict[float, list[UserToCheck]] = {
            ts: users for ts, users in buckets.items()
            if len(users) >= settings.antibot.LOGINS_THRESHOLD
        }

        return suspicious_groups

    def _kick_with_delay(self,
                         suspicious_login_groups: dict[float, list[UserToCheck]]) -> None:
        """Kicks Users with some delay between kicks

        Args:
            suspicious_login_groups: Users to kick"""

        time.sleep(1)
        for group in suspicious_login_groups.values():
            for user in group:
                if not user.initial_coordinates or not user.ip:
                    self._wait_for_data(user)
                time.sleep(0.05)
                self._kick_user(user=user, reason='Are you a bot?', add_relogin_extra=True)

    def _wait_for_data(self,
                       user: UserToCheck) -> None:
        """Waits a bit for receiving data for user

        Args:
            user: User to wait for"""

        for _ in range(20):
            # Check if we have what we need
            if user.initial_coordinates and user.ip:
                return  # Exit early because we have the data

            time.sleep(1)

    def _protect_from_static_users(self) -> None:
        """Protects from static Users, which don't want to leave spawn or move at all"""

        static_in_spawn_point, static_in_spawn_area = self._get_static_users()
        for user in static_in_spawn_point:
            self._kick_user(user,
                            reason='Please leave spawn point',
                            login_again_after=settings.antibot.KICK_COOLDOWN_STATIC_POINT_SECONDS)
            time.sleep(0.05)
        for user in static_in_spawn_area:
            self._kick_user(user,
                            reason='Please leave spawn area',
                            login_again_after=settings.antibot.KICK_COOLDOWN_STATIC_AREA_SECONDS)
            time.sleep(0.05)

    def _get_static_users(self) -> tuple[list[UserToCheck], list[UserToCheck]]:
        """Collects Users that are considered static

        Notes:
            Considers Users as static if they are standing in spawn point or if they don't leave spawn area. These
            checks are based on different time window - less time is given to Users, that are standing still in
            spawn point, while Users in spawn area have more time before been considered static (aka bot)
        Returns:
            Users, static in spawn point and in spawn area"""

        static_in_spawn_point = []
        static_in_spawn_area  = []

        for user in self._tracked_users.values():

            if not user.current_coordinates:
                logger.debug(f'User {user.name} does not yet have current coordinates')
                continue

            if self._check_if_user_in_spawn_point_too_long(user):
                static_in_spawn_point.append(user)
                continue

            if self._check_if_user_in_spawn_area_too_long(user):
                static_in_spawn_area.append(user)

        return static_in_spawn_point, static_in_spawn_area

    def _check_if_user_in_spawn_point_too_long(self,
                                               user: UserToCheck) -> bool:
        """Checks if User is in spawn point for too long

        Args:
            user: User to check
        Returns:
            True, if User is in spawn point for too long without moving away from it"""

        if self._check_if_coords_in_spawn_point(user.current_coordinates) and not user.moved:
            time_since_login = user.get_time_since_login()
            if time_since_login > settings.antibot.KICK_STATIC_IN_SPAWN_POINT_AFTER_SEC:
                logger.debug(f'User {user.name} in spawn point for too long and will be kicked')
                return True
            return False
        else:
            return False

    def _check_if_user_in_spawn_area_too_long(self,
                                              user: UserToCheck) -> bool:
        """Checks if User is in spawn area for too long

        Args:
            user: User to check
        Returns:
            True, if User is in spawn area for too long without leaving it"""

        if self._check_if_coords_are_in_spawn_area(user.current_coordinates) and not user.left_spawn:
            time_since_login = user.get_time_since_login()
            if time_since_login > settings.antibot.KICK_STATIC_IN_SPAWN_AREA_AFTER_SEC:
                logger.debug(f'User {user.name} in spawn area for too long and will be kicked')
                return True
            return False
        return False

    def _protect_from_disconnected_users(self) -> None:
        """Kicks Users, for which we were unable to get coordinates (most likely disconnected shortly)"""

        users_to_kick = []
        for user in self._tracked_users.values():
            time_since_login = user.get_time_since_login()
            logged_long_ago = time_since_login > settings.antibot.KICK_STATIC_IN_SPAWN_AREA_AFTER_SEC
            if logged_long_ago and not user.initial_coordinates:
                logger.warning(f'User {user.name} will be kicked as no initial coords present')
                users_to_kick.append(user)
            if user.initial_coordinates and logged_long_ago and not user.current_coordinates:
                logger.warning(f'User {user.name} will be kicked as no current coords present')
                users_to_kick.append(user)

        for user in users_to_kick:
            self._kick_user(user, reason='Unable to get your coordinates. Try to login again in a minute')
            time.sleep(0.05)

    def _protect_aggressively(self) -> None:
        """Logic for aggressive antibot protection"""

        ips_to_ban = self._collect_ips_to_ban()

        if len(ips_to_ban) > 0:
            logger.warning(f'Banning IPs due to aggressive antibot mode! {ips_to_ban}')
        else:
            logger.warning('No IPs to ban (aggressive mode is on)')

        self._ban_ips(ips_to_ban)

    def _collect_ips_to_ban(self) -> list[KickedIp]:
        """Collects IPs to ban them

        Returns:
            IPs to ban"""

        ips_to_ban = []
        for kicked_ip in self._kicked_ips.values():
            if kicked_ip.banned:
                continue
            if kicked_ip.kicks_counter > settings.antibot.AGGRESSIVE_BAN_IP_AFTER_IP_KICKED_TIMES:
                ips_to_ban.append(kicked_ip)
        return ips_to_ban

    def _ban_ips(self,
                 ips_to_ban: list[KickedIp]) -> None:
        """Bans provided IPs

        Args:
            ips_to_ban: IPs to ban"""

        for ip in ips_to_ban:
            logger.warning(f'Banning IP: {ip.ip}')
            command = f'ban-ip {ip.ip}\n'
            try:
                self._server_comm.send_to_server(command)
                ip.banned = True
                time.sleep(0.05)
            except Exception as e:
                logger.exception(e)

    def _protect_by_ips(self) -> None:
        """Searches for IPs to ban them by different criteria, and bans them"""

        if len(self._kicked_ips) == 0:
            return

        ips_to_ban = self._collect_ips_with_lots_of_kicked_users()
        ips_to_ban = ips_to_ban + self._collect_ips_with_lots_of_kicks_for_single_user()
        if len(ips_to_ban) > 0:
            logger.warning(f'Collected IPs to ban: {ips_to_ban}')
        self._ban_ips(ips_to_ban)

    def _collect_ips_with_lots_of_kicked_users(self) -> list[KickedIp]:
        """Collects IPs, from which there were too many kicks for different users

        Returns:
            list with IPs to ban"""

        ips_to_ban = []
        for kicked_ip in self._kicked_ips.values():
            if kicked_ip.banned:
                continue

            kicked_users = {}
            for user in self._kicked_users.values():
                if user.ip == kicked_ip.ip and user.kicked_count > 0:
                    kicked_users[user.name] = user

            for user in self._tracked_users.values():
                if user.ip == kicked_ip.ip and user.kicked_count > 0:
                    kicked_users[user.name] = user

            if len(kicked_users) >= settings.antibot.BAN_IP_IF_KICKED_USERS_NUMBER and not kicked_ip.banned:
                ips_to_ban.append(kicked_ip)

        if ips_to_ban:
            logger.warning(f'Collected IPs to kick due to lots of kicked users: {ips_to_ban}')
        return ips_to_ban

    def _collect_ips_with_lots_of_kicks_for_single_user(self) -> list[KickedIp]:
        """Collects IPs, from which there is a user with lots of kicks"""

        ips_to_ban = []
        for ip in self._kicked_ips.values():
            if ip.banned:
                continue

            unique_users = set(ip.kicked_user_names)
            for user_name in unique_users:
                if user_name in self._kicked_users:
                    user = self._kicked_users[user_name]
                    if user.kicked_count >= settings.antibot.BAN_IP_IF_SINGLE_USER_KICKED_NUMBER and not ip.banned:
                        ips_to_ban.append(ip)

        if ips_to_ban:
            logger.warning(f'Collected IPs to kick due to lots of logins for single user: {ips_to_ban}')
        return ips_to_ban

    def add_user(self,
                 user_uuid: str | None,
                 user_name: str):
        """Saves User for later tracking

        Args:
            user_uuid: UUID of a User
            user_name: User's name"""

        if not user_name:
            logger.error(f'Skipping adding new user {user_name=}, {user_uuid=}')
            return

        if user_name not in self._tracked_users:
            if user_name in self._kicked_users:
                self._restore_previously_tracked_user(user_name)
            else:
                self._create_new_user_to_track(user_name=user_name, user_uuid=user_uuid)

        else:
            self._update_user_to_track(user_name=user_name, user_uuid=user_uuid)

    def _restore_previously_tracked_user(self,
                                         user_name: str) -> None:
        """Restores User, that was previously tracked but was kicked, to track this User again

        Args:
            user_name: Name of a User"""

        user            = self._kicked_users[user_name]
        user.login_time = datetime.datetime.now()
        self._tracked_users[user_name] = user

        logger.debug(f'Tracking kicked user {user_name} once again')

    def _create_new_user_to_track(self,
                                  user_name: str,
                                  user_uuid: str) -> None:
        """Creates new User to track

        Args:
            user_name: Name of a User
            user_uuid: UUID of a User"""

        logger.debug(f'Creating new tracked_user {user_name=}')
        user      = UserToCheck()
        user.uuid = user_uuid
        user.name = user_name
        self._tracked_users[user_name] = user

    def _update_user_to_track(self,
                              user_name: str,
                              user_uuid: str) -> None:
        """Updates User's data, for User that is already tracked

        Args:
            user_name: Name of a User
            user_uuid: UUID of a User"""

        logger.debug(f'User already tracked {user_name=}')
        user = self._tracked_users[user_name]
        if user.uuid != user_uuid and user_uuid is not None:
            logger.warning(f'UUID of player {user.name} ({user_uuid}) is not what we initially saved ({user.uuid})')
            user.uuid = user_uuid
        user.login_time = datetime.datetime.now()

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
            logger.warning('Was not able to login coords!')
            return

        if user_name in self._tracked_users:
            user                     = self._tracked_users[user_name]
            user.initial_coordinates = login_coords
            user.ip                  = ip_address
            logger.debug(f'Saved login coords for {user_name}')

            if not user.is_login_allowed():
                login_again_after = user.get_seconds_till_login_allowed()
                reason = f'Next login is allowed after {login_again_after} seconds. Wait a bit'
                threading.Thread(target=self._kick_on_start, args=(user, reason)).start()

            self._check_same_ip_login(user)

        else:
            logger.warning(f'user {user_name=} is not tracked!')

    def _check_same_ip_login(self,
                             user: UserToCheck) -> None:
        """Kicks user, in case this IP already have another account logged in, that was kicked

        Args:
            user: User to check for kick"""

        # Already tracking at least one more user
        if user.ip and len(self._tracked_users) > 1:
            for another_user in self._tracked_users.values():
                already_tracking_user_from_same_ip = another_user.ip == user.ip and another_user.name != user.name
                if already_tracking_user_from_same_ip:
                    login_again_after = user.get_seconds_till_login_allowed()
                    reason = f'You already logged in from another account. Wait {login_again_after} seconds'
                    threading.Thread(target=self._kick_on_start, args=(user, reason,)).start()

    def _kick_on_start(self,
                       user: UserToCheck,
                       reason: str) -> None:
        """Kicks user, that is not yet allowed to login

        Args:
            user: User to kick
            reason: Reason for kick"""

        if not user.initial_coordinates or not user.ip:
            self._wait_for_data(user)

        time.sleep(0.05)
        login_again_after = user.get_seconds_till_login_allowed()
        self._kick_user(user,
                        reason=reason,
                        login_again_after=login_again_after,
                        save_ip=False,
                        update_kick_counter=False)

    def update_current_coordinates(self,
                                   user_name: str,
                                   coordinates_str: str) -> None:
        """Updates current coordinates for tracked User

        Args:
            user_name: Name of a User
            coordinates_str: Current coordinates of a User"""

        if user_name in self._tracked_users:
            coords = self._parse_coords(coordinates_str)
            logger.debug(f'Parsed coords for {user_name=}: {coords}')
            if not coords:
                logger.warning('Was not able to parse coords!')
                return

            user = self._tracked_users[user_name]
            user.current_coordinates = coords
        else:
            if user_name not in self._kicked_users:
                logger.debug(f'Attempt to get coords for user, that is not tracked: {user_name}')

    def become_aggressive(self) -> None:
        """Sets antibot to be aggressive for some period of time"""

        self._aggressive          = True
        self._run_every           = settings.antibot.AGGRESSIVE_RUN_EVERY
        self._aggressive_start_at = datetime.datetime.now().timestamp()

        command = 'say Antibot is now in aggressive mode! Try not to login for a few minutes not to get banned\n'
        self._server_comm.send_to_server(command)

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
            logger.exception(e)

    def _check_movements(self) -> None:
        """Checks all Users for any movements"""

        for user in self._tracked_users.values():
            self._check_user_movement(user)

    def _check_user_movement(self,
                             user: UserToCheck) -> None:
        """Checks if User moved at all and leave spawn

        Args:
            user: User to check"""

        if not user.current_coordinates or not user.initial_coordinates:
            return

        if user.initial_coordinates.x != user.current_coordinates.x \
                or user.initial_coordinates.z != user.current_coordinates.z:
            user.moved = True
            logger.debug(f'User {user.name} moved')

        if not self._check_if_coords_are_in_spawn_area(user.current_coordinates):
            user.left_spawn = True
            logger.debug(f'User {user.name} is not in spawn are')

    def _check_if_coords_in_spawn_point(self,
                                        coords: Coordinates) -> bool:
        """Checks if provided coordinates are in spawn point

        Notes:
            Only check x and z, does not check height
        Args:
            coords: Coords to check
        Returns:
            True, in case coordinates (x,z) are in spawn point"""

        x_spawn = settings.antibot.SPAWN_POINT_X
        z_spawn = settings.antibot.SPAWN_POINT_Z
        in_x = x_spawn - 1 <= coords.x <= x_spawn + 1
        in_z = z_spawn - 1 <= coords.z <= z_spawn + 1
        if in_x and in_z:
            return True
        return False

    def _check_if_coords_are_in_spawn_area(self,
                                           coords: Coordinates) -> bool:
        """Checks if provided coordinates are in spawn area

        Notes:
            Only checks x and z, does not check height
        Args:
            coords: Coords to check
        Returns:
            True, in case coords are in spawn area"""

        x_in = False
        z_in = False
        if settings.antibot.SPAWN_X_MIN <= coords.x <= settings.antibot.SPAWN_X_MAX:
            x_in = True
        if settings.antibot.SPAWN_Z_MIN <= coords.z <= settings.antibot.SPAWN_Z_MAX:
            z_in = True

        coords_in_spawn_area = x_in and z_in
        return coords_in_spawn_area

    def _untrack_moved_users(self) -> None:
        """Forgets User, who moved or were spawned outside spawn area"""

        users_to_untrack = []
        for user in self._tracked_users.values():
            if user.initial_coordinates:
                if not self._check_if_coords_are_in_spawn_area(user.initial_coordinates):
                    logger.info(f'User {user.name} spawned outside spawn area')
                    users_to_untrack.append(user)
                    continue

            if user.left_spawn:
                logger.info(f'User {user.name} left spawn')
                users_to_untrack.append(user)

        for user in users_to_untrack:
            if user.name in self._tracked_users:
                del self._tracked_users[user.name]

    def _kick_user(self,
                   user: UserToCheck,
                   reason: str,
                   login_again_after: int = settings.antibot.KICK_COOLDOWN_DEFAULT_SECONDS,
                   add_relogin_extra: bool = False,
                   update_kick_counter: bool = True,
                   save_ip: bool = True) -> None:
        """Kicks users and saves IP of a kicked user

        Args:
            user: User to kick
            reason: Reason to kick
            login_again_after: Seconds to allow user to login again
            add_relogin_extra: If we should add additional several seconds for wait cooldown before relogin
            update_kick_counter: If set to False, kick will be made in soft manner - without updating counter
            save_ip: If user should be saved in kicked IPs"""

        logger.info(f'Kicking {user.name}, {reason=}')
        try:
            command = f'kick {user.name} {reason}\n'
            self._server_comm.send_to_server(command)
            if update_kick_counter:
                user.kicked_event(login_again_after, add_relogin_extra)
        except Exception as e:
            logger.error(f'Was not able to kick user {user.name}')
            logger.exception(e)

        self._replace_user_to_kicked(user)
        if save_ip:
            self._save_kicked_ip(user)

    def _replace_user_to_kicked(self,
                                user: UserToCheck) -> None:
        """Replaces user from tracked to kicked

        Args:
            user: User to replace"""

        if user.name in self._tracked_users:
            del self._tracked_users[user.name]
            logger.debug(f'Kicked User {user.name} is removed from tracked users!')
        else:
            logger.error(f'Kicked User {user.name} was not tracked!')

        self._kicked_users[user.name] = user

    def _save_kicked_ip(self,
                        user: UserToCheck) -> None:
        """Saves IP as kicked one

        Args:
            user: User that was kicked to save their IP"""

        if user.ip:
            if user.ip not in self._kicked_ips:
                kicked_ip = KickedIp(ip=user.ip, kicked_user_name=user.name)
            else:
                kicked_ip = self._kicked_ips[user.ip]
                kicked_ip.add_kicked_user(user.name)
            self._kicked_ips[kicked_ip.ip] = kicked_ip
            logger.debug(f'Kicked IPs: {self._kicked_ips.values()}')
        else:
            logger.warning(f'User {user.name} did not have an IP!')
