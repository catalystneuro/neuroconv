import unittest
from datetime import datetime
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import numpy as np
from pynwb import NWBFile

from neuroconv import (
    BaseDataInterface,
    BaseTemporalAlignmentInterface,
    ConverterPipe,
    NWBConverter,
)

try:
    from ndx_events import LabeledEvents

    HAVE_NDX_EVENTS = True
except ImportError:
    HAVE_NDX_EVENTS = False


def test_converter():
    if HAVE_NDX_EVENTS:
        test_dir = Path(mkdtemp())
        nwbfile_path = str(test_dir / "extension_test.nwb")

        class NdxEventsInterface(BaseTemporalAlignmentInterface):
            def __init__(self, verbose: bool = False):
                self._timestamps = np.array([0.0, 0.5, 0.6, 2.0, 2.05, 3.0, 3.5, 3.6, 4.0])
                self._original_timestamps = np.array(self._timestamps)

            def get_original_timestamps(self) -> np.ndarray:
                return self._original_timestamps

            def get_timestamps(self) -> np.ndarray:
                return self._timestamps

            def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
                self._timestamps = aligned_timestamps

            def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict):
                events = LabeledEvents(
                    name="LabeledEvents",
                    description="events from my experiment",
                    timestamps=self.get_timestamps(),
                    resolution=1e-5,
                    data=[0, 1, 2, 3, 5, 0, 1, 2, 4],
                    labels=["trial_start", "cue_onset", "cue_offset", "response_left", "response_right", "reward"],
                )
                nwbfile.add_acquisition(events)

        class ExtensionTestNWBConverter(NWBConverter):
            data_interface_classes = dict(NdxEvents=NdxEventsInterface)

        converter = ExtensionTestNWBConverter(source_data=dict(NdxEvents=dict()))
        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        rmtree(test_dir)


class TestNWBConverterAndPipeInitialization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class InterfaceA(BaseTemporalAlignmentInterface):
            def __init__(self, **source_data):
                super().__init__(**source_data)

            def get_original_timestamps(self):
                pass

            def get_timestamps(self):
                pass

            def set_aligned_timestamps(self):
                pass

            def add_to_nwbfile(self):
                pass

        cls.InterfaceA = InterfaceA

        class InterfaceB(BaseDataInterface):
            def __init__(self, **source_data):
                super().__init__(**source_data)

            def add_to_nwbfile(self):
                pass

        cls.InterfaceB = InterfaceB

    def test_child_class_source_data_init(self):
        class NWBConverterChild(NWBConverter):
            data_interface_classes = dict(InterfaceA=self.InterfaceA, InterfaceB=self.InterfaceB)

        source_data = dict(InterfaceA=dict(), InterfaceB=dict())
        converter = NWBConverterChild(source_data)

        data_interface_names = converter.data_interface_classes.keys()
        assert ["InterfaceA", "InterfaceB"] == list(data_interface_names)

        assert converter.data_interface_classes["InterfaceA"] is self.InterfaceA
        assert converter.data_interface_classes["InterfaceB"] is self.InterfaceB

    def test_pipe_list_init(self):
        interface_a = self.InterfaceA()
        interface_b = self.InterfaceB()
        data_interfaces_list = [interface_a, interface_b]
        converter = ConverterPipe(data_interfaces=data_interfaces_list)

        data_interface_names = converter.data_interface_classes.keys()
        assert ["InterfaceA", "InterfaceB"] == list(data_interface_names)

        assert converter.data_interface_classes["InterfaceA"] is self.InterfaceA
        assert converter.data_interface_classes["InterfaceB"] is self.InterfaceB

        assert converter.data_interface_objects["InterfaceA"] is interface_a
        assert converter.data_interface_objects["InterfaceB"] is interface_b

    def test_pipe_list_dict(self):
        interface_a = self.InterfaceA()
        interface_b = self.InterfaceB()
        data_interfaces_dict = dict(InterfaceA=interface_a, InterfaceB=interface_b)
        converter = ConverterPipe(data_interfaces=data_interfaces_dict)

        data_interface_names = converter.data_interface_classes.keys()
        assert ["InterfaceA", "InterfaceB"] == list(data_interface_names)

        assert converter.data_interface_classes["InterfaceA"] is self.InterfaceA
        assert converter.data_interface_classes["InterfaceB"] is self.InterfaceB

        assert converter.data_interface_objects["InterfaceA"] is interface_a
        assert converter.data_interface_objects["InterfaceB"] is interface_b

    def test_consistent_init_pipe_vs_nwb(self):
        class NWBConverterChild(NWBConverter):
            data_interface_classes = dict(InterfaceA=self.InterfaceA, InterfaceB=self.InterfaceB)

        source_data = dict(InterfaceA=dict(), InterfaceB=dict())
        converter_child_class = NWBConverterChild(source_data)

        interface_a = self.InterfaceA()
        interface_b = self.InterfaceB()
        data_interfaces_dict = dict(InterfaceA=interface_a, InterfaceB=interface_b)
        converter_arguments = ConverterPipe(data_interfaces=data_interfaces_dict)

        assert converter_arguments.data_interface_classes == converter_child_class.data_interface_classes

    def test_unique_names_with_list_argument(self):
        interface_a = self.InterfaceA()
        interface_a2 = self.InterfaceA()
        interface_b = self.InterfaceB()
        data_interfaces_list = [interface_a, interface_b, interface_a2]
        converter = ConverterPipe(data_interfaces=data_interfaces_list)

        data_interface_names = list(converter.data_interface_objects.keys())
        expected_interface_names = ["InterfaceA001", "InterfaceB", "InterfaceA002"]
        self.assertListEqual(data_interface_names, expected_interface_names)


def test_converter_pipe_append_on_disk(tmp_path):
    """Test that append_on_disk_nwbfile works for ConverterPipe with multiple interfaces."""
    from pynwb import NWBHDF5IO
    from pynwb.testing.mock.file import mock_NWBFile

    from neuroconv.tools.testing.mock_interfaces import (
        MockRecordingInterface,
        MockSortingInterface,
    )

    nwbfile_path = tmp_path / "test_append.nwb"

    nwbfile = mock_NWBFile()
    with NWBHDF5IO(nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    # Append to existing file with converter containing both recording and sorting interfaces
    sorting_interface = MockSortingInterface(num_units=3, durations=(0.1,))
    recording_interface = MockRecordingInterface(num_channels=2, durations=(0.1,))
    converter = ConverterPipe(data_interfaces=[sorting_interface, recording_interface])
    converter.run_conversion(nwbfile_path=nwbfile_path, append_on_disk_nwbfile=True)

    # Verify both interfaces' data was appended
    with NWBHDF5IO(nwbfile_path, "r") as io:
        nwbfile = io.read()
        # Original mock file data still exists
        assert nwbfile.session_description is not None
        # Sorting interface data
        assert nwbfile.units is not None
        assert len(nwbfile.units) == 3
        # Recording interface data
        assert "ElectricalSeries" in nwbfile.acquisition
