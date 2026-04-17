import datetime

from loguru import logger
from typing import Optional

from settings import settings


class Coordinates:
    """Coordinates

    Attributes:
        x: X
        y: Y
        z: Z"""

    def __init__(self,
                 x: int,
                 y: int,
                 z: int):
        """Init

        Args:
            x: X
            y: Y
            z: Z"""

        self.x: int = x
        self.y: int = y
        self.z: int = z

    def __str__(self) -> str:
        """String representation

        Returns:
            String representation"""

        return f'x={self.x}, y={self.y}, z={self.z}'

    def __repr__(self) -> str:
        """String representation

        Returns:
            String representation"""

        return self.__str__()


class TrackedUser:
    """Single User to keep track of (check if bot or not)

    Attributes:
        login_events: Timestamp of login and Coordinates of login place
        login_time: Time of last know login
        name: Name, as is in Minecraft
        uuid: UUID from Minecraft
        ip: IP
        kicked_count: Number of kicks this user has
        kicked_at: Time when kicked last time
        login_allowed_at: Time when next login is allowed
        relogin_addition: Seconds to add to login_allowed_at, after each new kick
        initial_coordinates: Coordinates at which User logged in
        last_know_coords: Last known coordinates
        moved: True, in case User moved (initial coords != current coords at least once)
        left_spawn: True, if user left spawn area at least once"""

    def __init__(self):
        self.login_events: dict[float: Coordinates] = {}
        self.login_time:   datetime.datetime = datetime.datetime.now()
        self.name:         str               = ''
        self.uuid:         str               = ''
        self.ip:           str               = ''
        self.kicked_count:     int          = 0
        self.kicked_at:        float | None = None
        self.login_allowed_at: float | None = None
        self.relogin_addition: int          = 20
        self.initial_coordinates: Optional[Coordinates] = None
        self.last_know_coords:    Optional[Coordinates] = None
        self.moved:      bool = False
        self.left_spawn: bool = False

    def get_time_since_login(self) -> float:
        """Gets POSIX time since user logged in (seconds since epoch)

        Returns:
            POSIX time since user logged in"""

        time_since_login = datetime.datetime.now().timestamp() - self.login_time.timestamp()
        return time_since_login

    def kicked_event(self,
                     login_again_after: int = 60,
                     add_relogin_extra: bool = False) -> None:
        """Saves data, related to kick

        Args:
            login_again_after: Seconds to allow login again
            add_relogin_extra: If to add additional time for next login"""

        self.kicked_count += 1
        self.kicked_at = datetime.datetime.now().timestamp()

        if add_relogin_extra:
            addition = self.relogin_addition * self.kicked_count
        else:
            addition = 0
        # 1 in case of fast re-login, to extend time
        self.login_allowed_at = self.kicked_at + login_again_after + addition + 1

    def get_seconds_till_login_allowed(self) -> int:
        """Gets seconds till next login is allowed

        Returns:
            Seconds till next login is allowed, or 1 in case of some error"""

        if not self.login_allowed_at:
            logger.error(f'User {self.name} does not have next login allowed time!')
            return 1

        login_allowed_after = int(self.login_allowed_at - datetime.datetime.now().timestamp())
        return login_allowed_after

    def update_login_time(self) -> None:
        """Updates login time"""

        self.login_time = datetime.datetime.now()

    def save_login_data(self,
                        login_coords: Coordinates,
                        ip: str | None) -> None:
        """Save login data

        Args:
            login_coords: Coordinates of login place
            ip: IP of the User if was able to parse"""

        self.moved               = False
        self.left_spawn          = False
        self.last_know_coords    = login_coords
        self.initial_coordinates = login_coords
        self.ip                  = ip
        logger.debug(f'Saved login coords for {self.name}')

        self._update_login_events(login_coords)

    def _update_login_events(self,
                             login_coords: Coordinates) -> None:
        """Updates login collection to save current login time and place

        Args:
            login_coords: Coordinates of login place"""

        self._remove_old_login_events()
        current_ts = datetime.datetime.now().timestamp()
        self.login_events[current_ts] = login_coords

    def _remove_old_login_events(self) -> None:
        """Removes logins, that are older than tracked window"""

        if len(self.login_events) == 0:
            logger.debug(f'No old login events to remove for User {self.name}')
            return

        too_old_login_events_time_stamps = []
        current_ts = datetime.datetime.now().timestamp()
        for login_time_stamp, previous_login_coords in self.login_events.items():
            event_is_old = abs(current_ts - login_time_stamp) > settings.antibot.LOGINS_PERIOD_SEC
            if event_is_old:
                too_old_login_events_time_stamps.append(login_time_stamp)

        logger.debug(f'Removing old login events with TS: {too_old_login_events_time_stamps}')
        for ts in too_old_login_events_time_stamps:
            if ts in self.login_events:
                del self.login_events[ts]


class TrackedIp:
    """IP that was kicked

    Attributes:
        ip: IP that was kicked
        kicks_counter: Overall number of kicks on this IP (any players, all times combined)
        banned: True, if IP was already banned
        banned_at: Timestamp when was banned
        unban_me_at: Timestamp when should be unbanned
        kicked_user_names: User, that was kicked on that IP"""

    def __init__(self,
                 ip: str,
                 kicked_user_name: str):
        """Init

        Args:
            ip: IP that was kicked
            kicked_user_name: User, that was kicked on that IP"""

        self.ip:                str  = ip
        self.kicks_counter:     int  = 1

        self.banned:            bool            = False
        self.ban_counter:       int             = 0
        self.banned_at:         Optional[float] = None
        self.unban_me_at:       Optional[float] = None

        self.kicked_user_names: list[str] = []
        self.kicked_user_names.append(kicked_user_name)

    def add_kicked_user(self,
                        user_name: str) -> None:
        """Saves user to kicked records and updates kicked counter

        Args:
            user_name: User that was kicked"""

        if user_name not in self.kicked_user_names:
            self.kicked_user_names.append(user_name)
        self.kicks_counter += 1

    def get_next_ban_time(self) -> str:
        """Creates a string of upcoming ban time

        Returns:
            String of upcoming ban time"""

        next_ban_counter = self.ban_counter + 1
        hours   = settings.antibot.BAN_IP_FOR_HOURS * next_ban_counter
        minutes = settings.antibot.BAN_IP_FOR_MINUTES * next_ban_counter
        seconds = settings.antibot.BAN_IP_FOR_SECONDS * next_ban_counter
        expected_ban_time = f'Baned for Hours {hours} Minutes {minutes} Seconds {seconds}'
        return expected_ban_time

    def save_ban(self) -> None:
        """Saves ban status and time"""

        self.banned = True
        self.ban_counter += 1

        now              = datetime.datetime.now()
        self.banned_at   = now.timestamp()
        unban_at         = now + datetime.timedelta(hours=settings.antibot.BAN_IP_FOR_HOURS * self.ban_counter,
                                                    minutes=settings.antibot.BAN_IP_FOR_MINUTES * self.ban_counter,
                                                    seconds=settings.antibot.BAN_IP_FOR_SECONDS * self.ban_counter)
        self.unban_me_at = unban_at.timestamp()

    def save_unban(self) -> None:
        """Saves unban status"""

        self.banned      = False
        self.banned_at   = None
        self.unban_me_at = None

    def __str__(self):
        """Str"""

        return self.ip

    def __repr__(self):
        """Repr"""

        return self.__str__()
