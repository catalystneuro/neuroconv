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

    def test_map_electrode_indices(self):

        self.data_interface.create_nwbfile()


class TestRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = MockRecordingInterface
    interface_kwargs = dict(durations=[0.100])


class TestRecordingInterfaceOld(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.single_segment_recording_interface = MockRecordingInterface(durations=[0.100])
        cls.multi_segment_recording_interface = MockRecordingInterface(durations=[0.100, 0.100])

    def test_stub_single_segment(self):
        interface = self.single_segment_recording_interface
        metadata = interface.get_metadata()
        interface.create_nwbfile(stub_test=True, metadata=metadata)

    def test_stub_multi_segment(self):
        interface = self.multi_segment_recording_interface
        metadata = interface.get_metadata()
        interface.create_nwbfile(stub_test=True, metadata=metadata)

    def test_no_slash_in_name(self):
        interface = self.single_segment_recording_interface
        metadata = interface.get_metadata()
        metadata["Ecephys"]["ElectricalSeries"]["name"] = "test/slash"
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            interface.validate_metadata(metadata)


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


class TestSortingInterface:

    def test_run_conversion(self, tmp_path):

        nwbfile_path = Path(tmp_path) / "test_sorting.nwb"
        num_units = 4
        interface = MockSortingInterface(num_units=num_units, durations=(1.0,))
        interface.sorting_extractor = interface.sorting_extractor.rename_units(new_unit_ids=["a", "b", "c", "d"])

        interface.run_conversion(nwbfile_path=nwbfile_path)
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            units = nwbfile.units
            assert len(units) == num_units
            units_df = units.to_dataframe()
            # Get index in units table
            for unit_id in interface.sorting_extractor.unit_ids:
                # In pynwb we write unit name as unit_id
                row = units_df.query(f"unit_name == '{unit_id}'")
                spike_times = interface.sorting_extractor.get_unit_spike_train(unit_id=unit_id, return_times=True)
                written_spike_times = row["spike_times"].iloc[0]

                np.testing.assert_array_equal(spike_times, written_spike_times)


class TestSortingInterfaceOld(unittest.TestCase):
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

    def test_sorting_propagate_conversion_options(self):
        minimal_nwbfile = self.test_dir / "temp2.nwb"
        metadata = self.test_sorting_interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        units_description = "The processed units."
        conversion_options = dict(
            TestSortingInterface=dict(
                write_as="processing",
                units_name="processed_units",
                units_description=units_description,
            )
        )
        self.test_sorting_interface.run_conversion(
            nwbfile_path=minimal_nwbfile,
            metadata=metadata,
            conversion_options=conversion_options,
        )

        with NWBHDF5IO(minimal_nwbfile, "r") as io:
            nwbfile = io.read()
            ecephys = get_module(nwbfile, "ecephys")
            self.assertIsNone(nwbfile.units)
            self.assertIn("processed_units", ecephys.data_interfaces)
            self.assertEqual(ecephys["processed_units"].description, units_description)
