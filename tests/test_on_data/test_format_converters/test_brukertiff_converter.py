import shutil
import tempfile
from pathlib import Path
from warnings import warn

from hdmf.testing import TestCase
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO

from neuroconv import NWBConverter
from neuroconv.converters import BrukerTiffMultiPlaneConverter
from neuroconv.datainterfaces.ophys.brukertiff.brukertiffconverter import (
    BrukerTiffSinglePlaneConverter,
)
from tests.test_on_data.setup_paths import OPHYS_DATA_PATH


class TestBrukerTiffMultiPlaneConverterDisjointPlaneCase(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.folder_path = str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2022_11_03_IntoTheVoid_t_series-005"
        )
        cls.converter_kwargs = dict(folder_path=cls.folder_path, plane_separation_type="disjoint")
        cls.converter = BrukerTiffMultiPlaneConverter(**cls.converter_kwargs)
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

    def test_volumetric_imaging_raises_with_single_plane_converter(self):
        exc_msg = "For volumetric imaging data use BrukerTiffMultiPlaneConverter."
        with self.assertRaisesWith(ValueError, exc_msg=exc_msg):
            BrukerTiffSinglePlaneConverter(folder_path=self.folder_path)

    def test_incorrect_plane_separation_type_raises(self):
        exc_msg = "For volumetric imaging data the plane separation method must be one of 'disjoint' or 'contiguous'."
        with self.assertRaisesWith(ValueError, exc_msg=exc_msg):
            BrukerTiffMultiPlaneConverter(folder_path=self.folder_path, plane_separation_type="test")

    def test_run_conversion_add_conversion_options(self):
        nwbfile_path = str(self.test_dir / "test_brukertiff_converter_conversion_options.nwb")
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            **self.conversion_options,
        )

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()
            first_imaging_plane = nwbfile.imaging_planes[self.imaging_plane_names[0]]
            first_origin_coords = first_imaging_plane.origin_coords[:]

            second_imaging_plane = nwbfile.imaging_planes[self.imaging_plane_names[1]]
            second_origin_coords = second_imaging_plane.origin_coords[:]

        self.assertEqual(len(nwbfile.acquisition), len(self.photon_series_names))
        assert_array_equal(first_origin_coords, [56.215, 14.927, -130.0])
        assert_array_equal(second_origin_coords, [56.215, 14.927, 130.0])

        self.assertEqual(len(nwbfile.imaging_planes), len(self.imaging_plane_names))

        num_frames = nwbfile.acquisition[self.photon_series_names[0]].data.shape[0]
        self.assertEqual(num_frames, self.stub_frames)

    def test_converter_conversion_options(self):
        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestBrukerTiffConverter=BrukerTiffMultiPlaneConverter)

        nwbfile_path = str(self.test_dir / "test_brukertiff_converter_in_nwbconverter_conversion_options.nwb")
        converter = TestConverter(
            source_data=dict(
                TestBrukerTiffConverter=self.converter_kwargs,
            )
        )
        conversion_options = dict(TestBrukerTiffConverter=self.conversion_options)
        converter.run_conversion(nwbfile_path=nwbfile_path, conversion_options=conversion_options)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

        num_frames = nwbfile.acquisition[self.photon_series_names[0]].data.shape[0]
        self.assertEqual(num_frames, self.stub_frames)


class TestBrukerTiffMultiPlaneConverterContiguousPlaneCase(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.folder_path = str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2022_11_03_IntoTheVoid_t_series-005"
        )
        cls.converter_kwargs = dict(folder_path=cls.folder_path, plane_separation_type="contiguous")
        cls.converter = BrukerTiffMultiPlaneConverter(**cls.converter_kwargs)
        cls.test_dir = Path(tempfile.mkdtemp())

        cls.photon_series_name = "TwoPhotonSeries"
        cls.imaging_plane_name = "ImagingPlane"
        cls.stub_frames = 2
        cls.conversion_options = dict(stub_test=True, stub_frames=cls.stub_frames)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_run_conversion_add_conversion_options(self):
        nwbfile_path = str(self.test_dir / "test_brukertiff_volumetric_converter_conversion_options.nwb")
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            **self.conversion_options,
        )

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

        self.assertEqual(len(nwbfile.acquisition), 1)
        self.assertIn(self.photon_series_name, nwbfile.acquisition)
        self.assertEqual(len(nwbfile.imaging_planes), 1)
        self.assertIn(self.imaging_plane_name, nwbfile.imaging_planes)

        num_frames = nwbfile.acquisition[self.photon_series_name].data.shape[0]
        self.assertEqual(num_frames, self.stub_frames)

    def test_converter_conversion_options(self):
        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestBrukerTiffConverter=BrukerTiffMultiPlaneConverter)

        nwbfile_path = str(
            self.test_dir / "test_brukertiff_volumetric_converter_in_nwbconverter_conversion_options.nwb"
        )
        converter = TestConverter(
            source_data=dict(
                TestBrukerTiffConverter=self.converter_kwargs,
            )
        )
        conversion_options = dict(TestBrukerTiffConverter=self.conversion_options)
        converter.run_conversion(nwbfile_path=nwbfile_path, conversion_options=conversion_options)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

        num_frames = nwbfile.acquisition[self.photon_series_name].data.shape[0]
        self.assertEqual(num_frames, self.stub_frames)


class TestBrukerTiffSinglePlaneConverterCase(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.folder_path = str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR62_2023_07_06_IntoTheVoid_t_series_Dual_color-000"
        )
        cls.converter = BrukerTiffSinglePlaneConverter(folder_path=cls.folder_path)
        cls.test_dir = Path(tempfile.mkdtemp())

        cls.photon_series_names = ["TwoPhotonSeriesCh1", "TwoPhotonSeriesCh2"]
        cls.imaging_plane_names = ["ImagingPlaneCh1", "ImagingPlaneCh2"]
        cls.stub_frames = 2
        cls.conversion_options = dict(stub_test=True, stub_frames=cls.stub_frames)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_run_conversion_add_conversion_options(self):
        nwbfile_path = str(self.test_dir / "test_brukertiff_dualcolor_converter_conversion_options.nwb")
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            **self.conversion_options,
        )

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

        self.assertEqual(len(nwbfile.acquisition), 2)
        self.assertEqual(len(nwbfile.imaging_planes), 2)
        self.assertEqual(len(nwbfile.devices), 1)

        num_frames = nwbfile.acquisition[self.photon_series_names[0]].data.shape[0]
        self.assertEqual(num_frames, self.stub_frames)

    def test_converter_conversion_options(self):
        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestBrukerTiffConverter=BrukerTiffSinglePlaneConverter)

        nwbfile_path = str(self.test_dir / "test_brukertiff_dualcolor_converter_in_nwbconverter_conversion_options.nwb")
        converter = TestConverter(
            source_data=dict(
                TestBrukerTiffConverter=dict(folder_path=self.folder_path),
            )
        )
        conversion_options = dict(TestBrukerTiffConverter=self.conversion_options)
        converter.run_conversion(nwbfile_path=nwbfile_path, conversion_options=conversion_options)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

        num_frames = nwbfile.acquisition[self.photon_series_names[0]].data.shape[0]
        self.assertEqual(num_frames, self.stub_frames)
