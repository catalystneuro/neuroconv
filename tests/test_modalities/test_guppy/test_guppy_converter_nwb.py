"""Tests for the NWB seam of ``GuppyConverter``.

NWB is the one acquisition format whose source can be synthesized in-process, so unlike the tdt,
doric and npm seams this runs with no data on disk: a source file is built from the mock fiber
photometry and events interfaces, and the GuPPy output folder is generated to match the store ids
GuPPy would have derived from it.

What is specific to ``acquisition_format="nwb"``: how a GuPPy store id resolves to a response series
column or an events-table row set, how the ``FiberPhotometry`` chain is inherited from the source
rather than supplied by the user, and that the file the converter writes still reads back as the
same set of stores. Everything format-independent -- role grouping, event merging, the registries --
is asserted once in ``tests/test_on_data/fiber_photometry/guppy/test_reference_session.py``.
"""

from datetime import datetime, timezone

import numpy as np
import pytest
from pynwb import read_nwb
from pynwb.event import EventsTable
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv import ConverterPipe
from neuroconv.converters import GuppyConverter
from neuroconv.datainterfaces.fiber_photometry.guppy.nwb_utils import (
    _event_sources,
    _NwbEventsInterface,
    _NwbFiberPhotometryInterface,
)
from neuroconv.tools.testing.mock_guppy import generate_mock_guppy_output_folder
from neuroconv.tools.testing.mock_interfaces import (
    MockEventsInterface,
    MockFiberPhotometryInterface,
)

# The source file is laid out the way GuppyConverter itself writes one: one 2-D series per role,
# column-stacking the two recording sites, and one merged EventsTable with an event_type column.
RECORDING_SITES = ("dms", "dls")
SIGNAL_SERIES_NAME = "FiberPhotometryResponseSeriesSignal"
CONTROL_SERIES_NAME = "FiberPhotometryResponseSeriesControl"
MERGED_EVENTS_TABLE_NAME = "BehavioralEvents"
EVENT_NAMES = ("port_entry", "reward", "lever_press")

# The store ids GuPPy derives from that layout: one per column of each 2-D series, and one per
# distinct value of the merged table's single value column.
RECORDING_SITE_TO_STORES = {
    recording_site: {
        "signal": f"{SIGNAL_SERIES_NAME}_{index}",
        "control": f"{CONTROL_SERIES_NAME}_{index}",
    }
    for index, recording_site in enumerate(RECORDING_SITES)
}
EVENT_STORE_TO_NAME = {f"{MERGED_EVENTS_TABLE_NAME}_{event_name}": event_name for event_name in EVENT_NAMES}

SAMPLING_RATE = 200.0
NUM_SAMPLES = 600


def _fiber_photometry_source_metadata():
    """The provenance chain written into the source file, which the converter must inherit back."""
    devices = {
        "excitation_source": {
            "type": "ExcitationSource",
            "name": "excitation_source",
            "device_model_metadata_key": "excitation_source_model",
        },
        "photodetector": {
            "type": "Photodetector",
            "name": "photodetector",
            "device_model_metadata_key": "photodetector_model",
        },
    }
    for recording_site in RECORDING_SITES:
        devices[f"optical_fiber_{recording_site}"] = {
            "type": "OpticalFiber",
            "name": f"optical_fiber_{recording_site}",
            "device_model_metadata_key": "optical_fiber_model",
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
        "DeviceModels": {
            "optical_fiber_model": {
                "type": "OpticalFiberModel",
                "name": "optical_fiber_model",
                "manufacturer": "Doric Lenses",
                "numerical_aperture": 0.48,
            },
            "excitation_source_model": {
                "type": "ExcitationSourceModel",
                "name": "excitation_source_model",
                "manufacturer": "Doric Lenses",
                "source_type": "LED",
                "excitation_mode": "one-photon",
            },
            "photodetector_model": {
                "type": "PhotodetectorModel",
                "name": "photodetector_model",
                "manufacturer": "Doric Lenses",
                "detector_type": "photodiode",
            },
        },
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
                # Row order is site-major, signal-before-control, so the signal rows are 0 and 2.
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
    """Write the source NWB file and return its folder plus the event timestamps it holds."""
    folder_path = tmp_path_factory.mktemp("nwb_source")
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
    for key, value in _fiber_photometry_source_metadata().items():
        metadata[key] = value

    # Merge the three mock event types into one table with an event_type column, which is the layout
    # GuPPy splits into <table>_<value> stores.
    event_types = metadata["Events"][events_interface.metadata_key]["event_types"]
    source_id_to_event_name = dict(zip(event_types, EVENT_NAMES))
    for source_id, event_name in source_id_to_event_name.items():
        event_types[source_id]["event_name"] = event_name
        event_types[source_id]["table_metadata_key"] = "merged"
    metadata["Events"]["EventTables"] = {
        "merged": {"table_name": MERGED_EVENTS_TABLE_NAME, "description": "The session's behavioral events."}
    }

    nwbfile_path = folder_path / "source.nwb"
    converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

    events_data = events_interface._get_events_data_dict()
    event_name_to_onsets = {
        event_name: events_data[source_id].timestamps for source_id, event_name in source_id_to_event_name.items()
    }
    return folder_path, event_name_to_onsets


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
def converter(source_session, guppy_folder):
    source_folder, _ = source_session
    return GuppyConverter(
        fiber_photometry_folder_path=source_folder,
        events_folder_path=source_folder,
        guppy_folder_path=guppy_folder,
        acquisition_format="nwb",
    )


class TestGuppyConverterNWB:
    def test_one_interface_per_role_and_one_for_events(self, converter):
        """The source is a single file, so the events fan out no further than one interface."""
        assert set(converter.data_interface_objects) == {
            "FiberPhotometry_signal",
            "FiberPhotometry_control",
            "Events",
            "Guppy",
        }

    def test_store_ids_resolve_to_series_columns(self, converter, source_session):
        """A store id names a series and a column of it, and reads back that column's own values."""
        source_folder, _ = source_session
        source_nwbfile = read_nwb(path=str(source_folder / "source.nwb"))

        for role, series_name in (("signal", SIGNAL_SERIES_NAME), ("control", CONTROL_SERIES_NAME)):
            interface = converter.data_interface_objects[f"FiberPhotometry_{role}"]
            expected_store_ids = [RECORDING_SITE_TO_STORES[site][role] for site in RECORDING_SITES]
            assert interface.stream_names == expected_store_ids

            source_data = source_nwbfile.acquisition[series_name].data[:]
            for column_index, store_id in enumerate(expected_store_ids):
                np.testing.assert_array_equal(
                    interface._get_stream_data(stream_name=store_id), source_data[:, column_index]
                )

    def test_store_timestamps_reconstructed_from_rate(self, converter):
        """The source series is regularly sampled, so its timestamps are rebuilt from starting_time and rate."""
        interface = converter.data_interface_objects["FiberPhotometry_signal"]
        timestamps = interface._get_stream_timestamps(stream_name=RECORDING_SITE_TO_STORES["dms"]["signal"])
        assert len(timestamps) == NUM_SAMPLES
        np.testing.assert_allclose(timestamps[:3], [0.0, 0.005, 0.010], atol=1e-9)

    def test_event_store_ids_resolve_to_their_rows(self, converter, source_session):
        """A merged-table store id selects exactly the rows whose event_type matches it."""
        _, event_name_to_onsets = source_session
        events_interface = converter.data_interface_objects["Events"]
        events_data = events_interface._get_events_data_dict()

        assert set(events_data) == set(EVENT_STORE_TO_NAME)
        for store_id, event_name in EVENT_STORE_TO_NAME.items():
            np.testing.assert_allclose(events_data[store_id].timestamps, event_name_to_onsets[event_name])

    def test_fiber_photometry_chain_inherited_from_source(self, converter):
        """The source states the whole chain, so the user supplies none of it."""
        metadata = converter.get_metadata()
        fiber_photometry_metadata = metadata["FiberPhotometry"]

        assert set(metadata["Devices"]) == {
            "excitation_source",
            "photodetector",
            "optical_fiber_dms",
            "optical_fiber_dls",
        }
        assert metadata["Devices"]["optical_fiber_dms"]["device_model_metadata_key"] == "optical_fiber_model"
        assert metadata["DeviceModels"]["optical_fiber_model"]["numerical_aperture"] == 0.48
        assert set(fiber_photometry_metadata["FiberPhotometryIndicators"]) == {"gcamp"}

        rows = fiber_photometry_metadata["FiberPhotometryTable"]["rows"]
        assert list(rows) == ["row0", "row1", "row2", "row3"]
        assert rows["row0"]["location"] == "DMS"
        assert rows["row0"]["excitation_wavelength_in_nm"] == 465.0
        assert rows["row0"]["optical_fiber_metadata_key"] == "optical_fiber_dms"
        assert rows["row0"]["indicator_metadata_key"] == "gcamp"

        # Source row order is site-major, signal-before-control: signal is rows 0 and 2, control 1 and 3.
        assert fiber_photometry_metadata["signal"]["fiber_photometry_table_region"] == ["row0", "row2"]
        assert fiber_photometry_metadata["control"]["fiber_photometry_table_region"] == ["row1", "row3"]

    def test_conversion_writes_registries_linked_to_the_inherited_table(self, converter, tmp_path):
        """End to end: the fresh file carries the source's table and both GuPPy registries link into it."""
        nwbfile_path = tmp_path / "converted.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path)

        nwbfile = read_nwb(path=str(nwbfile_path))
        guppy_module = nwbfile.processing["guppy"]

        recording_sites_table = guppy_module["recording_sites"]
        assert list(recording_sites_table["recording_site"].data) == list(RECORDING_SITES)
        # The source table is site-major, signal-before-control, so dms owns rows 0 and 1, dls 2 and 3.
        assert list(recording_sites_table["fiber_photometry_table_region"].target.data[:]) == [0, 1, 2, 3]
        for row_index, recording_site in enumerate(RECORDING_SITES):
            linked = recording_sites_table["fiber_photometry_table_region"][row_index]
            assert set(linked["location"]) == {recording_site.upper()}
            assert sorted(linked["excitation_wavelength_in_nm"]) == [405.0, 465.0]

        events_table = guppy_module["events"]
        registry_event_names = list(events_table["event_name"].data)
        assert set(registry_event_names) == set(EVENT_NAMES)
        for row_index, event_name in enumerate(registry_event_names):
            linked = events_table["events"][row_index]
            assert set(linked["event_type"]) == {event_name}

    def test_written_file_yields_the_same_store_ids(self, converter, tmp_path):
        """Round trip: the store ids derived from the converted file are the ones GuPPy started from."""
        nwbfile_path = tmp_path / "round_trip.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path)

        expected_acquisition_store_ids = {
            store_id for stores in RECORDING_SITE_TO_STORES.values() for store_id in stores.values()
        }
        assert set(_NwbFiberPhotometryInterface.get_available_streams(nwbfile_path)) == expected_acquisition_store_ids
        assert set(_NwbEventsInterface.get_available_streams(nwbfile_path)) == set(EVENT_STORE_TO_NAME)

    def test_store_absent_from_source_fails_at_construction(self, source_session, guppy_folder, tmp_path):
        """A store GuPPy listed that the source does not hold fails when the converter is built."""
        source_folder, event_name_to_onsets = source_session
        stale_stores = {site: dict(stores) for site, stores in RECORDING_SITE_TO_STORES.items()}
        stale_stores["dls"]["signal"] = "NoSuchSeries_0"
        stale_guppy_folder = generate_mock_guppy_output_folder(
            tmp_path / "stale_output_1",
            recording_site_to_stores=stale_stores,
            event_store_to_name=EVENT_STORE_TO_NAME,
            event_onsets=event_name_to_onsets,
            sampling_rate=SAMPLING_RATE,
        )

        with pytest.raises(AssertionError, match="does not name any FiberPhotometryResponseSeries"):
            GuppyConverter(
                fiber_photometry_folder_path=source_folder,
                events_folder_path=source_folder,
                guppy_folder_path=stale_guppy_folder,
                acquisition_format="nwb",
            )

    def test_event_store_absent_from_source_fails_at_construction(self, source_session, tmp_path):
        """Likewise for a behavioral event store the source does not provide."""
        source_folder, event_name_to_onsets = source_session
        stale_guppy_folder = generate_mock_guppy_output_folder(
            tmp_path / "stale_events_output_1",
            recording_site_to_stores=RECORDING_SITE_TO_STORES,
            event_store_to_name={"NoSuchTable_reward": "reward"},
            event_onsets={"reward": event_name_to_onsets["reward"]},
            sampling_rate=SAMPLING_RATE,
        )

        with pytest.raises(AssertionError, match="the source NWB file does not provide"):
            GuppyConverter(
                fiber_photometry_folder_path=source_folder,
                events_folder_path=source_folder,
                guppy_folder_path=stale_guppy_folder,
                acquisition_format="nwb",
            )


class TestEventSourceLayouts:
    """The event layouts GuPPy accepts, each resolved to the store ids and timestamps it derives."""

    def test_table_without_a_value_column_is_one_store(self):
        nwbfile = mock_NWBFile()
        table = EventsTable(name="PortEntries", description="Port entries.")
        for timestamp in (0.5, 1.5, 2.5):
            table.add_row(timestamp=timestamp)
        nwbfile.add_events_table(table)

        event_sources = _event_sources(nwbfile)
        assert set(event_sources) == {"PortEntries"}
        np.testing.assert_allclose(event_sources["PortEntries"].timestamps, [0.5, 1.5, 2.5])

    def test_table_with_a_value_column_splits_on_it(self):
        nwbfile = mock_NWBFile()
        table = EventsTable(name="BehavioralEvents", description="Merged events.")
        table.add_column(name="event_type", description="Which event each row is.")
        for timestamp, event_type in ((0.5, "reward"), (1.0, "port_entry"), (1.5, "reward")):
            table.add_row(timestamp=timestamp, event_type=event_type)
        nwbfile.add_events_table(table)

        event_sources = _event_sources(nwbfile)
        assert set(event_sources) == {"BehavioralEvents_reward", "BehavioralEvents_port_entry"}
        np.testing.assert_allclose(event_sources["BehavioralEvents_reward"].timestamps, [0.5, 1.5])
        np.testing.assert_allclose(event_sources["BehavioralEvents_port_entry"].timestamps, [1.0])

    def test_table_with_several_value_columns_is_refused(self):
        nwbfile = mock_NWBFile()
        table = EventsTable(name="BehavioralEvents", description="Merged events.")
        table.add_column(name="event_type", description="Which event each row is.")
        table.add_column(name="strobe", description="The raw strobe code.")
        table.add_row(timestamp=0.5, event_type="reward", strobe=1)
        nwbfile.add_events_table(table)

        with pytest.raises(NotImplementedError, match="multiple value columns"):
            _event_sources(nwbfile)

    def test_ndx_events_v02_objects_are_read(self):
        """A v0.2 source needs no special handling: only timestamps cross into the merged table.

        Note this exercises the hand-written ``ndx_events`` classes. pynwb's type map is
        process-global, so the spec-generated classes (whose labels live on ``data__labels``) can only
        be reached in a process that never imports ``ndx_events``, and are not covered here.
        """
        ndx_events = pytest.importorskip("ndx_events")

        nwbfile = mock_NWBFile()
        nwbfile.add_acquisition(ndx_events.Events(name="Ttls", description="TTL pulses.", timestamps=[0.25, 0.75]))
        nwbfile.add_acquisition(
            ndx_events.LabeledEvents(
                name="Trials",
                description="Labeled trial events.",
                timestamps=[1.0, 2.0, 3.0],
                data=[0, 1, 0],
                labels=["go", "no_go"],
            )
        )

        event_sources = _event_sources(nwbfile)
        assert set(event_sources) == {"Ttls", "Trials_go", "Trials_no_go"}
        np.testing.assert_allclose(event_sources["Ttls"].timestamps, [0.25, 0.75])
        np.testing.assert_allclose(event_sources["Trials_go"].timestamps, [1.0, 3.0])
        np.testing.assert_allclose(event_sources["Trials_no_go"].timestamps, [2.0])
