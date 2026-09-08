"""Tests for a ``GuppyConverter`` session whose events do not all come from the acquisition format.

GuPPy's custom-event import writes the events it imported back out as one-column ``timestamps`` CSVs,
which then sit in the session folder beside whatever the rig recorded. Such a session's
``storesList.csv`` lists stores from two sources at once, and the converter reads both without being
told to: the events folder is scanned for those CSVs, and a store with one of its own is read from it
while everything else falls to the acquisition format.

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
# Each raw event type is written as its own EventsTable, named after the label GuPPy gave the store.
EVENT_NAME_TO_RAW_TABLE_NAME = {
    "rewarded_nose_pokes": "RewardedNosePokes",
    "unrewarded_nose_pokes": "UnrewardedNosePokes",
    "port_entries": "PortEntries",
    IMPORTED_EVENT_NAME: "Licks",
}
# The table the GuPPy interface writes its own analyzed onsets into, which the registry references.
GUPPY_EVENTS_TABLE_NAME = "GuppyEvents"

EXPECTED_ACQUISITION_INTERFACE_NAMES = {"FiberPhotometry_signal", "FiberPhotometry_control"}
EXPECTED_EVENTS_INTERFACE_NAMES = {"Events", f"Events_{IMPORTED_EVENT_STORE}"}


def store_ids_by_interface(converter):
    """Which stores each events interface was built to supply, which is the routing decision itself."""
    return {spec["interface_name"]: spec["store_ids"] for spec in converter._events_specs}


def build_session_metadata(converter):
    """The converter's own metadata, completed with the fiber photometry chain a caller must supply."""
    metadata = converter.get_metadata()
    metadata = dict_deep_update(metadata, build_device_metadata(RECORDING_SITES))
    metadata["FiberPhotometry"] = dict_deep_update(
        metadata["FiberPhotometry"], build_fiber_photometry_metadata(RECORDING_SITES)
    )
    metadata["FiberPhotometry"] = dict_deep_update(metadata["FiberPhotometry"], build_series_metadata(RECORDING_SITES))
    return metadata


class TestGuppyConverterMixedEvents:
    @pytest.fixture(scope="class")
    @classmethod
    def session_folder(cls, tmp_path_factory):
        """The tank symlinked into a writable folder, with the imported-event CSV beside it.

        One folder holds the traces and both event sources, which is how GuPPy lays a session out --
        and the symlinks keep the ~1 MB tank from being copied per test.
        """
        session_folder = tmp_path_factory.mktemp("mixed_session") / "session"
        session_folder.mkdir()
        for path in TANK_FOLDER.iterdir():
            # Resolved, because a relative target is read relative to the link's own directory rather
            # than to the working directory, and OPHYS_DATA_PATH is relative when CI is set.
            (session_folder / path.name).symlink_to(path.resolve())
        pandas.DataFrame({"timestamps": IMPORTED_EVENT_ONSETS}).to_csv(
            session_folder / f"{IMPORTED_EVENT_STORE}.csv", index=False
        )
        return session_folder

    @pytest.fixture(scope="class")
    @classmethod
    def event_onsets(cls, session_folder):
        """The onsets GuPPy analyzed: the tank's own epocs, plus the imported event's."""
        import tdt

        block = tdt.read_block(str(session_folder), evtype=["epocs"])
        onsets = {
            event_name: np.asarray(block.epocs[epoc_name].onset)[:NUM_MOCK_TRIALS].tolist()
            for epoc_name, event_name in EPOC_TO_EVENT_NAME.items()
        }
        onsets[IMPORTED_EVENT_NAME] = list(IMPORTED_EVENT_ONSETS)
        return onsets

    @pytest.fixture(scope="class")
    @classmethod
    def guppy_output_folder(cls, tmp_path_factory, event_onsets):
        """A storesList.csv listing the tank's three epocs and the imported store side by side."""
        event_store_to_name = {**EPOC_TO_EVENT_NAME, IMPORTED_EVENT_STORE: IMPORTED_EVENT_NAME}
        return generate_mock_guppy_output_folder(
            tmp_path_factory.mktemp("mixed_output") / "guppy_output",
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
        )

    @pytest.fixture
    def metadata(self, converter):
        return build_session_metadata(converter)

    def test_each_store_is_routed_to_the_format_that_carries_it(self, converter):
        """The tank claims its epocs and the CSV claims the imported store, by discovery rather than declaration."""
        assert store_ids_by_interface(converter) == {
            "Events": ["LNRW", "LNnR", "PrtR"],
            f"Events_{IMPORTED_EVENT_STORE}": [IMPORTED_EVENT_STORE],
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

    def test_the_imported_events_get_their_own_table_beside_the_tank_events(self, converter, metadata, tmp_path):
        """Each store keeps its own EventsTable, the imported one carrying the CSV's timestamps verbatim."""
        nwbfile_path = tmp_path / "mixed_events.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True)

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            assert set(nwbfile.events) == set(EVENT_NAME_TO_RAW_TABLE_NAME.values()) | {GUPPY_EVENTS_TABLE_NAME}

            imported_table = nwbfile.get_events_table(EVENT_NAME_TO_RAW_TABLE_NAME[IMPORTED_EVENT_NAME])
            # A table holding a single event type records no discriminator; the table is the identity.
            assert "event_type" not in imported_table.colnames
            np.testing.assert_allclose(
                np.sort(imported_table.to_dataframe().timestamp.to_numpy()), IMPORTED_EVENT_ONSETS
            )

    def test_a_session_whose_every_event_was_imported_reads_none_from_the_tank(self, session_folder, tmp_path):
        """With nothing left for the acquisition format, only the imported stores' interfaces are built."""
        guppy_output_folder = generate_mock_guppy_output_folder(
            tmp_path / "imported_only_output",
            event_store_to_name={IMPORTED_EVENT_STORE: IMPORTED_EVENT_NAME},
            event_onsets={IMPORTED_EVENT_NAME: list(IMPORTED_EVENT_ONSETS)},
        )
        converter = GuppyConverter(
            fiber_photometry_folder_path=session_folder,
            events_folder_path=session_folder,
            guppy_folder_path=guppy_output_folder,
            acquisition_format="tdt",
        )

        assert store_ids_by_interface(converter) == {f"Events_{IMPORTED_EVENT_STORE}": [IMPORTED_EVENT_STORE]}
        assert set(converter.data_interface_objects) == (
            EXPECTED_ACQUISITION_INTERFACE_NAMES | {f"Events_{IMPORTED_EVENT_STORE}", "Guppy"}
        )
