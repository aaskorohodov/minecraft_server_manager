import os


def find_my_file(file_to_find_name: str,
                 start_dir: str = ".") -> str:
    """Searches for file recursively, starting from start_dir and walking up each parent folder

    At each step, it also searches all subfolders.

    Args:
        file_to_find_name: Name of the file you need to find
        start_dir: Dir, from which to start searching
    Returns:
        Path to file or empty string"""

    current_dir = os.path.abspath(start_dir)

    while True:
        # Walk through current_dir and its subdirectories
        for root, dirs, files in os.walk(current_dir):
            if file_to_find_name in files:
                return os.path.join(root, file_to_find_name)

        # Move one directory up
        parent_dir = os.path.dirname(current_dir)

        # If we reached the root directory, break the loop
        if parent_dir == current_dir:
            break

        current_dir = parent_dir

    return ''
