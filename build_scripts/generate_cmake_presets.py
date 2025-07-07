import json
import os
from pathlib import Path


def generate_cmake_presets():
    print("All environment variables with GITHUB:")
    for key, value in os.environ.items():
        if "GITHUB" in key:
            print(f"{key}: {value}")
    github_workspace = Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
    print(f"GITHUB_WORKSPACE: {github_workspace}")
    vcpkg_root = github_workspace / "vcpkg"
    print(f"VCPKG_ROOT: {str(vcpkg_root)}")

    preset = {
        "version": 2,
        "configurePresets": [
            {
                "name": "default",
                "inherits": "vcpkg",
                "environment": {"VCPKG_ROOT": str(vcpkg_root)},
            }
        ],
    }

    with open("CMakeUserPresets.json", "w") as f:
        json.dump(preset, f, indent=2)

    print(f"Generated CMakeUserPresets.json: {preset}")


if __name__ == "__main__":
    generate_cmake_presets()
