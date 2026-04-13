import datetime

from typing import Optional

from loguru import logger


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


class UserToCheck:
    """Single User to keep track of (check if bot or not)

    Attributes:
        login_time: Time of last know login
        name: Name, as is in Minecraft
        uuid: UUID from Minecraft
        ip: IP
        kicked_count: Number of kicks this user has
        kicked_at: Time when kicked last time
        login_allowed_at: Time when next login is allowed
        relogin_addition: Seconds to add to login_allowed_at, after each new kick
        initial_coordinates: Coordinates at which User logged in
        current_coordinates: Last known coordinates
        moved: True, in case User moved (initial coords != current coords at least once)
        left_spawn: True, if user left spawn area at least once"""

    def __init__(self):
        self.login_time:   datetime.datetime = datetime.datetime.now()
        self.name:         str               = ''
        self.uuid:         str               = ''
        self.ip:           str               = ''
        self.kicked_count:     int          = 0
        self.kicked_at:        float | None = None
        self.login_allowed_at: float | None = None
        self.relogin_addition: int          = 20
        self.initial_coordinates: Optional[Coordinates] = None
        self.current_coordinates: Optional[Coordinates] = None
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

    def is_login_allowed(self) -> bool:
        """Checks if this User is allowed to log in"""

        if self.kicked_count < 1:
            return True

        if self.login_allowed_at is not None:
            if datetime.datetime.now().timestamp() > self.login_allowed_at:
                return True
            return False
        else:
            return True

    def get_seconds_till_login_allowed(self) -> int:
        """Gets seconds till next login is allowed

        Returns:
            Seconds till next login is allowed, or 1 in case of some error"""

        if not self.login_allowed_at:
            logger.error(f'User {self.name} does not have next login allowed time!')
            return 1

        login_allowed_after = int(self.login_allowed_at - datetime.datetime.now().timestamp())
        return login_allowed_after


class KickedIp:
    """IP that was kicked

    Attributes:
        ip: IP that was kicked
        kicks_counter: Overall number of kicks on this IP (any players, all times combined)
        banned: True, if IP was already banned
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
        self.banned:            bool = False
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

    def __str__(self):
        """Str"""

        return self.ip

    def __repr__(self):
        """Repr"""

        return self.__str__()
