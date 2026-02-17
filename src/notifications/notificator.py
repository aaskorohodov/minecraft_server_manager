import os
import json
import random

from loguru import logger

from settings import settings
from notifications.models import NotificationsCatalogue, UsersCatalogue, User, Notification


class Notificator:
    """Notifies Users with messages inside Minecraft"""

    def __init__(self):
        """Init

        Checks activation status"""

        self.activated: bool = False

        if settings.notifications.ACTIVATED:
            self.activated = self._check_files()
        else:
            logger.warning('Notificator disabled')
            self.activated = False

    def _check_files(self) -> bool:
        """Checks if there are files for notifications

        Returns:
            True, if files for notifications were found"""

        notification_file_ok = os.path.exists(settings.paths.MESSAGES)
        user_data_file_ok    = os.path.exists(settings.paths.USERS_DATA)
        if notification_file_ok and user_data_file_ok:
            logger.info('Notifications file found. Notificator activated')
            return True
        else:
            logger.warning(f'Some notificator-files are missing: {notification_file_ok=}, {user_data_file_ok=}')
            return False

    def get_login_message(self,
                          user_name: str) -> str:
        """Selects login message for Player and updates Player's data in JSON

        Args:
            user_name: User to get message for
        Returns:
            Message for User as JSON-string, or empty string, if no message was selected"""

        if not self.activated:
            return ''

        try:
            notifications = NotificationsCatalogue(self._load_data(settings.paths.MESSAGES))
            all_users     = UsersCatalogue(self._load_data(settings.paths.USERS_DATA))
            current_user  = self._get_or_create_user(all_users, user_name)
            notification  = self._select_notification(notifications, current_user)
            self._update_user_data(notification, current_user)
            self._save_data(settings.paths.USERS_DATA, data=all_users.to_dict())

            return notification.get_formatted_text()

        except Exception as e:
            logger.exception(e)
            return ''

    def _get_or_create_user(self,
                            users: UsersCatalogue,
                            user_name: str) -> User:
        """Gets User from JSON with data or creates new one, if User is not yet in JSON

        Args:
            users: All Users from JSON
            user_name: Current User to search or create
        Returns:
            User model"""

        if user_name not in users.users:
            user = self._create_new_user(user_name)
            users.users[user_name] = user
        else:
            user = users.users.get(user_name)
        return user

    def _create_new_user(self,
                         user_name: str) -> User:
        """Create new User model

        Args:
            user_name: User to create model for
        Returns:
            User model"""

        user = User(
            name=user_name,
            data=[]
        )
        return user

    def _select_notification(self,
                             notifications: NotificationsCatalogue,
                             current_user: User) -> Notification:
        """Selects notification. Prioritizes Notifications for random texts

        Args:
            notifications: All notifications
            current_user: User to get notification for
        Returns:
            Notification model"""

        for notification in notifications.announcements:
            if notification.id in current_user.seen_announcements:
                user_announcement = current_user.seen_announcements[notification.id]
                if notification.max_views > user_announcement.times_seen:
                    return notification
            else:
                return notification

        return random.choice(notifications.random_texts)

    def _update_user_data(self,
                          notification: Notification,
                          user: User) -> None:
        """Updates counter of number of seen times for User->Notification

        Creates Notification, if User does not have it yet. Skips notification, in case it has max_views set to 0

        Args:
            notification: Notification that was shown to User
            user: User that we showed notification to"""

        if notification.max_views == 0:
            return

        if notification.id in user.seen_announcements:
            user.seen_announcements[notification.id].times_seen += 1
        else:
            user.add_new_seen_notification(notification)

    def _load_data(self,
                   filepath: str) -> list | dict:
        """Reads raw-data from disk (expected to be Users and their data and Notifications)

        Args:
            filepath: Path to file to read data from
        Returns:
            List or Dict (json.load applied) - list for Notifications and dict for Users (and seen notifications)"""

        if not os.path.exists(filepath):
            return {}
        with open(filepath, encoding='utf-8') as f:
            return json.load(f)

    def _save_data(self,
                   filepath: str,
                   data: dict | list) -> None:
        """Saves data to dick

        Args:
            filepath: Where to save
            data: What to save (list for Notifications and dict for Users (and seen notifications))"""

        with open(filepath, 'w', encoding='utf-8') as f:
            # indent=4 makes the file human-readable for manual edits
            json.dump(data, f, indent=4, ensure_ascii=False)
