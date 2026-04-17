import time
import threading

from loguru import logger
from typing import TYPE_CHECKING

from settings import settings
from anti_bot.storage import STORAGE
from anti_bot.models import TrackedUser, TrackedIp

if TYPE_CHECKING:
    from server_communicator.communicator import ServerCommunicator


class Kicker:
    """Logic related to kicking Users

    Attributes:
        _server_comm: Communicator to send commands to server with"""

    def __init__(self,
                 server_comm: 'ServerCommunicator'):
        """Init

        Args:
            server_comm: Communicator to send commands to server with"""

        self._server_comm: 'ServerCommunicator' = server_comm

    def kick_by_user_name(self,
                          user_name: str) -> None:
        """Kicks by user_name with no sanctions

        Args:
            user_name: User to kick"""

        logger.warning(f'Kicking user_name {user_name} with no sanctions')
        reason = 'Something went wrong, try reconnecting. If error persists let us know on discord kPefhkduWZ'
        command = f'kick {user_name} {reason}\n'
        self._server_comm.send_to_server(command)

    def kick_due_to_login_sanctions(self,
                                    user: 'TrackedUser') -> None:
        """Kicks User on login, as User is not currently allowed to join server

        Args:
            user: User to kick"""

        login_again_after = user.get_seconds_till_login_allowed()
        reason            = f'Next login is allowed after {login_again_after} seconds. Wait a bit'
        threading.Thread(target=self._kick_on_login, args=(user, reason)).start()

    def kick_due_to_same_ip_sanctions(self,
                                      user: 'TrackedUser') -> None:
        """Kicks User on login, when same IP already has another User, that had not left spawn yet

        Args:
            user: User to kick"""

        reason = 'You already logged in from another account. Wait a bit, till we figure it out'
        threading.Thread(target=self._kick_on_login, args=(user, reason,)).start()

    def kick_due_to_login_bursts(self,
                                 users_to_kick: list[TrackedUser]) -> None:
        """Kicks Users with some delay between kicks

        Args:
            users_to_kick: Users to kick"""

        time.sleep(1)
        for user in users_to_kick:
            if not user.initial_coordinates or not user.ip:
                self._wait_for_data(user)
            time.sleep(0.05)
            self._kick_user(user=user, reason='Are you a bot?', add_relogin_extra=True)

    def kick_due_to_static(self,
                           static_in_spawn_point: list[TrackedUser],
                           static_in_spawn_area: list[TrackedUser]) -> None:
        """Kicks Users that are static

        Args:
            static_in_spawn_point: Users, that are static in spawn point
            static_in_spawn_area: Users, that are static in spawn area"""

        for user in static_in_spawn_point:
            self._kick_user(user,
                            reason='Please leave spawn point',
                            login_again_after=settings.antibot.KICK_COOLDOWN_STATIC_POINT_SECONDS)
            time.sleep(0.05)
        for user in static_in_spawn_area:
            self._kick_user(user,
                            reason='Please leave spawn area',
                            login_again_after=settings.antibot.KICK_COOLDOWN_STATIC_AREA_SECONDS)
            time.sleep(0.05)

    def kick_due_to_disconnected(self,
                                 users_to_kick: list[TrackedUser]) -> None:
        """Kicks Users that are most likely were disconnected shortly after login

        Args:
            users_to_kick: Users to kick"""

        for user in users_to_kick:
            self._kick_user(user, reason='Unable to get your coordinates. Try to login again in a minute')
            time.sleep(0.05)

    def _kick_on_login(self,
                       user: TrackedUser,
                       reason: str) -> None:
        """Kicks user, that is not yet allowed to login

        Args:
            user: User to kick
            reason: Reason for kick"""

        if not user.initial_coordinates or not user.ip:
            self._wait_for_data(user)

        time.sleep(0.05)
        login_again_after = user.get_seconds_till_login_allowed()
        self._kick_user(user,
                        reason=reason,
                        login_again_after=login_again_after,
                        save_ip=False,
                        update_kick_counter=False)

    def _kick_user(self,
                   user:                TrackedUser,
                   reason:              str,
                   login_again_after:   int = settings.antibot.KICK_COOLDOWN_DEFAULT_SECONDS,
                   add_relogin_extra:   bool = False,
                   update_kick_counter: bool = True,
                   save_ip:             bool = True) -> None:
        """Kicks users and saves IP of a kicked user

        Args:
            user: User to kick
            reason: Reason to kick
            login_again_after: Seconds to allow user to login again
            add_relogin_extra: If we should add additional several seconds for wait cooldown before relogin
            update_kick_counter: If set to False, kick will be made in soft manner - without updating counter
            save_ip: If user should be saved in kicked IPs"""

        logger.info(f'Kicking {user.name}, {reason=}')
        try:
            command = f'kick {user.name} {reason}\n'
            self._server_comm.send_to_server(command)
            if update_kick_counter:
                user.kicked_event(login_again_after, add_relogin_extra)
            logger.info(f'User {user.name} has {user.kicked_count} kicks')
        except Exception as e:
            logger.error(f'Was not able to kick user {user.name}')
            logger.exception(e)

        STORAGE.untrack_user(user)
        if save_ip:
            STORAGE.save_kicked_ip(user)

    def ban_ips(self,
                ips_to_ban: list[TrackedIp]) -> None:
        """Bans provided IPs

        Args:
            ips_to_ban: IPs to ban"""

        for ip in ips_to_ban:
            reason = ip.get_next_ban_time()
            logger.warning(f'Banning IP: {ip.ip} {reason=}')
            command = f'ban-ip {ip.ip} {reason}\n'
            try:
                self._server_comm.send_to_server(command)
                ip.save_ban()
                time.sleep(0.05)
            except Exception as e:
                logger.exception(e)

    def unban_ips(self,
                  ips_to_unban: list[TrackedIp]) -> None:
        """Unbans IPs

        Args:
            ips_to_unban: IPs to unban"""

        for ip in ips_to_unban:
            if not ip.banned:
                continue
            logger.warning(f'Unbanning IP: {ip.ip}')
            command = f'pardon-ip {ip.ip}\n'
            try:
                self._server_comm.send_to_server(command)
                ip.save_unban()
                STORAGE.drop_kick_counter(ip)
                time.sleep(0.05)
            except Exception as e:
                logger.exception(e)

    def _wait_for_data(self,
                       user: TrackedUser) -> None:
        """Waits a bit for receiving data for user

        Args:
            user: User to wait for"""

        for _ in range(20):
            # Check if we have what we need
            if user.initial_coordinates and user.ip:
                return  # Exit early because we have the data

            time.sleep(1)
