# Building Manylinux Wheels

This document explains how to build portable manylinux wheels for `pod5-random-access`.

## Quick Start (Automated)

### Option 1: GitHub Actions (Recommended)
Push to GitHub and the CI workflow will automatically build wheels for:

**Linux:**
- Python 3.10, 3.11, 3.12
- x86_64 and aarch64 architectures
- manylinux_2_17 compatible wheels

**Windows:**
- Python 3.10, 3.11, 3.12
- x64 and x86 architectures  
- Automatic DLL bundling with delvewheel

### Option 2: Local Build Scripts
```bash
# Linux: Build manylinux wheels
./build_manylinux.sh

# Windows: Build Windows wheels  
build_windows.bat
```

## Manual Building

### Method 1: Using cibuildwheel (Recommended)

```bash
# Install cibuildwheel
pip install cibuildwheel

# Build for current Python version and architecture
cibuildwheel --platform linux

# Build for specific Python version
CIBW_BUILD="cp311-*" cibuildwheel --platform linux

# Build for specific architecture (requires emulation setup)
CIBW_ARCHS="aarch64" cibuildwheel --platform linux
```

### Method 2: Direct Docker Build

```bash
# For x86_64
docker run --rm -v $(pwd):/project -w /project \
  quay.io/pypa/manylinux_2_17_x86_64 \
  /project/scripts/build_in_container.sh

# For aarch64 (requires emulation)
docker run --rm -v $(pwd):/project -w /project \
  quay.io/pypa/manylinux_2_17_aarch64 \
  /project/scripts/build_in_container.sh
```

### Method 3: Local auditwheel (Ubuntu/Debian only)

```bash
# Build normal wheel first
python build_wheel.py

# Install auditwheel and dependencies
sudo apt install patchelf
pip install auditwheel

# Repair the wheel
auditwheel repair dist/*.whl --plat manylinux_2_35_x86_64 -w dist/
```

## What Gets Built

The build process creates wheels with:

✅ **Self-contained libraries**: All dependencies bundled in `.libs/` directory  
✅ **Cross-platform**: Works on any Linux distro with glibc ≥ 2.17  
✅ **Multiple Python versions**: 3.10, 3.11, 3.12  
✅ **Multiple architectures**: x86_64, aarch64  

## Wheel Comparison

| Wheel Type | Size | Dependencies | Compatibility |
|------------|------|--------------|---------------|
| `linux_x86_64` | ~500KB | Requires system libs | Ubuntu/Debian only |
| `manylinux_2_17_x86_64` | ~17MB | Self-contained | Any Linux distro |

## Bundled Dependencies

The manylinux wheels include these libraries:
- `libarrow` (~30MB) - Apache Arrow C++
- `libzstd` - Compression library
- `libbrotli*` - Brotli compression
- `libcrypto`, `libssl` - OpenSSL
- `libcurl` - HTTP client
- And 30+ other dependencies

## Testing Wheels

```bash
# Create clean environment
python -m venv test_env
source test_env/bin/activate

# Install and test
pip install wheelhouse/pod5_random_access-*.whl
python -c "
import pod5_random_access
from pod5_random_access.pod5_random_access_pybind import Pod5Index
print('✅ Wheel works!')
"
```

## Troubleshooting

### Build Fails in Container
- Check that all system dependencies are installed
- Verify CMake version ≥ 3.18
- Ensure Arrow development libraries are available

### auditwheel Fails
- Install `patchelf`: `sudo apt install patchelf`
- Check wheel platform compatibility: `auditwheel show wheel.whl`

### Import Errors
- Verify wheel contains `.libs/` directory with bundled libraries
- Check that RPATH points to bundled libraries: `ldd binary.so`

## CI Configuration

The GitHub Actions workflow (`.github/workflows/CI.yml`) is configured to:

1. **Build in manylinux containers** for maximum compatibility
2. **Install Arrow and dependencies** from official repositories  
3. **Build wheels** using our custom CMake build system
4. **Automatically repair wheels** with auditwheel
5. **Test imports** to verify wheels work
6. **Upload artifacts** for download
7. **Publish to PyPI** on tagged releases

This ensures reliable, portable wheel distribution for all users.