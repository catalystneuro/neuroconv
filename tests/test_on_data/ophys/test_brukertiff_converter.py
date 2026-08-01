import shutil
import tempfile
import warnings
from pathlib import Path
from warnings import warn

import pytest
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal
from pynwb import read_nwb

from neuroconv import NWBConverter
from neuroconv.converters import BrukerTiffConverter, BrukerTiffMultiPlaneConverter
from neuroconv.datainterfaces.ophys.brukertiff.brukertiffconverter import (
    BrukerTiffSinglePlaneConverter,
)
from tests.test_on_data.setup_paths import OPHYS_DATA_PATH


class TestBrukerTiffConverterSinglePlane:
    """BrukerTiffConverter on single-channel single-plane data: one acquisition."""

    folder_path = (
        OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2023_02_20_Into_the_void_t_series_baseline-000"
    )
    stub_samples = 2

    def test_run_conversion(self, tmp_path):
        converter = BrukerTiffConverter(folder_path=str(self.folder_path))
        conversion_options = {
            name: dict(stub_test=True, stub_samples=self.stub_samples) for name in converter.data_interface_objects
        }

        nwbfile_path = str(tmp_path / "single_plane.nwb")
        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_description"] = "test"
        converter.run_conversion(
            nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata, conversion_options=conversion_options
        )

        nwbfile = read_nwb(nwbfile_path)
        assert len(nwbfile.acquisition) == 1
        assert len(nwbfile.imaging_planes) == 1
        assert len(nwbfile.devices) == 1
        assert nwbfile.acquisition["TwoPhotonSeries"].data.shape[0] == self.stub_samples
        nwbfile.read_io.close()


class TestBrukerTiffConverterVolumetric:
    """BrukerTiffConverter on single-channel volumetric data: one 4D acquisition."""

    folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2022_11_03_IntoTheVoid_t_series-005"
    stub_samples = 2

    def test_run_conversion(self, tmp_path):
        converter = BrukerTiffConverter(folder_path=str(self.folder_path))
        conversion_options = {
            name: dict(stub_test=True, stub_samples=self.stub_samples) for name in converter.data_interface_objects
        }

        nwbfile_path = str(tmp_path / "volumetric.nwb")
        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_description"] = "test"
        converter.run_conversion(
            nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata, conversion_options=conversion_options
        )

        nwbfile = read_nwb(nwbfile_path)
        assert len(nwbfile.acquisition) == 1
        photon_series = nwbfile.acquisition["TwoPhotonSeries"]
        # Volumetric: shape is (samples, height, width, planes)
        assert len(photon_series.data.shape) == 4
        assert photon_series.data.shape[0] == self.stub_samples
        nwbfile.read_io.close()


class TestBrukerTiffConverterMultiChannel:
    """BrukerTiffConverter on multi-channel single-plane data: one acquisition per channel."""

    folder_path = (
        OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR62_2023_07_06_IntoTheVoid_t_series_Dual_color-000"
    )
    stub_samples = 2

    def test_run_conversion(self, tmp_path):
        converter = BrukerTiffConverter(folder_path=str(self.folder_path))
        conversion_options = {
            name: dict(stub_test=True, stub_samples=self.stub_samples) for name in converter.data_interface_objects
        }

        nwbfile_path = str(tmp_path / "multi_channel.nwb")
        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_description"] = "test"
        converter.run_conversion(
            nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata, conversion_options=conversion_options
        )

        nwbfile = read_nwb(nwbfile_path)
        assert len(nwbfile.acquisition) == 2
        assert len(nwbfile.imaging_planes) == 2
        # One microscope for the folder, shared by both channels rather than one device per channel.
        assert len(nwbfile.devices) == 1
        nwbfile.read_io.close()


class TestBrukerTiffConverterDisjoint:
    """BrukerTiffConverter disjoint mode writes one 2D TwoPhotonSeries + ImagingPlane per depth plane.

    Also asserts equivalence with the deprecated ``BrukerTiffMultiPlaneConverter`` it replaces: the
    per-plane data and each plane's focal-depth ``origin_coords`` must match.
    """

    folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2022_11_03_IntoTheVoid_t_series-005"
    stub_samples = 2

    def test_disjoint_matches_deprecated_converter(self, tmp_path):
        converter = BrukerTiffConverter(folder_path=str(self.folder_path), plane_separation_type="disjoint")
        interface_names = list(converter.data_interface_objects)
        assert interface_names == ["BrukerImaging_plane0", "BrukerImaging_plane1"]

        new_path = str(tmp_path / "disjoint_new.nwb")
        converter.run_conversion(
            nwbfile_path=new_path,
            conversion_options={name: dict(stub_test=True, stub_samples=self.stub_samples) for name in interface_names},
        )

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=FutureWarning)
            old_converter = BrukerTiffMultiPlaneConverter(
                folder_path=str(self.folder_path), plane_separation_type="disjoint"
            )
        old_path = str(tmp_path / "disjoint_old.nwb")
        old_converter.run_conversion(nwbfile_path=old_path, stub_test=True, stub_samples=self.stub_samples)

        nwbfile_new = read_nwb(new_path)
        nwbfile_old = read_nwb(old_path)

        assert list(nwbfile_new.acquisition) == ["TwoPhotonSeriesPlane0", "TwoPhotonSeriesPlane1"]
        assert len(nwbfile_new.imaging_planes) == 2
        # One microscope for the folder, shared by both depth planes rather than one device per plane.
        assert len(nwbfile_new.devices) == 1

        # Old converter names planes by the Bruker stream index; match by acquisition order.
        new_series = [nwbfile_new.acquisition[f"TwoPhotonSeriesPlane{index}"] for index in range(2)]
        old_series = [nwbfile_old.acquisition[f"TwoPhotonSeriesCh2{index:06d}"] for index in (1, 2)]

        for new_two_photon_series, old_two_photon_series in zip(new_series, old_series):
            assert_array_equal(new_two_photon_series.data[:], old_two_photon_series.data[:])
            assert_array_equal(
                new_two_photon_series.imaging_plane.origin_coords[:],
                old_two_photon_series.imaging_plane.origin_coords[:],
            )
        nwbfile_new.read_io.close()
        nwbfile_old.read_io.close()


class TestBrukerTiffMultiPlaneConverterDisjointPlaneCase(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.folder_path = str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2022_11_03_IntoTheVoid_t_series-005"
        )
        cls.converter_kwargs = dict(folder_path=cls.folder_path, plane_separation_type="disjoint")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=FutureWarning)
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

    def test_deprecation_warning(self):
        with pytest.warns(FutureWarning, match="deprecated"):
            BrukerTiffMultiPlaneConverter(folder_path=self.folder_path, plane_separation_type="disjoint")

    def test_run_conversion_add_conversion_options(self):
        nwbfile_path = str(self.test_dir / "test_brukertiff_converter_conversion_options.nwb")
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            **self.conversion_options,
        )

        nwbfile = read_nwb(nwbfile_path)
        first_imaging_plane = nwbfile.imaging_planes[self.imaging_plane_names[0]]
        first_origin_coords = first_imaging_plane.origin_coords[:]

        second_imaging_plane = nwbfile.imaging_planes[self.imaging_plane_names[1]]
        second_origin_coords = second_imaging_plane.origin_coords[:]
        nwbfile.read_io.close()

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

        nwbfile = read_nwb(nwbfile_path)
        nwbfile.read_io.close()

        num_samples = nwbfile.acquisition[self.photon_series_names[0]].data.shape[0]
        self.assertEqual(num_samples, self.stub_samples)


class TestBrukerTiffMultiPlaneConverterContiguousPlaneCase(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.folder_path = str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2022_11_03_IntoTheVoid_t_series-005"
        )
        cls.converter_kwargs = dict(folder_path=cls.folder_path, plane_separation_type="contiguous")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=FutureWarning)
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

        nwbfile = read_nwb(nwbfile_path)
        nwbfile.read_io.close()

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

        nwbfile = read_nwb(nwbfile_path)
        nwbfile.read_io.close()

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

        nwbfile = read_nwb(nwbfile_path)
        nwbfile.read_io.close()

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

        nwbfile = read_nwb(nwbfile_path)
        nwbfile.read_io.close()

        num_samples = nwbfile.acquisition[self.photon_series_names[0]].data.shape[0]
        self.assertEqual(num_samples, self.stub_samples)
