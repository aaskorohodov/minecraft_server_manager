import datetime
from collections import defaultdict

from loguru import logger

from anti_bot.models import TrackedUser, Coordinates, TrackedIp
from anti_bot.storage import STORAGE
from settings import settings


class Detector:
    """Logic, related to detecting bots"""

    def detect_login_bursts(self) -> list[TrackedUser]:
        """Detects logins in a small time-window. Window is fixed

        Method automatically groups Users, that were logged in a small time-widow, based on LOGINS_THRESHOLD and
        WINDOW_SIZE_SECONDS, so returned Users are intended to be kicked

        Returns:
            Users that are considered bots"""

        tracked_users = STORAGE.get_tracked_users()
        buckets = defaultdict(list)

        for user in tracked_users:
            # Get the 'bucket' ID (integer division of timestamp)
            # This groups users into fixed blocks (e.g., 0-3s, 3-6s, 6-9s)
            timestamp_key = int(user.login_time.timestamp() // settings.antibot.WINDOW_SIZE_SECONDS)
            buckets[timestamp_key].append(user)

        # Filter for groups that meet 'Bot Attack' threshold
        suspicious_groups: dict[float, list[TrackedUser]] = {
            ts: users for ts, users in buckets.items()
            if len(users) >= settings.antibot.LOGINS_THRESHOLD
        }

        users_to_kick = []
        for users in suspicious_groups.values():
            for user in users:
                if user not in users_to_kick:
                    users_to_kick.append(user)

        return users_to_kick

    def get_disconnected_users(self) -> list[TrackedUser]:
        """Kicks Users, for which we were unable to get coordinates (most likely disconnected shortly)

        Returns:
            List with Users to kick"""

        tracked_users = STORAGE.get_tracked_users()
        users_to_kick = []
        for user in tracked_users:
            time_since_login = user.get_time_since_login()
            logged_long_ago  = time_since_login > settings.antibot.KICK_STATIC_IN_SPAWN_AREA_AFTER_SEC
            if logged_long_ago and not user.initial_coordinates:
                logger.warning(f'User {user.name} will be kicked as no initial coords present for too long')
                users_to_kick.append(user)
            if user.initial_coordinates and logged_long_ago and not user.last_know_coords:
                logger.warning(f'User {user.name} will be kicked as no current coords present for too long')
                users_to_kick.append(user)

        return users_to_kick

    def collect_ips_with_lots_of_kicks(self) -> list[TrackedIp]:
        """Collects IPs, which has lots of kicks

        Returns:
            IPs to ban"""

        tracked_ips = STORAGE.get_tracked_ips()
        ips_to_ban = []
        for kicked_ip in tracked_ips:
            if kicked_ip.banned:
                continue
            if kicked_ip.kicks_counter > settings.antibot.AGGRESSIVE_BAN_IP_AFTER_IP_KICKED_TIMES:
                ips_to_ban.append(kicked_ip)
        return ips_to_ban

    def collect_ips_with_lots_of_kicked_users(self) -> list[TrackedIp]:
        """Collects IPs, from which there were too many kicks for different users

        Returns:
            list with IPs to ban"""

        kicked_ips = STORAGE.get_tracked_ips()
        all_users  = STORAGE.get_all_users()
        ips_to_ban = []

        for kicked_ip in kicked_ips:
            if kicked_ip.banned:
                continue

            kicked_users_count_on_ip = 0
            for user in all_users:
                if user.ip == kicked_ip.ip and user.kicked_count > 0:
                    kicked_users_count_on_ip += 1

            if kicked_users_count_on_ip >= settings.antibot.BAN_IP_IF_KICKED_USERS_NUMBER and not kicked_ip.banned:
                ips_to_ban.append(kicked_ip)

        if ips_to_ban:
            logger.warning(f'Collected IPs to kick due to lots of kicked users: {ips_to_ban}')
        return ips_to_ban

    def collect_ips_with_lots_of_kicks_for_single_user(self) -> list[TrackedIp]:
        """Collects IPs, from which there is a user with lots of kicks"""

        kicked_ips = STORAGE.get_tracked_ips()
        ips_to_ban = []
        for ip in kicked_ips:
            if ip.banned:
                continue

            unique_users = set(ip.kicked_user_names)
            for user_name in unique_users:
                user = STORAGE.get_user(user_name)
                if user:
                    if user.kicked_count >= settings.antibot.BAN_IP_IF_SINGLE_USER_KICKED_NUMBER and not ip.banned:
                        ips_to_ban.append(ip)

        if ips_to_ban:
            logger.warning(f'Collected IPs to kick due to lots of logins for single user: {ips_to_ban}')
        return ips_to_ban

    def get_static_users(self) -> tuple[list[TrackedUser], list[TrackedUser]]:
        """Collects Users that are considered static

        Notes:
            Considers Users as static if they are standing in spawn point or if they don't leave spawn area. These
            checks are based on different time window - less time is given to Users, that are standing still in
            spawn point, while Users in spawn area have more time before been considered static (aka bot)
        Returns:
            Users, static in spawn point and in spawn area"""

        static_in_spawn_point = []
        static_in_spawn_area  = []

        tracked_users = STORAGE.get_tracked_users()
        for user in tracked_users:

            if not user.last_know_coords:
                logger.debug(f'User {user.name} does not yet have current coordinates')
                continue

            if self._check_if_user_in_spawn_point_too_long(user):
                static_in_spawn_point.append(user)
                continue

            if self._check_if_user_in_spawn_area_too_long(user):
                static_in_spawn_area.append(user)

        return static_in_spawn_point, static_in_spawn_area

    def _check_if_user_in_spawn_point_too_long(self,
                                               user: TrackedUser) -> bool:
        """Checks if User is in spawn point for too long

        Args:
            user: User to check
        Returns:
            True, if User is in spawn point for too long without moving away from it"""

        if self.check_if_coords_in_spawn_point(user.last_know_coords) and not user.moved:
            time_since_login = user.get_time_since_login()
            if time_since_login > settings.antibot.KICK_STATIC_IN_SPAWN_POINT_AFTER_SEC:
                logger.debug(f'User {user.name} in spawn point for too long and will be kicked')
                return True
            return False
        else:
            return False

    def _check_if_user_in_spawn_area_too_long(self,
                                              user: TrackedUser) -> bool:
        """Checks if User is in spawn area for too long

        Args:
            user: User to check
        Returns:
            True, if User is in spawn area for too long without leaving it"""

        if self.check_if_coords_are_in_spawn_area(user.last_know_coords) and not user.left_spawn:
            time_since_login = user.get_time_since_login()
            if time_since_login > settings.antibot.KICK_STATIC_IN_SPAWN_AREA_AFTER_SEC:
                logger.debug(f'User {user.name} in spawn area for too long and will be kicked')
                return True
            return False
        return False

    def check_if_coords_in_spawn_point(self,
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

    def check_if_coords_are_in_spawn_area(self,
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

    def check_movements(self) -> None:
        """Checks all Users for any movements"""

        tracked_users = STORAGE.get_tracked_users()
        for user in tracked_users:
            self._check_user_movement(user)

    def _check_user_movement(self,
                             user: TrackedUser) -> None:
        """Checks if User moved at all and leave spawn

        Args:
            user: User to check"""

        if not user.last_know_coords or not user.initial_coordinates:
            return

        if user.initial_coordinates.x != user.last_know_coords.x \
                or user.initial_coordinates.z != user.last_know_coords.z:
            user.moved = True
            logger.debug(f'User {user.name} moved')

        if not self.check_if_coords_are_in_spawn_area(user.last_know_coords):
            user.left_spawn = True
            logger.debug(f'User {user.name} is not in spawn are')

    def get_ips_to_unban(self) -> list[TrackedIp]:
        """Collects IPs that can be unbanned

        Returns:
            IPs that can be unbanned"""

        ips_to_unban = []
        now = datetime.datetime.now().timestamp()
        all_ips = STORAGE.get_tracked_ips()
        for ip in all_ips:
            if ip.unban_me_at and ip.unban_me_at < now:
                ips_to_unban.append(ip)

        return ips_to_unban
