import os
import sqlite3
import datetime
import pandas as pd
import matplotlib.pyplot as plt

from settings import settings


class PlotDrawer:
    """Draws plots"""

    @staticmethod
    def draw_data_24h() -> None:
        """Draws connectivity timeline for the last 24 hours"""

        df_net_status = PlotDrawer._read_connectivity_statuses()
        df_net_status = PlotDrawer._convert_timestamps_to_date_times(df_net_status)

        if df_net_status.empty:
            print("No data found")
            return

        df_24h = PlotDrawer._extract_24_hours_data(df_net_status)

        if len(df_24h) < 2:
            print("Not enough data to plot (less than 2 points)")
            return

        PlotDrawer._draw_plot(df_24h)

    @staticmethod
    def _read_connectivity_statuses() -> pd.DataFrame:
        """Reads all data from connectivity table and returns them as DF

        Returns:
            All data from connectivity table as DF"""

        root_folder = os.path.dirname(os.path.dirname(__file__))
        os.chdir(root_folder)
        conn = sqlite3.connect(settings.DB_PATH)

        df = pd.read_sql_query(
            "SELECT * FROM connectivity ORDER BY timestamp",
            conn
        )

        return df

    @staticmethod
    def _convert_timestamps_to_date_times(df_net_status: pd.DataFrame) -> pd.DataFrame:
        """Converts column timestamp from string into datetime objects

        Args:
            df_net_status: DataFrame with column timestamp to convert
        Returns:
            Same DF, but with column timestamp converted into datetime objects"""

        df_net_status['timestamp'] = pd.to_datetime(df_net_status['timestamp'])
        return df_net_status

    @staticmethod
    def _extract_24_hours_data(df_net_status: pd.DataFrame) -> pd.DataFrame:
        """Extracts records for the last 24 hours from all df_net_status

        Notes:
            Creates synthetic records, if there are no records for the last 24 hours. This works, as server only
            writes changes in status, and in case last change was more than 24 hours ago, actual status for the last
            24 hours simply was not changing, and we just need to create synthetic record for that exact status
        Returns:
            DF with net-statuses for the last 24 hours"""

        now                 = datetime.datetime.now()
        cutoff_24_hours_ago = now - datetime.timedelta(hours=24)

        # Split data before and after cutoff
        all_records_earlier_24_hours = df_net_status[df_net_status['timestamp'] < cutoff_24_hours_ago]
        all_records_within_24_hours  = df_net_status[df_net_status['timestamp'] >= cutoff_24_hours_ago]

        start_status = PlotDrawer._extract_starting_status(all_records_earlier_24_hours)

        # Add synthetic start record (exactly 24 hours ago)
        start_record = pd.DataFrame([{
            'timestamp': cutoff_24_hours_ago,
            'status': start_status
        }])

        df_24h = pd.concat([start_record, all_records_within_24_hours], ignore_index=True)

        # Add synthetic end record (now)
        end_status = df_24h.iloc[-1]['status']
        end_record = pd.DataFrame([{
            'timestamp': now,
            'status': end_status
        }])
        df_24h = pd.concat([df_24h, end_record], ignore_index=True)

        return df_24h

    @staticmethod
    def _extract_starting_status(all_records_earlier_24_hours: pd.Series) -> str:
        """Finds starting status

        Args:
            all_records_earlier_24_hours: Records, made more than 24 hours ago
        Returns:
            Earliest status, either earliest from records made more than 24 hours ago, or off-status"""

        if all_records_earlier_24_hours.empty:
            start_status       = 'off'
        else:
            last_record_earlier_than_24_hours = all_records_earlier_24_hours.iloc[-1]
            start_status = last_record_earlier_than_24_hours['status']

        return start_status

    @staticmethod
    def _draw_plot(df_24h: pd.DataFrame) -> None:
        """Draws plot, from collected data

        Args:
            df_24h: Records for the last 24 hours, updated with start and end synthetic data"""

        # Plot
        plt.figure(figsize=(10, 2))

        PlotDrawer._add_coloured_statuses(df_24h)

        # Calculate uptime %
        uptime_percent = PlotDrawer._calculate_uptime(df_24h)
        print(f"Uptime (last 24h): {uptime_percent:.2%}")

        plt.yticks([])
        plt.title(f"Internet Connectivity Timeline (Last 24h). Uptime {uptime_percent:.2%}")
        plt.xlabel("Time")
        plt.tight_layout()
        plt.show()

    @staticmethod
    def _add_coloured_statuses(df_24h: pd.DataFrame) -> None:
        """Determines colors for lines on plot, based on status, and adds them to plot

        Args:
            df_24h: DataFrame with record for last 24 hours"""

        for i in range(1, len(df_24h)):
            status = df_24h.loc[i - 1, 'status']
            if status == 'online':
                color = 'green'
            elif status == 'off':
                color = 'gray'
            else:
                color = 'red'

            current_status_segment: pd.Series = df_24h['timestamp'].iloc[i - 1:i + 1]
            plt.plot(current_status_segment, [1, 1], color=color, linewidth=3)

    @staticmethod
    def _calculate_uptime(df_24h: pd.DataFrame) -> int | float:
        """Calculates percentage of uptime in current records

        Args:
            df_24h: DataFrame with record for last 24 hours
        Returns:
            Percentage of uptime in current records"""

        total_segments  = len(df_24h) - 1
        online_segments = sum(df_24h.iloc[i - 1]['status'] == 'online' for i in range(1, len(df_24h)))
        uptime_percent  = online_segments / total_segments

        return uptime_percent

    @staticmethod
    def draw_data() -> None:
        """Draws collected downtime"""

        root_folder = os.path.dirname(os.path.dirname(__file__))
        os.chdir(root_folder)
        df = pd.read_sql_query(
            "SELECT * FROM connectivity ORDER BY timestamp",
            sqlite3.connect(settings.DB_PATH)
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        if len(df) < 2:
            print("Not enough data to plot.")
            return

        # Calculate uptime %
        overall_statuses = len(df)
        online_statuses  = (df['status'] == 'online').sum()
        uptime_percent   = online_statuses / overall_statuses
        print(f"Uptime: {uptime_percent:.2%}")

        # Plot timeline with colored segments
        plt.figure(figsize=(10, 2))
        for i in range(1, len(df)):
            color = 'green' if df.loc[i - 1, 'status'] == 'online' else 'red'
            plt.plot(df['timestamp'].iloc[i-1:i+1], [1, 1], color=color, linewidth=3)

        plt.yticks([])
        plt.title("Internet Connectivity Timeline")
        plt.xlabel("Time")
        plt.tight_layout()
        plt.show()


if __name__ == '__main__':
    PlotDrawer.draw_data_24h()
