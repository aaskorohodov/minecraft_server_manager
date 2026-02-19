import datetime
from unittest.mock import MagicMock

from _pytest.monkeypatch import MonkeyPatch

from main_comm import MainComm
from server_manager import MinecraftServerManager


class TestMinecraftServerManager:
    """Tests for MinecraftServerManager"""

    def test_check_backup_triggers(self,
                                   monkeypatch: MonkeyPatch):
        """Checks if method correctly triggers at specified time and day

        Args:
            monkeypatch: patch to mock variables"""

        main_comm = MainComm()
        manager = MinecraftServerManager(main_comm)

        # Assume these settings for the test
        monkeypatch.setattr("settings.settings.backups.BACKUP_TIME", "03:00")
        monkeypatch.setattr("settings.settings.backups.BACKUP_INTERVAL_DAYS", 2)

        # --- SCENARIO 1: Correct Day (Day 0), Correct Time ---
        # 1970-01-01 03:00:00 is exactly 3 hours (10800 seconds) after epoch
        mock_now = datetime.datetime(1970, 1, 1, 3, 0)

        datetime_mock = MagicMock(wraps=datetime.datetime)
        datetime_mock.now.return_value = mock_now
        monkeypatch.setattr("server_manager.datetime", datetime_mock)

        main_comm.backup_now_trigger = False
        assert manager._check_backup_triggers() is True
        assert main_comm.record_net_stat_trigger is True

        # --- SCENARIO 2: Wrong Day (Day 1), Correct Time ---
        # 1970-01-02 03:00:00 (Day 1 % 2 != 0)
        datetime_mock.now.return_value = datetime.datetime(1970, 1, 2, 3, 0)
        assert manager._check_backup_triggers() is False

        # --- SCENARIO 3: Wrong Time, but Manual Trigger is Active ---
        datetime_mock.now.return_value = datetime.datetime(1970, 1, 2, 15, 0)  # 3:00 PM
        main_comm.backup_now_trigger = True
        assert manager._check_backup_triggers() is True
