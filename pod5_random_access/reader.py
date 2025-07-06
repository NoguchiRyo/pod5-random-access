from .pod5_random_access_pybind import Pod5Index
from .settings import IndexSettings
import numpy as np
import numpy.typing as npt
from typing import Sequence, Any
from concurrent.futures import ThreadPoolExecutor
import itertools


class Pod5RandomAccessReader:
    """
    Class to read a Pod5 file and its index.
    This class is used to read the signal data from a Pod5 file using the index.
    """

    def __init__(self) -> None:
        """
        Initialize the Pod5RandomAccessReader with the index settings.

        Args:
            settings (IndexSettings): Index settings containing the Pod5 file and index file paths.
        """
        self.settings = IndexSettings()
        self.indexers: dict[str, Pod5Index] = {}

    def add_pod5_index_settings(self, index_settings: IndexSettings) -> None:
        """
        Add Pod5 file and index file paths to the settings.

        Args:
            index_settings (IndexSettings): Index settings containing the Pod5 file and index file paths.
        """
        self.settings += index_settings

    def __getstate__(self) -> dict[str, Any]:
        state = self.__dict__.copy()
        state["indexers"] = {}
        return state

    def get_or_load_indexer(self, pod5_file_name: str) -> Pod5Index:
        """
        Load the index for the given Pod5 file.

        Args:
            pod5_file (Path): Path to the Pod5 file.
        """
        if pod5_file_name not in self.indexers:
            indexer = Pod5Index(str(self.settings.get_pod5_file_path(pod5_file_name)))
            indexer.load_index(str(self.settings.get_pod5_index_path(pod5_file_name)))
            self.indexers[pod5_file_name] = indexer
        return self.indexers[pod5_file_name]

    def get_calibration(
        self, pod5_file_name: str, uuid: bytes | str
    ) -> tuple[float, float]:
        """
        Get the calibration offset and scale for the given UUID from the Pod5 file.

        Args:
            pod5_file_name (str): Name of the Pod5 file.
            uuid (bytes | str): UUID of the signal.

        Returns:
            tuple[float, float]: Calibration offset and scale.
        """
        return self.get_or_load_indexer(pod5_file_name).get_calibration(uuid)

    def fetch_signal(
        self, pod5_file_name: str, uuid: bytes | str
    ) -> npt.NDArray[np.int16]:
        """
        Fetch the signal data for the given UUID from the Pod5 file.

        Args:
            pod5_file_name (str): Name of the Pod5 file.
            uuid (bytes | str): UUID of the signal to fetch.

        Returns:
            npt.NDArray[np.int16]: Signal data as a numpy array.
        """
        return self.get_or_load_indexer(pod5_file_name).fetch_signal(uuid)

    def fetch_signals_from_file(
        self, pod5_file_name: str, uuid_list: Sequence[bytes | str]
    ) -> list[npt.NDArray[np.int16]]:
        """
        Fetch the signal data for the given UUIDs from the Pod5 file.

        Args:
            pod5_file_name (str): Name of the Pod5 file.
            uuid_list (Sequence[bytes | str]): List of UUIDs of the signals to fetch.

        Returns:
            list[npt.NDArray[np.int16]]: List of signal data as numpy arrays.
        """
        return self.get_or_load_indexer(pod5_file_name).fetch_signals(uuid_list)

    def fetch_signals(
        self,
        filename_and_uuid_list: Sequence[tuple[str, bytes | str]],
        max_workers: int = 4,
    ) -> list[npt.NDArray[np.int16]]:
        """
        Fetch the signal data for the given UUIDs from the Pod5 files.
        Args:
            filename_and_uuid_list (Sequence[tuple[str, bytes | str]]):
                List of tuples containing the Pod5 file name and UUID of the signals to fetch.

        Returns:
            list[npt.NDArray[np.int16]]: List of signal data as numpy arrays.
        """
        # First, group the UUIDs by their Pod5 file name
        grouped_uuids: dict[str, list[bytes | str]] = {}
        for pod5_file_name, uuid in filename_and_uuid_list:
            if pod5_file_name not in grouped_uuids:
                grouped_uuids[pod5_file_name] = []
            grouped_uuids[pod5_file_name].append(uuid)

        def fetch_signals_from_file(
            item: tuple[str, list[bytes | str]],
        ) -> list[npt.NDArray[np.int16]]:
            pod5_file_name, uuids = item
            indexer = self.get_or_load_indexer(pod5_file_name)
            return indexer.fetch_signals(uuids)

        # Then, fetch the signals for each group with multi threading
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = executor.map(fetch_signals_from_file, grouped_uuids.items())

        flattened_results = list(itertools.chain.from_iterable(futures))
        return flattened_results

    def get_signal_length(self, pod5_file_name: str, uuid: bytes | str) -> int:
        """
        Get the signal length for the given UUID from the Pod5 file.
        This is more efficient than fetching the entire signal.

        Args:
            pod5_file_name (str): Name of the Pod5 file.
            uuid (bytes | str): UUID of the signal.

        Returns:
            int: Signal length (number of samples).
        """
        return self.get_or_load_indexer(pod5_file_name).get_signal_length(uuid)
