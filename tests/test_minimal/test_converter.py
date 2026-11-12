import unittest
import warnings
from datetime import datetime
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import numpy as np
import pytest
from pynwb import NWBFile
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv import (
    BaseDataInterface,
    BaseTemporalAlignmentInterface,
    ConverterPipe,
    NWBConverter,
)
from neuroconv.tools.testing.mock_interfaces import MockInterface
from neuroconv.utils import DeepDict

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


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_converter_pipe_append_on_disk(tmp_path, backend):
    """Test that append_on_disk_nwbfile works for ConverterPipe with multiple interfaces."""
    from pynwb.testing.mock.file import mock_NWBFile

    from neuroconv.tools.nwb_helpers import BACKEND_NWB_IO
    from neuroconv.tools.testing.mock_interfaces import MockTimeSeriesInterface

    nwbfile_path = tmp_path / ("test_append.nwb" if backend == "hdf5" else "test_append.nwb.zarr")

    nwbfile = mock_NWBFile()
    IO = BACKEND_NWB_IO[backend]
    with IO(str(nwbfile_path), mode="w") as io:
        io.write(nwbfile)

    # Append to existing file with converter containing two TimeSeries interfaces
    timeseries_interface1 = MockTimeSeriesInterface(num_channels=2, duration=0.1, metadata_key="TimeSeriesAnalog")
    timeseries_interface2 = MockTimeSeriesInterface(num_channels=3, duration=0.1, metadata_key="TimeSeriesAuxiliary")
    converter = ConverterPipe(data_interfaces=[timeseries_interface1, timeseries_interface2])

    # Get metadata and modify TimeSeries names to be unique
    metadata = converter.get_metadata()
    metadata["TimeSeries"]["TimeSeriesAnalog"]["name"] = "MockTimeSeriesAnalog"
    metadata["TimeSeries"]["TimeSeriesAuxiliary"]["name"] = "MockTimeSeriesAuxiliary"

    converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, append_on_disk_nwbfile=True)

    # Verify all interfaces' data was appended, in a file still written with the backend it started with
    with IO(str(nwbfile_path), "r") as io:
        nwbfile = io.read()
        # Original mock file data still exists
        assert nwbfile.session_description is not None
        # First TimeSeries interface data
        assert "MockTimeSeriesAnalog" in nwbfile.acquisition
        assert nwbfile.acquisition["MockTimeSeriesAnalog"].data.shape[1] == 2
        # Second TimeSeries interface data
        assert "MockTimeSeriesAuxiliary" in nwbfile.acquisition
        assert nwbfile.acquisition["MockTimeSeriesAuxiliary"].data.shape[1] == 3
        # Verify we have exactly 2 TimeSeries
        timeseries_names = list(nwbfile.acquisition.keys())
        assert len(timeseries_names) == 2


def test_converter_forwards_the_metadata_format_it_was_asked_for():
    """A converter asks each interface for the format the caller asked for, not for the default.

    The two are indistinguishable while the default is `False`, so this asks the interface itself what it
    was handed rather than reading the shape that comes back.
    """

    class RecordingTheArgumentInterface(BaseDataInterface):
        def __init__(self):
            super().__init__()
            self.asked_for = []

        # The default is deliberately the opposite of what the test asks for, so a converter that drops
        # the argument and lets this default answer is caught whatever the library's own default is.
        def get_metadata(self, *, use_new_metadata_format: bool = True) -> DeepDict:
            self.asked_for.append(use_new_metadata_format)
            return super().get_metadata()

        def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None):
            pass

    interface = RecordingTheArgumentInterface()
    converter = ConverterPipe(data_interfaces=dict(Recording=interface))

    converter.get_metadata(use_new_metadata_format=False)
    converter.get_metadata(use_new_metadata_format=True)

    assert interface.asked_for == [False, True]


def test_nested_converter_receives_its_conversion_options():
    """A converter nested in another one is handed its options as a mapping, not as keyword arguments.

    An outer converter unpacks one level of `conversion_options` per container, and the entry for a nested
    converter names that converter's own children, so it has to arrive whole. The two halves are asserted
    together because they used to disagree: the shape the schema describes was the shape the call rejected.
    """
    inner_converter = ConverterPipe(data_interfaces=dict(Recording=MockInterface()))
    outer_converter = ConverterPipe(data_interfaces=dict(Inner=inner_converter))

    conversion_options = dict(Inner=dict(Recording=dict(add_subject=True)))

    outer_converter.validate_conversion_options(conversion_options=conversion_options)
    nwbfile = mock_NWBFile()
    outer_converter.add_to_nwbfile(
        nwbfile=nwbfile,
        metadata=outer_converter.get_metadata(),
        conversion_options=conversion_options,
    )

    assert nwbfile.subject is not None


def test_converter_pipe_accepts_a_tuple_of_interfaces():
    from neuroconv.tools.testing.mock_interfaces import MockBehaviorEventInterface

    converter = ConverterPipe(data_interfaces=(MockBehaviorEventInterface(), MockBehaviorEventInterface()))

    assert list(converter.data_interface_objects) == ["MockBehaviorEventInterface001", "MockBehaviorEventInterface002"]


def test_converter_pipe_rejects_other_types_up_front():
    from neuroconv.tools.testing.mock_interfaces import MockBehaviorEventInterface

    with pytest.raises(TypeError, match="`data_interfaces` must be a list of interfaces, or a dict.*not set"):
        ConverterPipe(data_interfaces={MockBehaviorEventInterface()})


class TestConverterTemporalAlignment:
    def test_child_access(self):
        from neuroconv.tools.testing.mock_interfaces import MockIcephysInterface

        icephys_interface = MockIcephysInterface()
        converter = ConverterPipe(data_interfaces=dict(Icephys=icephys_interface, Static=MockInterface()))

        assert converter.temporal_alignment.keys() == ("Icephys",)
        assert converter.temporal_alignment["Icephys"] is icephys_interface.temporal_alignment

    def test_nested_access(self):
        from neuroconv.tools.testing.mock_interfaces import MockIcephysInterface

        icephys_interface = MockIcephysInterface(metadata_key="cell")
        inner_converter = ConverterPipe(data_interfaces=dict(Icephys=icephys_interface))
        outer_converter = ConverterPipe(data_interfaces=dict(Inner=inner_converter))

        assert outer_converter.temporal_alignment.keys() == ("Inner",)
        assert outer_converter.temporal_alignment["Inner"].keys() == ("Icephys",)
        time_bearing_object = outer_converter.temporal_alignment["Inner"]["Icephys"]["cell"]
        assert time_bearing_object is icephys_interface.temporal_alignment["cell"]

    def test_access_rejects_undeclared_alignment(self):
        converter = ConverterPipe(data_interfaces=dict(Static=MockInterface()))

        with pytest.raises(KeyError, match="'Static' is a MockInterface, which has no temporal alignment"):
            converter.temporal_alignment["Static"]

    def test_unknown_child_lists_available_names(self):
        converter = ConverterPipe(data_interfaces=dict(Static=MockInterface()))

        with pytest.raises(KeyError, match="'Missing' is not a child of this converter. It holds 'Static'"):
            converter.temporal_alignment["Missing"]

    def test_shift_times_reaches_every_descendant(self):
        from neuroconv.tools.testing.mock_interfaces import MockIcephysInterface

        first_interface = MockIcephysInterface(
            metadata_key="first", num_sweeps=1, sampling_frequency=4.0, stimulus_duration=0.5
        )
        second_interface = MockIcephysInterface(
            metadata_key="second", num_sweeps=1, sampling_frequency=4.0, starting_time=10.0
        )
        inner_converter = ConverterPipe(data_interfaces=dict(Second=second_interface))
        converter = ConverterPipe(data_interfaces=dict(First=first_interface, Inner=inner_converter))
        first_response = first_interface.temporal_alignment["first"]
        first_stimulus = first_interface.temporal_alignment["first_stimulus"]
        second_response = second_interface.temporal_alignment["second"]
        first_times = first_response.get_times().copy()
        stimulus_times = first_stimulus.get_times().copy()
        second_times = second_response.get_times().copy()

        converter.temporal_alignment.shift_times(5.0)

        np.testing.assert_allclose(first_response.get_times(), first_times + 5.0)
        np.testing.assert_allclose(first_stimulus.get_times(), stimulus_times + 5.0)
        np.testing.assert_allclose(second_response.get_times(), second_times + 5.0)

    def test_shift_times_only_moves_selected_subtree(self):
        from neuroconv.tools.testing.mock_interfaces import MockIcephysInterface

        first_interface = MockIcephysInterface(metadata_key="first", num_sweeps=1, sampling_frequency=4.0)
        second_interface = MockIcephysInterface(metadata_key="second", num_sweeps=1, sampling_frequency=4.0)
        inner_converter = ConverterPipe(data_interfaces=dict(Second=second_interface))
        converter = ConverterPipe(
            data_interfaces=dict(First=first_interface, Inner=inner_converter, Unsupported=MockInterface())
        )
        first_response = first_interface.temporal_alignment["first"]
        second_response = second_interface.temporal_alignment["second"]
        first_times = first_response.get_times().copy()
        second_times = second_response.get_times().copy()

        converter.temporal_alignment["Inner"].shift_times(5.0)

        np.testing.assert_array_equal(first_response.get_times(), first_times)
        np.testing.assert_allclose(second_response.get_times(), second_times + 5.0)

    def test_shift_times_warns_when_alignment_is_undeclared(self):
        from neuroconv.tools.testing.mock_interfaces import MockIcephysInterface

        interface = MockIcephysInterface(metadata_key="cell", num_sweeps=1, sampling_frequency=4.0)
        inner_converter = ConverterPipe(data_interfaces=dict(Unsupported=MockInterface()))
        converter = ConverterPipe(data_interfaces=dict(Icephys=interface, Inner=inner_converter))
        response = interface.temporal_alignment["cell"]
        response.shift_times(2.0)
        original_times = response.get_times().copy()

        with pytest.warns(UserWarning, match="Skipping 'Inner/Unsupported'.*temporal_alignment = None"):
            converter.temporal_alignment.shift_times(5.0)

        np.testing.assert_allclose(response.get_times(), original_times + 5.0)

    def test_shift_times_skips_explicitly_unalignable_children(self):
        from neuroconv.datainterfaces import ExternalImageInterface, ImageInterface
        from neuroconv.tools.testing.mock_interfaces import MockIcephysInterface

        interface = MockIcephysInterface(metadata_key="cell", num_sweeps=1, sampling_frequency=4.0)
        image_interface = ImageInterface(file_paths=[])
        external_image_interface = ExternalImageInterface(file_paths=[])
        images_converter = ConverterPipe(data_interfaces=dict(ExternalImages=external_image_interface))
        converter = ConverterPipe(
            data_interfaces=dict(Icephys=interface, Images=image_interface, Nested=images_converter)
        )
        response = interface.temporal_alignment["cell"]
        original_times = response.get_times().copy()

        with warnings.catch_warnings(record=True) as recorded_warnings:
            warnings.simplefilter("always")
            converter.temporal_alignment.shift_times(5.0)

        assert not recorded_warnings
        np.testing.assert_allclose(response.get_times(), original_times + 5.0)
        assert converter.temporal_alignment.keys() == ("Icephys", "Nested")
        assert images_converter.temporal_alignment.keys() == ()
        with pytest.raises(KeyError, match="'Images' is an? ImageInterface, which has no temporal alignment"):
            converter.temporal_alignment["Images"]
