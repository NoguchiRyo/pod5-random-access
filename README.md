# pod5-random-access

## Introduction

A high-performance Python library for efficient random access to nanopore sequencing signals stored in POD5 files. This library creates optimized indexes that enable fast retrieval of specific reads without loading entire files into memory.

### Why pod5-random-access?

The standard pod5 library requires scanning Read Table batches to locate a specific read, making true random access expensive. This library pre-builds a lightweight index that maps each UUID directly to its Signal Table location, bypassing the Read Table entirely at runtime. Combined with `plan_fetch_order`, which sorts accesses by on-disk position, even HDD-based workflows achieve near-sequential I/O performance.

## Installation

Install from PyPI:

```bash
pip install pod5-random-access
```

Requirements:

- Python 3.10+

## Usage

### Adding POD5 files

Index files (`.pod5.idx`) are automatically managed. When a POD5 file is added, the library checks for an existing index next to it. If found, loading is deferred until first access. If not, the index is built immediately and saved alongside the POD5 file.

```python
from pod5_random_access import Pod5RandomAccessReader

reader = Pod5RandomAccessReader()

# Add a single file
reader.add_pod5("path/to/run1.pod5")

# Or add all .pod5 files in a directory (recursive)
reader.add_pod5_dir("path/to/pod5/files")
```

To skip saving index files, set `save_index=False`:
```python
reader = Pod5RandomAccessReader(save_index=False)
reader.add_pod5("path/to/run1.pod5")  # builds in memory only
```

### Fetching signals

```python
# Raw signal (int16)
signal = reader.fetch_signal("run1.pod5", "read-uuid-string")

# Calibrated pA signal (float32) — (raw + offset) * scale
pA_signal = reader.fetch_pA_signal("run1.pod5", "read-uuid-string")

# Calibration parameters
offset, scale = reader.get_calibration("run1.pod5", "read-uuid-string")

# Signal length (without reading the signal)
length = reader.get_signal_length("run1.pod5", "read-uuid-string")
```

### Batch index building

To pre-build indexes for all POD5 files in a directory:

```python
from pod5_random_access import build_pod5_index

# Builds .pod5.idx next to each .pod5 file
# Automatically parallelizes on SSD, runs sequentially on HDD
build_pod5_index("path/to/pod5/files")
```

### Optimizing read order for HDD

When reading many signals from HDD, sorting by on-disk position avoids random seeks:

```python
sorted_items = reader.plan_fetch_order(
    read_info_list,
    key=lambda x: (x.filename, x.read_id),
)
for item in sorted_items:
    signal = reader.fetch_signal(item.filename, item.read_id)
```

## Building from Source

### Dependencies

Install system packages:
```bash
sudo apt install -y build-essential cmake python3-dev libzstd-dev \
  libssl-dev libbz2-dev liblz4-dev libsnappy-dev libcurl4-openssl-dev \
  libre2-dev libutf8proc-dev libprotobuf-dev protobuf-compiler \
  libflatbuffers-dev flatbuffers-compiler
```

### Apache Arrow (source build)

The Arrow package is not available via apt on Ubuntu 25.10. Build from source:
```bash
git clone --depth 1 --branch apache-arrow-23.0.1 https://github.com/apache/arrow.git
cd arrow/cpp
cmake -B build \
  -DCMAKE_INSTALL_PREFIX=/usr/local \
  -DCMAKE_BUILD_TYPE=Release \
  -DARROW_COMPUTE=ON \
  -DARROW_CSV=ON \
  -DARROW_JSON=ON \
  -DARROW_DATASET=ON \
  -DARROW_FILESYSTEM=ON \
  -DARROW_WITH_ZSTD=ON \
  -DARROW_WITH_LZ4=ON \
  -DARROW_WITH_SNAPPY=ON \
  -DARROW_WITH_BZ2=ON
cmake --build build -j$(nproc)
sudo cmake --install build
sudo ldconfig
cd ../..
```

> **Note:** The CI uses Arrow 12.0.1, but older versions may fail to build on newer systems due to OpenSSL incompatibilities. Arrow 23.0.1 works on Ubuntu 25.10.

### Arrow version compatibility fix

When building with lastest Arrow, `DCHECK_EQ` has been renamed to `ARROW_DCHECK_EQ`. Apply this fix before building:
```bash
sed -i 's/DCHECK_EQ/ARROW_DCHECK_EQ/g' extern/pod5-file-format/c++/pod5_format/types.cpp
```

### Build and install
```bash
git clone --recursive https://github.com/NoguchiRyo/pod5-random-access.git
cd pod5-random-access

# Build C++ extension
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
cmake --install build

# Install Python package
uv venv
source .venv/bin/activate
uv pip install .
```
