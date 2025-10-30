import os
import requests

from tqdm import tqdm
from loguru import logger
from typing import BinaryIO

from settings import settings


class ProgressFile:
    """Wrapper around a binary file that reports read progress to a tqdm bar

    This class is useful for tracking upload progress when streaming a file through an HTTP request
    (e.g., with the ``requests`` library). Each time a chunk is read from the underlying file,
    the tqdm progress bar is updated

    Attributes:
        file: The underlying binary file object being read
        progress: A tqdm progress bar used to visualize upload progress"""

    def __init__(self, file: BinaryIO, progress: tqdm) -> None:
        """Initialize the progress-tracking file wrapper

        Args:
            file: Open file object in binary mode (e.g. ``open(path, "rb")``)
            progress: tqdm progress bar instance to update as data is read"""

        self.file:     BinaryIO = file
        self.progress: tqdm     = progress

    def read(self, size: int = -1) -> bytes:
        """Read bytes from the file and update the progress bar

        Args:
            size: Maximum number of bytes to read. Defaults to -1, meaning read the entire remaining file

        Returns:
            The bytes read from the file. Returns an empty bytes object when end of file is reached"""

        chunk = self.file.read(size)
        if chunk:
            self.progress.update(len(chunk))
        return chunk

    def __getattr__(self,
                    attr: any) -> any:
        """Delegate attribute access to the underlying file object

        Args:
            attr: attr to read"""

        return getattr(self.file, attr)


class HttpFileSender:
    """Send zipped world backup to remote server via HTTP"""

    def __init__(self,
                 file_to_send_path: str):
        """Init

        Args:
            file_to_send_path: ABS-path to a file we want to send"""

        self.file_to_send_path: str = file_to_send_path
        self.file_size:         int = os.path.getsize(file_to_send_path)
        self.file_name:         str = os.path.basename(file_to_send_path)

    def send(self) -> bool:
        """Send file via HTTP

        Returns:
            True, in case file was sent"""

        try:
            with open(self.file_to_send_path, 'rb') as f, tqdm(total=self.file_size,
                                                               unit='B',
                                                               unit_scale=True,
                                                               unit_divisor=1024,
                                                               desc=f"Uploading {self.file_name}") as progress:
                response = requests.post(
                    f"http://{settings.RECEIVER_IP}:{settings.RECEIVER_PORT}",
                    data=ProgressFile(f, progress),
                    headers={
                        'X-Auth-Token': settings.RECEIVER_TOKEN.get_secret_value(),
                        'X-Filename': self.file_name,
                    },
                    timeout=1800,  # 30 minutes
                )

            logger.info(f"Server responded: {response.status_code} - {response.text}")
            return True
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP error {response.status_code}: {response.text.strip() or http_err}"
            )
        except requests.exceptions.ConnectionError as conn_err:
            logger.error(f"Connection error: {conn_err}")
        except requests.exceptions.Timeout:
            logger.error("Upload timed out!")
        except Exception as e:
            logger.exception(e)
            return False
