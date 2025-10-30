import os
import sys
import traceback

from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    parent = str(Path(__file__).resolve().parents[1])
    print(parent)
    sys.path.append(parent)
    from settings import settings
    from file_transfer.cleaner import BackupsCleaner
except Exception as e:
    import time

    traceback.print_exc()
    time.sleep(10)


CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB


class SafeFileReceiver(BaseHTTPRequestHandler):
    """Receives files over HTTP, saves them, and cleans old files"""

    def _check_token(self) -> bool:
        """Checks auth token

        Returns:
            True, if token is correct"""

        token = self.headers.get('X-Auth-Token')
        if token != settings.RECEIVER_TOKEN.get_secret_value():
            self._send_error(403, "Forbidden: Invalid token")
            return False
        return True

    def _get_length_from_headers(self) -> int | None:
        """Checks of there is a length header, as it is essential

        Returns:
            Length from header, if header present in HTTP-request"""

        length = self.headers.get('Content-Length')
        if not length:
            self._send_error(400, "Missing Content-Length")
            return
        return int(length)

    def _write_file_in_chunks(self,
                              file_path: str,
                              length: int) -> int:
        """Writes file in chunks as we keep receiving them

        Args:
            file_path: ABS-path with file_name, where we will save file
            length: Expected length of the file in bytes
        Returns:
            Number of saved bytes"""

        bytes_written = 0
        with open(file_path, 'wb') as f:
            while bytes_written < length:
                chunk = self.rfile.read(min(CHUNK_SIZE, length - bytes_written))
                if not chunk:
                    break
                f.write(chunk)
                bytes_written += len(chunk)

        return bytes_written

    def do_POST(self):
        """Post request handler"""

        try:
            print('Upload started')
            if not self._check_token():
                return

            length = self._get_length_from_headers()
            if not length:
                return

            filename = self.headers.get('X-Filename', 'received_file')
            os.makedirs(settings.RECEIVER_DIR, exist_ok=True)
            file_path = os.path.join(settings.RECEIVER_DIR, filename)

            # noinspection PyTypeChecker
            bytes_written = self._write_file_in_chunks(file_path, length)
            if bytes_written < length:
                self._send_error(499, f"Incomplete upload: got {bytes_written}/{length} bytes")
                return

            self._send_ok(f"File '{filename}' received successfully ({bytes_written} bytes)")
            BackupsCleaner.cleanup_old_backups(
                backup_days=settings.BACK_UP_DAYS,
                folder_to_check=settings.RECEIVER_DIR
            )

        except Exception as ex:
            traceback.print_exc()
            self._send_error(500, f"Internal server error: {ex}")

    def _send_ok(self,
                 message: str) -> None:
        """Send ok message to receiver with code 200

        Args:
            message: Message in body"""

        self.send_response(200)
        self.end_headers()
        self.wfile.write(message.encode())

    def _send_error(self,
                    code: int,
                    message: str) -> None:
        """Send error message to receiver

        Args:
            code: Error code to send
            message: Message in body"""

        print(f'Sending error with code {code}')
        self.send_response(code)
        self.end_headers()
        self.wfile.write(message.encode())


def main():
    print('Receiver running...')
    # noinspection PyTypeChecker
    server = HTTPServer(('0.0.0.0', settings.RECEIVER_PORT), SafeFileReceiver)
    print(f"Receiver running on port {settings.RECEIVER_PORT}...")
    server.serve_forever()


if __name__ == "__main__":
    main()
