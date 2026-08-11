#!/usr/bin/env python3
"""
Collect the gallery entries to test, from the extras table the conversion gallery declares.

Outputs a JSON array of strings in the format "category:page:extra", one per page that is tested. The
extra may be empty, meaning the page converts on a base install and nothing beyond `.` is installed.
"""

import json
import sys
from pathlib import Path


def collect_gallery_formats() -> list[str]:
    """
    Read the gallery's format table and check it against the pages on disk.

    `docs/conversion_examples_gallery/extras_by_gallery_entry.json` is the source of truth for which page
    is tested and
    which extra it needs. The two names are independent: the workflow installs `.[<extra>]` and separately
    runs `<category>/<page>.rst`, and an extra that does not exist installs nothing without erroring, so a
    page whose name is merely assumed to match an extra fails much later with an import error that reads
    like a missing dependency. Stating the pairing keeps it a decision rather than a coincidence.

    The directory is still walked, but only to hold the table to it: a page nobody registers would
    otherwise be silently untested, which is a quieter failure than being tested wrongly.

    Returns
    -------
    list[str]
        list of strings in the format "category:page:extra"
    """

    repo_root_path = Path(__file__).resolve().parent.parent.parent
    gallery_path = repo_root_path / "docs" / "conversion_examples_gallery"

    if not gallery_path.exists():
        raise FileNotFoundError(f"Gallery path not found: {gallery_path}")

    table_path = gallery_path / "extras_by_gallery_entry.json"
    table = json.loads(table_path.read_text(encoding="utf-8"))

    pages_on_disk = {
        f"{rst_file.parent.name}/{rst_file.stem}"
        for rst_file in gallery_path.glob("*/*.rst")
        if rst_file.stem != "index"
    }
    unregistered = sorted(pages_on_disk - set(table))
    if unregistered:
        raise ValueError(
            f"Gallery pages missing from {table_path.name}: {', '.join(unregistered)}. "
            "Add an entry naming the extra to install, `null` if the page converts on a base install, "
            "and `skip` with a reason if it should not be tested."
        )
    missing = sorted(set(table) - pages_on_disk)
    if missing:
        raise ValueError(f"Entries in {table_path.name} with no gallery page: {', '.join(missing)}")

    formats = []
    for page, entry in sorted(table.items()):
        if "skip" in entry:
            continue
        category, page_name = page.split("/", 1)
        formats.append(f"{category}:{page_name}:{entry['extra'] or ''}")

    return formats


def main():
    """Main function to collect and output formats."""
    try:
        formats = collect_gallery_formats()

        if not formats:
            print("Warning: No formats collected", file=sys.stderr)
            sys.exit(1)

        # Output as JSON for GitHub Actions consumption
        print(json.dumps(formats))

    except Exception as e:
        print(f"Error collecting formats: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
