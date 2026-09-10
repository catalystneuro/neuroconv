"""Tests for the CSV seam of ``GuppyConverter``.

Only what is specific to ``acquisition_format="csv"``: how a GuPPy store id resolves to a file, and how
a missing one fails. Everything format-independent -- role grouping, fiber-region linking, event
merging, the registries -- is asserted once in ``test_reference_session``, which runs the full
conversion on this same session.

CSV is the plainest of the four formats: GuPPy names a store by its filename stem, so there is no
translation step, and each event store is its own file rather than a stream inside one.
"""

import shutil
from pathlib import Path

import pytest

from neuroconv.converters import GuppyConverter

from ...setup_paths import OPHYS_DATA_PATH

SESSION_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "Guppy" / "guppy_example_1"
GUPPY_OUTPUT_FOLDER = SESSION_FOLDER / "guppy_example_1_output_1"

# storesList.csv order, which is the order each role interface opens its files in.
ROLE_TO_STORE_IDS = {
    "signal": ["dms_signal_channel", "nac_signal_channel"],
    "control": ["dms_control_channel", "nac_control_channel"],
}
EXPECTED_ACQUISITION_INTERFACE_NAMES = {"FiberPhotometry_signal", "FiberPhotometry_control"}
EXPECTED_EVENTS_INTERFACE_NAMES = {"Events_poke_ttl", "Events_reward_ttl"}


class TestGuppyConverterCSV:
    @pytest.fixture
    def converter(self):
        return GuppyConverter(
            fiber_photometry_folder_path=SESSION_FOLDER,
            events_folder_path=SESSION_FOLDER,
            guppy_folder_path=GUPPY_OUTPUT_FOLDER,
            acquisition_format="csv",
        )

    def test_one_events_interface_per_store_file(self, converter):
        """CSV keeps each event store in its own file, so each needs its own interface."""
        assert set(converter.data_interface_objects) == (
            EXPECTED_ACQUISITION_INTERFACE_NAMES | EXPECTED_EVENTS_INTERFACE_NAMES | {"Guppy"}
        )
        assert {spec["interface_name"] for spec in converter._events_specs} == EXPECTED_EVENTS_INTERFACE_NAMES

    def test_store_ids_resolve_to_their_own_files(self, converter):
        """A CSV store id is its filename stem, so each role interface opens one file per site."""
        for role, store_ids in ROLE_TO_STORE_IDS.items():
            interface = converter.data_interface_objects[f"FiberPhotometry_{role}"]
            assert [Path(path).stem for path in interface._file_paths] == store_ids

    def test_missing_store_file_raises(self, tmp_path):
        """A store GuPPy listed whose CSV is absent fails at construction rather than silently."""
        acquisition_folder = tmp_path / "session"
        acquisition_folder.mkdir()
        for source_path in SESSION_FOLDER.glob("*.csv"):
            shutil.copy(source_path, acquisition_folder / source_path.name)
        (acquisition_folder / "nac_signal_channel.csv").unlink()

        with pytest.raises(ValueError, match="nac_signal_channel.csv"):
            GuppyConverter(
                fiber_photometry_folder_path=acquisition_folder,
                events_folder_path=acquisition_folder,
                guppy_folder_path=GUPPY_OUTPUT_FOLDER,
                acquisition_format="csv",
            )
