"""Checks processes and closes them"""

import psutil


class InstanceChecker:
    """Checks processes and closes them"""

    def is_this_script_running(self, your_file_name: str) -> bool:
        """Checks, if there are other copies of some script already running

        Args:
            your_file_name: file_name, that needs to be checked

        Returns:
            True, if this script is already running, otherwise False"""

        running_script_copies = 0

        for process in psutil.process_iter():
            if process.name() == 'python.exe':
                for cmd_line in process.as_dict()['cmdline']:
                    if your_file_name in cmd_line:
                        running_script_copies += 1

        if running_script_copies > 1:
            return True
        else:
            return False

    def kill_process(self, your_file_name: str) -> bool:
        """Finds a process, by provided script_name, and kills it

        Args:
            your_file_name: file_name, that needs to be closed (without extension!)
        Returns:
            True, if process was found, otherwise False"""

        killed = False

        # 'try' is essential, DO NOT REMOVE!
        try:
            for process in psutil.process_iter():
                if process.name() == 'python.exe':
                    for cmd_line in process.as_dict()['cmdline']:
                        if your_file_name in cmd_line:
                            process.kill()
                            killed = True
        except:
            pass

        return killed
