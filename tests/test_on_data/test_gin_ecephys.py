import tempfile
import unittest
import os
from pathlib import Path
from datetime import datetime

import numpy as np
import numpy.testing as npt

import pytest
from spikeinterface.core.old_api_utils import OldToNewRecording, BaseRecording
from spikeextractors import NwbRecordingExtractor, NwbSortingExtractor, RecordingExtractor
from spikeextractors.testing import check_recordings_equal, check_sortings_equal
from spikeinterface.core.testing import check_recordings_equal as check_recordings_equal_si


from pynwb import NWBHDF5IO

from nwb_conversion_tools import (
    NWBConverter,
    CellExplorerSortingInterface,
    IntanRecordingInterface,
    NeuralynxRecordingInterface,
    NeuroscopeRecordingInterface,
    OpenEphysRecordingExtractorInterface,
    PhySortingInterface,
    SpikeGadgetsRecordingInterface,
    SpikeGLXRecordingInterface,
    SpikeGLXLFPInterface,
    BlackrockRecordingExtractorInterface,
    BlackrockSortingExtractorInterface,
    AxonaRecordingExtractorInterface,
    AxonaLFPDataInterface,
)
from nwb_conversion_tools.utils.json_schema import load_dict_from_file

try:
    from parameterized import parameterized, param

    HAVE_PARAMETERIZED = True
except ImportError:
    HAVE_PARAMETERIZED = False

# Load the configuration for the data tests
test_config_dict = load_dict_from_file("./tests/test_on_data/gin_test_config.json")

# GIN dataset: https://gin.g-node.org/NeuralEnsemble/ephy_testing_data
if os.getenv("CI"):
    LOCAL_PATH = Path(".")  # Must be set to "." for CI
    print("Running GIN tests on Github CI!")
else:
    # Override the LOCAL_PATH in the `gin_test_config.json` file to a point on your local system that contains the dataset folder
    # Use DANDIHub at hub.dandiarchive.org for open, free use of data found in the /shared/catalystneuro/ directory
    LOCAL_PATH = Path(test_config_dict["LOCAL_PATH"])
    print("Running GIN tests locally!")

DATA_PATH = LOCAL_PATH / "ephy_testing_data"
HAVE_DATA = DATA_PATH.exists()

if test_config_dict["SAVE_OUTPUTS"]:
    OUTPUT_PATH = LOCAL_PATH / "example_nwb_output"
    OUTPUT_PATH.mkdir(exist_ok=True)
else:
    OUTPUT_PATH = Path(tempfile.mkdtemp())

if not HAVE_PARAMETERIZED:
    pytest.fail("parameterized module is not installed! Please install (`pip install parameterized`).")

if not HAVE_DATA:
    pytest.fail(f"No ephy_testing_data folder found in location: {DATA_PATH}!")


def custom_name_func(testcase_func, param_num, param):
    return (
        f"{testcase_func.__name__}_{param_num}_"
        f"{parameterized.to_safe_name(param.kwargs['data_interface'].__name__)}"
    )


class TestEcephysNwbConversions(unittest.TestCase):
    savedir = OUTPUT_PATH

    parameterized_lfp_list = [
        param(
            data_interface=AxonaLFPDataInterface,
            interface_kwargs=dict(file_path=str(DATA_PATH / "axona" / "dataset_unit_spikes" / "20140815-180secs.eeg")),
        ),
        param(
            data_interface=SpikeGLXLFPInterface,
            interface_kwargs=dict(
                file_path=str(
                    DATA_PATH / "spikeglx" / "Noise4Sam_g0" / "Noise4Sam_g0_imec0" / "Noise4Sam_g0_t0.imec0.lf.bin"
                )
            ),
        ),
    ]

    @parameterized.expand(input=parameterized_lfp_list, name_func=custom_name_func)
    def test_convert_lfp_to_nwb(self, data_interface, interface_kwargs):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestLFP=data_interface)

        converter = TestConverter(source_data=dict(TestLFP=interface_kwargs))
        for interface_kwarg in interface_kwargs:
            if interface_kwarg in ["file_path", "folder_path"]:
                self.assertIn(member=interface_kwarg, container=converter.data_interface_objects["TestLFP"].source_data)
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S"))
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)
        recording = converter.data_interface_objects["TestLFP"].recording_extractor
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            nwb_lfp_unscaled = nwbfile.processing["ecephys"]["LFP"]["ElectricalSeries_lfp"].data
            nwb_lfp_conversion = nwbfile.processing["ecephys"]["LFP"]["ElectricalSeries_lfp"].conversion
            # Technically, check_recordings_equal only tests a snippet of data. Above tests are for metadata mostly.
            # For GIN test data, sizes should be OK to load all into RAM even on CI
            npt.assert_array_equal(x=recording.get_traces(return_scaled=False).T, y=nwb_lfp_unscaled)
            npt.assert_array_almost_equal(
                x=recording.get_traces(return_scaled=True).T * 1e-6, y=nwb_lfp_unscaled * nwb_lfp_conversion
            )

    parameterized_recording_list = [
        param(
            data_interface=NeuralynxRecordingInterface,
            interface_kwargs=dict(folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v5.7.4" / "original_data")),
        ),
        param(
            data_interface=NeuroscopeRecordingInterface,
            interface_kwargs=dict(file_path=str(DATA_PATH / "neuroscope" / "test1" / "test1.dat")),
        ),
        param(
            data_interface=OpenEphysRecordingExtractorInterface,
            interface_kwargs=dict(folder_path=str(DATA_PATH / "openephysbinary" / "v0.4.4.1_with_video_tracking")),
        ),
        param(
            data_interface=BlackrockRecordingExtractorInterface,
            interface_kwargs=dict(file_path=str(DATA_PATH / "blackrock" / "FileSpec2.3001.ns5")),
        ),
        param(
            data_interface=AxonaRecordingExtractorInterface,
            interface_kwargs=dict(file_path=str(DATA_PATH / "axona" / "axona_raw.bin")),
        ),
    ]
    for suffix in ["rhd", "rhs"]:
        parameterized_recording_list.append(
            param(
                data_interface=IntanRecordingInterface,
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
                    data_interface=SpikeGadgetsRecordingInterface,
                    interface_kwargs=interface_kwargs,
                )
            )
    for suffix in ["ap", "lf"]:
        sub_path = Path("spikeglx") / "Noise4Sam_g0" / "Noise4Sam_g0_imec0"
        parameterized_recording_list.append(
            param(
                data_interface=SpikeGLXRecordingInterface,
                interface_kwargs=dict(file_path=str(DATA_PATH / sub_path / f"Noise4Sam_g0_t0.imec0.{suffix}.bin")),
            )
        )

    @parameterized.expand(input=parameterized_recording_list, name_func=custom_name_func)
    def test_convert_recording_extractor_to_nwb(self, data_interface, interface_kwargs):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestRecording=data_interface)

        converter = TestConverter(source_data=dict(TestRecording=interface_kwargs))
        for interface_kwarg in interface_kwargs:
            if interface_kwarg in ["file_path", "folder_path"]:
                self.assertIn(
                    member=interface_kwarg, container=converter.data_interface_objects["TestRecording"].source_data
                )
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S"))
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)
        recording = converter.data_interface_objects["TestRecording"].recording_extractor
        nwb_recording = NwbRecordingExtractor(file_path=nwbfile_path)

        if "offset_to_uV" in nwb_recording.get_shared_channel_property_names():
            nwb_recording.set_channel_offsets(
                offsets=[
                    nwb_recording.get_channel_property(channel_id=channel_id, property_name="offset_to_uV")
                    for channel_id in nwb_recording.get_channel_ids()
                ]
            )

        if isinstance(recording, BaseRecording):
            nwb_recording = OldToNewRecording(oldapi_recording_extractor=nwb_recording)

        if isinstance(recording, RecordingExtractor):
            check_recordings_equal(RX1=recording, RX2=nwb_recording, check_times=False, return_scaled=False)
            check_recordings_equal(RX1=recording, RX2=nwb_recording, check_times=False, return_scaled=True)

            # Technically, check_recordings_equal only tests a snippet of data. Above tests are for metadata mostly.
            # For GIN test data, sizes should be OK to load all into RAM even on CI
            npt.assert_array_equal(
                x=recording.get_traces(return_scaled=False), y=nwb_recording.get_traces(return_scaled=False)
            )

        else:
            check_recordings_equal_si(RX1=recording, RX2=nwb_recording, return_scaled=False)
            # This can only be tested if both gain and offest are present
            if recording.has_scaled_traces() and nwb_recording.has_scaled_traces():
                check_recordings_equal_si(RX1=recording, RX2=nwb_recording, return_scaled=True)

    @parameterized.expand(
        input=[
            param(
                data_interface=PhySortingInterface,
                interface_kwargs=dict(folder_path=str(DATA_PATH / "phy" / "phy_example_0")),
            ),
            param(
                data_interface=BlackrockSortingExtractorInterface,
                interface_kwargs=dict(file_path=str(DATA_PATH / "blackrock" / "FileSpec2.3001.nev")),
            ),
            param(
                data_interface=CellExplorerSortingInterface,
                interface_kwargs=dict(
                    file_path=str(
                        DATA_PATH
                        / "cellexplorer"
                        / "dataset_1"
                        / "20170311_684um_2088um_170311_134350.spikes.cellinfo.mat"
                    )
                ),
            ),
            param(
                data_interface=CellExplorerSortingInterface,
                interface_kwargs=dict(
                    file_path=str(
                        DATA_PATH / "cellexplorer" / "dataset_2" / "20170504_396um_0um_merge.spikes.cellinfo.mat"
                    )
                ),
            ),
            param(
                data_interface=CellExplorerSortingInterface,
                interface_kwargs=dict(
                    file_path=str(
                        DATA_PATH / "cellexplorer" / "dataset_3" / "20170519_864um_900um_merge.spikes.cellinfo.mat"
                    )
                ),
            ),
        ],
        name_func=custom_name_func,
    )
    def test_convert_sorting_extractor_to_nwb(self, data_interface, interface_kwargs):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestSorting=data_interface)

        converter = TestConverter(source_data=dict(TestSorting=interface_kwargs))
        for interface_kwarg in interface_kwargs:
            if interface_kwarg in ["file_path", "folder_path"]:
                self.assertIn(
                    member=interface_kwarg, container=converter.data_interface_objects["TestSorting"].source_data
                )
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S"))
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)
        sorting = converter.data_interface_objects["TestSorting"].sorting_extractor
        sf = sorting.get_sampling_frequency()
        if sf is None:  # need to set dummy sampling frequency since no associated acquisition in file
            sf = 30000
            sorting.set_sampling_frequency(sf)
        nwb_sorting = NwbSortingExtractor(file_path=nwbfile_path, sampling_frequency=sf)
        check_sortings_equal(SX1=sorting, SX2=nwb_sorting)

    @parameterized.expand(
        input=[
            param(
                name="complete",
                conversion_options=None,
            ),
            param(name="stub", conversion_options=dict(TestRecording=dict(stub_test=True))),
        ]
    )
    def test_neuroscope_gains(self, name, conversion_options):
        input_gain = 2.0
        interface_kwargs = dict(file_path=str(DATA_PATH / "neuroscope" / "test1" / "test1.dat"), gain=input_gain)

        nwbfile_path = str(self.savedir / f"test_neuroscope_gains_{name}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestRecording=NeuroscopeRecordingInterface)

        converter = TestConverter(source_data=dict(TestRecording=interface_kwargs))
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S"))
        converter.run_conversion(
            nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata, conversion_options=conversion_options
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            output_conversion = nwbfile.acquisition["ElectricalSeries_raw"].conversion
            output_gain = output_conversion * 1e6
            self.assertEqual(first=input_gain, second=output_gain)

            nwb_recording = NwbRecordingExtractor(file_path=nwbfile_path)
            nwb_recording_gains = nwb_recording.get_channel_gains()
            npt.assert_almost_equal(input_gain * np.ones_like(nwb_recording_gains), nwb_recording_gains)

    @parameterized.expand(
        input=[
            param(
                name="complete",
                conversion_options=None,
            ),
            param(name="stub", conversion_options=dict(TestRecording=dict(stub_test=True))),
        ]
    )
    def test_neuroscope_dtype(self, name, conversion_options):
        interface_kwargs = dict(file_path=str(DATA_PATH / "neuroscope" / "test1" / "test1.dat"), gain=2.0)

        nwbfile_path = str(self.savedir / f"test_neuroscope_dtype_{name}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestRecording=NeuroscopeRecordingInterface)

        converter = TestConverter(source_data=dict(TestRecording=interface_kwargs))
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S"))
        converter.run_conversion(
            nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata, conversion_options=conversion_options
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            output_dtype = nwbfile.acquisition["ElectricalSeries_raw"].data.dtype
            self.assertEqual(first=output_dtype, second=np.dtype("int16"))

    def test_neuroscope_starting_time(self):
        nwbfile_path = str(self.savedir / "testing_start_time.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestRecording=NeuroscopeRecordingInterface)

        converter = TestConverter(
            source_data=dict(TestRecording=dict(file_path=str(DATA_PATH / "neuroscope" / "test1" / "test1.dat")))
        )
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S"))
        starting_time = 123.0
        converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
            conversion_options=dict(TestRecording=dict(starting_time=starting_time)),
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            self.assertEqual(first=starting_time, second=nwbfile.acquisition["ElectricalSeries_raw"].starting_time)


if __name__ == "__main__":
    unittest.main()
