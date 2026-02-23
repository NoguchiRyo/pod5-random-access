"""
POD5 signal-index with direct Signal Table access
"""

from __future__ import annotations
import numpy as np
import numpy.typing as npt
from typing import Iterable

__all__ = ["Pod5Index", "SigLoc"]

class Pod5Index:
    def __init__(self, pod5_file: str) -> None: ...
    def build_index(self) -> None:
        """Read Table を走査してインデックスを構築"""

    def save_index(self, path: str) -> None:
        """インデックスをバイナリファイルに保存"""

    def load_index(self, path: str) -> None:
        """バイナリファイルからインデックスを読み込み"""

    def fetch_signal(self, uuid: bytes | str) -> npt.NDArray[np.int16]:
        """Signal Table から直接シグナルを取得 (numpy int16 array)"""

    def fetch_pA_signal(self, uuid: bytes | str) -> npt.NDArray[np.float32]:
        """pA キャリブレーション済みシグナルを取得 (numpy float32 array)"""

    def get_calibration(self, uuid: bytes | str) -> tuple[float, float]:
        """インデックスから (offset, scale) タプルを返す"""

    def get_calibration_offset(self, uuid: bytes | str) -> float: ...
    def get_calibration_scale(self, uuid: bytes | str) -> float: ...
    def get_signal_length(self, uuid: bytes | str) -> int:
        """インデックスからシグナル長を返す"""

    def list_read_ids(self) -> list[str]:
        """インデックス内の全 read_id 文字列を返す"""

    def sort_uuids_by_location(self, uuids: Iterable[bytes | str]) -> list[bytes | str]:
        """UUID リストを Signal Table 上の物理位置順にソート"""

    def get_signal_row_starts(self, uuids: Iterable[bytes | str]) -> npt.NDArray[np.uint64]:
        """UUID リストの signal_row_start を一括取得 (numpy uint64 array)"""

class SigLoc:
    def __repr__(self) -> str: ...
    @property
    def signal_row_start(self) -> int: ...
    @property
    def signal_row_count(self) -> int: ...
    @property
    def n_samples(self) -> int: ...
    @property
    def calibration_offset(self) -> float: ...
    @property
    def calibration_scale(self) -> float: ...
