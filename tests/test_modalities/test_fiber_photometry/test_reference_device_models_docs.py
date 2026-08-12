"""Guard that the device-model reference page still matches the catalogue it is rendered from.

The page and the shipped data are the same rows, so a hand-edited page, or a catalogue edit that was
never re-rendered, would let the table a user reads disagree with the values
the getters return. This test needs no extension and only reads files, so it
lives beside the catalogue's other tests rather than in the docs build.
"""

import importlib.util
from pathlib import Path

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[3]
GENERATOR_FILE_PATH = REPOSITORY_ROOT_PATH / "docs" / "user_guide" / "_generate_fiber_photometry_device_models.py"


def _load_generator():
    specification = importlib.util.spec_from_file_location("_generate_device_models", GENERATOR_FILE_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_reference_page_matches_the_catalogue():
    generator = _load_generator()

    with open(generator.PAGE_FILE_PATH, "r", encoding="utf-8") as file:
        committed_page = file.read()

    assert committed_page == generator.render_page(), (
        "docs/user_guide/fiber_photometry_device_models.rst is out of date with the reference "
        "catalogue. Regenerate it with "
        "`python docs/user_guide/_generate_fiber_photometry_device_models.py`."
    )
