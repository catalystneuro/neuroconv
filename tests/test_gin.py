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
    PhySortingInterface,
    SpikeGLXRecordingInterface,
)

try:
    from datalad.api import install, Dataset

    HAVE_DATALAD = True
except ImportError:
    HAVE_DATALAD = False

try:
    from parameterized import parameterized

    HAVE_PARAMETERIZED = True
except ImportError:
    HAVE_PARAMETERIZED = False

RUN_LOCAL = True
LOCAL_PATH = Path("E:/GIN")  # Path to dataset downloaded from https://gin.g-node.org/NeuralEnsemble/ephy_testing_data


if HAVE_PARAMETERIZED and (HAVE_DATALAD and sys.platform == "linux" or RUN_LOCAL):

    class TestNwbConversions(unittest.TestCase):
        dataset = None
        savedir = Path(tempfile.mkdtemp())

        if RUN_LOCAL and LOCAL_PATH.exists():
            data_path = LOCAL_PATH
        else:
            data_path = Path.cwd() / "ephy_testing_data"

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

        @parameterized.expand(
            [
                (
                    IntanRecordingInterface,
                    "intan",
                    dict(file_path=str(data_path / "intan" / "intan_rhd_test_1.rhd")),
                ),
                (
                    IntanRecordingInterface,
                    "intan",
                    dict(file_path=str(data_path / "intan" / "intan_rhs_test_1.rhs")),
                ),
                (
                    NeuralynxRecordingInterface,
                    "neuralynx/Cheetah_v5.7.4/original_data",
                    dict(folder_path=str(data_path / "neuralynx" / "Cheetah_v5.7.4" / "original_data")),
                ),
                (
                    NeuroscopeRecordingInterface,
                    "neuroscope/test1",
                    dict(file_path=str(data_path / "neuroscope" / "test1" / "test1.dat")),
                ),
                (
                    SpikeGLXRecordingInterface,
                    "spikeglx/Noise4Sam_g0/Noise4Sam_g0_imec0",
                    dict(
                        file_path=str(
                            data_path
                            / "spikeglx"
                            / "Noise4Sam_g0"
                            / "Noise4Sam_g0_imec0"
                            / "Noise4Sam_g0_t0.imec0.ap.bin"
                        )
                    ),
                ),
                (
                    SpikeGLXRecordingInterface,
                    "spikeglx/Noise4Sam_g0/Noise4Sam_g0_imec0",
                    dict(
                        file_path=str(
                            data_path
                            / "spikeglx"
                            / "Noise4Sam_g0"
                            / "Noise4Sam_g0_imec0"
                            / "Noise4Sam_g0_t0.imec0.lf.bin"
                        )
                    ),
                ),
            ]
        )
        def test_convert_recording_extractor_to_nwb(self, recording_interface, dataset_path, interface_kwargs):
            print(f"\n\n\n TESTING {recording_interface.__name__}...")
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
                (
                    PhySortingInterface,
                    "phy/phy_example_0",
                    dict(folder_path=str(data_path / "phy" / "phy_example_0"))
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
            recording = converter.data_interface_objects["TestSorting"].sortinging_extractor
            nwb_recording = NwbSortingExtractor(file_path=nwbfile_path)
            check_sortings_equal(RX1=recording, RX2=nwb_recording, check_times=False, return_scaled=False)
            check_sortings_equal(RX1=recording, RX2=nwb_recording, check_times=False, return_scaled=True)

if __name__ == "__main__":
    unittest.main()
