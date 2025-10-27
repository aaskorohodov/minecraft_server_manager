import datetime


class MainComm:
    """Thread-communicator

    Attributes:
        draw_plot_trigger: Flag. When set to True, DownDetector will show plot
        backup_now_trigger: Flag. When set to True, ServerManager will execute BackUp process
        record_net_stat_trigger: Flag. Indicates that network status should be recorded now
        trayer_running: Flag, indicating that the main thread is running
        errors: Error, to display in Trayer's status-button
        stop_server: Flag. If True – ServerManager should read this flag and stop
        stop_trayer: Main flag to stop application"""

    def __init__(self):
        """Init"""

        self.draw_plot_trigger:       bool = False
        self.backup_now_trigger:      bool = False
        self.record_net_stat_trigger: bool = False
        self.trayer_running:          bool = True
        self.errors:                  str  = 'All good!'
        self.stop_server:             bool = False
        self.stop_trayer:             bool = False

    def set_error(self, error_text: str) -> None:
        """Sets error, that happened

        Args:
            error_text: Text of the error"""

        error_text = (f'{datetime.datetime.now()}\n'
                      f'{error_text}')
        self.errors = str(error_text)
