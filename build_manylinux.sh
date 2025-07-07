#!/bin/bash
# Build manylinux wheels for pod5-random-access
# This script can be run locally or adapted for CI

set -e

echo "🐳 Building manylinux wheels for pod5-random-access"

# Configuration
PYTHON_VERSIONS=("3.10" "3.11" "3.12")
PLATFORMS=("manylinux_2_17_x86_64" "manylinux_2_17_aarch64")

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first:"
    echo "   curl -fsSL https://get.docker.com -o get-docker.sh"
    echo "   sudo sh get-docker.sh"
    exit 1
fi

# Create wheelhouse directory
mkdir -p wheelhouse

# Build for each Python version and platform
for py_version in "${PYTHON_VERSIONS[@]}"; do
    for platform in "${PLATFORMS[@]}"; do
        echo "🔧 Building for Python ${py_version} on ${platform}"
        
        # Determine architecture
        if [[ "$platform" == *"aarch64"* ]]; then
            arch="aarch64"
        else
            arch="x86_64"
        fi
        
        # Run cibuildwheel
        CIBW_BUILD="cp${py_version//.}-*" \
        CIBW_ARCHS="$arch" \
        CIBW_BEFORE_BUILD_LINUX="
            yum update -y &&
            yum install -y epel-release wget cmake3 &&
            ln -sf /usr/bin/cmake3 /usr/bin/cmake &&
            wget https://apache.jfrog.io/artifactory/arrow/centos/apache-arrow-release-latest.rpm &&
            yum install -y apache-arrow-release-latest.rpm &&
            yum install -y arrow-devel zstd-devel flatbuffers-devel brotli-devel utf8proc-devel re2-devel bzip2-devel lz4-devel snappy-devel libcurl-devel openssl-devel
        " \
        CIBW_BUILD_FRONTEND="build[uv]" \
        CIBW_TEST_COMMAND="python -c 'import pod5_random_access; from pod5_random_access.pod5_random_access_pybind import Pod5Index; print(\"✅ Import successful!\")'" \
        CIBW_SKIP="*-musllinux* pp*" \
        cibuildwheel --platform linux
        
        echo "✅ Completed Python ${py_version} on ${platform}"
    done
done

echo "📦 Built wheels:"
ls -la wheelhouse/

echo "🎉 All manylinux wheels built successfully!"
echo "📂 Wheels are in the 'wheelhouse' directory"

# Optional: Test one of the wheels
if ls wheelhouse/*.whl 1> /dev/null 2>&1; then
    echo "🧪 Testing a wheel..."
    wheel_file=$(ls wheelhouse/*.whl | head -1)
    echo "Testing: $wheel_file"
    
    # Create temporary test environment
    python -m venv test_wheel_env
    source test_wheel_env/bin/activate
    pip install "$wheel_file"
    python -c "
import pod5_random_access
from pod5_random_access.pod5_random_access_pybind import Pod5Index
print('✅ Wheel test successful!')
"
    deactivate
    rm -rf test_wheel_env
    echo "🎯 Wheel verification completed!"
fi