import json
import os


def generate_cmake_presets():
    github_workspace = os.environ.get("GITHUB_WORKSPACE", "")
    if github_workspace == "":
        raise ValueError("GITHUB_WORKSPACE environment variable is not set.")

    preset = {
        "version": 2,
        "configurePresets": [
            {
                "name": "default",
                "inherits": "vcpkg",
                "environment": {"VCPKG_ROOT": f"{github_workspace}/vcpkg"},
            }
        ],
    }

    with open("CMakeUserPresets.json", "w") as f:
        json.dump(preset, f, indent=2)

    print(f"GITHUB_WORKSPACE: {github_workspace}")
    print(f"Generated CMakeUserPresets.json: {preset}")


if __name__ == "__main__":
    generate_cmake_presets()
