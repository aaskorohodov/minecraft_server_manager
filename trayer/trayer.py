"""Builds and handles Tray-icon"""

import os
import sys
import time
import ctypes
import threading

from typing import Optional
from infi.systray import SysTrayIcon, traybar

from main_comm import MainComm
from utils.instance_checker import InstanceChecker


class Trayer(SysTrayIcon):
    """Builds and handles Tray-icon

    Attributes:
        logo_main: Path to main logo in tray
        logo_info: Path to info-icon in tray's menu
        logo_restart: Path to restart-icon in tray's menu
        menu_options: Options for tray's menu (texts)
        main_comm: Thread-communicator"""

    def __init__(self,
                 main_comm: MainComm):
        """Init

        Args:
            main_comm: Tread-communicator"""

        self.logo_main:    str = ''
        self.logo_info:    str = ''
        self.logo_restart: str = ''
        self.logo_backup:  str = ''
        self._make_logos()

        self.menu_options: Optional[tuple[tuple[str, str, ()]]] = None
        self._make_menu_options()

        self.main_comm: MainComm = main_comm

        super().__init__(self.logo_main, 'MinecraftServer', self.menu_options, on_quit=self._quit)
        self.start()
        threading.Thread(target=self._check_communicator, daemon=True).start()

    # Commands

    def show_status(self, _: traybar.SysTrayIcon) -> None:
        """Button 'Status' action.

        Args:
            _: being provided by systray"""

        show_status_thread = threading.Thread(target=ctypes.windll.user32.MessageBoxW,
                                              args=(0, self.main_comm.errors, 'Status', 0),
                                              daemon=True)
        show_status_thread.start()

    def restart(self, _: traybar.SysTrayIcon) -> None:
        """Button 'Restart' action.

        Args:
            _: being provided by systray"""

        self.main_comm.trayer_running = False
        self.main_comm.stop_server    = True

        time.sleep(5)

        python = sys.executable
        os.execl(python, python, *sys.argv)

    # Actions

    def _quit(self, _):
        """Custom action. Being called automatically by systray on exit.

        Args:
            _: Trayer (self's class), provided by systray"""

        self.main_comm.trayer_running = False
        self.main_comm.stop_server    = True
        time.sleep(1)

        # Killing GUI, if it exists
        InstanceChecker().kill_process('main_launcher')

    # Service

    def _check_communicator(self) -> None:
        """Checks Communicator-object. Destroys tray, in case there is a signal to do so"""

        while not self.main_comm.stop_trayer:
            time.sleep(1)

        self._quit(None)

    def _make_logos(self) -> None:
        """Saves paths to icons"""

        current_file_path = os.path.abspath(__file__)
        trayer_dir = os.path.dirname(current_file_path)
        project_dir = os.path.dirname(trayer_dir)

        self.logo_main = os.path.join(project_dir, 'media/main_logo.ico')
        self.logo_info = os.path.join(project_dir, 'media/info.ico')
        self.logo_restart = os.path.join(project_dir, 'media/restart.ico')
        self.logo_backup = os.path.join(project_dir, 'media/backup.ico')

    def _back_up(self, _: traybar.SysTrayIcon) -> None:
        """Sends signal for back up world now"""

        self.main_comm.backup_now_trigger = True

    def _make_menu_options(self) -> None:
        """Makes menu for Trayer"""

        # Меню в трее (вылазит по клику правой кнопкой). Содержит (текст, картинку, что вызвать по нажатию)
        self.menu_options = (
            ("Info", self.logo_info, self.show_status),
            ("Restart", self.logo_restart, self.restart),
            ("BackUp", self.logo_backup, self._back_up)
        )
