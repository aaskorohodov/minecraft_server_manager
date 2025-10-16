import threading
import time

from main_comm import MainComm
from server_manager import MinecraftServerManager
from trayer.trayer import Trayer


main_comm = MainComm()
Trayer(main_comm)
server_manager = MinecraftServerManager(main_comm)
threading.Thread(target=server_manager.run, daemon=True).start()

while main_comm.trayer_running:
    time.sleep(1)
