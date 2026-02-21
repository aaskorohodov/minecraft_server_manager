import os
import shutil
import zipfile

from tqdm import tqdm
from loguru import logger
from typing import Optional
from datetime import datetime

from settings import settings


class FileBackuper:
    """Logic, related to backing up world

    Attributes:
        temp_folder: ABS-path to folder with backups
        zip_path: ABS-path to zipped backup"""

    def __init__(self):
        """Init"""

        self.temp_folder: Optional[str] = None
        self.zip_path:    Optional[str] = None

    def copy_backups_to_temp_folder(self,
                                    backup_paths: list[str]) -> None:
        """Creates copy of folders and files that require to be backed up

        Args:
            backup_paths: ABS-paths to folders and files to copy them"""

        self._validate_paths(backup_paths)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.temp_folder = os.path.join(settings.paths.BACKUP_DIR, f"backup_{timestamp}")
        self.zip_path    = os.path.join(settings.paths.BACKUP_DIR, f"backup_{timestamp}.zip")

        self._copy_backups_to_temp_location(self.temp_folder, backup_paths)

    def zip_backup(self) -> str | None:
        """Zips backups folders and files (copy) and deletes temp-folder (copy of backup files and folders)

        Returns:
            ABS-zip-path, if successfully zipped, to backup-file"""

        logger.info('Zipping backups...')

        try:
            self._zip_folders(self.temp_folder, self.zip_path)
            logger.info('Successfully zipped backups!')
            return self.zip_path
        except Exception as e:
            logger.exception(e)
        finally:
            self.delete_temp_folder()

    def _validate_paths(self,
                        paths_to_validate: list[str]) -> None:
        """Checks if provided paths exist

        Args:
            paths_to_validate: Paths to check
        Raises:
            FileNotFoundError: In case any file from provided list is missing"""

        some_path_is_wrong = False
        for path in paths_to_validate:
            if not os.path.exists(path):
                logger.error(f"Backup aborted: Path does not exist: {path}")
                some_path_is_wrong = True
        if some_path_is_wrong:
            raise FileNotFoundError("Backup canceled as some path is wrong")

    def _copy_backups_to_temp_location(self,
                                       temp_folder: str,
                                       backups_paths: list[str]) -> None:
        """Copies worlds (or single world) into tempt folder

        Args:
            temp_folder: Folder to copy worlds into
            backups_paths: List with paths to folders and files, to copy them into temp_folder"""

        os.makedirs(temp_folder, exist_ok=True)

        for backup_item_path in backups_paths:
            original_backup_item_name = os.path.basename(backup_item_path)
            destination               = os.path.join(temp_folder, original_backup_item_name)

            # Collision Handling Logic
            counter = 1
            # Split extension only for files; directories keep their full name
            name_part, extension = os.path.splitext(original_backup_item_name)

            while os.path.exists(destination):
                new_name = f"{name_part}_{counter}{extension}"
                destination = os.path.join(temp_folder, new_name)
                counter += 1

            final_name = os.path.basename(destination)
            if final_name != original_backup_item_name:
                logger.warning(f"Collision detected! Renaming {original_backup_item_name} -> {final_name}")

            logger.info(f"Copying {original_backup_item_name} to temp directory {temp_folder}")
            if os.path.isdir(backup_item_path):
                shutil.copytree(backup_item_path, destination)
            else:
                shutil.copy2(backup_item_path, destination)  # copy2 preserves metadata

            logger.info(f'Copied {original_backup_item_name} successfully')

    def _zip_folders(self,
                     temp_copy: str,
                     zip_path: str) -> None:
        """Zips world with progress status

        Args:
            temp_copy: ABS-path to world-copy folder to zip
            zip_path: ABS-path to where zipped folder will be saved"""

        logger.info("Zipping all folders...")

        # Collect all files
        all_files = []
        for root, _, files in os.walk(temp_copy):
            for f in files:
                all_files.append(os.path.join(root, f))

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf, tqdm(
                total=len(all_files), unit="files", desc="Zipping world"
        ) as pbar:
            for abs_path in all_files:
                rel_path = os.path.relpath(abs_path, temp_copy)
                zipf.write(abs_path, rel_path)
                pbar.update(1)

    def delete_temp_folder(self) -> None:
        """Deletes temp folder, from where we were zipping"""

        if os.path.exists(self.temp_folder):
            shutil.rmtree(self.temp_folder)
            logger.info("Temporary files cleaned up.")
