from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from logging import getLogger
from pathlib import Path

from .pod5_random_access_pybind import Pod5Index
from .reader import INDEX_SUFFIX, _is_rotational

logger = getLogger(__name__)


def _build_single(pod5_path: Path) -> None:
    """1 つの pod5 ファイルに対してインデックスをビルドし保存する。"""
    index_path = pod5_path.parent / (pod5_path.name + INDEX_SUFFIX)
    if index_path.exists():
        logger.debug("Index already exists, skipping: %s", index_path)
        return

    indexer = Pod5Index(str(pod5_path))
    indexer.build_index()
    indexer.save_index(str(index_path))
    logger.info("Built index: %s", index_path)


def build_pod5_index(
    pod5_dir: str | Path,
    *,
    max_workers: int | None = None,
    force: bool = False,
) -> list[Path]:
    """
    ディレクトリ内の全 .pod5 ファイルに対してインデックスをビルドし保存する。

    既存の .pod5.idx があるファイルはスキップする（force=True で強制再ビルド）。
    SSD 上では自動的にマルチスレッドで並列ビルドし、
    HDD 上では順次ビルドする。

    Args:
        pod5_dir: .pod5 ファイルを含むディレクトリ。
        max_workers: 並列ワーカー数。
            None: SSD なら os.cpu_count()、HDD または判別不能なら 1（自動判別）。
            1: 強制順次処理。
            N (>1): 強制 N 並列。
        force: True の場合、既存の .pod5.idx を無視して再ビルドする。

    Returns:
        ビルド対象となった pod5 ファイルのパスのリスト。
    """
    pod5_dir = Path(pod5_dir)
    if not pod5_dir.is_dir():
        raise NotADirectoryError(f"{pod5_dir} is not a directory")

    all_pod5 = sorted(pod5_dir.rglob("*.pod5"))
    if not all_pod5:
        logger.warning("No .pod5 files found in %s", pod5_dir)
        return []

    # --- ビルド対象の選別 ---
    if force:
        targets = all_pod5
    else:
        targets = [
            f for f in all_pod5
            if not (f.parent / (f.name + INDEX_SUFFIX)).exists()
        ]

    if not targets:
        logger.info("All index files already exist — nothing to build")
        return []

    logger.info(
        "%d / %d files need index building in %s",
        len(targets), len(all_pod5), pod5_dir,
    )

    # --- ワーカー数の決定 ---
    if max_workers is None:
        rotational = _is_rotational(pod5_dir)
        if rotational is None or rotational:
            max_workers = 1
            logger.debug("HDD or unknown disk type — sequential build")
        else:
            max_workers = os.cpu_count() or 1
            logger.debug("SSD detected — using %d workers", max_workers)

    # --- 順次ビルド ---
    if max_workers == 1:
        for f in targets:
            _build_single(f)
        return targets

    # --- 並列ビルド (SSD) ---
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_build_single, f): f for f in targets}
        for future in as_completed(futures):
            pod5_file = futures[future]
            try:
                future.result()
            except Exception:
                logger.error(
                    "Failed to build index for %s", pod5_file.name, exc_info=True
                )

    return targets
