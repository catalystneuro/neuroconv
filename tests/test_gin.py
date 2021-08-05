import tempfile
import unittest
from pathlib import Path
import sys

from datalad.api import install, Dataset
from parameterized import parameterized

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

run_local = False

if sys.platform == "linux" or run_local:
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
            # Klusta - no .prm config file in ephy_testing
            # (
            #     se.KlustaRecordingExtractor,
            #     "kwik",
            #     dict(folder_path=Path.cwd() / "ephy_testing_data" / "kwik")
            # ),
            # (
            #     se.MEArecRecordingExtractor,
            #     "mearec/mearec_test_10s.h5",
            #     dict(file_path=Path.cwd() / "ephy_testing_data" / "mearec" / "mearec_test_10s.h5")
            # ),
            # (
            #     se.NeuralynxRecordingExtractor,
            #     "neuralynx/Cheetah_v5.7.4/original_data",
            #     dict(
            #         dirname=Path.cwd() / "ephy_testing_data" / "neuralynx" / "Cheetah_v5.7.4" / "original_data",
            #         seg_index=0
            #     )
            # ),
            (
                NeuroscopeRecordingInterface,
                "neuroscope/test1",
                dict(file_path=Path.cwd() / "ephy_testing_data" / "neuroscope" / "test1" / "test1.dat")
            ),
            # Nixio - RuntimeError: Cannot open non-existent file in ReadOnly mode!
            # (
            #     se.NIXIORecordingExtractor,
            #     "nix",
            #     dict(file_path=str(Path.cwd() / "ephy_testing_data" / "neoraw.nix"))
            # ),
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
            # (
            #     se.NeuropixelsDatRecordingExtractor,
            #     "openephysbinary/v0.5.3_two_neuropixels_stream",
            #     dict(
            #         file_path=Path.cwd() / "ephy_testing_data" / "openephysbinary" / "v0.5.3_two_neuropixels_stream" /
            #                   "Record_Node_107" / "experiment1" / "recording1" / "continuous" /
            #                   "Neuropix-PXI-116.0" / "continuous.dat",
            #         settings_file=Path.cwd() / "ephy_testing_data" / "openephysbinary" /
            #                       "v0.5.3_two_neuropixels_stream" / "Record_Node_107" / "settings.xml")
            # ),
            # (
            #     se.PhyRecordingExtractor,
            #     "phy/phy_example_0",
            #     dict(folder_path=Path.cwd() / "ephy_testing_data" / "phy" / "phy_example_0")
            # ),
            # Plexon - AssertionError: This file have several channel groups spikeextractors support only one groups
            # (
            #     se.PlexonRecordingExtractor,
            #     "plexon",
            #     dict(filename=Path.cwd() / "ephy_testing_data" / "plexon" / "File_plexon_2.plx")
            # ),
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
            print(f"\n\n\n TESTING {recording_interface.extractor_name}...")
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
            ),
            # (
            #     se.KlustaSortingExtractor,
            #     "kwik",
            #     dict(file_or_folder_path=Path.cwd() / "ephy_testing_data" / "kwik" / "neo.kwik")
            # ),
            # Neuralynx - units_ids = nwbfile.units.id[:] - AttributeError: 'NoneType' object has no attribute 'id'
            # Is the GIN data OK? Or are there no units?
            # (
            #     se.NeuralynxSortingExtractor,
            #     "neuralynx/Cheetah_v5.7.4/original_data",
            #     dict(
            #         dirname=Path.cwd() / "ephy_testing_data" / "neuralynx" / "Cheetah_v5.7.4" / "original_data",
            #         seg_index=0
            #     )
            # ),
            # NIXIO - return [int(da.label) for da in self._spike_das]
            # TypeError: int() argument must be a string, a bytes-like object or a number, not 'NoneType'
            # (
            #     se.NIXIOSortingExtractor,
            #     "nix/nixio_fr.nix",
            #     dict(file_path=str(Path.cwd() / "ephy_testing_data" / "nix" / "nixio_fr.nix"))
            # ),
            # (
            #     se.MEArecSortingExtractor,
            #     "mearec/mearec_test_10s.h5",
            #     dict(file_path=Path.cwd() / "ephy_testing_data" / "mearec" / "mearec_test_10s.h5")
            # ),
            # (
            #     se.PhySortingExtractor,
            #     "phy/phy_example_0",
            #     dict(folder_path=Path.cwd() / "ephy_testing_data" / "phy" / "phy_example_0")
            # ),
            # (
            #     se.PlexonSortingExtractor,
            #     "plexon",
            #     dict(filename=Path.cwd() / "ephy_testing_data" / "plexon" / "File_plexon_2.plx")
            # ),
            # (
            #     se.SpykingCircusSortingExtractor,
            #     "spykingcircus/spykingcircus_example0",
            #     dict(
            #         file_or_folder_path=Path.cwd() / "ephy_testing_data" / "spykingcircus" / "spykingcircus_example0" /
            #                             "recording"
            #     )
            # ),
            # # Tridesclous - dataio error, GIN data is not correct?
            # (
            #     se.TridesclousSortingExtractor,
            #     "tridesclous/tdc_example0",
            #     dict(folder_path=Path.cwd() / "ephy_testing_data" / "tridesclous" / "tdc_example0")
            # )
        ])
        def test_convert_sorting_extractor_to_nwb(self, sorting_interface, dataset_path, interface_kwargs):
            print(f"\n\n\n TESTING {sorting_interface.extractor_name}...")
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
