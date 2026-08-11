"""Tests for the Doric seam of ``GuppyConverter``.

Only what is specific to ``acquisition_format="doric"``. Everything format-independent -- role grouping,
fiber-region linking, event merging, the registries -- is asserted once in ``test_reference_session``.

Doric is the one format whose GuPPy store ids are not the interface's stream names, so the seam is a
translation step and each layout resolves it differently: the two ``.doric`` HDF5 layouts name a store
by the tail of its internal path, while a DoricStudio ``.csv`` export names it by column and needs no
translation. Each layout therefore gets its own class.

Most assertions here stop at the constructed interface rather than running a conversion, since the
translation is settled at construction.

Each class stages its one acquisition file into ``tmp_path``, because the shared GIN folder holds all
four Doric files and a GuPPy session folder must hold exactly one.
"""

import shutil
from pathlib import Path

import h5py
import numpy as np
import pandas
import pytest
from pynwb import NWBHDF5IO

from neuroconv.converters import GuppyConverter
from neuroconv.datainterfaces.fiber_photometry.guppy.doric_utils import (
    doric_store_id_to_stream_name,
    resolve_doric_file,
)
from neuroconv.tools.testing import generate_mock_guppy_output_folder
from neuroconv.utils import dict_deep_update

from ._metadata import (
    build_device_metadata,
    build_fiber_photometry_metadata,
    build_series_metadata,
)
from ...setup_paths import OPHYS_DATA_PATH

DORIC_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "doric"
# Only the modern layout carries its own clock origin, so the metadata fixture supplies one for every
# layout; the test that reads the file's own value goes to ``converter.get_metadata()`` directly.
FALLBACK_SESSION_START_TIME = "2024-01-01T00:00:00+00:00"


def read_doric_hdf5_stream(file_path, data_path):
    """Read one dataset out of a ``.doric`` file, independently of the interface under test."""
    with h5py.File(file_path, "r") as file:
        return np.asarray(file[data_path][:])


def digital_line_rising_edges(file_path, group_path, line_name):
    """The times a digital line goes low-to-high, which is what its events become."""
    line = read_doric_hdf5_stream(file_path, f"{group_path}/{line_name}")
    times = read_doric_hdf5_stream(file_path, f"{group_path}/Time")
    rising = np.flatnonzero((line[1:] > 0) & (line[:-1] == 0)) + 1
    return times[rising].tolist()


class DoricConverterTestMixin:
    """Shared assertions; each subclass supplies one layout's fixtures and expectations.

    Subclasses define ``ACQUISITION_FILE_NAME``, ``RECORDING_SITE_TO_STORES``, ``EVENT_STORE_TO_NAME``
    and a ``read_expected_store_data`` staticmethod that reads a store's samples straight from the
    source file, so the resolved stream is compared against the file rather than against the interface.
    """

    @pytest.fixture
    def acquisition_folder(self, tmp_path):
        folder_path = tmp_path / "session"
        folder_path.mkdir()
        shutil.copy(DORIC_FOLDER / self.ACQUISITION_FILE_NAME, folder_path / self.ACQUISITION_FILE_NAME)
        return folder_path

    @pytest.fixture
    def event_onsets(self, acquisition_folder):
        """Onsets for the mock to record as GuPPy's, defaulting to the generator's own.

        Only a layout whose tests convert needs real ones -- the converter matches them against the
        events table it builds from the acquisition file.
        """
        return None

    @pytest.fixture
    def guppy_output_folder(self, tmp_path, event_onsets):
        return generate_mock_guppy_output_folder(
            tmp_path / "session_output_1",
            recording_site_to_stores=self.RECORDING_SITE_TO_STORES,
            event_store_to_name=self.EVENT_STORE_TO_NAME,
            cross_correlation_pairs=(),
            event_onsets=event_onsets,
        )

    @pytest.fixture
    def converter(self, acquisition_folder, guppy_output_folder):
        return GuppyConverter(
            fiber_photometry_folder_path=acquisition_folder,
            events_folder_path=acquisition_folder,
            guppy_folder_path=guppy_output_folder,
            acquisition_format="doric",
        )

    @pytest.fixture
    def metadata(self, converter):
        recording_sites = list(self.RECORDING_SITE_TO_STORES)
        metadata = converter.get_metadata()
        metadata = dict_deep_update(metadata, build_device_metadata(recording_sites))
        metadata["FiberPhotometry"] = dict_deep_update(
            metadata["FiberPhotometry"], build_fiber_photometry_metadata(recording_sites)
        )
        metadata["FiberPhotometry"] = dict_deep_update(
            metadata["FiberPhotometry"], build_series_metadata(recording_sites)
        )
        metadata["NWBFile"].setdefault("session_start_time", FALLBACK_SESSION_START_TIME)
        return metadata

    def test_store_ids_translate_to_stream_names(self, acquisition_folder):
        """Every store GuPPy listed resolves to a stream the Doric interface knows."""
        mapping = doric_store_id_to_stream_name(acquisition_folder / self.ACQUISITION_FILE_NAME)
        for stores in self.RECORDING_SITE_TO_STORES.values():
            for store_id in stores.values():
                assert store_id in mapping
        for store_id in self.EVENT_STORE_TO_NAME:
            assert store_id in mapping

    def test_resolved_streams_hold_the_stores_samples(self, converter, acquisition_folder):
        """Each store id resolves to the stream actually holding that store's samples."""
        source_path = acquisition_folder / self.ACQUISITION_FILE_NAME
        for role in ("signal", "control"):
            interface = converter.data_interface_objects[f"FiberPhotometry_{role}"]
            stream_names = interface.source_data["stream_names"]
            store_ids = [stores[role] for stores in self.RECORDING_SITE_TO_STORES.values()]
            assert len(stream_names) == len(store_ids)
            for stream_name, store_id in zip(stream_names, store_ids):
                expected = self.read_expected_store_data(source_path, store_id)
                np.testing.assert_array_equal(interface._get_stream_data(stream_name=stream_name), expected)


class TestGuppyConverterDoricModernHDF5(DoricConverterTestMixin):
    """Modern ``DataAcquisition`` layout: three ROIs across two excitation groups, plus digital lines.

    The richest of the three -- it is the only Doric fixture exercising multi-site role grouping, and
    each excitation group carries its own ``Time`` so both stacked series stay on one clock. Its two
    digital lines also cover both cases: ``Camera1`` toggles, ``DigitalCh1`` is held high throughout.
    """

    ACQUISITION_FILE_NAME = "BBC300_Acq_0093_stub.doric"
    RECORDING_SITE_TO_STORES = {
        "roi01": {"signal": "CAM1EXC1/ROI01", "control": "CAM1EXC2/ROI01"},
        "roi02": {"signal": "CAM1EXC1/ROI02", "control": "CAM1EXC2/ROI02"},
        "roi03": {"signal": "CAM1EXC1/ROI03", "control": "CAM1EXC2/ROI03"},
    }
    EVENT_STORE_TO_NAME = {"DigitalIO/Camera1": "camera_frames", "DigitalIO/DigitalCh1": "port_entries"}
    EXPECTED_EVENT_TABLE_TO_COUNT = {"CameraFrames": 6, "PortEntries": 0}
    DIGITAL_IO_GROUP = "DataAcquisition/BBC300/Signals/Series0001/DigitalIO"

    @staticmethod
    def read_expected_store_data(file_path, store_id):
        group, dataset = store_id.split("/")
        prefix = "ROISignals/Series0001" if group.startswith("CAM1EXC") else "Signals/Series0001"
        return read_doric_hdf5_stream(file_path, f"DataAcquisition/BBC300/{prefix}/{group}/{dataset}")

    @pytest.fixture
    def event_onsets(self, acquisition_folder):
        """This layout converts, so the mock records the lines' real rising edges as GuPPy's onsets."""
        file_path = acquisition_folder / self.ACQUISITION_FILE_NAME
        return {
            event_name: digital_line_rising_edges(file_path, self.DIGITAL_IO_GROUP, store_id.split("/")[-1])
            for store_id, event_name in self.EVENT_STORE_TO_NAME.items()
        }

    def test_session_start_time_comes_from_the_doric_file(self, converter):
        """The modern layout carries a ``Created`` attribute, so the acquisition wins the metadata merge."""
        session_start_time = converter.get_metadata()["NWBFile"]["session_start_time"]
        assert str(session_start_time).startswith("2024-06-24 13:58:38")

    def test_a_line_that_never_toggles_still_earns_an_event_type(self, converter, metadata, tmp_path):
        """``DigitalCh1`` is high throughout, contributing zero occurrences but keeping its own table.

        The Doric events interfaces keep an event type with no occurrences; the TDT and CSV ones drop it.
        """
        nwbfile_path = tmp_path / "doric_events.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True)

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            counts = {
                table_name: len(nwbfile.get_events_table(table_name))
                for table_name in self.EXPECTED_EVENT_TABLE_TO_COUNT
            }
            assert counts == self.EXPECTED_EVENT_TABLE_TO_COUNT

            registry = nwbfile.processing["guppy"]["events"]
            registry_names = {str(registry["event_name"][row]) for row in range(len(registry.id))}
            assert registry_names == set(self.EVENT_STORE_TO_NAME.values())


class TestGuppyConverterDoricLegacyHDF5(DoricConverterTestMixin):
    """Legacy ``Traces`` layout: GuPPy names a store by its group alone, with no console prefix.

    This fixture's storesList lists no event store, which also makes it the case that covers a session
    with nothing behavioral in it -- the converter must then build no events interface at all.
    """

    ACQUISITION_FILE_NAME = "D2-EPConsole_0039_stub.doric"
    RECORDING_SITE_TO_STORES = {"region": {"signal": "AIn-1 - Raw", "control": "AIn-2 - Raw"}}
    EVENT_STORE_TO_NAME = {}

    @staticmethod
    def read_expected_store_data(file_path, store_id):
        return read_doric_hdf5_stream(file_path, f"Traces/Console/{store_id}/{store_id}")

    def test_no_session_start_time_without_a_created_attribute(self, converter):
        """The legacy layout carries no clock origin, and no GuPPy output supplies one either."""
        assert "session_start_time" not in converter.get_metadata()["NWBFile"]

    def test_no_event_stores_builds_no_events_interface(self, converter, metadata, tmp_path):
        """A storesList with only signal/control stores yields no events interface and no events table.

        The GuPPy events registry is still written, with no rows.
        """
        assert converter._events_interface_names == []
        assert not any(name.startswith("Events") for name in converter.data_interface_objects)

        nwbfile_path = tmp_path / "doric_no_events.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True)
        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            assert not nwbfile.events
            assert len(nwbfile.processing["guppy"]["events"].id) == 0


class TestGuppyConverterDoricCSV(DoricConverterTestMixin):
    """DoricStudio CSV export: store ids are column names and need no translation."""

    ACQUISITION_FILE_NAME = "12282020-cfc-pppda7_0000.csv"
    RECORDING_SITE_TO_STORES = {"region": {"signal": "Raw", "control": "AIn-1 - Dem (ref)"}}
    EVENT_STORE_TO_NAME = {"DI/O-1": "ttl"}

    @staticmethod
    def read_expected_store_data(file_path, store_id):
        # The real header is the second line; the first is a device/channel grouping row.
        return pandas.read_csv(file_path, header=1, usecols=[store_id])[store_id].to_numpy()


class TestDoricStoreIdTranslation:
    """Unit tests for the translation paths the three end-to-end fixtures do not reach."""

    def test_values_leaf_is_skipped(self, tmp_path):
        """A V6 lock-in stream stores its samples under a ``Values`` leaf, which GuPPy's id omits."""
        file_path = tmp_path / "lock_in.doric"
        with h5py.File(file_path, "w") as file:
            group = file.create_group("DataAcquisition/FPConsole/Signals/Series0001/AIN01xAOUT01-LockIn")
            group.create_dataset("Values", data=np.arange(4, dtype=float))
            group.create_dataset("Time", data=np.arange(4, dtype=float))

        mapping = doric_store_id_to_stream_name(file_path)
        assert "Series0001/AIN01xAOUT01-LockIn" in mapping

    def test_colliding_store_ids_raise(self, tmp_path):
        """Two series whose tails match cannot be told apart from a storesList entry."""
        file_path = tmp_path / "two_series.doric"
        with h5py.File(file_path, "w") as file:
            for series in ("Series0001", "Series0002"):
                group = file.create_group(f"DataAcquisition/FPConsole/Signals/{series}/AnalogIn")
                group.create_dataset("AIN01", data=np.arange(4, dtype=float))
                group.create_dataset("Time", data=np.arange(4, dtype=float))

        with pytest.raises(AssertionError, match="GuPPy would name identically"):
            doric_store_id_to_stream_name(file_path)

    def test_unknown_store_raises_naming_it(self, tmp_path):
        """A storesList store absent from the file fails loudly rather than as a later KeyError."""
        guppy_output_folder = generate_mock_guppy_output_folder(
            tmp_path / "session_output_1",
            recording_site_to_stores={"region": {"signal": "not_a_stream", "control": "AIn-2 - Raw"}},
            event_store_to_name={"DI--O-1": "ttl"},
            cross_correlation_pairs=(),
        )
        acquisition_folder = tmp_path / "session"
        acquisition_folder.mkdir()
        shutil.copy(DORIC_FOLDER / "D2-EPConsole_0039_stub.doric", acquisition_folder / "D2-EPConsole_0039_stub.doric")

        with pytest.raises(AssertionError, match="not_a_stream"):
            GuppyConverter(
                fiber_photometry_folder_path=acquisition_folder,
                events_folder_path=acquisition_folder,
                guppy_folder_path=guppy_output_folder,
                acquisition_format="doric",
            )

    def test_multiple_doric_files_raise(self, tmp_path):
        """A GuPPy Doric session folder holds exactly one acquisition file."""
        acquisition_folder = tmp_path / "session"
        acquisition_folder.mkdir()
        for name in ("D2-EPConsole_0039_stub.doric", "BBC300_Acq_0093_stub.doric"):
            shutil.copy(DORIC_FOLDER / name, acquisition_folder / name)

        with pytest.raises(AssertionError, match="Expected exactly one Doric acquisition file"):
            resolve_doric_file(Path(acquisition_folder))
