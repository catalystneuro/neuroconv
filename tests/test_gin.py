import sys
import tempfile
import unittest
from pathlib import Path

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
)

try:
    from datalad.api import install, Dataset

    HAVE_DATALAD = True
except ImportError:
    HAVE_DATALAD = False

try:
    from parameterized import parameterized, param

    HAVE_PARAMETERIZED = True
except ImportError:
    HAVE_PARAMETERIZED = False

RUN_LOCAL = True
LOCAL_PATH = Path("E:/GIN")  # Path to dataset downloaded from https://gin.g-node.org/NeuralEnsemble/ephy_testing_data


if HAVE_PARAMETERIZED and (HAVE_DATALAD and sys.platform == "linux" or RUN_LOCAL):

    def custom_name_func(testcase_func, param_num, param):
        return (
            f"{testcase_func.__name__}_{param_num}_"
            f"{parameterized.to_safe_name(param.kwargs['recording_interface'].__name__)}"
        )

    class TestNwbConversions(unittest.TestCase):
        dataset = None
        savedir = Path(tempfile.mkdtemp())

        if RUN_LOCAL and LOCAL_PATH.exists():
            data_path = LOCAL_PATH
        else:
            data_path = Path.cwd() / "ephy_testing_data"

        parameterized_expand_list = [
            param(
                recording_interface=NeuralynxRecordingInterface,
                dataset_path="neuralynx/Cheetah_v5.7.4/original_data",
                interface_kwargs=dict(folder_path=str(data_path / "neuralynx" / "Cheetah_v5.7.4" / "original_data")),
            ),
            param(
                recording_interface=NeuroscopeRecordingInterface,
                dataset_path="neuroscope/test1",
                interface_kwargs=dict(file_path=str(data_path / "neuroscope" / "test1" / "test1.dat")),
            ),
            param(
                recording_interface=OpenEphysRecordingExtractorInterface,
                dataset_path="openephysbinary/v0.4.4.1_with_video_tracking",
                interface_kwargs=dict(folder_path=str(data_path / "openephysbinary" / "v0.4.4.1_with_video_tracking")),
            ),
        ]
        for suffix in ["rhd", "rhs"]:
            parameterized_expand_list.append(
                param(
                    recording_interface=IntanRecordingInterface,
                    dataset_path="intan",
                    interface_kwargs=dict(file_path=str(data_path / "intan" / f"intan_{suffix}_test_1.{suffix}")),
                )
            )
        for file_name, num_channels in zip(["20210225_em8_minirec2_ac", "W122_06_09_2019_1_fromSD"], [512, 128]):
            for gains in [None, [0.195], [0.385] * num_channels]:
                interface_kwargs = dict(filename=str(data_path / "spikegadgets" / f"{file_name}.rec"))
                if gains is not None:
                    interface_kwargs.update(gains=gains)
                parameterized_expand_list.append(
                    param(
                        recording_interface=SpikeGadgetsRecordingInterface,
                        dataset_path="spikegadgets",
                        interface_kwargs=interface_kwargs,
                    )
                )
        for suffix in ["ap", "lf"]:
            sub_path = Path("spikeglx") / "Noise4Sam_g0" / "Noise4Sam_g0_imec0"
            parameterized_expand_list.append(
                param(
                    recording_interface=SpikeGLXRecordingInterface,
                    dataset_path=sub_path,
                    interface_kwargs=dict(file_path=str(data_path / sub_path / f"Noise4Sam_g0_t0.imec0.{suffix}.bin")),
                )
            )

        def setUp(self):
            data_exists = self.data_path.exists()
            if HAVE_DATALAD and data_exists:
                self.dataset = Dataset(self.data_path)
            if RUN_LOCAL:
                if not data_exists:
                    if HAVE_DATALAD:
                        self.dataset = install("https://gin.g-node.org/NeuralEnsemble/ephy_testing_data")
                    else:
                        raise FileNotFoundError(f"The manually specified data path ({self.data_path}) does not exist!")
            elif not data_exists:
                self.dataset = install("https://gin.g-node.org/NeuralEnsemble/ephy_testing_data")

        @parameterized.expand(input=parameterized_expand_list, name_func=custom_name_func)
        def test_convert_recording_extractor_to_nwb(self, recording_interface, dataset_path, interface_kwargs):
            if HAVE_DATALAD:
                loc = list(interface_kwargs.values())[0]
                if Path(loc).is_dir():
                    for file in Path(loc).iterdir():
                        self.dataset.get(f"{dataset_path}/{file.name}")
                else:
                    self.dataset.get(dataset_path)
            dataset_stem = Path(dataset_path).stem
            nwbfile_path = self.savedir / f"{recording_interface.__name__}_test_{dataset_stem}.nwb"

            class TestConverter(NWBConverter):
                data_interface_classes = dict(TestRecording=recording_interface)

            converter = TestConverter(source_data=dict(TestRecording=dict(interface_kwargs)))
            converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)
            recording = converter.data_interface_objects["TestRecording"].recording_extractor
            nwb_recording = NwbRecordingExtractor(file_path=nwbfile_path)
            check_recordings_equal(RX1=recording, RX2=nwb_recording, check_times=False, return_scaled=False)
            check_recordings_equal(RX1=recording, RX2=nwb_recording, check_times=False, return_scaled=True)

        @parameterized.expand(
            [
                param(
                    sorting_interface=PhySortingInterface,
                    dataset_path="phy/phy_example_0",
                    interface_kwargs=dict(folder_path=str(data_path / "phy" / "phy_example_0")),
                )
            ]
        )
        def test_convert_sorting_extractor_to_nwb(self, sorting_interface, dataset_path, interface_kwargs):
            print(f"\n\n\n TESTING {sorting_interface.__name__}...")
            if HAVE_DATALAD:
                loc = list(interface_kwargs.values())[0]
                if Path(loc).is_dir():
                    for file in Path(loc).iterdir():
                        self.dataset.get(f"{dataset_path}/{file.name}")
                else:
                    self.dataset.get(dataset_path)
            dataset_stem = Path(dataset_path).stem
            nwbfile_path = self.savedir / f"{sorting_interface.__name__}_test_{dataset_stem}.nwb"

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


if __name__ == "__main__":
    unittest.main()
