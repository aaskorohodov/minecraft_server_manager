import threading

from loguru import logger
from typing import Optional

from anti_bot.models import TrackedUser, TrackedIp


class Storage:
    """Stores Users and IPs

    Attributes:
        _not_tracked_users: Users that are not currently tracked because of kick or because considered not bots
        _tracked_users: Users that are currently tracked
        _tracked_ips: IPs that were kicked, so we are tracking them"""

    def __init__(self):
        """Init"""

        self._not_tracked_users: dict[str, TrackedUser] = {}
        self._tracked_users:     dict[str, TrackedUser] = {}
        self._tracked_ips:        dict[str, TrackedIp]  = {}

        self._lock = threading.RLock()

    def get_user(self,
                 user_name: str) -> TrackedUser | None:
        """Gets User by user_name from all possible collections, in case User exists

        Args:
            user_name: Name of the User to search for
        Returns:
            User if such was found"""

        with self._lock:
            user: Optional[TrackedUser] = None
            if user_name in self._tracked_users:
                user = self._tracked_users[user_name]
            elif user_name in self._not_tracked_users:
                user = self._not_tracked_users[user_name]

        return user

    def untrack_user(self,
                     user: TrackedUser) -> None:
        """Stops tracking User by placing them in _not_tracked_users

        Args:
            user: User to replace"""

        with self._lock:
            if user.name in self._tracked_users:
                del self._tracked_users[user.name]
                logger.debug(f'User {user.name} is removed from tracked users!')
            else:
                logger.error(f'User {user.name} was not tracked, no User to delete from _tracked_users!')

            self._not_tracked_users[user.name] = user

    def save_kicked_ip(self,
                       user: TrackedUser) -> None:
        """Saves IP as kicked one

        Args:
            user: User that was kicked to save their IP"""

        with self._lock:
            if user.ip:
                if user.ip not in self._tracked_ips:
                    kicked_ip = TrackedIp(ip=user.ip, kicked_user_name=user.name)
                else:
                    kicked_ip = self._tracked_ips[user.ip]
                    kicked_ip.add_kicked_user(user.name)
                self._tracked_ips[kicked_ip.ip] = kicked_ip
                logger.debug(f'Kicked IPs: {self._tracked_ips.values()}')
            else:
                logger.warning(f'User {user.name} did not have an IP!')

    def drop_kick_counter(self,
                          ip: TrackedIp) -> None:
        """Drops counters for kicks for Users on provided IP

        Args:
            ip: IP to drop counters for"""

        with self._lock:
            all_users = self.get_all_users()
            for user in all_users:
                if user.ip == ip.ip:
                    user.kicked_count = 0

    def get_tracked_users_count(self) -> int:
        """Counts number of currently tracked users

        Returns:
            Number of currently tracked users"""

        with self._lock:
            tracked_users = len(self._tracked_users)
        return tracked_users

    def get_tracked_ips_count(self) -> int:
        """Counts number of currently tracked IPs

        Returns:
            Number of currently tracked IPs"""

        with self._lock:
            tracked_ips = len(self._tracked_ips)
        return tracked_ips

    def are_there_another_tracked_users_with_same_ip(self,
                                                     user: TrackedUser) -> bool:
        """Checks if there are other Users, that are currently tracked, connected from the same IP

        Args:
            user: User, for which we are looking for other connections from the same IP
        Returns:
            True, in case there are other Users, connected from the same IP, that are currently tracked"""

        with self._lock:
            for some_user in self._tracked_users.values():
                if some_user.ip == user.ip and some_user.name != user.name:
                    return True
            return False

    def get_tracked_users(self) -> list[TrackedUser]:
        """Gets currently tracked Users

        Returns:
            currently tracked Users"""

        with self._lock:
            tracked_users = list(self._tracked_users.values())
            return tracked_users

    def get_not_tracked_users(self) -> list[TrackedUser]:
        """Gets currently NOT tracked Users

        Returns:
            currently tracked Users"""

        with self._lock:
            not_tracked_users = list(self._not_tracked_users.values())
            return not_tracked_users

    def get_all_users(self) -> list[TrackedUser]:
        """Gets both tracked and not tracked Users"""

        with self._lock:
            tracked_users     = self.get_tracked_users()
            not_tracked_users = self.get_not_tracked_users()
            overall_users     = tracked_users + not_tracked_users
            return overall_users

    def get_tracked_ips(self) -> list[TrackedIp]:
        """Gets IPs that we are tracking

        Returns:
            IPs that we are tracking"""

        with self._lock:
            tracked_ips = list(self._tracked_ips.values())
            return tracked_ips

    def add_user(self,
                 user_uuid: str,
                 user_name: str):
        """Saves User for later tracking

        Args:
            user_uuid: UUID of a User
            user_name: User's name"""

        with self._lock:
            if user_name in self._tracked_users:
                self._update_user_to_track(user_name=user_name, user_uuid=user_uuid)
            else:
                if user_name in self._not_tracked_users:
                    self._restore_previously_tracked_user(user_name)
                else:
                    self._create_new_user_to_track(user_name=user_name, user_uuid=user_uuid)

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
        user.update_login_time()

    def _restore_previously_tracked_user(self,
                                         user_name: str) -> None:
        """Restores User, that was previously tracked but was kicked, to track this User again

        Args:
            user_name: Name of a User"""

        with self._lock:
            user = self._not_tracked_users[user_name]
            user.update_login_time()
            self._tracked_users[user_name] = user

            logger.debug(f'Tracking kicked user {user_name} once again')

    def _create_new_user_to_track(self,
                                  user_name: str,
                                  user_uuid: str) -> None:
        """Creates new User to track

        Args:
            user_name: Name of a User
            user_uuid: UUID of a User"""

        with self._lock:
            logger.debug(f'Creating new tracked_user {user_name=}')
            user      = TrackedUser()
            user.uuid = user_uuid
            user.name = user_name
            self._tracked_users[user_name] = user


STORAGE = Storage()
"""Instance with data about Users and IPs. Must be a single instance"""
