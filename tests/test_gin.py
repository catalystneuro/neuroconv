import tempfile
import unittest
from pathlib import Path
import sys

from spikeextractors import NwbRecordingExtractor, NwbSortingExtractor
from spikeextractors.testing import check_recordings_equal, check_sortings_equal
from nwb_conversion_tools import (
    NWBConverter,
    AxonaRecordingExtractorInterface,
    BlackrockRecordingExtractorInterface,
    BlackrockSortingExtractorInterface,
    IntanRecordingInterface,
    NeuroscopeRecordingInterface,
    OpenEphysRecordingExtractorInterface,
    CEDRecordingInterface,
    SpikeGLXRecordingInterface
)

try:
    from datalad.api import install, Dataset
    from parameterized import parameterized

    HAVE_DATALAD = True
except ImportError:
    HAVE_DATALAD = False

run_local = False

if HAVE_DATALAD and (sys.platform == "linux" or run_local):
    class TestNwbConversions(unittest.TestCase):

        def setUp(self):
            pt = Path.cwd() / 'ephy_testing_data'
            if pt.exists():
                self.dataset = Dataset(pt)
            else:
                self.dataset = install('https://gin.g-node.org/NeuralEnsemble/ephy_testing_data')
            self.savedir = Path(tempfile.mkdtemp())

        @parameterized.expand([
            (
                AxonaRecordingExtractorInterface,
                "axona",
                dict(filename=str(Path.cwd() / "ephy_testing_data" / "axona" / "axona_raw.set"))
            ),
            (
                BlackrockRecordingExtractorInterface,
                "blackrock/blackrock_2_1",
                dict(
                    filename=str(Path.cwd() / "ephy_testing_data" / "blackrock" / "blackrock_2_1" / "l101210-001"),
                    seg_index=0,
                    nsx_to_load=5
                )
            ),
            (
                IntanRecordingInterface,
                "intan",
                dict(file_path=Path.cwd() / "ephy_testing_data" / "intan" / "intan_rhd_test_1.rhd")
            ),
            (
                IntanRecordingInterface,
                "intan",
                dict(file_path=Path.cwd() / "ephy_testing_data" / "intan" / "intan_rhs_test_1.rhs")
            ),
            (
                NeuroscopeRecordingInterface,
                "neuroscope/test1",
                dict(file_path=Path.cwd() / "ephy_testing_data" / "neuroscope" / "test1" / "test1.dat")
            ),
            (
                OpenEphysRecordingExtractorInterface,
                "openephys/OpenEphys_SampleData_1",
                dict(folder_path=Path.cwd() / "ephy_testing_data" / "openephys" / "OpenEphys_SampleData_1")
            ),
            (
                OpenEphysRecordingExtractorInterface,
                "openephysbinary/v0.4.4.1_with_video_tracking",
                dict(folder_path=Path.cwd() / "ephy_testing_data" / "openephysbinary" / "v0.4.4.1_with_video_tracking")
            ),
            (
                OpenEphysRecordingExtractorInterface,
                "openephysbinary/v0.5.3_two_neuropixels_stream",
                dict(
                    folder_path=Path.cwd() / "ephy_testing_data" / "openephysbinary" / "v0.5.3_two_neuropixels_stream"
                    / "Record_Node_107"
                )
            ),
            (
                CEDRecordingInterface,
                "spike2/m365_1sec.smrx",
                dict(
                    file_path=Path.cwd() / "ephy_testing_data" / "spike2" / "m365_1sec.smrx",
                    smrx_channel_ids=range(10)
                )
            ),
            (
                SpikeGLXRecordingInterface,
                "spikeglx/Noise4Sam_g0",
                dict(
                    file_path=Path.cwd() / "ephy_testing_data" / "spikeglx" / "Noise4Sam_g0" / "Noise4Sam_g0_imec0" /
                    "Noise4Sam_g0_t0.imec0.ap.bin"
                )
            )
        ])
        def test_convert_recording_extractor_to_nwb(self, recording_interface, dataset_path, interface_kwargs):
            print(f"\n\n\n TESTING {recording_interface.__name__}...")
            dataset_stem = Path(dataset_path).stem
            self.dataset.get(dataset_path)
            nwbfile_path = self.savedir / f"{recording_interface.__name__}_test_{dataset_stem}.nwb"

            class TestConverter(NWBConverter):
                data_interface_classes = dict(TestRecording=recording_interface)

            converter = TestConverter(source_data=dict(TestRecording=dict(interface_kwargs)))
            converter.run_conversion(nwbfile_path=nwbfile_path)
            nwb_recording = NwbRecordingExtractor(file_path=nwbfile_path)
            check_recordings_equal(
                RX1=converter.data_interface_objects["TestRecording"].recording_extractor,
                RX2=nwb_recording,
                check_times=False
            )

        @parameterized.expand([
            (
                BlackrockSortingExtractorInterface,
                "blackrock/blackrock_2_1",
                dict(
                    filename=str(Path.cwd() / "ephy_testing_data" / "blackrock" / "blackrock_2_1" / "l101210-001"),
                    seg_index=0,
                    nsx_to_load=5
                 )
            )
        ])
        def test_convert_sorting_extractor_to_nwb(self, sorting_interface, dataset_path, interface_kwargs):
            print(f"\n\n\n TESTING {sorting_interface.__name__}...")
            dataset_stem = Path(dataset_path).stem
            self.dataset.get(dataset_path)
            nwbfile_path = self.savedir / f"{sorting_interface.__name__}_test_{dataset_stem}.nwb"

            class TestConverter(NWBConverter):
                data_interface_classes = dict(TestSorting=sorting_interface)

            converter = TestConverter(source_data=dict(TestSorting=dict(interface_kwargs)))
            converter.run_conversion(nwbfile_path=nwbfile_path)
            nwb_recording = NwbSortingExtractor(file_path=nwbfile_path)
            check_sortings_equal(
                SX1=converter.data_interface_objects["TestRecording"].recording_extractor, SX2=nwb_recording
            )

if __name__ == '__main__':
    unittest.main()
