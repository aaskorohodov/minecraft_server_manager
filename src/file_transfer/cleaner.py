import os

from loguru import logger
from datetime import datetime, timedelta


class BackupsCleaner:
    """Deletes old backup"""

    @staticmethod
    def cleanup_old_backups(backup_days: int,
                            folder_to_check: str) -> None:
        """Remove .zip backups older than given number of days

        Args:
            backup_days: Files, older than this number of days, will be deleted
            folder_to_check: Folder to delete files in"""

        backup_days_delta = datetime.now() - timedelta(days=backup_days)

        deleted = 0
        for filename in os.listdir(folder_to_check):
            if not filename.startswith("world_") or not filename.endswith(".zip"):
                continue

            file_path = os.path.join(folder_to_check, filename)
            try:
                # Parse timestamp from filename: world_YYYYMMDD_HHMMSS.zip
                time_part = filename[len("world_"):-4]  # remove prefix + ".zip"
                file_time = datetime.strptime(time_part, "%Y%m%d_%H%M%S")

                if file_time < backup_days_delta:
                    os.remove(file_path)
                    deleted += 1
            except Exception as e:
                logger.warning(f"[WARN] Skipped file {filename}: {e}")

        if deleted:
            logger.info(f"[{datetime.now()}] Deleted {deleted} old backup(s) older than {backup_days} days")
        else:
            logger.info(f"[{datetime.now()}] No old backups found for deletion")
