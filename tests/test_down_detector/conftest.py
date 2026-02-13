import pytest

from pathlib import Path
from types import SimpleNamespace
from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture
def fake_main_comm() -> SimpleNamespace:
    """Fake MainComm for testing

    Returns:
        Fake MainComm for testing"""

    return SimpleNamespace(
        trayer_running=True,
        draw_plot_trigger=False,
        record_net_stat_trigger=False,
        backup_now_trigger=False,
    )


@pytest.fixture
def temp_db_path(tmp_path: Path,
                 monkeypatch: MonkeyPatch) -> Path:
    """Patch settings.DB_PATH to a temporary file

    Args:
        tmp_path: path to a temp location to created DB for testing in
        monkeypatch: Patch to mock settings.DB_PATH with
    Returns:
        Path to test-db"""

    db_path = tmp_path / "test.db"
    monkeypatch.setattr("settings.settings.paths.DB", str(db_path))
    yield db_path

    # This is pytest-way to do things. Pytest will call this as a teardown to delete temp-files every time
    # Removing temp db, not to leave it during development
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            # This happens on Windows if the DB connection isn't closed
            pass
