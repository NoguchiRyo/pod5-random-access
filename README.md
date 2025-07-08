# pod5-random-access

## Introduction

A high-performance Python library for efficient random access to nanopore sequencing signals stored in POD5 files. This library creates optimized indexes that enable fast retrieval of specific reads without loading entire files into memory.

## Installation

Install from PyPI:

```bash
pip install pod5-random-access
```

Requirements:

- Python 3.10+

## Usage

### Basic workflow: Build index → Load reader → Fetch signals

```python
# 1. Build index from POD5 files
from pod5_random_access import build_pod5_index
from pathlib import Path

build_pod5_index(
    input_pod5_dir=Path("path/to/pod5/files"),
    output_index_dir=Path("path/to/index/output")
)

# 2. Load reader with index settings
from pod5_random_access import Pod5RandomAccessReader, IndexSettings

settings = IndexSettings.from_yaml(Path("path/to/index/output/index_settings.yaml"))
reader = Pod5RandomAccessReader()
reader.add_pod5_index_settings(settings)

# 3. Fetch signal data
signal_data = reader.fetch_signal("filename.pod5", "read_uuid")
signal_length = reader.get_signal_length("filename.pod5", "read_uuid")
calibration = reader.get_calibration("filename.pod5", "read_uuid")
```
