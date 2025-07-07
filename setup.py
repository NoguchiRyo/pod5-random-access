#!/usr/bin/env python3
"""
Setup script for pod5-random-access using pure CMake build.
This replaces scikit-build to ensure binary files are properly included in wheels.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from setuptools import setup, Extension, find_packages
from pybind11.setup_helpers import Pybind11Extension, build_ext

# Project directory
project_dir = Path(__file__).parent.absolute()
build_dir = project_dir / "build"
install_dir = project_dir / "pod5_random_access"

class CMakeBuildExt(build_ext):
    """Custom build extension that uses CMake instead of setuptools default compiler."""
    
    def build_extensions(self):
        # Create build directory
        build_dir.mkdir(exist_ok=True)
        
        # Use CMake preset for configuration
        if sys.platform.startswith('win'):
            # Windows: Use default preset
            configure_cmd = ["cmake", "-B", "build", "--preset=default"]
            print(f"Configuring with preset: {' '.join(configure_cmd)}")
            subprocess.run(configure_cmd, cwd=project_dir, check=True)
        else:
            # Linux: Simple configuration
            configure_cmd = ["cmake", "-B", "build", "-DCMAKE_BUILD_TYPE=Release"]
            print(f"Configuring: {' '.join(configure_cmd)}")
            subprocess.run(configure_cmd, cwd=project_dir, check=True)
        
        # Build
        build_cmd = ["cmake", "--build", "build", "-j"]
        print(f"Building: {' '.join(build_cmd)}")
        subprocess.run(build_cmd, cwd=project_dir, check=True)
        
        # Install
        install_cmd = ["cmake", "--install", "build"]
        print(f"Installing: {' '.join(install_cmd)}")
        subprocess.run(install_cmd, cwd=project_dir, check=True)

# We need to define a dummy extension to trigger the build process
extensions = [
    Pybind11Extension(
        "pod5_random_access.pod5_random_access_pybind",
        [],  # No sources - CMake handles compilation
        include_dirs=[],
        cxx_std=14,
    ),
]

if __name__ == "__main__":
    setup(
        name="pod5-random-access",
        version="0.1.0",
        packages=find_packages(),
        ext_modules=extensions,
        cmdclass={"build_ext": CMakeBuildExt},
        zip_safe=False,
        python_requires=">=3.10",
        install_requires=[
            "numpy>=2.2.6",
            "pyyaml>=6.0.2",
        ],
    )