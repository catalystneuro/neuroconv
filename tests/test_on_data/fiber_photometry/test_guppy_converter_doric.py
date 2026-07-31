"""Tests for ``GuppyConverter(acquisition_format="doric")``.

Real Doric acquisition files from GIN paired with a mock GuPPy output, the same shape as the TDT
converter tests. Doric is the first format whose GuPPy store ids are not the interface's stream names,
so each layout gets its own class: the two ``.doric`` HDF5 layouts name a store by the tail of its
internal path, while a DoricStudio ``.csv`` export names it by column and needs no translation.

Each class stages its one acquisition file into ``tmp_path``, because the shared GIN folder holds all
four Doric files and a GuPPy session folder must hold exactly one.
"""

import shutil
from pathlib import Path

import numpy as np
import pandas
import pytest
from pynwb import NWBHDF5IO

from neuroconv.converters import GuppyConverter
from neuroconv.tools.testing import generate_mock_guppy_output_folder
from neuroconv.utils import dict_deep_update

from ._guppy_converter_metadata import (
    build_device_metadata,
    build_fiber_photometry_metadata,
    build_series_metadata,
)
from ..setup_paths import OPHYS_DATA_PATH

DORIC_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "doric"
MERGED_EVENTS_TABLE_NAME = "BehavioralEvents"
EXPECTED_RESPONSE_SERIES_NAMES = {
    "FiberPhotometryResponseSeriesSignal",
    "FiberPhotometryResponseSeriesControl",
}


def read_doric_hdf5_stream(file_path, data_path):
    """Read one dataset out of a ``.doric`` file, independently of the interface under test."""
    import h5py

    with h5py.File(file_path, "r") as file:
        return np.asarray(file[data_path][:])


class DoricConverterTestMixin:
    """Shared assertions; each subclass supplies one layout's fixtures and expectations.

    Subclasses define ``ACQUISITION_FILE_NAME``, ``RECORDING_SITE_TO_STORES``, ``EVENT_STORE_TO_NAME``
    and a ``read_expected_store_data`` staticmethod that reads a store's samples straight from the
    source file, so the written data is compared against the file rather than against the interface.
    """

    @pytest.fixture
    def acquisition_folder(self, tmp_path):
        folder_path = tmp_path / "session"
        folder_path.mkdir()
        shutil.copy(DORIC_FOLDER / self.ACQUISITION_FILE_NAME, folder_path / self.ACQUISITION_FILE_NAME)
        return folder_path

    @pytest.fixture
    def guppy_output_folder(self, tmp_path):
        return generate_mock_guppy_output_folder(
            tmp_path / "session_output_1",
            recording_site_to_stores=self.RECORDING_SITE_TO_STORES,
            event_store_to_name=self.EVENT_STORE_TO_NAME,
            cross_correlation_pairs=(),
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
        return metadata

    def test_store_ids_translate_to_stream_names(self, converter, acquisition_folder):
        """Every store GuPPy listed resolves to a stream the Doric interface knows."""
        mapping = converter._doric_store_id_to_stream_name(acquisition_folder / self.ACQUISITION_FILE_NAME)
        for stores in self.RECORDING_SITE_TO_STORES.values():
            for store_id in stores.values():
                assert store_id in mapping
        for store_id in self.EVENT_STORE_TO_NAME:
            assert store_id in mapping

    def test_run_conversion_writes_role_grouped_acquisition(self, converter, metadata, tmp_path):
        """Two series, one per role, each column-stacking that role's store from every recording site."""
        nwbfile_path = tmp_path / "doric.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True)
        source_path = tmp_path / "session" / self.ACQUISITION_FILE_NAME

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            assert EXPECTED_RESPONSE_SERIES_NAMES == set(nwbfile.acquisition)

            for role, series_name in [
                ("signal", "FiberPhotometryResponseSeriesSignal"),
                ("control", "FiberPhotometryResponseSeriesControl"),
            ]:
                series = nwbfile.acquisition[series_name]
                store_ids = [stores[role] for stores in self.RECORDING_SITE_TO_STORES.values()]
                data = np.asarray(series.data)
                if data.ndim == 1:  # a single recording site is squeezed to one dimension
                    data = data[:, np.newaxis]
                assert data.shape[1] == len(store_ids)
                for column, store_id in enumerate(store_ids):
                    expected = self.read_expected_store_data(source_path, store_id)
                    np.testing.assert_array_equal(data[:, column], expected)

    def test_run_conversion_links_recording_sites_to_their_own_fibers(self, converter, metadata, tmp_path):
        """Each GuPPy recording site's registry row points at that site's own acquisition rows."""
        nwbfile_path = tmp_path / "doric_registry.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True)

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            recording_sites_table = nwbfile.processing["guppy"]["recording_sites"]
            for row in range(len(recording_sites_table.id)):
                recording_site = str(recording_sites_table["recording_site"][row])
                linked = recording_sites_table["fiber_photometry_table_region"][row]
                assert set(linked["location"]) == {recording_site.upper()}
                assert sorted(linked["excitation_wavelength_in_nm"]) == [405.0, 465.0]


class DoricEventsTestMixin:
    """Events assertions, for the layouts whose fixture has a digital line that actually toggles.

    ``EXPECTED_EVENT_NAME_TO_COUNT`` gives the occurrences each GuPPy event name should contribute.
    A line that never toggles legitimately contributes zero: unlike TDT and CSV, the Doric interfaces
    keep a zero-occurrence event type rather than dropping it, so it still earns a registry row.
    """

    def test_run_conversion_merges_events_named_as_guppy_named_them(self, converter, metadata, tmp_path):
        """Digital lines land in one BehavioralEvents table under GuPPy's semantic names."""
        nwbfile_path = tmp_path / "doric_events.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True)

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            assert set(nwbfile.events) == {MERGED_EVENTS_TABLE_NAME}
            events_dataframe = nwbfile.events[MERGED_EVENTS_TABLE_NAME].to_dataframe()
            counts = {
                name: int((events_dataframe.event_type == name).sum()) for name in self.EVENT_STORE_TO_NAME.values()
            }
            assert counts == self.EXPECTED_EVENT_NAME_TO_COUNT

            # Every event GuPPy listed earns a registry row, including one that never fired.
            registry = nwbfile.processing["guppy"]["events"]
            registry_names = {str(registry["event_name"][row]) for row in range(len(registry.id))}
            assert registry_names == set(self.EVENT_STORE_TO_NAME.values())


class TestGuppyConverterDoricModernHDF5(DoricConverterTestMixin, DoricEventsTestMixin):
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
    EXPECTED_EVENT_NAME_TO_COUNT = {"camera_frames": 6, "port_entries": 0}

    @staticmethod
    def read_expected_store_data(file_path, store_id):
        group, dataset = store_id.split("/")
        prefix = "ROISignals/Series0001" if group.startswith("CAM1EXC") else "Signals/Series0001"
        return read_doric_hdf5_stream(file_path, f"DataAcquisition/BBC300/{prefix}/{group}/{dataset}")

    def test_session_start_time_comes_from_the_doric_file(self, converter):
        """The modern layout carries a ``Created`` attribute, so the acquisition wins the metadata merge."""
        session_start_time = converter.get_metadata()["NWBFile"]["session_start_time"]
        assert str(session_start_time).startswith("2024-06-24 13:58:38")


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

    def test_session_start_time_falls_back_to_guppy(self, converter):
        """The legacy layout has no ``Created`` attribute, so GuPPy's value stands."""
        session_start_time = converter.get_metadata()["NWBFile"]["session_start_time"]
        assert str(session_start_time).startswith("2018-10-30")

    def test_no_event_stores_builds_no_events_interface(self, converter, metadata, tmp_path):
        """A storesList with only signal/control stores yields no events interface and no events table."""
        assert converter._events_interface_names == []
        assert not any(name.startswith("Events") for name in converter.data_interface_objects)

        nwbfile_path = tmp_path / "doric_no_events.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True)
        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            assert not nwbfile.events
            # The GuPPy interface still writes its own link-free events registry, with no rows.
            assert len(nwbfile.processing["guppy"]["events"].id) == 0


class TestGuppyConverterDoricCSV(DoricConverterTestMixin, DoricEventsTestMixin):
    """DoricStudio CSV export: store ids are column names and need no translation."""

    ACQUISITION_FILE_NAME = "12282020-cfc-pppda7_0000.csv"
    RECORDING_SITE_TO_STORES = {"region": {"signal": "Raw", "control": "AIn-1 - Dem (ref)"}}
    EVENT_STORE_TO_NAME = {"DI/O-1": "ttl"}
    EXPECTED_EVENT_NAME_TO_COUNT = {"ttl": 5}

    @staticmethod
    def read_expected_store_data(file_path, store_id):
        # The real header is the second line; the first is a device/channel grouping row.
        return pandas.read_csv(file_path, header=1, usecols=[store_id])[store_id].to_numpy()


class TestDoricStoreIdTranslation:
    """Unit tests for the paths the three end-to-end fixtures do not reach."""

    def test_values_leaf_is_skipped(self, tmp_path):
        """A V6 lock-in stream stores its samples under a ``Values`` leaf, which GuPPy's id omits."""
        import h5py

        file_path = tmp_path / "lock_in.doric"
        with h5py.File(file_path, "w") as file:
            group = file.create_group("DataAcquisition/FPConsole/Signals/Series0001/AIN01xAOUT01-LockIn")
            group.create_dataset("Values", data=np.arange(4, dtype=float))
            group.create_dataset("Time", data=np.arange(4, dtype=float))

        mapping = GuppyConverter._doric_store_id_to_stream_name(file_path)
        assert "Series0001/AIN01xAOUT01-LockIn" in mapping

    def test_colliding_store_ids_raise(self, tmp_path):
        """Two series whose tails match cannot be told apart from a storesList entry."""
        import h5py

        file_path = tmp_path / "two_series.doric"
        with h5py.File(file_path, "w") as file:
            for series in ("Series0001", "Series0002"):
                group = file.create_group(f"DataAcquisition/FPConsole/Signals/{series}/AnalogIn")
                group.create_dataset("AIN01", data=np.arange(4, dtype=float))
                group.create_dataset("Time", data=np.arange(4, dtype=float))

        with pytest.raises(AssertionError, match="GuPPy would name identically"):
            GuppyConverter._doric_store_id_to_stream_name(file_path)

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
            GuppyConverter._resolve_doric_file(Path(acquisition_folder))
