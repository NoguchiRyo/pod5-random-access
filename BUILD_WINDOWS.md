# Building Windows Wheels

This document explains how to build Windows wheels for `pod5-random-access` with proper DLL bundling.

## 🔧 Prerequisites

### Required Software
1. **Python 3.10+** from [python.org](https://python.org)
2. **Visual Studio 2022** (Community Edition is fine)
3. **vcpkg** package manager
4. **Git** (with submodules support)

### Setting up vcpkg
```powershell
# Clone vcpkg
git clone https://github.com/Microsoft/vcpkg.git
cd vcpkg

# Bootstrap vcpkg
.\bootstrap-vcpkg.bat

# Integrate with Visual Studio
.\vcpkg integrate install

# Set environment variable (add to your PATH permanently)
$env:VCPKG_ROOT = "C:\path\to\vcpkg"
```

## 🚀 Building Methods

### Method 1: Automated GitHub Actions (Recommended)
Push to GitHub and wheels are built automatically for:
- Python 3.10, 3.11, 3.12
- x64 and x86 architectures  
- Automatic DLL bundling with `delvewheel`

### Method 2: Local Build Script
```batch
# Run the Windows build script
build_windows.bat
```

### Method 3: cibuildwheel (Advanced)
```powershell
# Install cibuildwheel
pip install cibuildwheel

# Build wheels
$env:CIBW_BUILD = "cp311-*"
$env:CIBW_ARCHS = "x64"
$env:VCPKG_ROOT = "C:\path\to\vcpkg"
cibuildwheel --platform windows
```

### Method 4: Manual Build
```powershell
# Install dependencies via vcpkg
vcpkg install arrow zstd brotli flatbuffers --triplet x64-windows

# Build using custom script
python build_wheel_windows.py
```

## 🔍 What Gets Built

Windows wheels include:

✅ **Binary Extension**: `.pyd` files (Python extensions)  
✅ **Required DLLs**: All Arrow and compression libraries  
✅ **Dependency Bundling**: Using `delvewheel` (Windows auditwheel)  
✅ **Platform Tags**: `win_amd64`, `win32`, `win_arm64`  

## 📦 Bundled DLLs

The Windows wheels automatically include:
- `arrow.dll` (~30MB) - Apache Arrow C++
- `zstd.dll` - Compression library
- `brotlienc.dll`, `brotlidec.dll`, `brotlicommon.dll` - Brotli compression
- `lz4.dll` - LZ4 compression  
- `snappy.dll` - Snappy compression
- `zlib1.dll` - Zlib compression
- And other vcpkg dependencies

## 🧪 Testing Windows Wheels

```powershell
# Create test environment
python -m venv test_env
test_env\Scripts\activate.bat

# Install wheel
pip install dist\pod5_random_access-*.whl

# Test import
python -c "
import pod5_random_access
from pod5_random_access.pod5_random_access_pybind import Pod5Index
print('✅ Windows wheel works!')
"

deactivate
rmdir /s /q test_env
```

## 🛠️ Build Configuration

### vcpkg.json Dependencies
Your project uses these vcpkg packages:
```json
{
  "dependencies": [
    "arrow",
    "zstd", 
    "brotli",
    "flatbuffers"
  ]
}
```

### CMake Configuration
The `src/CMakeLists.txt` automatically:
1. **Finds vcpkg packages** when `VCPKG_ROOT` is set
2. **Copies required DLLs** to the package directory
3. **Installs binaries** to the correct Python module location

## 🚨 Troubleshooting

### vcpkg Issues
```powershell
# Check vcpkg integration
vcpkg integrate install

# List installed packages  
vcpkg list

# Install missing packages
vcpkg install arrow:x64-windows
```

### Build Failures
- **Missing Visual Studio**: Install VS 2022 with C++ workload
- **DLL not found**: Check vcpkg installed packages
- **Python version mismatch**: Use same Python for build and test

### Wheel Issues
- **No .pyd files**: Check CMake install step completed
- **Missing DLLs**: Verify vcpkg dependencies installed
- **Import errors**: Test with `python -v` for detailed import info

## 📊 Wheel Comparison

| Platform | Size | Dependencies | Installation |
|----------|------|--------------|--------------|
| **Linux** (manylinux) | ~17MB | Bundled | `pip install` |
| **Windows** (win_amd64) | ~35MB | Bundled | `pip install` |

Windows wheels are larger due to:
- Static linking of more libraries
- Windows-specific dependencies
- Debug information (can be stripped)

## 🔄 CI/CD Configuration

The GitHub Actions workflow automatically:

1. **Sets up vcpkg** and Visual Studio environment
2. **Installs dependencies** for both x64 and x86
3. **Builds wheels** using cibuildwheel  
4. **Bundles DLLs** using delvewheel
5. **Tests imports** to verify functionality
6. **Uploads artifacts** for download
7. **Publishes to PyPI** on tagged releases

### Environment Variables Used
```yaml
VCPKG_ROOT: Path to vcpkg installation
CMAKE_TOOLCHAIN_FILE: vcpkg CMake integration
CMAKE_GENERATOR: "Visual Studio 17 2022" 
VCPKG_TARGET_TRIPLET: "x64-windows" or "x86-windows"
```

This ensures your Windows users get working wheels without needing to install any system dependencies!