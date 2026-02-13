import os
import shutil
import zipfile
from typing import Optional

from tqdm import tqdm
from loguru import logger
from datetime import datetime

from settings import settings


class FileBackuper:
    """Logic, related to backing up world"""

    def __init__(self):
        """Init"""

        self.temp_folder: Optional[str] = None
        self.zip_path:    Optional[str] = None

    def copy_world_to_temp_folder(self,
                                  world_paths: list[str]) -> None:
        """Creates copy of the worlds folders

        Args:
            world_paths: ABS-paths to world folders to copy them"""

        self._validate_paths(world_paths)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.temp_folder = os.path.join(settings.paths.BACKUP_DIR, f"world_{timestamp}")
        self.zip_path    = os.path.join(settings.paths.BACKUP_DIR, f"world_{timestamp}.zip")

        self._copy_folders_to_temp_location(self.temp_folder, world_paths)

    def zip_world(self) -> str | None:
        """Zips world folder (copy) and deletes temp-folder (copy of the world)

        Returns:
            ABS-zip-path, if successfully zipped"""

        logger.info('Zipping world...')

        try:
            self._zip_folders(self.temp_folder, self.zip_path)
            logger.info('Successfully zipped world!')
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

    def _copy_folders_to_temp_location(self,
                                       temp_folder: str,
                                       world_paths: list[str]) -> None:
        """Copies worlds (or single world) into tempt folder

        Args:
            temp_folder: Folder to copy worlds into
            world_paths: List with paths to worlds, to copy them into temp_folder"""

        os.makedirs(temp_folder, exist_ok=True)

        for world_path in world_paths:
            folder_name = os.path.basename(world_path)
            destination = os.path.join(temp_folder, folder_name)

            logger.info(f"Copying {folder_name} to temp directory {temp_folder}")
            shutil.copytree(world_path, destination)
            logger.info('Copied world successfully')

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
