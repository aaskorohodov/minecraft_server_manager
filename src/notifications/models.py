import json

from loguru import logger


class Text:
    """Text of notification or header

    Attributes:
        en: In English
        ru: In russian"""

    def __init__(self,
                 data: dict):
        """Init

        Args:
            data: dict with texts"""

        self.en: str = data.get("en", "")
        self.ru: str = data.get("ru", "")

    def __str__(self) -> str:
        """String representation

        Returns:
            String representation"""

        return f'{self.en}'

    def __repr__(self) -> str:
        """String representation

        Returns:
            String representation"""

        return f'{self.en}'


class Notification:
    """Single notification

    Attributes:
        id: Unique ID
        max_views: Max number of views for each User, that this notification is intended to be shown
        header: Notification's Header (will be in chat in Minecraft as header)
        body: Notification's main text"""

    def __init__(self,
                 data: dict):
        """Init

        Args:
            data: Data to assemble Notification-instance from"""

        self.id:        str = data.get('id')
        self.max_views: int = data.get('max_views', 0)
        self.header:    Text = Text(data.get('header'))
        self.body:      Text = Text(data.get('body'))

    def get_formatted_text(self) -> str:
        """Creates text that can be sent as command to Minecraft-Server

        Returns:
            Text that can be sent as command to Minecraft-Server"""

        text = {"text": f"{self.header.en}\n{self.body.en}"}
        return json.dumps(text)

    def __str__(self) -> str:
        """String representation

        Returns:
            String representation"""

        return f'{self.id}'

    def __repr__(self) -> str:
        """String representation

        Returns:
            String representation"""

        return f'{self.id}'


class NotificationsCatalogue:
    """Holds all notifications, retrieved from Disk

    Attributes:
        announcements: More important notifications, that has some amount of max_views set (not 0)
        random_texts: Random texts to show when announcements are empty (max_views set to 0)"""

    def __init__(self,
                 data: list):
        """Init

        Args:
            data: Data to create notifications from"""

        # Just in case
        if len(data) == 0:
            data = []

        unsorted_announcements      = self._convert_to_models(data)
        announcements, random_texts = self._sort_announcements(unsorted_announcements)

        self.announcements: list[Notification] = announcements
        self.random_texts:  list[Notification] = random_texts

    def _convert_to_models(self,
                           data: list) -> list[Notification]:
        """Converts raw-data into models

        Args:
            data: Raw data with all notifications
        Returns:
            List with Notifications (instances, models)"""

        notifications: list[Notification] = []

        for el in data:
            try:
                notification = Notification(el)
                notifications.append(notification)
            except Exception as e:
                logger.warning(f'Announcement {el} skipped')
                logger.exception(e)

        if len(notifications) == 0:
            logger.warning('No notifications collected!')

        return notifications

    def _sort_announcements(self,
                            all_notifications: list[Notification]) -> tuple[list[Notification], list[Notification]]:
        """Sorts Notifications to get separate lists with important (announcements) and others (random-texts)

        Args:
            all_notifications: List with Notification-models
        Returns:
            List[Announcements, RandomTexts]"""

        announcements: list[Notification] = []
        random_texts:  list[Notification] = []
        for notification in all_notifications:
            if notification.id and notification.max_views > 0:
                announcements.append(notification)
            else:
                random_texts.append(notification)

        return announcements, random_texts


class UserNotifications:
    """Stores information about which notifications (Announcements) were shown to User and how many times

    Stores only Announcements - more important notifications, which has max_views set to some number (not 0),
    which means that these notifications has some limited amount of shows available. In contrast, Notification with
    max_views=0 are such, which can be shown infinite amount of times (no show-limit)

    Attributes:
        id: Unique ID of Notification
        times_seen: How many times this User have seen this notification"""

    def __init__(self,
                 data: dict):
        """Init

        Args:
            data: Data to assemble this instance from"""

        self.id:         str = data.get('id')
        self.times_seen: int = data.get('times_seen', 0)

    def __str__(self) -> str:
        """String representation

        Returns:
            String representation"""

        return f'{self.id}'

    def __repr__(self) -> str:
        """String representation

        Returns:
            String representation"""

        return f'{self.id}'


class User:
    """Single User

    Attributes:
        name: User's Name from Minecraft
        seen_announcements: UserNotifications for this User, that this User have seen (not including random-texts)"""

    def __init__(self,
                 name: str,
                 data: list[dict]):
        """Init

        Args:
            name: User's Name from Minecraft
            data: Raw-data to assemble UserNotifications models"""

        self.name: str = name
        self.seen_announcements: dict[str, UserNotifications] = self._parse_user_data(data)

    def _parse_user_data(self,
                         data: list[dict]) -> dict[str, UserNotifications]:
        """Pareses raw-data into UserNotifications models

        Args:
            data: Raw-data to parse UserNotifications from
        Returns:
            Dict with [UserNotifications.id: UserNotifications]"""

        all_user_notifications: dict[str, UserNotifications] = {}
        for notification_data in data:
            try:
                user_notification = UserNotifications(notification_data)
                all_user_notifications[user_notification.id] = user_notification
            except Exception as e:
                logger.warning(f'Unable to process user notification {notification_data=}')
                logger.exception(e)

        return all_user_notifications

    def add_new_seen_notification(self,
                                  notification: Notification) -> None:
        """Creates new model UserNotifications with times_seen set to 1, and saves it into self

        Args:
            notification: Notification that this User have now seen once"""

        user_notification = UserNotifications(
            data={
                'id': notification.id,
                'times_seen': 1
            }
        )
        self.seen_announcements[notification.id] = user_notification

    def __str__(self) -> str:
        """String representation

        Returns:
            String representation"""

        return f'{self.name}'

    def __repr__(self) -> str:
        """String representation

        Returns:
            String representation"""

        return f'{self.name}'


class UsersCatalogue:
    """Stores all Users and their notifications

    Attributes:
        users: Dict {User.name: User}"""

    def __init__(self,
                 data: dict):
        """Init

        Args:
            data: Raw data to create Users and their UserNotifications"""

        # Just in case
        if len(data) == 0:
            data = {}

        self.users: dict[str, User] = self._parse_data(data)

    def _parse_data(self,
                    data: dict) -> dict[str, User]:
        """Parses raw data into User and UserNotifications models

        Args:
            data: Raw-data to parse User and UserNotifications models from
        Returns:
            User and UserNotifications models, created from incoming data"""

        users: dict[str, User] = {}
        for user_name, user_data in data.items():
            try:
                user_model = User(user_name, user_data)
                users[user_name] = user_model
            except Exception as e:
                logger.warning('Skipped User!')
                logger.exception(e)

        return users

    def to_dict(self) -> dict:
        """Converts all Users and their data into dict, to save on disc (or elsewhere)

        Returns:
            self.users, converted into dict"""

        all_users_data: dict = {}
        for user_name, user_data in self.users.items():
            notifications_list = []
            for notification_id, notification in user_data.seen_announcements.items():
                notification_dict = {
                    'id': notification_id,
                    'times_seen': notification.times_seen
                }
                notifications_list.append(notification_dict)
            all_users_data[user_name] = notifications_list

        return all_users_data
