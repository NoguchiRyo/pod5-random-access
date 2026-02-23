from pathlib import Path
import shutil

import pytest


DATA_DIR = Path(__file__).parent / "data" / "pod5_dir"


@pytest.fixture
def pod5_dir(tmp_path: Path) -> Path:
    """テスト用 pod5 ファイルを tmp_path にコピーして返す。"""
    dest = tmp_path / "pod5_dir"
    shutil.copytree(DATA_DIR, dest)
    return dest


@pytest.fixture
def pod5_file(pod5_dir: Path) -> Path:
    """テスト用の単一 pod5 ファイルパスを返す。"""
    return sorted(pod5_dir.glob("*.pod5"))[0]
