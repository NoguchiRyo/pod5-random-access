from pathlib import Path
import yaml
from logging import getLogger

logger = getLogger(__name__)


class IndexSettings:
    """
    Class to handle index settings.
    This class is used to create and save the index_settings.yaml file.

    """

    file_name = "index_settings.yaml"

    def __init__(self) -> None:
        self.data: dict[str, tuple[Path, Path]] = {}

    def add_pod5_index_pair(self, pod5_file: Path, index_file: Path) -> None:
        """
        Add a pod5 file and its corresponding index file to the settings.

        Args:
            pod5_file (Path): Path to the pod5 file.
            index_file (Path): Path to the index file.
        """
        self.data[pod5_file.name] = (pod5_file, index_file)

    def get_pod5_file_path(self, pod5_file_name: str) -> Path:
        """
        Get the path of the pod5 file by its name.

        Args:
            pod5_file_name (str): Name of the pod5 file.

        Returns:
            Path: Path to the pod5 file.
        """
        if pod5_file_name not in self.data:
            raise KeyError(f"Pod5 file {pod5_file_name} not found in settings.")
        return self.data[pod5_file_name][0]

    def get_pod5_index_path(self, pod5_file_name: str) -> Path:
        """
        Get the path of the index file by its corresponding pod5 file name.

        Args:
            pod5_file_name (str): Name of the pod5 file.

        Returns:
            Path: Path to the index file.
        """
        if pod5_file_name not in self.data:
            raise KeyError(f"Index file for {pod5_file_name} not found in settings.")
        return self.data[pod5_file_name][1]

    def get_pod5_paths(self, pod5_file_name: str) -> tuple[Path, Path]:
        """
        Get the paths of the pod5 file and its corresponding index file.

        Args:
            pod5_file_name (str): Name of the pod5 file.

        Returns:
            tuple[Path, Path]: Tuple containing the path to the pod5 file and the path to the index file.
        """
        if pod5_file_name not in self.data:
            raise KeyError(f"Pod5 file {pod5_file_name} not found in settings.")
        return self.data[pod5_file_name]

    def to_yaml(self, output_dir: Path) -> None:
        """
        Save the index settings to a YAML file.
        The output dict should be in the format:
        {
            file_name_of_pod5: {
                "pod5": path/to/pod5_file,
                "index": file_name_of_index_file, # because the index file is saved in the same directory as the settings file
            }...
        }

        Args:
            output_dir (Path): Directory to save the index settings YAML file.
        """
        index_settings: dict[str, dict[str, str]] = {}
        for pod5_filename in self.data.keys():
            index_settings[pod5_filename] = {
                "pod5": str(self.get_pod5_file_path(pod5_filename).resolve()),
                "index": self.get_pod5_index_path(pod5_filename).name,
            }

        index_settings_path = output_dir / self.file_name
        with open(index_settings_path, "w") as f:
            yaml.dump(index_settings, f, default_flow_style=False)

    @classmethod
    def from_yaml(cls, settings_path: Path) -> "IndexSettings":
        """
        Load the index settings from a YAML file.
        The input dict should be in the format:
        {
            file_name_of_pod5: {
                "pod5": path/to/pod5_file,
                "index": file_name
            }...
        }

        Args:
            input_dir (Path): Directory to load the index settings YAML file from.

        Returns:
            IndexSettings: An instance of IndexSettings with loaded settings.
        """
        logger.info(f"Loading index settings from {settings_path}")
        if not settings_path.exists():
            raise FileNotFoundError(f"Settings file {settings_path} not found.")
        index_settings = cls()
        with open(settings_path, "r") as f:
            index_settings_dict = yaml.safe_load(f)
        input_dir = settings_path.parent
        for pod5_filename, paths in index_settings_dict.items():
            pod5_path = Path(paths["pod5"])
            index_path = input_dir.joinpath(paths["index"])
            if not pod5_path.exists():
                logger.warning(f"Pod5 file {pod5_filename} does not exist: {pod5_path}")
                continue
            if not index_path.exists():
                logger.warning(
                    f"Index file {pod5_filename} does not exist: {index_path}"
                )
                continue
            index_settings.add_pod5_index_pair(pod5_path, index_path)
        if len(index_settings.data) == 0:
            raise ValueError(
                f"No valid pod5 files found in index settings: {settings_path}"
            )
        logger.debug(
            f"Loaded index settings from {input_dir / cls.file_name}: {index_settings.data}"
        )
        return index_settings

    def __repr__(self) -> str:
        """
        String representation of the IndexSettings object.
        """
        return f"<IndexSettings({self.data})>"

    def __add__(self, other: "IndexSettings") -> "IndexSettings":
        """
        Add two IndexSettings objects together.
        This will merge the pod5 and index file paths from both objects.

        Args:
            other (IndexSettings): Another IndexSettings object to merge with.

        Returns:
            IndexSettings: A new IndexSettings object with merged settings.
        """
        if not isinstance(other, IndexSettings):  # type: ignore[unreachable]
            raise TypeError("Can only merge with another IndexSettings object.")
        merged_settings = IndexSettings()
        merged_settings.data = {**self.data, **other.data}
        return merged_settings

    def __radd__(self, other: "IndexSettings") -> "IndexSettings":
        """
        Reverse add two IndexSettings objects together.
        This will merge the pod5 and index file paths from both objects.

        Args:
            other (IndexSettings): Another IndexSettings object to merge with.

        Returns:
            IndexSettings: A new IndexSettings object with merged settings.
        """
        return self.__add__(other)

    def __iadd__(self, other: "IndexSettings") -> "IndexSettings":
        """
        In-place add two IndexSettings objects together.
        This will merge the pod5 and index file paths from both objects.

        Args:
            other (IndexSettings): Another IndexSettings object to merge with.

        Returns:
            IndexSettings: The current IndexSettings object with merged settings.
        """
        return self.__add__(other)

    def update(self, other: "IndexSettings") -> "IndexSettings":
        """
        Update the current IndexSettings object with another IndexSettings object.

        Args:
            other (IndexSettings): Another IndexSettings object to merge with.
        """
        if not isinstance(other, IndexSettings):  # type: ignore[unreachable]
            raise TypeError("Can only merge with another IndexSettings object.")
        self.data.update(other.data)
        logger.debug(f"Updated index settings: {self.data}")
        return self
