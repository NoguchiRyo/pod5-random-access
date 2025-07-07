# Project Build Files Organization

This document explains the organization of build-related files in the project.

## 📁 **Current File Structure**

```
pod5-random-access/
├── 🔧 Build Scripts
│   ├── build_wheel.py              # Main cross-platform wheel builder
│   ├── build_wheel_windows.py      # Windows-specific wheel builder
│   ├── build_manylinux.sh          # Linux manylinux build script
│   └── build_windows.bat           # Windows build script
│
├── 📚 Documentation  
│   ├── BUILD_WHEELS.md             # Main build documentation
│   └── BUILD_WINDOWS.md            # Windows-specific documentation
│
├── ⚙️ Configuration
│   ├── pyproject.toml              # Python project config (updated for setuptools)
│   ├── setup.py                    # Custom setuptools build (for fallback)
│   ├── MANIFEST.in                 # Source distribution manifest
│   └── .github/workflows/CI.yml    # Updated CI with manylinux + Windows
│
└── 🏗️ CMake Build System
    ├── CMakeLists.txt              # Main CMake config
    ├── src/CMakeLists.txt          # Source build config (with Windows DLL handling)
    ├── CMakePresets.json           # CMake presets
    └── vcpkg.json                  # Windows dependencies
```

## 🎯 **Recommended Usage**

### For Users (Simple)
```bash
# GitHub Actions (automatic)
git push

# Local quick build
./build_manylinux.sh        # Linux
build_windows.bat           # Windows
```

### For Developers (Advanced)
```bash
# Custom builds
python build_wheel.py               # Generic wheel builder
python build_wheel_windows.py       # Windows-specific builder

# CI debugging
cibuildwheel --platform linux       # Test Linux build locally
cibuildwheel --platform windows     # Test Windows build locally
```

## 🧹 **Cleanup Completed**

**Removed outdated files:**
- ❌ `build_manylinux_wheel.sh` - Replaced by cibuildwheel approach
- ❌ `manylinux_explanation.md` - Content moved to BUILD_WHEELS.md

**Kept essential files:**
- ✅ All current build scripts are up-to-date and serve specific purposes
- ✅ Documentation is consolidated and comprehensive
- ✅ CI workflow handles both Linux and Windows automatically

## 📝 **File Purposes**

| File | Purpose | When to Use |
|------|---------|-------------|
| `build_wheel.py` | Cross-platform wheel builder | Manual builds, debugging |
| `build_wheel_windows.py` | Windows-specific with DLL handling | Windows development |
| `build_manylinux.sh` | Automated Linux manylinux builds | Linux development |
| `build_windows.bat` | Simple Windows build script | Windows quick builds |
| `BUILD_WHEELS.md` | Main build documentation | First-time setup |
| `BUILD_WINDOWS.md` | Windows-specific guide | Windows troubleshooting |

## 🔄 **Future Maintenance**

**Keep updated:**
- CI workflow when adding new Python versions
- vcpkg.json when changing Windows dependencies
- Build scripts when CMake config changes

**Can be removed if:**
- You only use GitHub Actions → Remove local build scripts
- You only support Linux → Remove Windows-specific files
- You switch to pure setuptools → Remove custom wheel builders

All current files are actively maintained and serve specific purposes in the build system.