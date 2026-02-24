import pickle
from pathlib import Path

import numpy as np
import pytest

from pod5_random_access.reader import INDEX_SUFFIX, Pod5RandomAccessReader


# ------------------------------------------------------------------
#  add_pod5 / add_pod5_dir
# ------------------------------------------------------------------


def test_add_pod5_builds_when_no_idx(pod5_file: Path):
    """.idx がない状態で add_pod5 → ビルドされ .idx が生成される。"""
    reader = Pod5RandomAccessReader()
    reader.add_pod5(pod5_file)

    idx_path = pod5_file.parent / (pod5_file.name + INDEX_SUFFIX)
    assert idx_path.exists()
    assert pod5_file.name in reader._indexers


def test_add_pod5_defers_when_idx_exists(pod5_file: Path):
    """.idx がある状態で add_pod5 → indexer は遅延ロード（_indexers に入らない）。"""
    # まずビルドして .idx を作る
    reader1 = Pod5RandomAccessReader()
    reader1.add_pod5(pod5_file)

    # 新しい reader で add_pod5 → .idx があるので遅延
    reader2 = Pod5RandomAccessReader()
    reader2.add_pod5(pod5_file)

    assert pod5_file.name in reader2._pod5_paths
    assert pod5_file.name not in reader2._indexers


def test_add_pod5_no_save(pod5_file: Path):
    """save_index=False → ビルドされるが .idx ファイルは作られない。"""
    reader = Pod5RandomAccessReader(save_index=False)
    reader.add_pod5(pod5_file)

    idx_path = pod5_file.parent / (pod5_file.name + INDEX_SUFFIX)
    assert not idx_path.exists()
    # indexer はメモリ上に存在する
    assert pod5_file.name in reader._indexers


def test_add_pod5_dir(pod5_dir: Path):
    """ディレクトリ内の全ファイルが _pod5_paths に登録される。"""
    reader = Pod5RandomAccessReader()
    reader.add_pod5_dir(pod5_dir)

    pod5_files = sorted(pod5_dir.glob("*.pod5"))
    assert len(reader._pod5_paths) == len(pod5_files)
    for f in pod5_files:
        assert f.name in reader._pod5_paths


# ------------------------------------------------------------------
#  シグナルアクセス
# ------------------------------------------------------------------


def _make_reader(pod5_file: Path) -> Pod5RandomAccessReader:
    """テスト用の reader を作成する。"""
    reader = Pod5RandomAccessReader()
    reader.add_pod5(pod5_file)
    return reader


def _get_read_ids(reader: Pod5RandomAccessReader, pod5_file: Path) -> list[str]:
    """登録済み indexer から read_id 一覧を取得する。"""
    return reader._get_indexer(pod5_file.name).list_read_ids()


def test_fetch_signal(pod5_file: Path):
    """シグナルが int16 ndarray で、長さが get_signal_length と一致する。"""
    reader = _make_reader(pod5_file)
    name = pod5_file.name
    read_ids = _get_read_ids(reader, pod5_file)

    for rid in read_ids:
        sig = reader.fetch_signal(name, rid)
        assert sig.dtype == np.int16
        assert len(sig) == reader.get_signal_length(name, rid)
        assert len(sig) > 0


def test_fetch_pA_signal(pod5_file: Path):
    """pA シグナルが float32 で、(raw + offset) * scale と一致する。"""
    reader = _make_reader(pod5_file)
    name = pod5_file.name
    read_ids = _get_read_ids(reader, pod5_file)

    rid = read_ids[0]
    raw = reader.fetch_signal(name, rid)
    pA = reader.fetch_pA_signal(name, rid)
    offset, scale = reader.get_calibration(name, rid)

    assert pA.dtype == np.float32
    expected = (raw.astype(np.float32) + offset) * scale
    np.testing.assert_allclose(pA, expected, rtol=1e-6)


def test_get_calibration(pod5_file: Path):
    """offset, scale が float で返る。"""
    reader = _make_reader(pod5_file)
    name = pod5_file.name
    read_ids = _get_read_ids(reader, pod5_file)

    offset, scale = reader.get_calibration(name, read_ids[0])
    assert isinstance(offset, float)
    assert isinstance(scale, float)


def test_get_signal_length(pod5_file: Path):
    """全 read で正の整数が返る。"""
    reader = _make_reader(pod5_file)
    name = pod5_file.name
    read_ids = _get_read_ids(reader, pod5_file)

    for rid in read_ids:
        length = reader.get_signal_length(name, rid)
        assert isinstance(length, int)
        assert length > 0


# ------------------------------------------------------------------
#  インデックス情報
# ------------------------------------------------------------------


def test_filenames(pod5_file: Path):
    """filenames プロパティが登録済みファイル名を返す。"""
    reader = _make_reader(pod5_file)
    assert reader.filenames == [pod5_file.name]


def test_list_read_ids(pod5_file: Path):
    """list_read_ids が全 read_id を返す。"""
    reader = _make_reader(pod5_file)
    read_ids = reader.list_read_ids(pod5_file.name)

    assert len(read_ids) == 10
    assert all(isinstance(rid, str) for rid in read_ids)


def test_list_read_ids_sorted(pod5_file: Path):
    """sort=True で signal_row_start 昇順に返される。"""
    reader = _make_reader(pod5_file)
    name = pod5_file.name
    sorted_ids = reader.list_read_ids(name, sort=True)

    indexer = reader._get_indexer(name)
    starts = indexer.get_signal_row_starts(sorted_ids)
    assert list(starts) == sorted(starts)


def test_iter_read_ids(pod5_file: Path):
    """iter_read_ids が全 (filename, read_id) を物理位置順で返す。"""
    reader = _make_reader(pod5_file)
    name = pod5_file.name

    pairs = list(reader.iter_read_ids())
    assert len(pairs) == 10
    assert all(fn == name for fn, _ in pairs)

    # 物理位置順であることを確認
    indexer = reader._get_indexer(name)
    starts = indexer.get_signal_row_starts([rid for _, rid in pairs])
    assert list(starts) == sorted(starts)


def test_unknown_uuid_raises(pod5_file: Path):
    """存在しない UUID で例外が発生する。"""
    reader = _make_reader(pod5_file)
    fake_uuid = "00000000-0000-0000-0000-000000000000"

    with pytest.raises(Exception):
        reader.fetch_signal(pod5_file.name, fake_uuid)


# ------------------------------------------------------------------
#  遅延ロード
# ------------------------------------------------------------------


def test_lazy_load_on_fetch(pod5_file: Path):
    """add_pod5_dir 後、fetch_signal で初めて indexer がロードされる。"""
    # まず .idx を作っておく
    reader1 = Pod5RandomAccessReader()
    reader1.add_pod5(pod5_file)
    read_ids = _get_read_ids(reader1, pod5_file)

    # 新しい reader で add_pod5_dir（遅延登録）
    reader2 = Pod5RandomAccessReader()
    reader2.add_pod5_dir(pod5_file.parent)
    assert pod5_file.name not in reader2._indexers

    # fetch_signal で初めてロードされる
    sig = reader2.fetch_signal(pod5_file.name, read_ids[0])
    assert pod5_file.name in reader2._indexers
    assert len(sig) > 0


# ------------------------------------------------------------------
#  pickle
# ------------------------------------------------------------------


def test_pickle_roundtrip(pod5_file: Path):
    """pickle → unpickle 後に fetch_signal が動く。"""
    reader = _make_reader(pod5_file)
    name = pod5_file.name
    read_ids = _get_read_ids(reader, pod5_file)

    data = pickle.dumps(reader)
    restored: Pod5RandomAccessReader = pickle.loads(data)

    # indexers はクリアされているが、fetch で再ロードされる
    assert name not in restored._indexers
    sig = restored.fetch_signal(name, read_ids[0])
    assert len(sig) > 0
    assert name in restored._indexers
