import datetime
import matplotlib
import pandas as pd

from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from down_detecror.plot_drawer import PlotDrawer

# That prevents GUI leaks
matplotlib.use("Agg")


class TestPlotDrawer:
    def test_convert_timestamps(self):
        """Timestamps should be converted to datetime"""

        df = pd.DataFrame({
            "timestamp": ["2024-01-01T00:00:00"],
            "status": ["online"],
        })

        result = PlotDrawer._convert_timestamps_to_date_times(df)

        assert pd.api.types.is_datetime64_any_dtype(result["timestamp"])

    def test_extract_starting_status_empty(self):
        """Empty earlier records should return 'off'"""

        empty_df = pd.DataFrame(columns=["timestamp", "status"])

        # noinspection PyTypeChecker
        status = PlotDrawer._extract_starting_status(empty_df)

        assert status == "off"

    def test_extract_starting_status_non_empty(self):
        """Last earlier record determines starting status"""

        df = pd.DataFrame([
            {"timestamp": datetime.datetime.now(), "status": "offline"},
        ])

        # noinspection PyTypeChecker
        status = PlotDrawer._extract_starting_status(df)

        assert status == "offline"

    def test_calculate_uptime(self):
        """Uptime should be calculated correctly"""

        df = pd.DataFrame([
            {"timestamp": 1, "status": "online"},
            {"timestamp": 2, "status": "offline"},
            {"timestamp": 3, "status": "online"},
        ])

        uptime = PlotDrawer._calculate_uptime(df)

        # 2 segments total, 1 online
        assert uptime == 0.5

    def test_draw_plot_calls_matplotlib(self,
                                        monkeypatch: MonkeyPatch):
        """_draw_plot should call plotting functions

        Args:
            monkeypatch: Patch for variables"""

        df = pd.DataFrame([
            {"timestamp": datetime.datetime.now(), "status": "online"},
            {"timestamp": datetime.datetime.now(), "status": "offline"},
        ])

        called = {"plot": 0, "show": 0}

        monkeypatch.setattr("matplotlib.pyplot.plot", lambda *a, **k: called.__setitem__("plot", called["plot"] + 1))
        monkeypatch.setattr("matplotlib.pyplot.show", lambda: called.__setitem__("show", 1))

        PlotDrawer._draw_plot(df)

        assert called["plot"] > 0
        assert called["show"] == 1

    def test_draw_data_24h_no_data(self,
                                   monkeypatch: MonkeyPatch,
                                   capsys: CaptureFixture):
        """Should print message when no data exists

        Args:
            monkeypatch: Patch for variables
            capsys: Object to read prints, executed somewhere in code we are testing"""

        empty_df = pd.DataFrame(columns=["id", "timestamp", "status"])

        monkeypatch.setattr(
            PlotDrawer,
            "_read_connectivity_statuses",
            lambda: empty_df
        )

        PlotDrawer.draw_data_24h()

        captured = capsys.readouterr()
        assert "No data found" in captured.out
