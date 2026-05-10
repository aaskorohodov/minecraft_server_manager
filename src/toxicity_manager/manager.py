import os.path
import pymorphy3

from loguru import logger
from typing import TYPE_CHECKING
from better_profanity import profanity

from settings import settings

if TYPE_CHECKING:
    from server_communicator.communicator import ServerCommunicator


class ToxicityManager:
    """Searches toxicity in messages and punishes for it

    Attributes:
        bad_words: List with bad words
        profanity: Profanity to check messages
        morph: Helper to morph text

        _server_comm: Communicator to send commands with"""

    def __init__(self,
                 server_comm: 'ServerCommunicator'):
        """Init

        Args:
            server_comm: Communicator to send commands with"""

        self.bad_words: list[str]               = []
        self.profanity: profanity               = profanity
        self.morph:     pymorphy3.MorphAnalyzer = pymorphy3.MorphAnalyzer()

        self._server_comm: 'ServerCommunicator' = server_comm

        self._read_words()

    def _read_words(self) -> None:
        """Reads words and gets checker ready"""

        try:
            if settings.paths.BAD_WORDS and os.path.exists(settings.paths.BAD_WORDS):
                with open(settings.paths.BAD_WORDS, encoding='utf-8') as f:
                    raw_bad_words  = f.read().splitlines()
                    bad_words = []
                    for w in raw_bad_words:
                        bad_words.append(w.replace('ё', 'е'))
                    self.bad_words = raw_bad_words
                    self.profanity.add_censor_words(self.bad_words)
            else:
                logger.warning(f'Path to bad words is empty or invalid: {settings.paths.BAD_WORDS}')
        except Exception as e:
            logger.exception(e)

    def _normalize_text(self,
                        text_to_normilize: str) -> str:
        """Normalizes text to better profanity-check it

        Args:
            text_to_normilize: Text to normalize
        Returns:
            Normalized text"""

        words = text_to_normilize.split()
        pre_normalized_words = []
        normalized_words = []
        for word in words:
            # Strip punctuation and get the lemma
            clean_word = word.strip('.,!?-')
            lemma = self.morph.parse(clean_word)[0].normal_form
            pre_normalized_words.append(lemma)

        for el in pre_normalized_words:
            el = el.replace('ё', 'е')
            normalized_words.append(el)

        return " ".join(normalized_words)

    def check_text(self,
                   text_to_check: str,
                   user_name: str) -> None:
        """Checks if message contains profanity

        Args:
            text_to_check: Text to check
            user_name: User-name to punish, in case text contains profanity"""

        try:
            normalized_input = self._normalize_text(text_to_check)
            has_bad_word = self.profanity.contains_profanity(normalized_input)
            if has_bad_word:
                logger.warning(f'User {user_name} will be punished for: {text_to_check=}')
                self._punish(user_name)
        except Exception as e:
            logger.exception(e)

    def _punish(self,
                user_name: str) -> None:
        """Punished User

        Args:
            user_name: User to punish"""

        command = f'msg {user_name} Language!'
        self._server_comm.send_to_server(command)

        command = f'effect give {user_name} minecraft:instant_damage 1'
        self._server_comm.send_to_server(command)

        command = f'effect give {user_name} minecraft:levitation 5'
        self._server_comm.send_to_server(command)


if __name__ == '__main__':
    from unittest.mock import Mock

    manager = ToxicityManager(server_comm=Mock())
    text = 'тупой ты убью'
    manager.check_text(text, 'user_name')
