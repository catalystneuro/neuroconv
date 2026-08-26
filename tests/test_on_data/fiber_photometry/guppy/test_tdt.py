"""Tests for the TDT seam of ``GuppyConverter``.

Only what is specific to ``acquisition_format="tdt"``. Everything format-independent -- role grouping,
fiber-region linking, event merging, the registries, the metadata schema -- is asserted once in
``test_reference_session``.

TDT is specific in three ways: it reads every epoc out of one tank, so a single events interface covers
them all; it is the only acquisition that supplies a session start time from its own clock; and its
interface writes a ``FiberPhotometry`` lab_meta_data object, which is what forces the GuPPy processing
module to be named something else.

The real data is the small (~1 MB) Photo_249 stubbed tank already shared with the TDT fiber photometry
and events interface tests. The mock GuPPy generator's default store and event names
(Dv1A/Dv2A/Dv3B/Dv4B, LNRW/LNnR/PrtR) are exactly the ones this tank exposes.
"""

from datetime import datetime, timezone

import numpy as np
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

SESSION_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "TDT" / "Photo_249_391-200721-120136_stubbed"

RECORDING_SITES = ["dms", "dls"]
EPOC_TO_EVENT_NAME = {"LNRW": "rewarded_nose_pokes", "LNnR": "unrewarded_nose_pokes", "PrtR": "port_entries"}
# The converter matches GuPPy's analyzed onsets against the events table it builds from the tank, so the
# mock has to be given real epoc onsets. Only a handful per event, because they also label every
# peri-event product's trial columns and LNnR alone fires 1457 times.
NUM_MOCK_TRIALS = 4
EXPECTED_TDT_SESSION_START_TIME = datetime(2020, 7, 21, 17, 2, 24, 999999, tzinfo=timezone.utc)
EXPECTED_ACQUISITION_INTERFACE_NAMES = {"FiberPhotometry_signal", "FiberPhotometry_control"}
# The mock GuPPy timebase is regular: 1.0 s of lights-on delay, then 200 Hz.
MOCK_GUPPY_STARTING_TIME = 1.0
MOCK_GUPPY_RATE = 200.0


class TestGuppyConverterTDT:
    @pytest.fixture(scope="class")
    @classmethod
    def epoc_onsets(cls):
        """The first few onsets of each epoc GuPPy listed, read straight from the tank."""
        import tdt

        block = tdt.read_block(str(SESSION_FOLDER), evtype=["epocs"])
        return {
            event_name: np.asarray(block.epocs[epoc_name].onset)[:NUM_MOCK_TRIALS].tolist()
            for epoc_name, event_name in EPOC_TO_EVENT_NAME.items()
        }

    @pytest.fixture(scope="class")
    @classmethod
    def guppy_output_folder(cls, tmp_path_factory, epoc_onsets):
        return generate_mock_guppy_output_folder(
            tmp_path_factory.mktemp("tdt_output") / "guppy_output", event_onsets=epoc_onsets
        )

    @pytest.fixture
    def converter(self, guppy_output_folder):
        return GuppyConverter(
            fiber_photometry_folder_path=SESSION_FOLDER,
            events_folder_path=SESSION_FOLDER,
            guppy_folder_path=guppy_output_folder,
            acquisition_format="tdt",
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

    def test_one_events_interface_covers_the_whole_tank(self, converter):
        """Every epoc lives in one tank, so TDT needs a single events interface."""
        assert set(converter.data_interface_objects) == EXPECTED_ACQUISITION_INTERFACE_NAMES | {"Events", "Guppy"}

    def test_session_start_time_taken_from_tdt(self, converter):
        """TDT is the only acquisition format carrying an absolute clock origin of its own."""
        metadata = converter.get_metadata()
        assert metadata["NWBFile"]["session_start_time"] == EXPECTED_TDT_SESSION_START_TIME.isoformat()

    def test_guppy_processing_module_avoids_the_tdt_name_collision(self, converter):
        """The GuPPy module is renamed away from the interface default of "fiber_photometry".

        The TDT acquisition interface writes a ``FiberPhotometry`` lab_meta_data object of that name,
        which no other acquisition format does.
        """
        metadata = converter.get_metadata()
        guppy_metadata_key = converter.data_interface_objects["Guppy"].metadata_key
        assert metadata["FiberPhotometry"]["Guppy"][guppy_metadata_key]["ProcessingModule"]["name"] == "guppy"

    def test_epoc_names_translate_to_the_names_guppy_gave_them(self, converter):
        """Only the storesList.csv behavioral event stores propagate, under GuPPy's semantic names."""
        events_interface = converter.data_interface_objects["Events"]
        event_types = converter.get_metadata()["Events"][events_interface.metadata_key]["event_types"]
        epoc_name_to_event_name = {epoc_name: entry["event_name"] for epoc_name, entry in event_types.items()}
        assert epoc_name_to_event_name == EPOC_TO_EVENT_NAME

    def test_guppy_timestamps_are_not_realigned_onto_the_tdt_clock(self, converter, metadata, tmp_path):
        """GuPPy traces keep their native timestamps -- no cross-system offset is applied.

        GuPPy and TDT already share a clock origin, so the first sample stays at the 1 s lights-on delay
        rather than being shoved to the stream start.
        """
        nwbfile_path = tmp_path / "tdt_guppy_alignment.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True)

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            processing_module = io.read().processing["guppy"]
            for recording_site in RECORDING_SITES:
                dff_series = processing_module.data_interfaces[f"dff_{recording_site}"]
                assert dff_series.timestamps is None
                assert float(dff_series.starting_time) == pytest.approx(MOCK_GUPPY_STARTING_TIME)
                assert float(dff_series.rate) == pytest.approx(MOCK_GUPPY_RATE)
