from .pod5_random_access_pybind import Pod5Index
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from .utils import fetch_all_pod5_paths
from logging import getLogger
from .settings import IndexSettings

logger = getLogger(__name__)


def process_single_pod5(pod5_file: Path, output_index_dir: Path) -> tuple[Path, Path]:
    indexer = Pod5Index(str(pod5_file.absolute()))
    indexer.build_index()

    index_file_name = pod5_file.with_suffix(".index").name
    output_path = output_index_dir / index_file_name
    indexer.save_index(str(output_path))

    return pod5_file, output_path


def build_pod5_index(
    input_pod5_dir: Path, output_index_dir: Path, max_workers: int | None = None
) -> IndexSettings:
    """
    Build and save Pod5 index for all .pod5 files in a directory.
    1. Fetch all .pod5 files from the input directory.
    2. For each .pod5 file:
        - Initialize Pod5Index
        - Build index
        - Save index to the output directory with the same name as the input file.
    3. Create the index_settings.yaml file in the output directory.
        This file contains the correspondance between the input .pod5 files and their respective index files.
    4. Print the number of files processed and the total size of the index files.

    Args:
        input_pod5_dir (Path): Directory containing .pod5 files.
        output_index_dir (Path): Directory to save the index files.
    """
    # Fetch all .pod5 files from the input directory
    logger.info(f"Fetching all .pod5 files from {input_pod5_dir}...")
    if not input_pod5_dir.exists():
        raise FileNotFoundError(f"Input directory {input_pod5_dir} does not exist")
    if not input_pod5_dir.is_dir():
        raise FileNotFoundError(f"Input path {input_pod5_dir} is not a directory")
    pod5_files = fetch_all_pod5_paths(input_pod5_dir)
    if not pod5_files:
        logger.warning(f"No .pod5 files found in {input_pod5_dir}")
        return IndexSettings()
    logger.info(f"Found {len(pod5_files)} .pod5 files in {input_pod5_dir}")

    # Create output directory if it doesn't exist
    if not output_index_dir.exists():
        logger.info(f"Creating output directory {output_index_dir}...")
        output_index_dir.mkdir(parents=True, exist_ok=True)
    if not output_index_dir.is_dir():
        raise FileNotFoundError(f"Output path {output_index_dir} is not a directory")
    logger.info(f"Output directory: {output_index_dir}")

    # Initialize index settings
    index_settings = IndexSettings()

    # Process pod5 files in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_pod5 = {
            executor.submit(process_single_pod5, pod5_file, output_index_dir): pod5_file
            for pod5_file in pod5_files
        }

        # Process results as they complete
        for future in as_completed(future_to_pod5):
            pod5_file = future_to_pod5[future]
            try:
                pod5_file, output_path = future.result()
                index_settings.add_pod5_index_pair(pod5_file, output_path)
                logger.info(f"Successfully processed {pod5_file.name}")
            except Exception as exc:
                logger.error(f"Failed to process {pod5_file.name}: {exc}")

    # Save index settings to YAML file
    logger.info(
        f"Saving index settings to {output_index_dir / IndexSettings.file_name}..."
    )
    index_settings.to_yaml(output_index_dir)

    return index_settings
