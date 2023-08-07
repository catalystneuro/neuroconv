import shutil
import tempfile
from pathlib import Path
from warnings import warn

from hdmf.testing import TestCase
from pynwb import NWBHDF5IO

from neuroconv import NWBConverter
from neuroconv.converters import BrukerTiffMultiPlaneConverter
from tests.test_on_data.setup_paths import OPHYS_DATA_PATH


class TestBrukerTiffMultiPlaneConverterDisjointPlaneCase(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.folder_path = str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2022_11_03_IntoTheVoid_t_series-005"
        )
        cls.converter = BrukerTiffMultiPlaneConverter(folder_path=cls.folder_path, plane_separation_type="disjoint")
        cls.test_dir = Path(tempfile.mkdtemp())

        cls.photon_series_names = ["TwoPhotonSeriesCh2000001", "TwoPhotonSeriesCh2000002"]
        cls.imaging_plane_names = ["ImagingPlaneCh2000001", "ImagingPlaneCh2000002"]
        cls.stub_frames = 2
        cls.conversion_options = dict(stub_test=True, stub_frames=cls.stub_frames)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_run_conversion_add_conversion_options(self):
        nwbfile_path = str(self.test_dir / "test_miniscope_converter_conversion_options.nwb")
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            **self.conversion_options,
        )

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

        self.assertEqual(len(nwbfile.acquisition), len(self.photon_series_names))
        self.assertEqual(len(nwbfile.imaging_planes), len(self.imaging_plane_names))

        num_frames = nwbfile.acquisition[self.photon_series_names[0]].data.shape[0]
        self.assertEqual(num_frames, self.stub_frames)

    def test_converter_conversion_options(self):
        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestBrukerTiffConverter=BrukerTiffMultiPlaneConverter)

        nwbfile_path = str(self.test_dir / "test_miniscope_converter_in_nwbconverter_conversion_options.nwb")
        converter = TestConverter(
            source_data=dict(
                TestBrukerTiffConverter=dict(folder_path=self.folder_path, plane_separation_type="disjoint"),
            )
        )
        conversion_options = dict(TestBrukerTiffConverter=self.conversion_options)
        converter.run_conversion(nwbfile_path=nwbfile_path, conversion_options=conversion_options)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

        num_frames = nwbfile.acquisition[self.photon_series_names[0]].data.shape[0]
        self.assertEqual(num_frames, self.stub_frames)
