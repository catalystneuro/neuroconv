import shutil
import unittest
from datetime import datetime
from pathlib import Path
from platform import python_version as get_python_version
from tempfile import mkdtemp
from warnings import warn

import jsonschema
import numpy as np
import pytest
from hdmf.testing import TestCase
from packaging.version import Version
from pynwb import NWBHDF5IO
from spikeinterface.extractors import NumpySorting

from neuroconv import NWBConverter
from neuroconv.datainterfaces import Spike2RecordingInterface
from neuroconv.datainterfaces.ecephys.basesortingextractorinterface import (
    BaseSortingExtractorInterface,
)
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.tools.testing.mock_interfaces import (
    MockRecordingInterface,
    MockSortingInterface,
)

python_version = Version(get_python_version())

from neuroconv.tools.testing.data_interface_mixins import (
    RecordingExtractorInterfaceTestMixin,
    SortingExtractorInterfaceTestMixin,
)


class TestSortingInterface(SortingExtractorInterfaceTestMixin):

    data_interface_cls = MockSortingInterface
    interface_kwargs = dict(num_units=4, durations=[0.100])

    def test_propagate_conversion_options(self, setup_interface):
        interface = self.interface
        metadata = interface.get_metadata()
        nwbfile = interface.create_nwbfile(
            stub_test=True,
            metadata=metadata,
            write_as="processing",
            units_name="processed_units",
            units_description="The processed units.",
        )

        ecephys = get_module(nwbfile, "ecephys")

        assert nwbfile.units is None
        assert "processed_units" in ecephys.data_interfaces

    def test_electrode_indices(self, setup_interface):

        recording_interface = MockRecordingInterface(num_channels=4, durations=[0.100])
        recording_extractor = recording_interface.recording_extractor
        recording_extractor = recording_extractor.rename_channels(new_channel_ids=["a", "b", "c", "d"])
        recording_extractor.set_property(key="property", values=["A", "B", "C", "D"])
        recording_interface.recording_extractor = recording_extractor

        nwbfile = recording_interface.create_nwbfile()

        unit_electrode_indices = [[3], [0, 1], [1], [2]]
        expected_properties_matching = [["D"], ["A", "B"], ["B"], ["C"]]
        self.interface.add_to_nwbfile(nwbfile=nwbfile, unit_electrode_indices=unit_electrode_indices)

        unit_table = nwbfile.units

        for unit_row, electrode_indices, property in zip(
            unit_table.to_dataframe().itertuples(index=False),
            unit_electrode_indices,
            expected_properties_matching,
        ):
            electrode_table_region = unit_row.electrodes
            electrode_table_region_indices = electrode_table_region.index.to_list()
            assert electrode_table_region_indices == electrode_indices

            electrode_table_region_properties = electrode_table_region["property"].to_list()
            assert electrode_table_region_properties == property

    def test_electrode_indices_assertion_error_when_missing_table(self, setup_interface):
        with pytest.raises(
            ValueError,
            match="Electrodes table is required to map units to electrodes. Add an electrode table to the NWBFile first.",
        ):
            self.interface.create_nwbfile(unit_electrode_indices=[[0], [1], [2], [3]])


class TestRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = MockRecordingInterface
    interface_kwargs = dict(durations=[0.100])

    def test_stub(self, setup_interface):
        interface = self.interface
        metadata = interface.get_metadata()
        interface.create_nwbfile(stub_test=True, metadata=metadata)

    def test_no_slash_in_name(self, setup_interface):
        interface = self.interface
        metadata = interface.get_metadata()
        metadata["Ecephys"]["ElectricalSeries"]["name"] = "test/slash"
        with pytest.raises(jsonschema.exceptions.ValidationError):
            interface.validate_metadata(metadata)

    def test_stub_multi_segment(self):

        interface = MockRecordingInterface(durations=[0.100, 0.100])
        metadata = interface.get_metadata()
        interface.create_nwbfile(stub_test=True, metadata=metadata)

    def test_always_write_timestamps(self, setup_interface):

        nwbfile = self.interface.create_nwbfile(always_write_timestamps=True)
        electrical_series = nwbfile.acquisition["ElectricalSeries"]
        expected_timestamps = self.interface.recording_extractor.get_times()
        np.testing.assert_array_equal(electrical_series.timestamps[:], expected_timestamps)


class TestAssertions(TestCase):
    @pytest.mark.skipif(python_version.minor != 10, reason="Only testing with Python 3.10!")
    def test_spike2_import_assertions_3_10(self):
        with self.assertRaisesWith(
            exc_type=ModuleNotFoundError,
            exc_msg="\nThe package 'sonpy' is not available for Python version 3.10!",
        ):
            Spike2RecordingInterface.get_all_channels_info(file_path="does_not_matter.smrx")

    @pytest.mark.skipif(python_version.minor != 11, reason="Only testing with Python 3.11!")
    def test_spike2_import_assertions_3_11(self):
        with self.assertRaisesWith(
            exc_type=ModuleNotFoundError,
            exc_msg="\nThe package 'sonpy' is not available for Python version 3.11!",
        ):
            Spike2RecordingInterface.get_all_channels_info(file_path="does_not_matter.smrx")


class TestSortingInterfaceOld(unittest.TestCase):
    """Old-style tests for the SortingInterface. Remove once we we are sure all the behaviors are covered by the mock."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.test_dir = Path(mkdtemp())
        cls.sorting_start_frames = [100, 200, 300]
        cls.num_frames = 1000
        cls.sampling_frequency = 3000.0
        times = np.array([], dtype="int")
        labels = np.array([], dtype="int")
        for i, start_frame in enumerate(cls.sorting_start_frames):
            times_i = np.arange(start_frame, cls.num_frames, dtype="int")
            labels_i = (i + 1) * np.ones_like(times_i, dtype="int")
            times = np.concatenate((times, times_i))
            labels = np.concatenate((labels, labels_i))
        sorting = NumpySorting.from_times_labels(times, labels, sampling_frequency=cls.sampling_frequency)

        class TestSortingInterface(BaseSortingExtractorInterface):
            ExtractorName = "NumpySorting"

            def __init__(self, verbose: bool = True):
                self.sorting_extractor = sorting
                self.source_data = dict()
                self.verbose = verbose

        class TempConverter(NWBConverter):
            data_interface_classes = dict(TestSortingInterface=TestSortingInterface)

        source_data = dict(TestSortingInterface=dict())
        cls.test_sorting_interface = TempConverter(source_data)

    @classmethod
    def tearDownClass(cls):
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:  # Windows CI bug
            warn(f"Unable to fully clean the temporary directory: {cls.test_dir}\n\nPlease remove it manually.")

    def test_sorting_stub(self):
        minimal_nwbfile = self.test_dir / "stub_temp.nwb"
        conversion_options = dict(TestSortingInterface=dict(stub_test=True))
        metadata = self.test_sorting_interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        self.test_sorting_interface.run_conversion(
            nwbfile_path=minimal_nwbfile, metadata=metadata, conversion_options=conversion_options
        )
        with NWBHDF5IO(minimal_nwbfile, "r") as io:
            nwbfile = io.read()
            start_frame_max = np.max(self.sorting_start_frames)
            for i, start_times in enumerate(self.sorting_start_frames):
                assert len(nwbfile.units["spike_times"][i]) == (start_frame_max * 1.1) - start_times

    def test_sorting_stub_with_recording(self):
        subset_end_frame = int(np.max(self.sorting_start_frames) * 1.1 - 1)
        sorting_interface = self.test_sorting_interface.data_interface_objects["TestSortingInterface"]
        sorting_interface.sorting_extractor = sorting_interface.sorting_extractor.frame_slice(
            start_frame=0, end_frame=subset_end_frame
        )
        recording_interface = MockRecordingInterface(
            durations=[subset_end_frame / self.sampling_frequency],
            sampling_frequency=self.sampling_frequency,
        )
        sorting_interface.register_recording(recording_interface)

        minimal_nwbfile = self.test_dir / "stub_temp_recording.nwb"
        conversion_options = dict(TestSortingInterface=dict(stub_test=True))
        metadata = self.test_sorting_interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        self.test_sorting_interface.run_conversion(
            nwbfile_path=minimal_nwbfile, metadata=metadata, conversion_options=conversion_options
        )
        with NWBHDF5IO(minimal_nwbfile, "r") as io:
            nwbfile = io.read()
            for i, start_times in enumerate(self.sorting_start_frames):
                assert len(nwbfile.units["spike_times"][i]) == subset_end_frame - start_times

    def test_sorting_full(self):
        minimal_nwbfile = self.test_dir / "temp.nwb"
        metadata = self.test_sorting_interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        self.test_sorting_interface.run_conversion(nwbfile_path=minimal_nwbfile, metadata=metadata)
        with NWBHDF5IO(minimal_nwbfile, "r") as io:
            nwbfile = io.read()
            for i, start_times in enumerate(self.sorting_start_frames):
                assert len(nwbfile.units["spike_times"][i]) == self.num_frames - start_times
