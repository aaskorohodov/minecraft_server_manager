import time
import random

from initializer.start_logos import START_LOGOS


class LogoPrinter:
    """Prints logo in startup"""

    @staticmethod
    def print_logo() -> None:
        """Print start logo"""

        start_logo = random.choice(START_LOGOS)
        for line in start_logo.splitlines():
            print(line)
            time.sleep(0.05)
