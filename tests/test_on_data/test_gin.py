import tempfile
import unittest
from pathlib import Path
import numpy.testing as npt
import os

import pytest
from spikeextractors import NwbRecordingExtractor, NwbSortingExtractor
from spikeextractors.testing import check_recordings_equal, check_sortings_equal
from nwb_conversion_tools import (
    NWBConverter,
    IntanRecordingInterface,
    NeuralynxRecordingInterface,
    NeuroscopeRecordingInterface,
    OpenEphysRecordingExtractorInterface,
    PhySortingInterface,
    SpikeGadgetsRecordingInterface,
    SpikeGLXRecordingInterface,
    BlackrockRecordingExtractorInterface,
    BlackrockSortingExtractorInterface,
)

try:
    from parameterized import parameterized, param

    HAVE_PARAMETERIZED = True
except ImportError:
    HAVE_PARAMETERIZED = False

# Path to dataset downloaded from https://gin.g-node.org/NeuralEnsemble/ephy_testing_data
#   ecephys: https://gin.g-node.org/NeuralEnsemble/ephy_testing_data
#   ophys: TODO
#   icephys: TODO
if os.getenv("CI"):
    LOCAL_PATH = Path(".")  # Must be set to "." for CI
    print("Running GIN tests on Github CI!")
else:
    LOCAL_PATH = Path("/home/jovyan/")  # Override this on personal device for local testing
    print("Running GIN tests locally!")

DATA_PATH = LOCAL_PATH / "ephy_testing_data"
HAVE_DATA = DATA_PATH.exists()

if not HAVE_PARAMETERIZED:
    pytest.fail("parameterized module is not installed! Please install (`pip install parameterized`).")

if not HAVE_DATA:
    pytest.fail(f"No ephy_testing_data folder found in location: {DATA_PATH}!")


def custom_name_func(testcase_func, param_num, param):
    return (
        f"{testcase_func.__name__}_{param_num}_"
        f"{parameterized.to_safe_name(param.kwargs['recording_interface'].__name__)}"
    )


class TestNwbConversions(unittest.TestCase):
    savedir = Path(tempfile.mkdtemp())

    parameterized_recording_list = [
        param(
            recording_interface=NeuralynxRecordingInterface,
            interface_kwargs=dict(folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v5.7.4" / "original_data")),
        ),
        param(
            recording_interface=NeuroscopeRecordingInterface,
            interface_kwargs=dict(file_path=str(DATA_PATH / "neuroscope" / "test1" / "test1.dat")),
        ),
        param(
            recording_interface=OpenEphysRecordingExtractorInterface,
            interface_kwargs=dict(folder_path=str(DATA_PATH / "openephysbinary" / "v0.4.4.1_with_video_tracking")),
        ),
        param(
            recording_interface=BlackrockRecordingExtractorInterface,
            interface_kwargs=dict(file_path=str(DATA_PATH / "blackrock" / "FileSpec2.3001.ns5")),
        ),
    ]
    for suffix in ["rhd", "rhs"]:
        parameterized_recording_list.append(
            param(
                recording_interface=IntanRecordingInterface,
                interface_kwargs=dict(file_path=str(DATA_PATH / "intan" / f"intan_{suffix}_test_1.{suffix}")),
            )
        )
    for file_name, num_channels in zip(["20210225_em8_minirec2_ac", "W122_06_09_2019_1_fromSD"], [512, 128]):
        for gains in [None, [0.195], [0.385] * num_channels]:
            interface_kwargs = dict(file_path=str(DATA_PATH / "spikegadgets" / f"{file_name}.rec"))
            if gains is not None:
                interface_kwargs.update(gains=gains)
            parameterized_recording_list.append(
                param(
                    recording_interface=SpikeGadgetsRecordingInterface,
                    interface_kwargs=interface_kwargs,
                )
            )
    for suffix in ["ap", "lf"]:
        sub_path = Path("spikeglx") / "Noise4Sam_g0" / "Noise4Sam_g0_imec0"
        parameterized_recording_list.append(
            param(
                recording_interface=SpikeGLXRecordingInterface,
                interface_kwargs=dict(file_path=str(DATA_PATH / sub_path / f"Noise4Sam_g0_t0.imec0.{suffix}.bin")),
            )
        )

    @parameterized.expand(input=parameterized_recording_list, name_func=custom_name_func)
    def test_convert_recording_extractor_to_nwb(self, recording_interface, interface_kwargs):
        nwbfile_path = str(self.savedir / f"{recording_interface.__name__}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestRecording=recording_interface)

        converter = TestConverter(source_data=dict(TestRecording=dict(interface_kwargs)))
        for interface_kwarg in interface_kwargs:
            if interface_kwarg in ["file_path", "folder_path"]:
                self.assertIn(
                    member=interface_kwarg, container=converter.data_interface_objects["TestRecording"].source_data
                )
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)
        recording = converter.data_interface_objects["TestRecording"].recording_extractor
        nwb_recording = NwbRecordingExtractor(file_path=nwbfile_path)
        check_recordings_equal(RX1=recording, RX2=nwb_recording, check_times=False, return_scaled=False)
        check_recordings_equal(RX1=recording, RX2=nwb_recording, check_times=False, return_scaled=True)
        # Technically, check_recordings_equal only tests a snippet of data. Above tests are for metadata mostly.
        # For GIN test data, sizes should be OK to load all into RAM even on CI
        npt.assert_array_equal(
            x=recording.get_traces(return_scaled=False), y=nwb_recording.get_traces(return_scaled=False)
        )

    @parameterized.expand(
        [
            param(
                sorting_interface=PhySortingInterface,
                interface_kwargs=dict(folder_path=str(DATA_PATH / "phy" / "phy_example_0")),
            ),
            param(
                sorting_interface=BlackrockSortingExtractorInterface,
                interface_kwargs=dict(file_path=str(DATA_PATH / "blackrock" / "FileSpec2.3001.nev")),
            ),
        ],
    )
    def test_convert_sorting_extractor_to_nwb(self, sorting_interface, interface_kwargs):
        nwbfile_path = str(self.savedir / f"{sorting_interface.__name__}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestSorting=sorting_interface)

        converter = TestConverter(source_data=dict(TestSorting=dict(interface_kwargs)))
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)
        sorting = converter.data_interface_objects["TestSorting"].sorting_extractor
        sf = sorting.get_sampling_frequency()
        if sf is None:  # need to set dummy sampling frequency since no associated acquisition in file
            sf = 30000
            sorting.set_sampling_frequency(sf)
        nwb_sorting = NwbSortingExtractor(file_path=nwbfile_path, sampling_frequency=sf)
        check_sortings_equal(SX1=sorting, SX2=nwb_sorting)
