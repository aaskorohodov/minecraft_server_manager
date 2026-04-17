import datetime

from loguru import logger

from anti_bot.storage import STORAGE
from settings import settings
from anti_bot.models import TrackedUser


class LoginsManager:
    """Responsible for logic, related to login events"""

    def is_login_allowed(self,
                         user: TrackedUser) -> bool:
        """Checks if this User is allowed to log in

        Args:
            user: User to check
        Returns:
            True, in case User is allowed to login"""

        if user.kicked_count < 1:
            return True

        sanctions_exist = user.login_allowed_at is not None
        if not sanctions_exist:
            return True

        sanctions_expired = datetime.datetime.now().timestamp() > user.login_allowed_at
        if sanctions_expired:
            return True
        else:
            return False

    def is_too_many_logins(self,
                           user: TrackedUser) -> bool:
        """Checks if there were too many logins for that User in recent time

        Args:
            user: User to check
        Returns:
            True, in case there were too many login events in recent time"""

        if len(user.login_events) > settings.antibot.LOGINS_ALLOWED_IN_TS:
            logger.warning(f'User {user.name} has too many logins!')
            return True
        return False

    def check_same_ip_login(self,
                            user: TrackedUser) -> bool:
        """Checks if there is another User, connected from the same IP, that is not yet left spawn

        Notes:
            This check prevents another User (or bot) to login, while another User is still hanging in spawn. If first
            User was able to leave spawn, another User from same IP will be able to login
        Args:
            user: User to check for kick
        Returns:
            True, in case User can not login"""

        if user.ip:
            # Already tracking at least one more user
            if STORAGE.get_tracked_users_count() > 1:
                if STORAGE.are_there_another_tracked_users_with_same_ip(user):
                    return True
        return False
