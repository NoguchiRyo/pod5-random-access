$py = python -c "import sys, pathlib; print(pathlib.Path(sys.executable).resolve())"
Write-Host "Using Python: $py"
& $py build_scripts/generate_cmake_presets.py
& $py --version

cmake -B build --preset=default `
  -DPython_EXECUTABLE="$py" `
  -DPython3_EXECUTABLE="$py" `
  -DPython_ROOT_DIR="$(Split-Path $py)" `
  -DPython_FIND_STRATEGY=LOCATION `
  -DPython_FIND_REGISTRY=NEVER `
  -DPython3_FIND_REGISTRY=NEVER `
  -DPython_FIND_FRAMEWORK=NEVER `
  -DPython3_FIND_FRAMEWORK=NEVER

cmake --build build --config Release -j
cmake --install build --config Release
