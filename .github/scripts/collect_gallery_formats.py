#!/usr/bin/env python3
"""
Discover all formats from the neuroconv conversion examples gallery.
Outputs a JSON array of format strings in the format "category:format_name".
"""

import json
import sys
from pathlib import Path


def discover_gallery_formats() -> list[str]:
    """
    Discover all formats from the conversion examples gallery.

    Returns
    -------
    list[str]
        list of format strings in the format "category:format_name"
    """

    repo_root_path = Path(__file__).resolve().parent.parent.parent
    gallery_path = repo_root_path / "docs" / "conversion_examples_gallery"

    if not gallery_path.exists():
        raise FileNotFoundError(f"Gallery path not found: {gallery_path}")

    formats = []
    excluded_dirs = {
        "combinations",  # These do not have an associated installation extra
    }
    excluded_files = {
        "index.rst",
        "conftest.py",
        "__init__.py",
        "spike2.rst",  # Only supported for python 3.9 and earlier
        "mearec.rst",  # Setup tools problems and I want to discuss this with Ben
        "edf.rst",  # Does not allow parallel read so we don't test the gallery because of race condition
        "plexon2.rst",  # Not being tested because it requires wine
    }

    # The conversion gallery is organized in folders per category: recordings, behavior, ophys, etc.
    category_folder_paths = [path for path in gallery_path.iterdir() if path.is_dir()]
    valid_category_folder_paths = [path for path in category_folder_paths if path.name not in excluded_dirs]

    for category_folder_path in valid_category_folder_paths:
        category = category_folder_path.name

        # Find all .rst files in the category
        rst_files = list(category_folder_path.glob("*.rst"))
        valid_rst_files = [rst_file for rst_file in rst_files if rst_file.name not in excluded_files]
        for rst_file in valid_rst_files:
            format_name = rst_file.stem
            formats.append(f"{category}:{format_name}")

    return sorted(formats)


def main():
    """Main function to discover and output formats."""
    try:
        formats = discover_gallery_formats()

        if not formats:
            print("Warning: No formats discovered", file=sys.stderr)
            sys.exit(1)

        # Output as JSON for GitHub Actions consumption
        print(json.dumps(formats))

    except Exception as e:
        print(f"Error discovering formats: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
