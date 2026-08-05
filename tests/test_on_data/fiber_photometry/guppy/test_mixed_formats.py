"""Tests for a ``GuppyConverter`` session whose events do not all come from the acquisition format.

GuPPy's custom-event import writes the events it imported back out as one-column ``timestamps`` CSVs,
which then sit in the session folder beside whatever the rig recorded. Such a session's
``storesList.csv`` lists stores from two sources at once, and ``events_formats`` is what lets the
converter read both: each format is asked what it carries and every listed store is routed to the one
that has it.

The fixture is that shape exactly -- the Photo_249 tank supplying the traces and its three epocs, plus
one imported-event CSV -- assembled by symlinking the tank into a temporary folder so the custom CSV
can be dropped in beside it without touching the shared fixture.
"""

import numpy as np
import pandas
import pytest
from pynwb import NWBHDF5IO

from neuroconv.converters import GuppyConverter
from neuroconv.tools.testing import generate_mock_guppy_output_folder
from neuroconv.utils import dict_deep_update

from ._metadata import (
    build_device_metadata,
    build_fiber_photometry_metadata,
    build_series_metadata,
)
from ...setup_paths import OPHYS_DATA_PATH

TANK_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "TDT" / "Photo_249_391-200721-120136_stubbed"

RECORDING_SITES = ["dms", "dls"]
EPOC_TO_EVENT_NAME = {"LNRW": "rewarded_nose_pokes", "LNnR": "unrewarded_nose_pokes", "PrtR": "port_entries"}
# The store GuPPy's custom-event import contributed: its id names its CSV, exactly as a GuPPy CSV store id
# always does, and it is absent from the tank.
IMPORTED_EVENT_STORE = "custom_lick"
IMPORTED_EVENT_NAME = "licks"
# Onsets for the imported event. They are written verbatim into both the CSV and the mock GuPPy output,
# which is what a real pair does: GuPPy analyzed the very timestamps the CSV holds. They fall inside the
# mock GuPPy timebase (1.0 s of lights-on delay, then 200 Hz for 400 samples).
IMPORTED_EVENT_ONSETS = [1.125, 1.5, 2.0, 2.625]
NUM_MOCK_TRIALS = len(IMPORTED_EVENT_ONSETS)

EXPECTED_ACQUISITION_INTERFACE_NAMES = {"FiberPhotometry_signal", "FiberPhotometry_control"}
EXPECTED_EVENTS_INTERFACE_NAMES = {"Events_tdt", f"Events_csv_{IMPORTED_EVENT_STORE}"}


class TestGuppyConverterMixedEvents:
    @pytest.fixture
    def session_folder(self, tmp_path):
        """The tank symlinked into a writable folder, with the imported-event CSV beside it.

        One folder holds the traces and both event sources, which is how GuPPy lays a session out --
        and the symlinks keep the ~1 MB tank from being copied per test.
        """
        session_folder = tmp_path / "session"
        session_folder.mkdir()
        for path in TANK_FOLDER.iterdir():
            # Resolved, because a relative target is read relative to the link's own directory rather
            # than to the working directory, and OPHYS_DATA_PATH is relative when CI is set.
            (session_folder / path.name).symlink_to(path.resolve())
        pandas.DataFrame({"timestamps": IMPORTED_EVENT_ONSETS}).to_csv(
            session_folder / f"{IMPORTED_EVENT_STORE}.csv", index=False
        )
        return session_folder

    @pytest.fixture
    def event_onsets(self, session_folder):
        """The onsets GuPPy analyzed: the tank's own epocs, plus the imported event's."""
        import tdt

        block = tdt.read_block(str(session_folder), evtype=["epocs"])
        onsets = {
            event_name: np.asarray(block.epocs[epoc_name].onset)[:NUM_MOCK_TRIALS].tolist()
            for epoc_name, event_name in EPOC_TO_EVENT_NAME.items()
        }
        onsets[IMPORTED_EVENT_NAME] = list(IMPORTED_EVENT_ONSETS)
        return onsets

    @pytest.fixture
    def guppy_output_folder(self, tmp_path, event_onsets):
        """A storesList.csv listing the tank's three epocs and the imported store side by side."""
        event_store_to_name = {**EPOC_TO_EVENT_NAME, IMPORTED_EVENT_STORE: IMPORTED_EVENT_NAME}
        return generate_mock_guppy_output_folder(
            tmp_path / "guppy_output",
            event_store_to_name=event_store_to_name,
            event_onsets=event_onsets,
        )

    @pytest.fixture
    def converter(self, session_folder, guppy_output_folder):
        return GuppyConverter(
            fiber_photometry_folder_path=session_folder,
            events_folder_path=session_folder,
            guppy_folder_path=guppy_output_folder,
            acquisition_format="tdt",
            events_formats={"tdt", "csv"},
        )

    @pytest.fixture
    def metadata(self, converter):
        metadata = converter.get_metadata()
        metadata = dict_deep_update(metadata, build_device_metadata(RECORDING_SITES))
        metadata["FiberPhotometry"] = dict_deep_update(
            metadata["FiberPhotometry"], build_fiber_photometry_metadata(RECORDING_SITES)
        )
        metadata["FiberPhotometry"] = dict_deep_update(
            metadata["FiberPhotometry"], build_series_metadata(RECORDING_SITES)
        )
        return metadata

    def test_each_store_is_routed_to_the_format_that_carries_it(self, converter):
        """The tank claims its epocs and the CSV claims the imported store, by discovery rather than declaration."""
        assert converter._event_store_ownership == {
            "tdt": ["LNRW", "LNnR", "PrtR"],
            "csv": [IMPORTED_EVENT_STORE],
        }

    def test_both_formats_build_their_own_events_interfaces(self, converter):
        """One interface reads the whole tank; the CSV store, having its own file, gets its own."""
        assert set(converter.data_interface_objects) == (
            EXPECTED_ACQUISITION_INTERFACE_NAMES | EXPECTED_EVENTS_INTERFACE_NAMES | {"Guppy"}
        )

    def test_every_store_takes_the_name_guppy_gave_it(self, converter):
        """Select/rename runs across both events interfaces, so all four stores survive under GuPPy's names."""
        metadata = converter.get_metadata()
        store_to_event_name = {}
        for interface_name in EXPECTED_EVENTS_INTERFACE_NAMES:
            metadata_key = converter.data_interface_objects[interface_name].metadata_key
            for source_id, entry in metadata["Events"][metadata_key]["event_types"].items():
                store_to_event_name[source_id] = entry["event_name"]
        assert store_to_event_name == {**EPOC_TO_EVENT_NAME, IMPORTED_EVENT_STORE: IMPORTED_EVENT_NAME}

    def test_imported_events_land_in_the_merged_table_beside_the_tank_events(self, converter, metadata, tmp_path):
        """Both sources write into the one BehavioralEvents table, with the CSV's timestamps verbatim."""
        nwbfile_path = tmp_path / "mixed_events.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True)

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            events_table = nwbfile.events["BehavioralEvents"]
            event_types = list(events_table["event_type"][:])
            timestamps = np.asarray(events_table["timestamp"][:], dtype=np.float64)

            assert set(event_types) == {*EPOC_TO_EVENT_NAME.values(), IMPORTED_EVENT_NAME}
            imported_rows = [index for index, name in enumerate(event_types) if name == IMPORTED_EVENT_NAME]
            np.testing.assert_allclose(timestamps[imported_rows], IMPORTED_EVENT_ONSETS)

    def test_guppy_events_registry_links_the_imported_event(self, converter, metadata, tmp_path):
        """The imported event's registry row points at its own occurrences in the merged table."""
        nwbfile_path = tmp_path / "mixed_events_registry.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True)

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            guppy_events_table = nwbfile.processing["guppy"].data_interfaces["events"]
            event_names = list(guppy_events_table["event_name"][:])
            referenced_rows = guppy_events_table["events"][event_names.index(IMPORTED_EVENT_NAME)]

            events_table = nwbfile.events["BehavioralEvents"]
            assert list(referenced_rows["event_type"]) == [IMPORTED_EVENT_NAME] * NUM_MOCK_TRIALS
            np.testing.assert_allclose(
                np.asarray(referenced_rows["timestamp"], dtype=np.float64), IMPORTED_EVENT_ONSETS
            )
            assert len(events_table) > len(referenced_rows)

    def test_an_undeclared_events_format_names_the_stores_it_left_behind(self, session_folder, guppy_output_folder):
        """Defaulting to the acquisition format leaves the imported store with no source, which is an error."""
        with pytest.raises(AssertionError, match=IMPORTED_EVENT_STORE):
            GuppyConverter(
                fiber_photometry_folder_path=session_folder,
                events_folder_path=session_folder,
                guppy_folder_path=guppy_output_folder,
                acquisition_format="tdt",
            )

    def test_a_store_two_formats_both_carry_is_rejected(self, session_folder, guppy_output_folder):
        """A tank epoc that also has a CSV would be written twice, so the ambiguity is refused up front."""
        pandas.DataFrame({"timestamps": [1.0, 2.0]}).to_csv(session_folder / "PrtR.csv", index=False)

        with pytest.raises(AssertionError, match="carried by more than one"):
            GuppyConverter(
                fiber_photometry_folder_path=session_folder,
                events_folder_path=session_folder,
                guppy_folder_path=guppy_output_folder,
                acquisition_format="tdt",
                events_formats={"tdt", "csv"},
            )
