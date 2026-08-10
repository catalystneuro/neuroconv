"""Tests for ``GuppyInterface`` writing into an NWBFile that already holds the acquisition.

This is how a session GuPPy processed out of an existing NWB file is converted: the file already has
the response series, so the interface adds only GuPPy's own products and points the recording sites
registry at the ``FiberPhotometryTable`` that is already there. Nothing is read in and nothing is
copied. The events registry references GuPPy's own analyzed onsets, written as an ``EventsTable``
alongside whatever events the file already holds.

The source can be synthesized in-process, so this needs no data on disk: it is built from the mock
fiber photometry and events interfaces, and the GuPPy output folder is generated to match the store
ids GuPPy would have derived from it. What is asserted here is the linking specifically -- how a
GuPPy store id resolves to a ``FiberPhotometryTable`` row, what the recording sites registry becomes
when it cannot, and the events table GuPPy's onsets are written into. The products are covered in
``test_guppy_interface.py`` and against genuine GuPPy output in
``tests/test_on_data/fiber_photometry/guppy/test_reference_session.py``.
"""

from datetime import datetime, timezone

import numpy as np
import pytest
from pynwb import read_nwb
from pynwb.event import EventsTable
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv import ConverterPipe
from neuroconv.datainterfaces import GuppyInterface
from neuroconv.datainterfaces.fiber_photometry.guppy.nwb_linking import (
    resolve_acquisition_store_rows,
)
from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile
from neuroconv.tools.testing.mock_guppy import generate_mock_guppy_output_folder
from neuroconv.tools.testing.mock_interfaces import (
    MockEventsInterface,
    MockFiberPhotometryInterface,
)

# The source is laid out the way a fiber photometry conversion writes one: a 2-D series per role,
# column-stacking the two recording sites, and one EventsTable with an event_type column.
RECORDING_SITES = ("dms", "dls")
SIGNAL_SERIES_NAME = "FiberPhotometryResponseSeriesSignal"
CONTROL_SERIES_NAME = "FiberPhotometryResponseSeriesControl"
SOURCE_EVENTS_TABLE_NAME = "BehavioralEvents"
EVENT_NAMES = ("port_entry", "reward", "lever_press")

# The store ids GuPPy derives from that layout.
RECORDING_SITE_TO_STORES = {
    recording_site: {
        "signal": f"{SIGNAL_SERIES_NAME}_{index}",
        "control": f"{CONTROL_SERIES_NAME}_{index}",
    }
    for index, recording_site in enumerate(RECORDING_SITES)
}
EVENT_STORE_TO_NAME = {f"{SOURCE_EVENTS_TABLE_NAME}_{event_name}": event_name for event_name in EVENT_NAMES}

SAMPLING_RATE = 200.0
NUM_SAMPLES = 600

# Something GuPPy has no concept of, to prove the export carries the whole source across.
UNRELATED_TRIAL_START_TIMES = (0.5, 1.5, 2.5)

# The source table is site-major, signal before control, so dms owns rows 0 and 1, dls 2 and 3.
RECORDING_SITE_TO_TABLE_ROWS = {"dms": [0, 1], "dls": [2, 3]}


def _fiber_photometry_source_metadata():
    """The provenance chain written into the source, which the registries must reference in place."""
    devices = {
        "excitation_source": {"type": "ExcitationSource", "name": "excitation_source"},
        "photodetector": {"type": "Photodetector", "name": "photodetector"},
    }
    for recording_site in RECORDING_SITES:
        devices[f"optical_fiber_{recording_site}"] = {
            "type": "OpticalFiber",
            "name": f"optical_fiber_{recording_site}",
            "fiber_insertion": {"depth_in_mm": 2.8},
        }

    rows = {}
    for recording_site in RECORDING_SITES:
        for role, wavelength in (("signal", 465.0), ("control", 405.0)):
            rows[f"{recording_site}_{role}"] = {
                "location": recording_site.upper(),
                "excitation_wavelength_in_nm": wavelength,
                "emission_wavelength_in_nm": 525.0,
                "indicator_metadata_key": "gcamp",
                "optical_fiber_metadata_key": f"optical_fiber_{recording_site}",
                "excitation_source_metadata_key": "excitation_source",
                "photodetector_metadata_key": "photodetector",
            }

    return {
        "Devices": devices,
        "FiberPhotometry": {
            "FiberPhotometryIndicators": {
                "gcamp": {"name": "gcamp", "label": "GCaMP7b", "description": "GCaMP7b calcium indicator."},
            },
            "FiberPhotometryTable": {
                "name": "fiber_photometry_table",
                "description": "The source session's fiber photometry setup.",
                "rows": rows,
            },
            "signal": {
                "name": SIGNAL_SERIES_NAME,
                "fiber_photometry_table_region": [f"{site}_signal" for site in RECORDING_SITES],
            },
            "control": {
                "name": CONTROL_SERIES_NAME,
                "fiber_photometry_table_region": [f"{site}_control" for site in RECORDING_SITES],
            },
        },
    }


@pytest.fixture(scope="module")
def source_session(tmp_path_factory):
    """Write the source NWB file and return its path plus the event onsets it holds."""
    events_interface = MockEventsInterface(num_event_types=len(EVENT_NAMES), num_events=6)
    converter = ConverterPipe(
        data_interfaces={
            "signal": MockFiberPhotometryInterface(
                stream_names=[f"{site}_signal" for site in RECORDING_SITES],
                num_samples=NUM_SAMPLES,
                sampling_rate=SAMPLING_RATE,
                metadata_key="signal",
            ),
            "control": MockFiberPhotometryInterface(
                stream_names=[f"{site}_control" for site in RECORDING_SITES],
                num_samples=NUM_SAMPLES,
                sampling_rate=SAMPLING_RATE,
                metadata_key="control",
            ),
            "events": events_interface,
        }
    )

    metadata = converter.get_metadata()
    metadata["NWBFile"]["session_start_time"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
    metadata["NWBFile"]["session_description"] = "The source session, written before GuPPy ran."
    metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    for key, value in _fiber_photometry_source_metadata().items():
        metadata[key] = value

    event_types = metadata["Events"][events_interface.metadata_key]["event_types"]
    source_id_to_event_name = dict(zip(event_types, EVENT_NAMES))
    for source_id, event_name in source_id_to_event_name.items():
        event_types[source_id]["event_name"] = event_name
        event_types[source_id]["table_metadata_key"] = "merged"
    metadata["Events"]["EventTables"] = {
        "merged": {"table_name": SOURCE_EVENTS_TABLE_NAME, "description": "The session's behavioral events."}
    }

    nwbfile = converter.create_nwbfile(metadata=metadata)
    # Unrelated to GuPPy, and unreachable through any fiber photometry interface.
    nwbfile.add_trial_column(name="condition", description="The trial's condition.")
    for trial_start_time in UNRELATED_TRIAL_START_TIMES:
        nwbfile.add_trial(start_time=trial_start_time, stop_time=trial_start_time + 0.4, condition="go")

    nwbfile_path = tmp_path_factory.mktemp("nwb_source") / "source.nwb"
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path, backend="hdf5")

    events_data = events_interface._get_events_data_dict()
    event_name_to_onsets = {
        event_name: events_data[source_id].timestamps for source_id, event_name in source_id_to_event_name.items()
    }
    return nwbfile_path, event_name_to_onsets


@pytest.fixture(scope="module")
def guppy_folder(tmp_path_factory, source_session):
    """A GuPPy output folder whose storesList.csv names the source file's stores."""
    _, event_name_to_onsets = source_session
    return generate_mock_guppy_output_folder(
        tmp_path_factory.mktemp("guppy") / "session_output_1",
        recording_site_to_stores=RECORDING_SITE_TO_STORES,
        event_store_to_name=EVENT_STORE_TO_NAME,
        event_onsets=event_name_to_onsets,
        sampling_rate=SAMPLING_RATE,
    )


@pytest.fixture
def interface(guppy_folder):
    return GuppyInterface(folder_path=str(guppy_folder))


@pytest.fixture
def converted_nwbfile_path(interface, source_session, tmp_path):
    """The source, exported with GuPPy's outputs added to it."""
    source_nwbfile_path, _ = source_session
    nwbfile = read_nwb(path=str(source_nwbfile_path))
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

    nwbfile_path = tmp_path / "converted.nwb"
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path, backend="hdf5")
    return nwbfile_path


class TestGuppyInterfaceLinksIntoExistingTables:
    def test_export_carries_the_whole_source_across(self, converted_nwbfile_path, source_session):
        """Everything the source held survives, including what GuPPy has no concept of."""
        source_nwbfile_path, _ = source_session
        source_nwbfile = read_nwb(path=str(source_nwbfile_path))
        converted = read_nwb(path=str(converted_nwbfile_path))

        assert converted.session_description == "The source session, written before GuPPy ran."
        assert converted.session_start_time == source_nwbfile.session_start_time
        assert converted.subject.subject_id == "subject1"
        np.testing.assert_allclose(converted.trials["start_time"][:], UNRELATED_TRIAL_START_TIMES)
        assert list(converted.trials["condition"][:]) == ["go", "go", "go"]

        for series_name in (SIGNAL_SERIES_NAME, CONTROL_SERIES_NAME):
            np.testing.assert_array_equal(
                converted.acquisition[series_name].data[:], source_nwbfile.acquisition[series_name].data[:]
            )

    def test_the_acquisition_is_not_duplicated(self, converted_nwbfile_path):
        """The source's own series are the only ones; GuPPy added no copies."""
        converted = read_nwb(path=str(converted_nwbfile_path))
        assert set(converted.acquisition) == {SIGNAL_SERIES_NAME, CONTROL_SERIES_NAME}
        # guppy_parameters is GuPPy's own provenance; fiber_photometry is the source's, referenced not restated.
        assert set(converted.lab_meta_data) == {"fiber_photometry", "guppy_parameters"}

    def test_recording_sites_registry_links_to_the_source_table(self, converted_nwbfile_path):
        """Each site's row points at the FiberPhotometryTable rows its two stores were recorded on."""
        converted = read_nwb(path=str(converted_nwbfile_path))
        recording_sites_table = converted.processing["guppy"]["recording_sites"]

        assert list(recording_sites_table["recording_site"].data) == list(RECORDING_SITES)
        assert recording_sites_table["fiber_photometry_table_region"].target.table.name == "fiber_photometry_table"
        for row_index, recording_site in enumerate(RECORDING_SITES):
            linked = recording_sites_table["fiber_photometry_table_region"][row_index]
            assert set(linked["location"]) == {recording_site.upper()}
            assert sorted(linked["excitation_wavelength_in_nm"]) == [405.0, 465.0]

    def test_events_registry_links_to_guppys_own_events(self, converted_nwbfile_path, source_session):
        """Each event's row points at that event's onsets in GuPPy's own table, added beside the source's.

        The source's own events table is left exactly as it was: GuPPy's onsets are a processing
        output and are written as a table of their own, whatever the file already holds.
        """
        _, event_name_to_onsets = source_session
        converted = read_nwb(path=str(converted_nwbfile_path))
        events_table = converted.processing["guppy"]["events"]

        assert set(converted.events) == {SOURCE_EVENTS_TABLE_NAME, "GuppyEvents"}
        assert events_table["events"].target.table.name == "GuppyEvents"
        registry_event_names = list(events_table["event_name"].data)
        assert set(registry_event_names) == set(EVENT_NAMES)
        for row_index, event_name in enumerate(registry_event_names):
            linked = events_table["events"][row_index]
            assert set(linked["event_type"]) == {event_name}
            np.testing.assert_allclose(sorted(linked["timestamp"]), sorted(event_name_to_onsets[event_name]))

    def test_products_still_reference_the_registries(self, converted_nwbfile_path):
        """Linking the registries outward does not disturb the products' references into them."""
        converted = read_nwb(path=str(converted_nwbfile_path))
        guppy_module = converted.processing["guppy"]
        recording_site_names = list(guppy_module["recording_sites"]["recording_site"].data)

        for recording_site in RECORDING_SITES:
            series = guppy_module[f"dff_{recording_site}"]
            linked_rows = series.recording_site.data if hasattr(series.recording_site, "data") else None
            assert linked_rows is not None
            assert [recording_site_names[int(row)] for row in linked_rows] == [recording_site]


class TestGuppysOwnEventsTable:
    """The EventsTable GuPPy's analyzed onsets are written into, and the registry's region over it."""

    def test_bare_nwbfile_writes_guppys_own_events(self, interface, source_session):
        """The standalone case: the recording sites go link-free, but the events are written and linked.

        The onsets come from the GuPPy output rather than the file, so there is always something to
        reference.
        """
        _, event_name_to_onsets = source_session
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        guppy_module = nwbfile.processing["guppy"]
        assert list(guppy_module["recording_sites"]["recording_site"].data) == list(RECORDING_SITES)
        assert "fiber_photometry_table_region" not in guppy_module["recording_sites"].colnames

        written_events = nwbfile.events["GuppyEvents"]
        timestamps = np.asarray(written_events["timestamp"].data)
        assert timestamps.size == sum(len(onsets) for onsets in event_name_to_onsets.values())
        assert list(timestamps) == sorted(timestamps), "The written table must be chronological."
        assert set(written_events["event_type"].data) == set(EVENT_NAMES)

        events_registry = guppy_module["events"]
        assert events_registry["events"].target.table is written_events
        for row_index, event_name in enumerate(events_registry["event_name"].data):
            linked = events_registry["events"][row_index]
            assert set(linked["event_type"]) == {event_name}
            np.testing.assert_allclose(linked["timestamp"], sorted(event_name_to_onsets[event_name]))

    def test_guppys_own_events_round_trip(self, interface, source_session, tmp_path):
        """The fresh table and the registry's region into it survive a write and read back."""
        _, event_name_to_onsets = source_session
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        nwbfile_path = tmp_path / "guppy_own_events.nwb"
        configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path, backend="hdf5")

        read_back = read_nwb(path=str(nwbfile_path))
        events_registry = read_back.processing["guppy"]["events"]
        assert events_registry["events"].target.table.name == "GuppyEvents"
        for row_index, event_name in enumerate(events_registry["event_name"].data):
            linked = events_registry["events"][row_index]
            assert set(linked["event_type"]) == {event_name}
            np.testing.assert_allclose(linked["timestamp"], sorted(event_name_to_onsets[event_name]))

    def test_events_table_name_collision_fails_loudly(self, interface):
        """The fresh table never merges into one the file already holds under that name."""
        nwbfile = mock_NWBFile()
        occupant = EventsTable(name="GuppyEvents", description="Something else entirely.")
        occupant.add_row(timestamp=0.5)
        nwbfile.add_events_table(occupant)

        with pytest.raises(AssertionError, match="already holds an events table named 'GuppyEvents'"):
            interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

    def test_events_table_name_is_editable(self, interface, source_session):
        """A collision is resolved through the metadata, which names the table the onsets go into."""
        _, event_name_to_onsets = source_session
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        metadata["FiberPhotometry"]["Guppy"][interface.metadata_key]["Events"]["name"] = "GuppyOnsets"
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert set(nwbfile.events) == {"GuppyOnsets"}
        assert nwbfile.processing["guppy"]["events"]["events"].target.table is nwbfile.events["GuppyOnsets"]


class TestRecordingSitesFallback:
    """What the recording sites registry becomes when the file cannot answer for GuPPy's stores."""

    def test_unresolvable_acquisition_store_warns_and_falls_back(self, source_session, tmp_path_factory):
        """A store naming no series in the file leaves the recording sites unlinked, loudly."""
        source_nwbfile_path, event_name_to_onsets = source_session
        stale_stores = {site: dict(stores) for site, stores in RECORDING_SITE_TO_STORES.items()}
        stale_stores["dls"]["signal"] = "NoSuchSeries_0"
        stale_guppy_folder = generate_mock_guppy_output_folder(
            tmp_path_factory.mktemp("stale_guppy") / "session_output_1",
            recording_site_to_stores=stale_stores,
            event_store_to_name=EVENT_STORE_TO_NAME,
            event_onsets=event_name_to_onsets,
            sampling_rate=SAMPLING_RATE,
        )
        interface = GuppyInterface(folder_path=str(stale_guppy_folder))
        nwbfile = read_nwb(path=str(source_nwbfile_path))

        with pytest.warns(UserWarning, match="name no FiberPhotometryResponseSeries"):
            interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        guppy_module = nwbfile.processing["guppy"]
        assert "fiber_photometry_table_region" not in guppy_module["recording_sites"].colnames
        # The events are unaffected -- the two registries resolve independently.
        assert "events" in guppy_module["events"].colnames


class TestStoreIdResolution:
    """The acquisition id spellings, resolved against files built directly rather than through GuPPy."""

    def test_multi_channel_series_resolves_per_column(self, source_session):
        source_nwbfile_path, _ = source_session
        nwbfile = read_nwb(path=str(source_nwbfile_path))

        store_ids = [store_id for stores in RECORDING_SITE_TO_STORES.values() for store_id in stores.values()]
        resolved = resolve_acquisition_store_rows(nwbfile=nwbfile, store_ids=store_ids)
        assert resolved == {
            f"{SIGNAL_SERIES_NAME}_0": 0,
            f"{CONTROL_SERIES_NAME}_0": 1,
            f"{SIGNAL_SERIES_NAME}_1": 2,
            f"{CONTROL_SERIES_NAME}_1": 3,
        }

    def test_unknown_store_is_simply_absent(self, source_session):
        source_nwbfile_path, _ = source_session
        nwbfile = read_nwb(path=str(source_nwbfile_path))
        assert resolve_acquisition_store_rows(nwbfile=nwbfile, store_ids=["NoSuchSeries_0"]) == {}
