import pytest

from pathlib import Path
from typing import Optional
from types import SimpleNamespace
from _pytest.monkeypatch import MonkeyPatch

from down_detecror.detector import DownDetector
from settings import settings


class TestDownDetector:
    """Tests for DownDetector."""

    detector:  Optional[DownDetector]
    main_comm: Optional[SimpleNamespace]

    # noinspection PyShadowingNames
    @pytest.fixture(autouse=True)
    def setup(self,
              fake_main_comm: SimpleNamespace,
              temp_db_path: Path,
              monkeypatch: MonkeyPatch):
        """Common test setup

        - Disables background thread
        - Creates detector instance

        Args:
            fake_main_comm: Fixture, mock for MainComm
            temp_db_path: Path object that leads to DB for testing (local)
            monkeypatch: Patch for variables"""

        # Prevent background thread from starting
        monkeypatch.setattr(
            "threading.Thread.start",
            lambda self: None
        )

        settings.down_detector.DETECTOR_ON = True
        # noinspection PyTypeChecker
        self.detector  = DownDetector(main_comm=fake_main_comm)
        self.main_comm = fake_main_comm

        yield

        # This is pytest-way to do things. Pytest will call this as a teardown every time
        # TEARDOWN: Close the connection so Windows releases the file
        if hasattr(self, 'detector') and self.detector._cursor:
            self.detector._cursor.connection.close()

    def test_db_initialized(self):
        """DB should contain connectivity table"""

        cursor = self.detector._cursor
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='connectivity'"
        )
        table = cursor.fetchone()

        assert table is not None

    def test_record_status_inserts_row(self):
        """_record_status should insert a row into DB"""

        self.detector._record_status("online")

        self.detector._cursor.execute(
            "SELECT status FROM connectivity"
        )
        row = self.detector._cursor.fetchone()

        assert row[0] == "online"

    def test_get_status_online(self,
                               monkeypatch: MonkeyPatch):
        """_get_status returns 'online' when _is_online is True

        Args:
            monkeypatch: Patch to mock variables"""

        monkeypatch.setattr(self.detector, "_is_online", lambda: True)

        status = self.detector._get_status()

        assert status == "online"

    def test_get_status_offline(self,
                                monkeypatch: MonkeyPatch):
        """_get_status returns 'offline' when _is_online is False

        Args:
            monkeypatch: Patch to mock variables"""

        monkeypatch.setattr(self.detector, "_is_online", lambda: False)

        status = self.detector._get_status()

        assert status == "offline"

    def test_is_online_success(self,
                               monkeypatch: MonkeyPatch):
        """_is_online returns True if any request succeeds

        Args:
            monkeypatch: Patch to mock variables"""

        def fake_get(*_args, **_kwargs):
            return object()

        monkeypatch.setattr("requests.get", fake_get)

        assert self.detector._is_online() is True

    def test_is_online_failure(self,
                               monkeypatch: MonkeyPatch):
        """_is_online returns False if all requests fail

        Args:
            monkeypatch: Patch to mock variables"""

        def fake_get(*_args, **_kwargs):
            raise Exception("No internet")

        monkeypatch.setattr("requests.get", fake_get)

        assert self.detector._is_online() is False
