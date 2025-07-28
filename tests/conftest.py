from pathlib import Path
import pytest
import shutil

from pod5_random_access.build import build_pod5_index


@pytest.fixture
def pod5_dir(tmp_path: Path):
    source_dir = Path(__file__).parent / "data"
    folder_name = "pod5_dir"

    source_path = source_dir / folder_name
    destination_path = tmp_path / folder_name
    if not source_path.exists():
        raise FileNotFoundError(f"Source directory {source_path} does not exist.")
    shutil.copytree(source_path, destination_path)

    yield destination_path


@pytest.fixture
def pod5_index_dir(pod5_dir: Path, tmp_path: Path):
    pod5_index_dir = tmp_path / "pod5_index"
    pod5_index_dir.mkdir(exist_ok=True)
    build_pod5_index(pod5_dir, pod5_index_dir)
    return pod5_index_dir
