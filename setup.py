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
        
        # Configure CMake
        cmake_args = [
            f"-DCMAKE_BUILD_TYPE=Release",
            f"-DCMAKE_INSTALL_PREFIX={install_dir}",
            f"-DPYTHON_EXECUTABLE={sys.executable}",
        ]
        
        # Add Windows-specific args if needed
        if sys.platform.startswith('win'):
            cmake_args.extend([
                "-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_RELEASE={install_dir}",
                "-DCMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE={install_dir}",
            ])
        
        # Configure
        configure_cmd = ["cmake", str(project_dir)] + cmake_args
        print(f"Configuring with: {' '.join(configure_cmd)}")
        subprocess.run(configure_cmd, cwd=build_dir, check=True)
        
        # Build
        build_cmd = ["cmake", "--build", ".", "--config", "Release", "--parallel"]
        print(f"Building with: {' '.join(build_cmd)}")
        subprocess.run(build_cmd, cwd=build_dir, check=True)
        
        # Install
        install_cmd = ["cmake", "--install", ".", "--config", "Release"]
        print(f"Installing with: {' '.join(install_cmd)}")
        subprocess.run(install_cmd, cwd=build_dir, check=True)

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