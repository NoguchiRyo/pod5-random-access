from pathlib import Path

from pod5_random_access.reader import Pod5RandomAccessReader


def _make_reader(pod5_file: Path) -> Pod5RandomAccessReader:
    reader = Pod5RandomAccessReader()
    reader.add_pod5(pod5_file)
    return reader


def _get_read_ids(reader: Pod5RandomAccessReader, pod5_file: Path) -> list[str]:
    return reader._get_indexer(pod5_file.name).list_read_ids()


def test_plan_fetch_order_with_key(pod5_file: Path):
    """key 関数指定で signal_row_start 昇順にソートされる。"""
    reader = _make_reader(pod5_file)
    name = pod5_file.name
    read_ids = _get_read_ids(reader, pod5_file)

    # (filename, uuid) のタプルリストを作成
    items = [(name, rid) for rid in read_ids]
    sorted_items = reader.plan_fetch_order(items, key=lambda x: (x[0], x[1]))

    # ソート後の signal_row_start が昇順であることを確認
    indexer = reader._get_indexer(name)
    starts = [indexer.get_signal_row_starts([item[1]])[0] for item in sorted_items]
    assert starts == sorted(starts)


def test_plan_fetch_order_with_filenames_uuids(pod5_file: Path):
    """filenames + uuids 指定で key 指定と同じ結果になる。"""
    reader = _make_reader(pod5_file)
    name = pod5_file.name
    read_ids = _get_read_ids(reader, pod5_file)

    items = [(name, rid) for rid in read_ids]

    sorted_by_key = reader.plan_fetch_order(items, key=lambda x: (x[0], x[1]))
    sorted_by_args = reader.plan_fetch_order(
        items,
        filenames=[x[0] for x in items],
        uuids=[x[1] for x in items],
    )

    assert sorted_by_key == sorted_by_args


def test_plan_fetch_order_empty(pod5_file: Path):
    """空リストで空リストが返る。"""
    reader = _make_reader(pod5_file)
    result = reader.plan_fetch_order([], key=lambda x: (x[0], x[1]))
    assert result == []


def test_plan_fetch_order_single(pod5_file: Path):
    """要素 1 つで正常動作する。"""
    reader = _make_reader(pod5_file)
    name = pod5_file.name
    read_ids = _get_read_ids(reader, pod5_file)

    items = [(name, read_ids[0])]
    result = reader.plan_fetch_order(items, key=lambda x: (x[0], x[1]))

    assert len(result) == 1
    assert tuple(result[0]) == items[0]
