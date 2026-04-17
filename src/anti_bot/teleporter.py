from loguru import logger
from typing import TYPE_CHECKING

from settings import settings
from anti_bot.models import TrackedUser

if TYPE_CHECKING:
    from server_communicator.communicator import ServerCommunicator


class Teleporter:
    """Teleports Users

    Attributes:
        _server_comm: Communicator to send commands to server with"""

    def __init__(self,
                 server_comm: 'ServerCommunicator'):
        """Init

        Args:
            server_comm: Communicator to send commands to server with"""

        self._server_comm: 'ServerCommunicator' = server_comm

    def teleport_to_spawn(self,
                          user: TrackedUser) -> None:
        """Teleports User to spawn

        Args:
            user: User to teleport"""

        logger.warning(f'Teleporting User {user.name} to spawn...')
        spawn_coords = (f'{settings.antibot.SPAWN_POINT_X} '
                        f'{settings.antibot.SPAWN_POINT_Y} '
                        f'{settings.antibot.SPAWN_POINT_Z}')
        command = f'teleport {user.name} {spawn_coords}'
        self._server_comm.send_to_server(command)
