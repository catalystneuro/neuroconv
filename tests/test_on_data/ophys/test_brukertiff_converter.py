import shutil
import tempfile
import warnings
from pathlib import Path
from warnings import warn

import pytest
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO

from neuroconv import NWBConverter
from neuroconv.converters import BrukerTiffConverter, BrukerTiffMultiPlaneConverter
from neuroconv.datainterfaces.ophys.brukertiff.brukertiffconverter import (
    BrukerTiffSinglePlaneConverter,
)
from tests.test_on_data.setup_paths import OPHYS_DATA_PATH


class TestBrukerTiffConverterSinglePlane(TestCase):
    """BrukerTiffConverter on single-channel single-plane data: one acquisition."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.folder_path = str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2023_02_20_Into_the_void_t_series_baseline-000"
        )
        cls.converter = BrukerTiffConverter(folder_path=cls.folder_path)
        cls.test_dir = Path(tempfile.mkdtemp())
        cls.stub_samples = 2
        cls.conversion_options = {
            interface_name: dict(stub_test=True, stub_samples=cls.stub_samples)
            for interface_name in cls.converter.data_interface_objects
        }

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_run_conversion(self):
        nwbfile_path = str(self.test_dir / "test_brukertiff_converter_single_plane.nwb")
        metadata = self.converter.get_metadata()
        metadata["NWBFile"]["session_description"] = "test"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
            conversion_options=self.conversion_options,
        )
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()
        self.assertEqual(len(nwbfile.acquisition), 1)
        self.assertEqual(len(nwbfile.imaging_planes), 1)
        self.assertEqual(len(nwbfile.devices), 1)
        photon_series = nwbfile.acquisition["TwoPhotonSeries"]
        self.assertEqual(photon_series.data.shape[0], self.stub_samples)


class TestBrukerTiffConverterVolumetric(TestCase):
    """BrukerTiffConverter on single-channel volumetric data: one 4D acquisition."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.folder_path = str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2022_11_03_IntoTheVoid_t_series-005"
        )
        cls.converter = BrukerTiffConverter(folder_path=cls.folder_path)
        cls.test_dir = Path(tempfile.mkdtemp())
        cls.stub_samples = 2
        cls.conversion_options = {
            interface_name: dict(stub_test=True, stub_samples=cls.stub_samples)
            for interface_name in cls.converter.data_interface_objects
        }

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_run_conversion(self):
        nwbfile_path = str(self.test_dir / "test_brukertiff_converter_volumetric.nwb")
        metadata = self.converter.get_metadata()
        metadata["NWBFile"]["session_description"] = "test"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
            conversion_options=self.conversion_options,
        )
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()
        self.assertEqual(len(nwbfile.acquisition), 1)
        photon_series = nwbfile.acquisition["TwoPhotonSeries"]
        # Volumetric: shape is (samples, H, W, planes)
        self.assertEqual(len(photon_series.data.shape), 4)
        self.assertEqual(photon_series.data.shape[0], self.stub_samples)


class TestBrukerTiffConverterMultiChannel(TestCase):
    """BrukerTiffConverter on multi-channel single-plane data: one acquisition per channel."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.folder_path = str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR62_2023_07_06_IntoTheVoid_t_series_Dual_color-000"
        )
        cls.converter = BrukerTiffConverter(folder_path=cls.folder_path)
        cls.test_dir = Path(tempfile.mkdtemp())
        cls.stub_samples = 2
        cls.conversion_options = {
            interface_name: dict(stub_test=True, stub_samples=cls.stub_samples)
            for interface_name in cls.converter.data_interface_objects
        }

    def test_run_conversion(self):
        nwbfile_path = str(self.test_dir / "test_brukertiff_converter_multichannel.nwb")
        metadata = self.converter.get_metadata()
        metadata["NWBFile"]["session_description"] = "test"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
            conversion_options=self.conversion_options,
        )
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()
        self.assertEqual(len(nwbfile.acquisition), 2)
        self.assertEqual(len(nwbfile.imaging_planes), 2)


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
        cls.stub_samples = 2
        cls.conversion_options = dict(stub_test=True, stub_samples=cls.stub_samples)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_volumetric_imaging_raises_with_single_plane_converter(self):
        exc_msg = "For volumetric imaging data use BrukerTiffMultiPlaneConverter."
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=FutureWarning)
            with self.assertRaisesWith(ValueError, exc_msg=exc_msg):
                BrukerTiffSinglePlaneConverter(folder_path=self.folder_path)

    def test_incorrect_plane_separation_type_raises(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Input should be 'disjoint' or 'contiguous'"):
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

        num_samples = nwbfile.acquisition[self.photon_series_names[0]].data.shape[0]
        self.assertEqual(num_samples, self.stub_samples)

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

        num_samples = nwbfile.acquisition[self.photon_series_names[0]].data.shape[0]
        self.assertEqual(num_samples, self.stub_samples)


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
        cls.stub_samples = 2
        cls.conversion_options = dict(stub_test=True, stub_samples=cls.stub_samples)

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

        num_samples = nwbfile.acquisition[self.photon_series_name].data.shape[0]
        self.assertEqual(num_samples, self.stub_samples)

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

        num_samples = nwbfile.acquisition[self.photon_series_name].data.shape[0]
        self.assertEqual(num_samples, self.stub_samples)


class TestBrukerTiffSinglePlaneConverterCase(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.folder_path = str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR62_2023_07_06_IntoTheVoid_t_series_Dual_color-000"
        )
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=FutureWarning)
            cls.converter = BrukerTiffSinglePlaneConverter(folder_path=cls.folder_path)
        cls.test_dir = Path(tempfile.mkdtemp())

        cls.photon_series_names = ["TwoPhotonSeriesCh1", "TwoPhotonSeriesCh2"]
        cls.imaging_plane_names = ["ImagingPlaneCh1", "ImagingPlaneCh2"]
        cls.stub_samples = 2
        cls.conversion_options = dict(stub_test=True, stub_samples=cls.stub_samples)

    def test_deprecation_warning(self):
        with pytest.warns(FutureWarning, match="deprecated"):
            BrukerTiffSinglePlaneConverter(folder_path=self.folder_path)

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

        num_samples = nwbfile.acquisition[self.photon_series_names[0]].data.shape[0]
        self.assertEqual(num_samples, self.stub_samples)

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

        num_samples = nwbfile.acquisition[self.photon_series_names[0]].data.shape[0]
        self.assertEqual(num_samples, self.stub_samples)
