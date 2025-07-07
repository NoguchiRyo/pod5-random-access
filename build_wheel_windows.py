#!/usr/bin/env python3
"""
Windows-specific wheel builder for pod5-random-access.
This handles Windows-specific issues like DLL bundling and proper wheel naming.
"""

import os
import sys
import subprocess
import shutil
import tempfile
from pathlib import Path
import zipfile
import tomllib

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

def build_cmake_project():
    """Build the CMake project with Windows-specific settings."""
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
    
    # Configure CMake with Windows-specific settings
    cmake_args = [
        "cmake",
        str(project_dir),
        f"-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        f"-DPYTHON_EXECUTABLE={sys.executable}",
    ]
    
    # Add Windows-specific CMake args if available
    if os.environ.get("VCPKG_ROOT"):
        cmake_args.extend([
            f"-DCMAKE_TOOLCHAIN_FILE={os.environ['VCPKG_ROOT']}/scripts/buildsystems/vcpkg.cmake",
            f"-DVCPKG_TARGET_TRIPLET={os.environ.get('VCPKG_TARGET_TRIPLET', 'x64-windows')}",
        ])
    
    if os.environ.get("CMAKE_GENERATOR"):
        cmake_args.extend(["-G", os.environ["CMAKE_GENERATOR"]])
    
    if os.environ.get("CMAKE_GENERATOR_PLATFORM"):
        cmake_args.extend(["-A", os.environ["CMAKE_GENERATOR_PLATFORM"]])
    
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

def find_dlls_in_build():
    """Find all DLLs that were built or copied during the build process."""
    project_dir = Path(__file__).parent.absolute()
    build_dir = project_dir / "build"
    package_dir = project_dir / "pod5_random_access"
    
    dll_files = []
    
    # Look in build directory
    if build_dir.exists():
        for dll in build_dir.rglob("*.dll"):
            dll_files.append(dll)
    
    # Look in package directory (where CMake installs them)
    if package_dir.exists():
        for dll in package_dir.rglob("*.dll"):
            dll_files.append(dll)
    
    return dll_files

def create_windows_wheel():
    """Create a Windows wheel with proper DLL bundling."""
    project_dir = Path(__file__).parent.absolute()
    metadata = load_project_metadata()
    
    # Build the project
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
    
    # Find and copy all binary files
    binary_files_found = []
    
    # Check install directory first
    for pyd_file in install_dir.rglob("*.pyd"):
        print(f"Found .pyd file: {pyd_file}")
        shutil.copy2(pyd_file, pkg_dest)
        binary_files_found.append(pyd_file.name)
    
    for dll_file in install_dir.rglob("*.dll"):
        print(f"Found DLL: {dll_file}")
        shutil.copy2(dll_file, pkg_dest)
        binary_files_found.append(dll_file.name)
    
    # Also check package directory for in-place builds
    for pyd_file in pkg_dest.rglob("*.pyd"):
        if pyd_file.name not in binary_files_found:
            print(f"Found .pyd in package: {pyd_file}")
            binary_files_found.append(pyd_file.name)
    
    for dll_file in pkg_dest.rglob("*.dll"):
        if dll_file.name not in binary_files_found:
            print(f"Found DLL in package: {dll_file}")
            binary_files_found.append(dll_file.name)
    
    # Look for additional DLLs in build directory
    additional_dlls = find_dlls_in_build()
    for dll in additional_dlls:
        if dll.name not in binary_files_found:
            print(f"Found additional DLL: {dll}")
            shutil.copy2(dll, pkg_dest)
            binary_files_found.append(dll.name)
    
    if not binary_files_found:
        print("⚠️  WARNING: No binary files (.pyd/.dll) found!")
    else:
        print(f"✅ Total binary files copied: {len(binary_files_found)}")
        for f in sorted(binary_files_found):
            print(f"  - {f}")
    
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
    platform_tag = get_platform_tag()
    wheel_content = f"""Wheel-Version: 1.0
Generator: pod5-random-access-windows
Root-Is-Purelib: false
Tag: cp{sys.version_info.major}{sys.version_info.minor}-cp{sys.version_info.major}{sys.version_info.minor}-{platform_tag}
"""
    
    with open(metadata_dir / "WHEEL", "w") as f:
        f.write(wheel_content)
    
    # Create the wheel zip file
    wheel_name = f"{safe_name}-{metadata['version']}-cp{sys.version_info.major}{sys.version_info.minor}-cp{sys.version_info.major}{sys.version_info.minor}-{platform_tag}.whl"
    wheel_path = project_dir / "dist" / wheel_name
    
    # Create dist directory
    wheel_path.parent.mkdir(exist_ok=True)
    
    # Create RECORD file
    record_lines = []
    
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(wheel_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(wheel_dir)
                zf.write(file_path, arcname)
                
                # Add to RECORD
                if arcname.name != "RECORD":
                    record_lines.append(f"{arcname},,")
    
    # Update RECORD file
    record_content = "\n".join(record_lines) + f"\n{safe_name}-{metadata['version']}.dist-info/RECORD,,\n"
    
    with zipfile.ZipFile(wheel_path, "a") as zf:
        zf.writestr(f"{safe_name}-{metadata['version']}.dist-info/RECORD", record_content)
    
    print(f"Created Windows wheel: {wheel_path}")
    return wheel_path

def get_platform_tag():
    """Get the Windows platform tag."""
    import platform
    
    arch = platform.machine().lower()
    if arch in ("amd64", "x86_64"):
        return "win_amd64"
    elif arch in ("x86", "i386", "i686"):
        return "win32"
    elif arch in ("arm64", "aarch64"):
        return "win_arm64"
    else:
        return f"win_{arch}"

if __name__ == "__main__":
    wheel_path = create_windows_wheel()
    print(f"Windows wheel created successfully: {wheel_path}")
    
    # List contents
    print("\nWheel contents:")
    with zipfile.ZipFile(wheel_path, 'r') as zf:
        for name in sorted(zf.namelist()):
            print(f"  {name}")
    
    # Show DLL count
    dll_count = sum(1 for name in zf.namelist() if name.endswith('.dll'))
    pyd_count = sum(1 for name in zf.namelist() if name.endswith('.pyd'))
    print(f"\n📊 Binary files: {pyd_count} .pyd files, {dll_count} .dll files")