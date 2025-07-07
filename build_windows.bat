@echo off
REM Build Windows wheels for pod5-random-access
REM This script uses the custom Windows wheel builder

echo 🪟 Building Windows wheels for pod5-random-access

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python from https://python.org
    exit /b 1
)

REM Check if vcpkg is set up
if not defined VCPKG_ROOT (
    echo ⚠️  VCPKG_ROOT is not set
    echo Please set up vcpkg and run vcpkg integrate install
    echo See: https://vcpkg.io/en/getting-started.html
)

REM Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist wheel_build rmdir /s /q wheel_build
if exist wheel_install rmdir /s /q wheel_install

echo 🔧 Building wheel with custom Windows builder...
python build_wheel_windows.py

if errorlevel 1 (
    echo ❌ Build failed
    exit /b 1
)

echo 📦 Built wheels:
dir /b dist\*.whl

echo 🧪 Testing wheel...
python -m venv test_wheel_env
call test_wheel_env\Scripts\activate.bat

REM Find the first wheel file
for %%f in (dist\*.whl) do (
    echo Installing %%f
    pip install "%%f"
    goto :test_wheel
)

:test_wheel
python -c "import pod5_random_access; from pod5_random_access.pod5_random_access_pybind import Pod5Index; print('✅ Windows wheel test successful!')"

if errorlevel 1 (
    echo ❌ Wheel test failed
    call deactivate
    rmdir /s /q test_wheel_env
    exit /b 1
)

call deactivate
rmdir /s /q test_wheel_env

echo 🎉 Windows wheel build completed successfully!
echo 📂 Wheels are in the 'dist' directory