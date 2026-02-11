import os
import pytest
import zipfile

from pathlib import Path
from unittest.mock import MagicMock
from _pytest.monkeypatch import MonkeyPatch

from file_transfer.backuper import FileBackuper


class TestFileBackuper:
    """Tests for FileBackuper"""

    @pytest.fixture
    def mock_settings(self,
                      tmp_path: Path,
                      monkeypatch: MonkeyPatch) -> MagicMock:
        """Mocks the settings object

        Args:
            tmp_path: Path to a temp directory for testing
            monkeypatch: Patch for variables
        Returns:
            Mocked settings object"""

        world_dir = tmp_path / "world1"
        world_dir.mkdir()
        (world_dir / "level.dat").write_text("dummy data")

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        mock_settings = MagicMock()
        mock_settings.WORLD_DIRS = [str(world_dir)]
        mock_settings.BACKUP_DIR = str(backup_dir)

        # Just in case
        monkeypatch.setattr("settings.settings", mock_settings)

        return mock_settings

    def test_validate_paths_success(self,
                                    mock_settings: MagicMock):
        """Ensures validation passes when paths exist

        Args:
            mock_settings: Mock for settings"""

        backuper = FileBackuper()
        # Should not raise any exception
        backuper._validate_paths(mock_settings.WORLD_DIRS)

    def test_validate_paths_fails(self):
        """Ensures FileNotFoundError is raised for missing paths"""

        backuper = FileBackuper()
        with pytest.raises(FileNotFoundError, match="Backup canceled"):
            backuper._validate_paths(["/non/existent/path"])

    def test_copy_folders_to_temp_location(self,
                                           mock_settings: MagicMock,
                                           tmp_path: Path):
        """Tests the internal copy logic specifically

        Args:
            mock_settings: Mock for settings
            tmp_path: Path to a temp folder for testing"""

        backuper = FileBackuper()
        temp_dest = tmp_path / "manual_temp"

        backuper._copy_folders_to_temp_location(str(temp_dest), mock_settings.WORLD_DIRS)

        expected_file = temp_dest / "world1" / "level.dat"
        assert expected_file.exists()
