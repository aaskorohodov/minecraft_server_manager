import json
from pathlib import Path

from notifications.notificator import Notificator
from settings import settings


class TestNotificator:
    def _get_fixtures_path(self) -> tuple[Path, Path]:
        """"""

        test_notifications_folder = Path(__file__).parent
        fixtures_folder = test_notifications_folder / 'fixtures'
        notifications_data_json_path = fixtures_folder / 'notifications_data.json'
        user_data_json_path = fixtures_folder / 'user_data.json'

        return notifications_data_json_path, user_data_json_path

    def _fill_fixtures(self) -> None:
        """"""

        notifications = [
            {
                "id": "speed_up",
                "max_views": 5,
                "header": {"en": "Server Speed up", "ru": "Сервер стал быстрее"},
                "body": {"en": "Server is now 10x faster", "ru": "Сервер теперь х5 быстрее"}
            },
            {
                "id": "text_1",
                "max_views": 0,
                "header": {"en": "T1", "ru": "Тэ1"},
                "body": {"en": "Text 1", "ru": "Текст 1"}
            }
        ]

        user_data = {
            "PlayerOne": [
                {
                    "id": "speed_up",
                    "times_seen": 4
                },
                {
                    "id": "something_else",
                    "times_seen": 2
                },
            ],
            "OtherPlayer": [
                {
                    "id": "speed_up",
                    "times_seen": 5
                },
                {
                    "id": "something_else",
                    "times_seen": 1
                },
            ]
        }

        notifications_data_json_path, user_data_json_path = self._get_fixtures_path()

        with open(notifications_data_json_path, 'w', encoding='utf-8') as f:
            json.dump(notifications, f, indent=4, ensure_ascii=False)

        with open(user_data_json_path, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, indent=4, ensure_ascii=False)

    def _prepare_settings(self):
        """"""

        notifications_data_json_path, user_data_json_path = self._get_fixtures_path()
        settings.notifications.ACTIVATED       = True
        settings.notifications.MESSAGES_PATH   = str(notifications_data_json_path)
        settings.notifications.USERS_DATA_PATH = str(user_data_json_path)

    def test_notificator_activated(self):
        """"""

        self._fill_fixtures()
        self._prepare_settings()
        notificator = Notificator()
        assert notificator.activated

    def test_get_login_message(self):
        """"""

        self._fill_fixtures()
        self._prepare_settings()
        notificator = Notificator()

        message_1 = notificator.get_login_message('PlayerOne')
        assert message_1 == '{"text": "Server Speed up\\nServer is now 10x faster"}'

        message_2 = notificator.get_login_message('PlayerOne')
        assert message_2 == '{"text": "T1\\nText 1"}'

        message_3 = notificator.get_login_message('PlayerOne')
        assert message_3 == '{"text": "T1\\nText 1"}'

        message_4 = notificator.get_login_message('PlayerOne')
        assert message_4 == '{"text": "T1\\nText 1"}'

        message_5 = notificator.get_login_message('PlayerOne')
        assert message_5 == '{"text": "T1\\nText 1"}'

        message_6 = notificator.get_login_message('OtherPlayer')
        assert message_6 == '{"text": "T1\\nText 1"}'

        notifications_data_json_path, user_data_json_path = self._get_fixtures_path()
        with open(user_data_json_path, 'rb') as f:
            actual_data = json.load(f)

        expected_data = {
            "PlayerOne": [
                {
                    "id": "speed_up",
                    "times_seen": 5
                },
                {
                    "id": "something_else",
                    "times_seen": 2
                }
            ],
            "OtherPlayer": [
                {
                    "id": "speed_up",
                    "times_seen": 5
                },
                {
                    "id": "something_else",
                    "times_seen": 1
                }
            ]
        }
        assert actual_data == expected_data

    def test_new_user(self):
        """"""

        self._fill_fixtures()
        self._prepare_settings()
        notificator = Notificator()

        message_1 = notificator.get_login_message('NewPlayer')
        assert message_1 == '{"text": "Server Speed up\\nServer is now 10x faster"}'

        notifications_data_json_path, user_data_json_path = self._get_fixtures_path()
        with open(user_data_json_path, 'rb') as f:
            actual_data = json.load(f)

        expected_data = {
            "PlayerOne": [
                {
                    "id": "speed_up",
                    "times_seen": 4
                },
                {
                    "id": "something_else",
                    "times_seen": 2
                }
            ],
            "OtherPlayer": [
                {
                    "id": "speed_up",
                    "times_seen": 5
                },
                {
                    "id": "something_else",
                    "times_seen": 1
                }
            ],
            "NewPlayer": [
                {
                    "id": "speed_up",
                    "times_seen": 1
                }
            ]
        }
        assert actual_data == expected_data

    def test_empty_files(self):
        """"""

        notifications_data_json_path, user_data_json_path = self._get_fixtures_path()
        notifications_data_json_path = notifications_data_json_path.parent / 'new_notifications.json'
        user_data_json_path = user_data_json_path.parent / 'new_users.json'

        settings.notifications.ACTIVATED       = True
        settings.notifications.MESSAGES_PATH   = str(notifications_data_json_path)
        settings.notifications.USERS_DATA_PATH = str(user_data_json_path)

        with open(notifications_data_json_path, 'w', encoding='utf-8') as f:
            # indent=4 makes the file human-readable for manual edits
            json.dump([], f, indent=4, ensure_ascii=False)

        with open(user_data_json_path, 'w', encoding='utf-8') as f:
            # indent=4 makes the file human-readable for manual edits
            json.dump({}, f, indent=4, ensure_ascii=False)

        notificator = Notificator()
        assert notificator.activated

    def test_empty_users_file(self):
        """"""

        notifications_data_json_path, user_data_json_path = self._get_fixtures_path()
        user_data_json_path = user_data_json_path.parent / 'new_users.json'

        settings.notifications.ACTIVATED       = True
        settings.notifications.MESSAGES_PATH   = str(notifications_data_json_path)
        settings.notifications.USERS_DATA_PATH = str(user_data_json_path)

        with open(user_data_json_path, 'w', encoding='utf-8') as f:
            # indent=4 makes the file human-readable for manual edits
            json.dump({}, f, indent=4, ensure_ascii=False)

        notificator = Notificator()
        assert notificator.activated

        message_1 = notificator.get_login_message('PlayerOne')
        assert message_1 == '{"text": "Server Speed up\\nServer is now 10x faster"}'

        expected_data = {
            "PlayerOne": [
                {
                    "id": "speed_up",
                    "times_seen": 1
                }
            ]
        }
        with open(user_data_json_path, 'rb') as f:
            actual_data = json.load(f)
        assert actual_data == expected_data
