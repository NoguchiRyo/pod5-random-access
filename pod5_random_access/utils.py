from pathlib import Path


def fetch_all_pod5_paths(pod5_dir: Path) -> list[Path]:
    """
    Fetch all pod5 files from a given directory.

    Args:
        pod5_dir (Path): The directory containing pod5 files.

    Returns:
        list[Path]: A list of Paths to the pod5 files.
    """
    pod5_files: list[Path] = list(pod5_dir.rglob("*.pod5"))
    return pod5_files
