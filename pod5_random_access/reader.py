from __future__ import annotations

import os
from logging import getLogger
from operator import itemgetter
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence, TypeVar

import numpy as np
import numpy.typing as npt

from .pod5_random_access_pybind import Pod5Index

logger = getLogger(__name__)
T = TypeVar("T")

INDEX_SUFFIX = ".idx"


def _is_rotational(path: Path) -> bool | None:
    """
    パスが存在するディスクが HDD (rotational) かどうかを判別する。

    Linux の /sys/dev/block を参照して判定する。
    Linux 以外や判別不能な場合は None を返す。

    Returns:
        True: HDD, False: SSD, None: 判別不能。
    """
    try:
        st = os.stat(path)
        major = os.major(st.st_dev)
        minor = os.minor(st.st_dev)
        sysfs = Path(f"/sys/dev/block/{major}:{minor}").resolve()
        # パーティション (sda1) の場合は親デバイス (sda) を辿る
        while sysfs.parent.name != "block":
            sysfs = sysfs.parent
        rotational = sysfs / "queue" / "rotational"
        return rotational.read_text().strip() == "1"
    except (OSError, ValueError):
        return None


class Pod5RandomAccessReader:
    """
    Pod5 ファイルからインデックスを使ってシグナルを読み込むクラス。

    Signal Table への直接アクセスにより、Read Table batch を経由しない。
    インデックスファイル (.pod5.idx) は pod5 ファイルの隣に自動生成される。
    既存の .pod5.idx があればロードし、なければビルドして保存する。

    Examples::

        reader = Pod5RandomAccessReader()
        reader.add_pod5("run1.pod5")
        reader.add_pod5("run2.pod5")

        signal = reader.fetch_signal("run1.pod5", uuid)

        # ディレクトリ一括追加
        reader.add_pod5_dir("/data/pod5/")
    """

    def __init__(self, *, save_index: bool = True) -> None:
        self._pod5_paths: dict[str, Path] = {}
        self._indexers: dict[str, Pod5Index] = {}
        self.save_index = save_index
        """インデックスファイルの自動保存を行うかどうかのデフォルト値。"""

    @staticmethod
    def _index_path_for(pod5_path: Path) -> Path:
        """pod5 ファイルパスから対応するインデックスファイルパスを導出する。"""
        return pod5_path.parent / (pod5_path.name + INDEX_SUFFIX)

    def _load_indexer(self, pod5_path: Path) -> Pod5Index:
        """
        既存の .pod5.idx からインデックスをロードする。

        Args:
            pod5_path: pod5 ファイルの絶対パス。

        Raises:
            FileNotFoundError: .pod5.idx が存在しない場合。
        """
        index_path = self._index_path_for(pod5_path)
        if not index_path.exists():
            raise FileNotFoundError(f"Index file not found: {index_path}")
        indexer = Pod5Index(str(pod5_path))
        indexer.load_index(str(index_path))
        logger.debug("Loaded index from %s", index_path)
        return indexer

    def _build_indexer(
        self, pod5_path: Path, *, save_index: bool = True
    ) -> Pod5Index:
        """
        Read Table を走査してインデックスをビルドする。

        save_index=True の場合、.pod5.idx への保存を試みる。
        保存に失敗した場合は warning を出力し、メモリ上のインデックスを使用する。

        Args:
            pod5_path: pod5 ファイルの絶対パス。
            save_index: インデックスファイルを保存するかどうか。
        """
        indexer = Pod5Index(str(pod5_path))
        indexer.build_index()
        if save_index:
            index_path = self._index_path_for(pod5_path)
            try:
                indexer.save_index(str(index_path))
                logger.debug("Built and saved index to %s", index_path)
            except (OSError, RuntimeError) as e:
                logger.warning("Could not save index to %s: %s", index_path, e)
        else:
            logger.debug("Built index in memory for %s", pod5_path.name)
        return indexer

    # ------------------------------------------------------------------
    #  ファイル追加
    # ------------------------------------------------------------------

    def add_pod5(
        self, pod5_path: str | Path, *, save_index: bool | None = None
    ) -> None:
        """
        Pod5 ファイルを追加する。

        - .pod5.idx が存在する場合: パスのみ登録し、ロードは初回アクセスまで遅延する。
        - .pod5.idx が存在しない場合: 即座にビルドし、save_index=True なら保存を試みる。

        Args:
            pod5_path: pod5 ファイルのパス。
            save_index: ビルド時にインデックスファイルを保存するかどうか。
                None の場合はインスタンスのデフォルト値 (self.save_index) を使用。
        """
        pod5_path = Path(pod5_path).resolve()
        if save_index is None:
            save_index = self.save_index
        name = pod5_path.name
        self._pod5_paths[name] = pod5_path

        index_path = self._index_path_for(pod5_path)
        if index_path.exists():
            # 遅延ロード: _get_indexer で初回アクセス時にロードされる
            logger.debug("Index found for %s — deferred loading", name)
        else:
            # 即座にビルド
            self._indexers[name] = self._build_indexer(
                pod5_path, save_index=save_index
            )

    def add_pod5_dir(self, pod5_dir: str | Path) -> None:
        """
        ディレクトリ内の全 .pod5 ファイルを再帰的に探索して追加する。

        各ファイルについて add_pod5 と同じルールで処理する:
        - .pod5.idx が存在する → パスのみ登録（遅延ロード）
        - .pod5.idx が存在しない → 即座にビルド＋保存

        Args:
            pod5_dir: 探索するディレクトリ。
        """
        pod5_dir = Path(pod5_dir)
        if not pod5_dir.is_dir():
            raise NotADirectoryError(f"{pod5_dir} is not a directory")

        pod5_files = sorted(pod5_dir.rglob("*.pod5"))
        if not pod5_files:
            logger.warning("No .pod5 files found in %s", pod5_dir)
            return

        for f in pod5_files:
            self.add_pod5(f)

        logger.info("Registered %d pod5 files from %s", len(pod5_files), pod5_dir)

    # ------------------------------------------------------------------
    #  pickle サポート
    # ------------------------------------------------------------------

    def __getstate__(self) -> dict[str, Any]:
        """pickle 時に Pod5Index (C++ オブジェクト) を除外する。_pod5_paths は保持される。"""
        state = self.__dict__.copy()
        state["_indexers"] = {}
        return state

    def _get_indexer(self, pod5_file_name: str) -> Pod5Index:
        """
        Pod5Index を取得する。未ロードの場合は .pod5.idx から遅延ロードする。

        add_pod5_dir で登録済みのファイルや、pickle 復元後のファイルは
        初回アクセス時に自動でロードされる。

        Args:
            pod5_file_name: Pod5 ファイル名。
        """
        if pod5_file_name not in self._indexers:
            if pod5_file_name not in self._pod5_paths:
                raise KeyError(
                    f"Pod5 file '{pod5_file_name}' not registered. "
                    "Call add_pod5() or add_pod5_dir() first."
                )
            self._indexers[pod5_file_name] = self._load_indexer(
                self._pod5_paths[pod5_file_name]
            )
        return self._indexers[pod5_file_name]

    # ------------------------------------------------------------------
    #  インデックス情報
    # ------------------------------------------------------------------

    @property
    def filenames(self) -> list[str]:
        """登録済みの pod5 ファイル名一覧を返す。"""
        return list(self._pod5_paths.keys())

    def list_read_ids(
        self, pod5_file_name: str, *, sort: bool = False
    ) -> list[str]:
        """
        指定ファイル内の全 read_id を返す。

        Args:
            pod5_file_name: Pod5 ファイル名。
            sort: True の場合、Signal Table 上の物理位置順にソートして返す。

        Returns:
            read_id 文字列のリスト。
        """
        indexer = self._get_indexer(pod5_file_name)
        read_ids = indexer.list_read_ids()
        if sort:
            read_ids = indexer.sort_uuids_by_location(read_ids)
        return read_ids

    def iter_read_ids(self) -> Iterator[tuple[str, str]]:
        """
        全ファイルの (filename, read_id) を Signal Table 物理位置順に yield する。

        ファイルごとに signal_row_start 昇順でイテレートするため、
        この順番で fetch_signal を呼ぶと HDD 上でシーケンシャルアクセスが実現される。
        """
        for filename in self.filenames:
            for read_id in self.list_read_ids(filename, sort=True):
                yield filename, read_id

    # ------------------------------------------------------------------
    #  シグナルアクセス
    # ------------------------------------------------------------------

    def get_calibration(
        self, pod5_file_name: str, uuid: bytes | str
    ) -> tuple[float, float]:
        """
        UUID のキャリブレーション情報をインデックスから取得する。

        Args:
            pod5_file_name: Pod5 ファイル名。
            uuid: 対象の UUID。

        Returns:
            (offset, scale) のタプル。
        """
        return self._get_indexer(pod5_file_name).get_calibration(uuid)

    def fetch_signal(
        self, pod5_file_name: str, uuid: bytes | str
    ) -> npt.NDArray[np.int16]:
        """
        UUID を指定してシグナルを取得する（Signal Table 直接アクセス）。

        Args:
            pod5_file_name: Pod5 ファイル名。
            uuid: 対象の UUID。

        Returns:
            シグナルデータ (int16)。
        """
        return self._get_indexer(pod5_file_name).fetch_signal(uuid)

    def fetch_pA_signal(
        self, pod5_file_name: str, uuid: bytes | str
    ) -> npt.NDArray[np.float32]:
        """
        UUID を指定して pA キャリブレーション済みシグナルを取得する。

        (raw_signal + offset) * scale で pA 値に変換済み。
        hashmap lookup は 1 回のみ。

        Args:
            pod5_file_name: Pod5 ファイル名。
            uuid: 対象の UUID。

        Returns:
            pA 変換済みシグナルデータ (float32)。
        """
        return self._get_indexer(pod5_file_name).fetch_pA_signal(uuid)

    def get_signal_length(self, pod5_file_name: str, uuid: bytes | str) -> int:
        """
        UUID のシグナル長をインデックスから取得する。

        Args:
            pod5_file_name: Pod5 ファイル名。
            uuid: 対象の UUID。

        Returns:
            サンプル数。
        """
        return self._get_indexer(pod5_file_name).get_signal_length(uuid)

    # ------------------------------------------------------------------
    #  HDD シーケンシャルアクセス最適化
    # ------------------------------------------------------------------

    def plan_fetch_order(
        self,
        items: Sequence[T],
        key: Callable[[T], tuple[str, bytes | str]] | None = None,
        *,
        filenames: Sequence[str] | None = None,
        uuids: Sequence[bytes | str] | None = None,
    ) -> list[T]:
        """
        任意のリストを Signal Table 上の物理位置順にソートする。

        ファイルごとにグルーピングし、各ファイル内で signal_row_start 昇順に
        ソートした結果をフラットに返す。このソート順で fetch_signal を呼ぶと
        HDD 上でシーケンシャルアクセスが実現される。

        (filename, uuid) の指定方法は 2 通り:
          - key: 各要素から (filename, uuid) を抽出する関数を渡す
          - filenames + uuids: 事前にリスト化した filename と uuid を直接渡す

        Args:
            items: ソート対象の任意のリスト。
            key: 各要素から (pod5_filename, uuid) を返す関数。
            filenames: 各要素に対応する pod5 ファイル名のリスト。
            uuids: 各要素に対応する UUID のリスト。

        Returns:
            Signal Table の物理位置順にソートされたリスト。

        Raises:
            ValueError: key も (filenames, uuids) も指定されていない場合。

        Examples:
            key 関数を使う場合::

                sorted_infos = reader.plan_fetch_order(
                    read_info_list,
                    key=lambda x: (x.filename, x.read_id),
                )

            filenames と uuids を直接渡す場合::

                sorted_infos = reader.plan_fetch_order(
                    read_info_list,
                    filenames=[x.filename for x in read_info_list],
                    uuids=[x.read_id for x in read_info_list],
                )
        """
        n = len(items)
        if n == 0:
            return []

        # --- key 抽出 or 直接受け取り ---
        if key is not None:
            keys = [key(item) for item in items]
            fns_seq, uuids_list = zip(*keys)
            filenames_arr = np.array(fns_seq)
            uuids_list = list(uuids_list)
        elif filenames is not None and uuids is not None:
            filenames_arr = np.asarray(filenames)
            uuids_list = list(uuids) if not isinstance(uuids, list) else uuids
        else:
            raise ValueError("key or (filenames, uuids) must be provided")

        # --- NumPy グルーピング ---
        unique_fns, inverse, counts = np.unique(
            filenames_arr, return_inverse=True, return_counts=True
        )
        group_indices = np.argsort(inverse, kind="stable")
        splits = np.cumsum(counts[:-1])
        groups = np.split(group_indices, splits)

        # --- ファイルごとに signal_row_start 順でソート ---
        result_indices: list[np.ndarray] = []
        for fn, idx in zip(unique_fns, groups):
            if len(idx) == 1:
                result_indices.append(idx)
                continue
            group_uuids = itemgetter(*idx.tolist())(uuids_list)
            starts = self._get_indexer(fn).get_signal_row_starts(group_uuids)
            order = np.argsort(starts)
            result_indices.append(idx[order])

        # --- fancy index で一括取得 ---
        final_order = np.concatenate(result_indices)
        items_arr = np.array(items, dtype=object)
        return items_arr[final_order].tolist()
