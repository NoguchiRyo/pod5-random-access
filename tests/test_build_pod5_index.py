from pod5_random_access import IndexSettings
from pathlib import Path


def test_build_pod5_index(pod5_dir: Path, pod5_index_dir: Path):
    pod5_filename = list(pod5_dir.glob("*.pod5"))[0].stem
    # Check if the index settings file exists
    assert pod5_index_dir.joinpath(IndexSettings.file_name).exists()
    assert pod5_index_dir.joinpath(f"{pod5_filename}.index").exists()
