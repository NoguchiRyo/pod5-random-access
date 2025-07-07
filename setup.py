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

        # -------------------- 修正箇所 --------------------
        # プラットフォームに関係なく、CMakeの基本コマンドを定義
        configure_cmd = ["cmake", "-B", "build"]

        # CMAKE_ARGS環境変数から全ての引数を取得して追加
        cmake_args = os.environ.get("CMAKE_ARGS", "").split()
        if cmake_args:
            configure_cmd.extend(cmake_args)

        if sys.platform == "win32":
            cmake_args_str = os.environ.get("SETUPTOOLS_CMAKE_ARGS", "")
            if cmake_args_str:
                configure_cmd.extend(cmake_args_str.split(";"))

            # GITHUB_WORKSPACE環境変数から安全にパスを取得
            workspace = os.environ.get("GITHUB_WORKSPACE")
            if not workspace:
                raise RuntimeError(
                    "GITHUB_WORKSPACE environment variable is not set on Windows."
                )

            # Pythonで安全にパスを組み立てる
            toolchain_file = (
                Path(workspace) / "vcpkg" / "scripts" / "buildsystems" / "vcpkg.cmake"
            )

            # CMakeにはフォワードスラッシュで渡すのが最も安全
            configure_cmd.append(f"-DCMAKE_TOOLCHAIN_FILE={toolchain_file.as_posix()}")

            configure_cmd.append("-DCMAKE_GENERATOR_PLATFORM=x64")
            configure_cmd.append("-DCMAKE_GENERATOR=Visual Studio 17 2022")

        print(f"Configuring with: {' '.join(configure_cmd)}")
        subprocess.run(configure_cmd, cwd=project_dir, check=True)
        # ----------------------------------------------------

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

