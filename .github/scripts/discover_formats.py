#!/usr/bin/env python3
"""
Discover all formats from the neuroconv conversion examples gallery.
Outputs a JSON array of format strings in the format "category:format_name".
"""

import json
import sys
from pathlib import Path


def discover_gallery_formats(gallery_path: Path = None) -> list[str]:
    """
    Discover all formats from the conversion examples gallery.

    Parameters
    ----------
    gallery_path : Path, optional
        Path to the conversion examples gallery. If None, uses the default path
        relative to this script's location.

    Returns
    -------
    list[str]
        list of format strings in the format "category:format_name"
    """
    if gallery_path is None:
        # Get path relative to this script: .github/scripts/../../docs/conversion_examples_gallery
        root_repo_path = Path(__file__).resolve().parent.parent.parent
        gallery_path = root_repo_path / "docs" / "conversion_examples_gallery"

    if not gallery_path.exists():
        raise FileNotFoundError(f"Gallery path not found: {gallery_path}")

    formats = []
    excluded_dirs = {"__pycache__", ".pytest_cache", "combinations"}
    excluded_files = {"index.rst", "conftest.py", "__init__.py"}

    for category_dir in gallery_path.iterdir():
        if category_dir.is_dir() and category_dir.name not in excluded_dirs:
            category = category_dir.name

            # Find all .rst files in the category
            for rst_file in category_dir.glob("*.rst"):
                if rst_file.name not in excluded_files:
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
