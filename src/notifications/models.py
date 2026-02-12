import json

from loguru import logger


class Text:
    def __init__(self,
                 data: dict):
        """"""

        self.en: str = data.get("en", "")
        self.ru: str = data.get("ru", "")

    def __str__(self) -> str:
        """"""

        return f'{self.en}'

    def __repr__(self) -> str:
        """"""

        return f'{self.en}'


class Notification:

    TELL_RAW_TEMPLATE: dict = {"text": "{header}\n{body}"}

    def __init__(self,
                 data: dict):
        """"""

        self.id:        str = data.get('id')
        self.max_views: int = data.get('max_views', 0)
        self.header:    Text = Text(data.get('header'))
        self.body:      Text = Text(data.get('body'))

    def get_formatted_text(self) -> str:
        """"""

        text = {"text": f"{self.header.en}\n{self.body.en}"}
        return json.dumps(text)

    def __str__(self) -> str:
        """"""

        return f'{self.id}'

    def __repr__(self) -> str:
        """"""

        return f'{self.id}'


class NotificationsCatalogue:
    def __init__(self,
                 data: list):
        """"""

        if len(data) == 0:
            data = []
        unsorted_announcements      = self._convert_to_models(data)
        announcements, random_texts = self._sort_announcements(unsorted_announcements)

        self.announcements: list[Notification] = announcements
        self.random_texts:  list[Notification] = random_texts

    def _convert_to_models(self,
                           data: list) -> list[Notification]:
        """"""

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
        """"""

        announcements: list[Notification] = []
        random_texts:  list[Notification] = []
        for notification in all_notifications:
            if notification.id and notification.max_views > 0:
                announcements.append(notification)
            else:
                random_texts.append(notification)

        return announcements, random_texts


class UserNotifications:
    """"""

    def __init__(self,
                 data: dict):
        """"""

        self.id:         str = data.get('id')
        self.times_seen: int = data.get('times_seen', 0)

    def __str__(self) -> str:
        """"""

        return f'{self.id}'

    def __repr__(self) -> str:
        """"""

        return f'{self.id}'


class User:
    """"""

    def __init__(self,
                 name: str,
                 data: list[dict]):
        """"""

        self.name: str = name
        self.seen_announcements: dict[str, UserNotifications] = self._parse_user_data(data)

    def _parse_user_data(self,
                         data: list[dict]) -> dict[str, UserNotifications]:
        """"""

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
        """"""

        user_notification = UserNotifications(
            data={
                'id': notification.id,
                'times_seen': 1
            }
        )
        self.seen_announcements[notification.id] = user_notification

    def __str__(self) -> str:
        """"""

        return f'{self.name}'

    def __repr__(self) -> str:
        """"""

        return f'{self.name}'


class UsersCatalogue:
    """"""

    def __init__(self,
                 data: dict):
        """"""

        if len(data) == 0:
            data = {}
        self.users: dict[str, User] = self._parse_data(data)

    def _parse_data(self,
                    data: dict) -> dict[str, User]:
        """"""

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
        """"""

        all_users_data: dict = {}
        for user_name, user_data in self.users.items():
            notifications_list = []
            for notification_id, notification in user_data.seen_announcements.items():
                notification_dict = {notification_id: notification.times_seen}
                notification_dict = {
                    'id': notification_id,
                    'times_seen': notification.times_seen
                }
                notifications_list.append(notification_dict)
            all_users_data[user_name] = notifications_list

        return all_users_data
