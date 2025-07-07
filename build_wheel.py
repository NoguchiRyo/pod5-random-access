#!/usr/bin/env python3
"""
Direct CMake build script for pod5-random-access wheel.
This script builds the library using CMake and then packages it into a wheel.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import zipfile
import tomllib


def build_cmake_project():
    """Build the CMake project and install to a temporary directory."""
    project_dir = Path(__file__).parent.absolute()
    build_dir = project_dir / "build"

    # Create a temporary install directory
    install_dir = project_dir / "wheel_install"

    # Clean previous builds
    if build_dir.exists():
        shutil.rmtree(build_dir)
    if install_dir.exists():
        shutil.rmtree(install_dir)

    build_dir.mkdir(exist_ok=True)
    install_dir.mkdir(exist_ok=True)

    # Configure CMake
    cmake_args = [
        "cmake",
        str(project_dir),
        f"-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        f"-DPYTHON_EXECUTABLE={sys.executable}",
    ]

    print(f"Configuring with: {' '.join(cmake_args)}")
    subprocess.run(cmake_args, cwd=build_dir, check=True)

    # Build
    build_cmd = ["cmake", "--build", ".", "--config", "Release", "--parallel"]
    print(f"Building with: {' '.join(build_cmd)}")
    subprocess.run(build_cmd, cwd=build_dir, check=True)

    # Install
    install_cmd = ["cmake", "--install", ".", "--config", "Release"]
    print(f"Installing with: {' '.join(install_cmd)}")
    subprocess.run(install_cmd, cwd=build_dir, check=True)

    return install_dir


def load_project_metadata():
    """Load project metadata from pyproject.toml."""
    project_dir = Path(__file__).parent.absolute()
    pyproject_path = project_dir / "pyproject.toml"
    
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    
    project = data["project"]
    return {
        "name": project["name"],
        "version": project["version"],
        "description": project.get("description", ""),
        "requires_python": project.get("requires-python", ">=3.8"),
        "dependencies": project.get("dependencies", []),
    }

def create_wheel():
    """Create a wheel file manually."""
    project_dir = Path(__file__).parent.absolute()
    metadata = load_project_metadata()
    install_dir = build_cmake_project()

    # Create wheel directory structure
    wheel_dir = project_dir / "wheel_build"
    if wheel_dir.exists():
        shutil.rmtree(wheel_dir)
    wheel_dir.mkdir()

    # Copy Python package files
    pkg_source = project_dir / "pod5_random_access"
    pkg_dest = wheel_dir / "pod5_random_access"
    shutil.copytree(pkg_source, pkg_dest)

    # Copy built binary files
    binary_files_found = []
    
    # Linux/Mac: .so files
    for so_file in install_dir.glob("**/*.so"):
        print(f"Found binary: {so_file}")
        shutil.copy2(so_file, pkg_dest)
        binary_files_found.append(so_file.name)

    # Windows: .pyd files (Python extension modules)
    for pyd_file in install_dir.glob("**/*.pyd"):
        print(f"Found binary: {pyd_file}")
        shutil.copy2(pyd_file, pkg_dest)
        binary_files_found.append(pyd_file.name)

    # Windows: .dll files (shared libraries)
    for dll_file in install_dir.glob("**/*.dll"):
        print(f"Found DLL: {dll_file}")
        shutil.copy2(dll_file, pkg_dest)
        binary_files_found.append(dll_file.name)
    
    # Also check the source package directory for any binaries that were built in-place
    for so_file in pkg_source.glob("**/*.so"):
        if so_file.name not in binary_files_found:
            print(f"Found additional binary in source: {so_file}")
            shutil.copy2(so_file, pkg_dest)
            binary_files_found.append(so_file.name)
    
    for pyd_file in pkg_source.glob("**/*.pyd"):
        if pyd_file.name not in binary_files_found:
            print(f"Found additional binary in source: {pyd_file}")
            shutil.copy2(pyd_file, pkg_dest)
            binary_files_found.append(pyd_file.name)
    
    for dll_file in pkg_source.glob("**/*.dll"):
        if dll_file.name not in binary_files_found:
            print(f"Found additional DLL in source: {dll_file}")
            shutil.copy2(dll_file, pkg_dest)
            binary_files_found.append(dll_file.name)
    
    if not binary_files_found:
        print("⚠️  WARNING: No binary files (.so/.pyd/.dll) found!")
    else:
        print(f"✅ Copied {len(binary_files_found)} binary files: {binary_files_found}")

    # Create metadata directory
    safe_name = metadata["name"].replace("-", "_")
    metadata_dir = wheel_dir / f"{safe_name}-{metadata['version']}.dist-info"
    metadata_dir.mkdir()

    # Create METADATA file
    metadata_lines = [
        "Metadata-Version: 2.1",
        f"Name: {metadata['name']}",
        f"Version: {metadata['version']}",
    ]
    
    if metadata["description"]:
        metadata_lines.append(f"Summary: {metadata['description']}")
    
    if metadata["requires_python"]:
        metadata_lines.append(f"Requires-Python: {metadata['requires_python']}")
    
    for dep in metadata["dependencies"]:
        metadata_lines.append(f"Requires-Dist: {dep}")
    
    metadata_content = "\n".join(metadata_lines) + "\n"
    
    with open(metadata_dir / "METADATA", "w") as f:
        f.write(metadata_content)

    # Create WHEEL file
    wheel_content = f"""Wheel-Version: 1.0
Generator: pod5-random-access
Root-Is-Purelib: false
Tag: cp{sys.version_info.major}{sys.version_info.minor}-cp{sys.version_info.major}{sys.version_info.minor}-{get_platform_tag()}
"""

    with open(metadata_dir / "WHEEL", "w") as f:
        f.write(wheel_content)

    # Create RECORD file (will be populated during zip creation)
    record_lines = []

    # Create the wheel zip file
    wheel_name = f"{safe_name}-{metadata['version']}-cp{sys.version_info.major}{sys.version_info.minor}-cp{sys.version_info.major}{sys.version_info.minor}-{get_platform_tag()}.whl"
    wheel_path = project_dir / "dist" / wheel_name

    # Create dist directory
    wheel_path.parent.mkdir(exist_ok=True)

    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(wheel_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(wheel_dir)
                zf.write(file_path, arcname)

                # Add to RECORD
                if arcname.name != "RECORD":
                    record_lines.append(f"{arcname},,")

    # Create RECORD file
    record_content = (
        "\n".join(record_lines) + f"\n{safe_name}-{metadata['version']}.dist-info/RECORD,,\n"
    )

    # Update the wheel with RECORD
    with zipfile.ZipFile(wheel_path, "a") as zf:
        zf.writestr(f"{safe_name}-{metadata['version']}.dist-info/RECORD", record_content)

    print(f"Created wheel: {wheel_path}")
    return wheel_path


def get_platform_tag():
    """Get the platform tag for the current system."""
    import platform

    system = platform.system().lower()
    arch = platform.machine().lower()

    if system == "linux":
        return f"linux_{arch}"
    elif system == "windows":
        # Windows specific architecture mapping
        if arch in ("amd64", "x86_64"):
            return "win_amd64"
        elif arch in ("x86", "i386", "i686"):
            return "win32"
        elif arch in ("arm64", "aarch64"):
            return "win_arm64"
        else:
            return f"win_{arch}"
    elif system == "darwin":
        # Mac specific architecture mapping
        if arch in ("x86_64", "amd64"):
            return "macosx_10_9_x86_64"
        elif arch in ("arm64", "aarch64"):
            return "macosx_11_0_arm64"
        else:
            return f"macosx_10_9_{arch}"
    else:
        return f"{system}_{arch}"


if __name__ == "__main__":
    wheel_path = create_wheel()
    print(f"Wheel created successfully: {wheel_path}")

    # List contents
    print("\nWheel contents:")
    with zipfile.ZipFile(wheel_path, "r") as zf:
        for name in sorted(zf.namelist()):
            print(f"  {name}")

