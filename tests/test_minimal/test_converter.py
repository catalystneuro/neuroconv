from tempfile import mkdtemp
from shutil import rmtree
from pathlib import Path
from datetime import datetime
import unittest

from pynwb import NWBFile

from neuroconv import NWBConverter, ConverterPipe
from neuroconv.basedatainterface import BaseDataInterface

try:
    from ndx_events import LabeledEvents

    HAVE_NDX_EVENTS = True
except ImportError:
    HAVE_NDX_EVENTS = False


def test_converter():
    if HAVE_NDX_EVENTS:
        test_dir = Path(mkdtemp())
        nwbfile_path = str(test_dir / "extension_test.nwb")

        class NdxEventsInterface(BaseDataInterface):
            def run_conversion(self, nwbfile: NWBFile, metadata: dict):
                events = LabeledEvents(
                    name="LabeledEvents",
                    description="events from my experiment",
                    timestamps=[0.0, 0.5, 0.6, 2.0, 2.05, 3.0, 3.5, 3.6, 4.0],
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
        class InterfaceA(BaseDataInterface):
            def __init__(self, **source_data):
                super().__init__(**source_data)

            def run_conversion(self):
                pass

        cls.InterfaceA = InterfaceA

        class InterfaceB(BaseDataInterface):
            def __init__(self, **source_data):
                super().__init__(**source_data)

            def run_conversion(self):
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
