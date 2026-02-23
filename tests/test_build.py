from pathlib import Path

from pod5_random_access.build import build_pod5_index
from pod5_random_access.reader import INDEX_SUFFIX


def test_build_creates_idx_files(pod5_dir: Path):
    """ディレクトリ内の全 .pod5 に対して .pod5.idx が生成される。"""
    pod5_files = sorted(pod5_dir.glob("*.pod5"))
    built = build_pod5_index(pod5_dir)

    assert len(built) == len(pod5_files)
    for f in pod5_files:
        idx_path = f.parent / (f.name + INDEX_SUFFIX)
        assert idx_path.exists(), f"Index not created for {f.name}"


def test_build_skips_existing(pod5_dir: Path):
    """既に .idx があるファイルはスキップされる。"""
    build_pod5_index(pod5_dir)
    built = build_pod5_index(pod5_dir)

    assert built == []


def test_build_force_rebuilds(pod5_dir: Path):
    """force=True で既存 .idx を無視して再ビルドする。"""
    build_pod5_index(pod5_dir)
    built = build_pod5_index(pod5_dir, force=True)

    pod5_files = sorted(pod5_dir.glob("*.pod5"))
    assert len(built) == len(pod5_files)


def test_build_empty_dir(tmp_path: Path):
    """pod5 がないディレクトリでは空リストが返る。"""
    empty = tmp_path / "empty"
    empty.mkdir()
    built = build_pod5_index(empty)

    assert built == []
