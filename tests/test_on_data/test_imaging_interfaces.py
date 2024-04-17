import platform
from datetime import datetime
from pathlib import Path
from unittest import TestCase, skipIf

import numpy as np
import pytest
from dateutil.tz import tzoffset
from hdmf.testing import TestCase as hdmf_TestCase
from numpy.testing import assert_array_equal
from parameterized import parameterized_class
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import (
    BrukerTiffMultiPlaneImagingInterface,
    BrukerTiffSinglePlaneImagingInterface,
    Hdf5ImagingInterface,
    MicroManagerTiffImagingInterface,
    MiniscopeImagingInterface,
    SbxImagingInterface,
    ScanImageMultiPlaneImagingInterface,
    ScanImageMultiPlaneMultiFileImagingInterface,
    ScanImageSinglePlaneImagingInterface,
    ScanImageSinglePlaneMultiFileImagingInterface,
    TiffImagingInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    ImagingExtractorInterfaceTestMixin,
    MiniscopeImagingInterfaceMixin,
    ScanImageMultiPlaneImagingInterfaceMixin,
    ScanImageSinglePlaneImagingInterfaceMixin,
    ScanImageSinglePlaneMultiFileImagingInterfaceMixin,
)

try:
    from .setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH


class TestTiffImagingInterface(ImagingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = TiffImagingInterface
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "demoMovie.tif"),
        sampling_frequency=15.0,  # typically provided by user
    )
    save_directory = OUTPUT_PATH


@parameterized_class(
    [
        {
            "plane_name": "0",
            "channel_name": "Channel 1",
            "photon_series_name": "TwoPhotonSeriesChannel1Plane0",
            "imaging_plane_name": "ImagingPlaneChannel1Plane0",
        },
        {
            "plane_name": "1",
            "channel_name": "Channel 1",
            "photon_series_name": "TwoPhotonSeriesChannel1Plane1",
            "imaging_plane_name": "ImagingPlaneChannel1Plane1",
        },
        {
            "plane_name": "0",
            "channel_name": "Channel 4",
            "photon_series_name": "TwoPhotonSeriesChannel4Plane0",
            "imaging_plane_name": "ImagingPlaneChannel4Plane0",
        },
        {
            "plane_name": "1",
            "channel_name": "Channel 4",
            "photon_series_name": "TwoPhotonSeriesChannel4Plane1",
            "imaging_plane_name": "ImagingPlaneChannel4Plane1",
        },
    ],
)
class TestScanImageSinglePlaneImagingInterface(ScanImageSinglePlaneImagingInterfaceMixin, TestCase):
    data_interface_cls = ScanImageSinglePlaneImagingInterface
    save_directory = OUTPUT_PATH
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"),
    )

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 9, 22, 12, 51, 34, 124000)

    def test_not_recognized_scanimage_version(self):
        """Test that ValueError is returned when ScanImage version could not be determined from metadata."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "demoMovie.tif")
        with self.assertRaisesRegex(ValueError, "ScanImage version could not be determined from metadata."):
            self.data_interface_cls(file_path=file_path)

    def test_not_supported_scanimage_version(self):
        """Test that the interface raises ValueError for older ScanImage format and suggests to use a different interface."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "sample_scanimage.tiff")
        with self.assertRaisesRegex(ValueError, "ScanImage version 3.8 is not supported."):
            self.data_interface_cls(file_path=file_path)

    def test_channel_name_not_specified(self):
        """Test that ValueError is raised when channel_name is not specified for data with multiple channels."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20240320_multifile_00001.tif")
        with self.assertRaisesRegex(ValueError, "More than one channel is detected!"):
            self.data_interface_cls(file_path=file_path)

    def test_incorrect_channel_name(self):
        """Test that ValueError is raised when incorrect channel name is specified."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif")
        channel_name = "Channel 2"
        with self.assertRaisesRegex(AssertionError, "Channel 'Channel 2' not found in the tiff file."):
            self.data_interface_cls(file_path=file_path, channel_name=channel_name)

    def test_plane_name_not_specified(self):
        """Test that ValueError is raised when plane_name is not specified for data with multiple planes."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220801_volume.tif")
        with self.assertRaisesRegex(ValueError, "More than one plane is detected!"):
            self.data_interface_cls(file_path=file_path)


@parameterized_class(
    [
        {
            "channel_name": "Channel 1",
            "photon_series_name": "TwoPhotonSeriesChannel1",
            "imaging_plane_name": "ImagingPlaneChannel1",
        },
        {
            "channel_name": "Channel 4",
            "photon_series_name": "TwoPhotonSeriesChannel4",
            "imaging_plane_name": "ImagingPlaneChannel4",
        },
    ],
)
class TestScanImageMultiPlaneImagingInterface(ScanImageMultiPlaneImagingInterfaceMixin, TestCase):
    data_interface_cls = ScanImageMultiPlaneImagingInterface
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"),
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 9, 22, 12, 51, 34, 124000)

    def test_not_supported_scanimage_version(self):
        """Test that the interface raises ValueError for older ScanImage format and suggests to use a different interface."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "sample_scanimage.tiff")
        with self.assertRaisesRegex(ValueError, "ScanImage version 3.8 is not supported."):
            self.data_interface_cls(file_path=file_path)

    def test_non_volumetric_data(self):
        """Test that ValueError is raised for non-volumetric imaging data."""

        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20240320_multifile_00001.tif")
        channel_name = "Channel 1"
        with self.assertRaisesRegex(
            ValueError,
            "Only one plane detected. For single plane imaging data use ScanImageSinglePlaneImagingInterface instead.",
        ):
            self.data_interface_cls(file_path=file_path, channel_name=channel_name)

    def test_channel_name_not_specified(self):
        """Test that ValueError is raised when channel_name is not specified for data with multiple channels."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif")
        with self.assertRaisesRegex(ValueError, "More than one channel is detected!"):
            self.data_interface_cls(file_path=file_path)


@parameterized_class(
    [
        {
            "channel_name": "Channel 1",
            "photon_series_name": "TwoPhotonSeriesChannel1",
            "imaging_plane_name": "ImagingPlaneChannel1",
        },
        {
            "channel_name": "Channel 2",
            "photon_series_name": "TwoPhotonSeriesChannel2",
            "imaging_plane_name": "ImagingPlaneChannel2",
        },
    ],
)
class TestScanImageSinglePlaneMultiFileImagingInterface(ScanImageSinglePlaneMultiFileImagingInterfaceMixin, TestCase):
    data_interface_cls = ScanImageSinglePlaneMultiFileImagingInterface
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage"),
        file_pattern="scanimage_20240320_multifile*.tif",
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2024, 3, 26, 15, 7, 53, 110000)

    def test_not_recognized_scanimage_version(self):
        """Test that ValueError is returned when ScanImage version could not be determined from metadata."""
        folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif")
        file_pattern = "*.tif"
        with self.assertRaisesRegex(ValueError, "ScanImage version could not be determined from metadata."):
            self.data_interface_cls(folder_path=folder_path, file_pattern=file_pattern)

    def test_not_supported_scanimage_version(self):
        """Test that the interface raises ValueError for older ScanImage format and suggests to use a different interface."""
        folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif")
        file_pattern = "sample_scanimage.tiff"
        with self.assertRaisesRegex(
            ValueError, "ScanImage version 3.8 is not supported. Please use ScanImageImagingInterface instead."
        ):
            self.data_interface_cls(folder_path=folder_path, file_pattern=file_pattern)

    def test_channel_name_not_specified(self):
        """Test that ValueError is raised when channel_name is not specified for data with multiple channels."""
        folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage")
        file_pattern = "scanimage_20240320_multifile*.tif"
        with self.assertRaisesRegex(ValueError, "More than one channel is detected!"):
            self.data_interface_cls(folder_path=folder_path, file_pattern=file_pattern)

    def test_plane_name_not_specified(self):
        """Test that ValueError is raised when plane_name is not specified for data with multiple planes."""
        folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage")
        file_pattern = "scanimage_20220801_volume.tif"
        with self.assertRaisesRegex(ValueError, "More than one plane is detected!"):
            self.data_interface_cls(folder_path=folder_path, file_pattern=file_pattern)


@parameterized_class(
    [
        {
            "channel_name": "Channel 1",
            "photon_series_name": "TwoPhotonSeriesChannel1",
            "imaging_plane_name": "ImagingPlaneChannel1",
        },
        {
            "channel_name": "Channel 4",
            "photon_series_name": "TwoPhotonSeriesChannel4",
            "imaging_plane_name": "ImagingPlaneChannel4",
        },
    ],
)
class TestScanImageMultiPlaneMultiFileImagingInterface(ScanImageMultiPlaneImagingInterfaceMixin, TestCase):
    data_interface_cls = ScanImageMultiPlaneMultiFileImagingInterface
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage"),
        file_pattern="scanimage_20220923_roi.tif",
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 9, 22, 12, 51, 34, 124000)

    def test_not_supported_scanimage_version(self):
        """Test that the interface raises ValueError for older ScanImage format and suggests to use a different interface."""
        folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif")
        file_pattern = "sample_scanimage.tiff"
        with self.assertRaisesRegex(
            ValueError, "ScanImage version 3.8 is not supported. Please use ScanImageImagingInterface instead."
        ):
            self.data_interface_cls(folder_path=folder_path, file_pattern=file_pattern)

    def test_non_volumetric_data(self):
        """Test that ValueError is raised for non-volumetric imaging data."""

        folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage")
        file_pattern = "scanimage_20240320_multifile*.tif"
        channel_name = "Channel 1"
        with self.assertRaisesRegex(
            ValueError,
            "Only one plane detected. For single plane imaging data use ScanImageSinglePlaneMultiFileImagingInterface instead.",
        ):
            self.data_interface_cls(folder_path=folder_path, file_pattern=file_pattern, channel_name=channel_name)

    def test_channel_name_not_specified(self):
        """Test that ValueError is raised when channel_name is not specified for data with multiple channels."""
        folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage")
        file_pattern = "scanimage_20220923_roi.tif"
        with self.assertRaisesRegex(ValueError, "More than one channel is detected!"):
            self.data_interface_cls(folder_path=folder_path, file_pattern=file_pattern)


class TestHdf5ImagingInterface(ImagingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = Hdf5ImagingInterface
    interface_kwargs = dict(file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "hdf5" / "demoMovie.hdf5"))
    save_directory = OUTPUT_PATH


class TestSbxImagingInterface(ImagingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = SbxImagingInterface
    interface_kwargs = [
        dict(file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Scanbox" / f"sample.mat")),
        dict(file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Scanbox" / f"sample.sbx")),
    ]
    save_directory = OUTPUT_PATH


class TestBrukerTiffImagingInterface(ImagingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = BrukerTiffSinglePlaneImagingInterface
    interface_kwargs = dict(
        folder_path=str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2023_02_20_Into_the_void_t_series_baseline-000"
        )
    )
    save_directory = OUTPUT_PATH

    @classmethod
    def setUpClass(cls) -> None:
        cls.device_metadata = dict(name="BrukerFluorescenceMicroscope", description="Version 5.6.64.400")
        cls.optical_channel_metadata = dict(
            name="Ch2",
            emission_lambda=np.NAN,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlane",
            description="The imaging plane origin_coords units are in the microscope reference frame.",
            excitation_lambda=np.NAN,
            indicator="unknown",
            location="unknown",
            device=cls.device_metadata["name"],
            optical_channel=[cls.optical_channel_metadata],
            imaging_rate=29.873732099062256,
            grid_spacing=[1.1078125e-06, 1.1078125e-06],
            origin_coords=[0.0, 0.0],
        )

        cls.two_photon_series_metadata = dict(
            name="TwoPhotonSeries",
            description="Imaging data acquired from the Bruker Two-Photon Microscope.",
            unit="n.a.",
            dimension=[512, 512],
            imaging_plane=cls.imaging_plane_metadata["name"],
            scan_line_rate=15840.580398865815,
            field_of_view=[0.0005672, 0.0005672],
        )

        cls.ophys_metadata = dict(
            Device=[cls.device_metadata],
            ImagingPlane=[cls.imaging_plane_metadata],
            TwoPhotonSeries=[cls.two_photon_series_metadata],
        )

    def check_extracted_metadata(self, metadata: dict):
        self.assertEqual(metadata["NWBFile"]["session_start_time"], datetime(2023, 2, 20, 15, 58, 25))
        self.assertDictEqual(metadata["Ophys"], self.ophys_metadata)

    def check_read_nwb(self, nwbfile_path: str):
        """Check the ophys metadata made it to the NWB file"""

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            self.assertIn(self.device_metadata["name"], nwbfile.devices)
            self.assertEqual(
                nwbfile.devices[self.device_metadata["name"]].description, self.device_metadata["description"]
            )
            self.assertIn(self.imaging_plane_metadata["name"], nwbfile.imaging_planes)
            imaging_plane = nwbfile.imaging_planes[self.imaging_plane_metadata["name"]]
            optical_channel = imaging_plane.optical_channel[0]
            self.assertEqual(optical_channel.name, self.optical_channel_metadata["name"])
            self.assertEqual(optical_channel.description, self.optical_channel_metadata["description"])
            self.assertEqual(imaging_plane.description, self.imaging_plane_metadata["description"])
            self.assertEqual(imaging_plane.imaging_rate, self.imaging_plane_metadata["imaging_rate"])
            assert_array_equal(imaging_plane.grid_spacing[:], self.imaging_plane_metadata["grid_spacing"])
            self.assertIn(self.two_photon_series_metadata["name"], nwbfile.acquisition)
            two_photon_series = nwbfile.acquisition[self.two_photon_series_metadata["name"]]
            self.assertEqual(two_photon_series.description, self.two_photon_series_metadata["description"])
            self.assertEqual(two_photon_series.unit, self.two_photon_series_metadata["unit"])
            self.assertEqual(two_photon_series.scan_line_rate, self.two_photon_series_metadata["scan_line_rate"])
            assert_array_equal(two_photon_series.field_of_view[:], self.two_photon_series_metadata["field_of_view"])

        super().check_read_nwb(nwbfile_path=nwbfile_path)


class TestBrukerTiffImagingInterfaceDualPlaneCase(ImagingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = BrukerTiffMultiPlaneImagingInterface
    interface_kwargs = dict(
        folder_path=str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2022_11_03_IntoTheVoid_t_series-005"
        ),
    )
    save_directory = OUTPUT_PATH

    @classmethod
    def setUpClass(cls) -> None:
        cls.photon_series_name = "TwoPhotonSeries"
        cls.num_frames = 5
        cls.image_shape = (512, 512, 2)
        cls.device_metadata = dict(name="BrukerFluorescenceMicroscope", description="Version 5.6.64.400")
        cls.available_streams = dict(channel_streams=["Ch2"], plane_streams=dict(Ch2=["Ch2_000001"]))
        cls.optical_channel_metadata = dict(
            name="Ch2",
            emission_lambda=np.NAN,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlane",
            description="The imaging plane origin_coords units are in the microscope reference frame.",
            excitation_lambda=np.NAN,
            indicator="unknown",
            location="unknown",
            device=cls.device_metadata["name"],
            optical_channel=[cls.optical_channel_metadata],
            imaging_rate=20.629515014336377,
            grid_spacing=[1.1078125e-06, 1.1078125e-06, 0.00026],
            origin_coords=[56.215, 14.927, 260.0],
        )

        cls.two_photon_series_metadata = dict(
            name="TwoPhotonSeries",
            description="The volumetric imaging data acquired from the Bruker Two-Photon Microscope.",
            unit="n.a.",
            dimension=[512, 512, 2],
            imaging_plane=cls.imaging_plane_metadata["name"],
            scan_line_rate=15842.086085895791,
            field_of_view=[0.0005672, 0.0005672, 0.00026],
        )

        cls.ophys_metadata = dict(
            Device=[cls.device_metadata],
            ImagingPlane=[cls.imaging_plane_metadata],
            TwoPhotonSeries=[cls.two_photon_series_metadata],
        )

    def run_custom_checks(self):
        # check stream names
        streams = self.data_interface_cls.get_streams(
            folder_path=self.interface_kwargs["folder_path"], plane_separation_type="contiguous"
        )
        self.assertEqual(streams, self.available_streams)

    def check_extracted_metadata(self, metadata: dict):
        self.assertEqual(metadata["NWBFile"]["session_start_time"], datetime(2022, 11, 3, 11, 20, 34))
        self.assertDictEqual(metadata["Ophys"], self.ophys_metadata)

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()
            photon_series = nwbfile.acquisition[self.photon_series_name]
            self.assertEqual(photon_series.data.shape, (self.num_frames, *self.image_shape))
            assert_array_equal(photon_series.dimension[:], self.image_shape)
            self.assertEqual(photon_series.rate, 20.629515014336377)


class TestBrukerTiffImagingInterfaceDualPlaneDisjointCase(ImagingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = BrukerTiffSinglePlaneImagingInterface
    interface_kwargs = dict(
        folder_path=str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2022_11_03_IntoTheVoid_t_series-005"
        ),
        stream_name="Ch2_000002",
    )
    save_directory = OUTPUT_PATH

    @classmethod
    def setUpClass(cls) -> None:
        cls.photon_series_name = "TwoPhotonSeriesCh2000002"
        cls.num_frames = 5
        cls.image_shape = (512, 512)
        cls.device_metadata = dict(name="BrukerFluorescenceMicroscope", description="Version 5.6.64.400")
        cls.available_streams = dict(channel_streams=["Ch2"], plane_streams=dict(Ch2=["Ch2_000001", "Ch2_000002"]))
        cls.optical_channel_metadata = dict(
            name="Ch2",
            emission_lambda=np.NAN,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlaneCh2000002",
            description="The imaging plane origin_coords units are in the microscope reference frame.",
            excitation_lambda=np.NAN,
            indicator="unknown",
            location="unknown",
            device=cls.device_metadata["name"],
            optical_channel=[cls.optical_channel_metadata],
            imaging_rate=10.314757507168189,
            grid_spacing=[1.1078125e-06, 1.1078125e-06, 0.00013],
            origin_coords=[56.215, 14.927, 130.0],
        )

        cls.two_photon_series_metadata = dict(
            name=cls.photon_series_name,
            description="Imaging data acquired from the Bruker Two-Photon Microscope.",
            unit="n.a.",
            dimension=[512, 512],
            imaging_plane=cls.imaging_plane_metadata["name"],
            scan_line_rate=15842.086085895791,
            field_of_view=[0.0005672, 0.0005672, 0.00013],
        )

        cls.ophys_metadata = dict(
            Device=[cls.device_metadata],
            ImagingPlane=[cls.imaging_plane_metadata],
            TwoPhotonSeries=[cls.two_photon_series_metadata],
        )

    def run_custom_checks(self):
        # check stream names
        streams = self.data_interface_cls.get_streams(folder_path=self.interface_kwargs["folder_path"])
        self.assertEqual(streams, self.available_streams)

    def check_extracted_metadata(self, metadata: dict):
        self.assertEqual(metadata["NWBFile"]["session_start_time"], datetime(2022, 11, 3, 11, 20, 34))
        self.assertDictEqual(metadata["Ophys"], self.ophys_metadata)

    def check_nwbfile_temporal_alignment(self):
        nwbfile_path = str(
            self.save_directory / f"{self.data_interface_cls.__name__}_{self.case}_test_starting_time_alignment.nwb"
        )

        interface = self.data_interface_cls(**self.test_kwargs)

        aligned_starting_time = 1.23
        interface.set_aligned_starting_time(aligned_starting_time=aligned_starting_time)

        metadata = interface.get_metadata()
        interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert nwbfile.acquisition[self.photon_series_name].starting_time == aligned_starting_time

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()
            photon_series = nwbfile.acquisition[self.photon_series_name]
            self.assertEqual(photon_series.data.shape, (self.num_frames, *self.image_shape))
            assert_array_equal(photon_series.dimension[:], self.image_shape)
            self.assertEqual(photon_series.rate, 10.314757507168189)


class TestBrukerTiffImagingInterfaceDualColorCase(ImagingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = BrukerTiffSinglePlaneImagingInterface
    interface_kwargs = dict(
        folder_path=str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR62_2023_07_06_IntoTheVoid_t_series_Dual_color-000"
        ),
        stream_name="Ch2",
    )
    save_directory = OUTPUT_PATH

    @classmethod
    def setUpClass(cls) -> None:
        cls.photon_series_name = "TwoPhotonSeriesCh2"
        cls.num_frames = 10
        cls.image_shape = (512, 512)
        cls.device_metadata = dict(name="BrukerFluorescenceMicroscope", description="Version 5.8.64.200")
        cls.available_streams = dict(channel_streams=["Ch1", "Ch2"], plane_streams=dict())
        cls.optical_channel_metadata = dict(
            name="Ch2",
            emission_lambda=np.NAN,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlaneCh2",
            description="The imaging plane origin_coords units are in the microscope reference frame.",
            excitation_lambda=np.NAN,
            indicator="unknown",
            location="unknown",
            device=cls.device_metadata["name"],
            optical_channel=[cls.optical_channel_metadata],
            imaging_rate=29.873615189896864,
            grid_spacing=[1.1078125e-06, 1.1078125e-06],
            origin_coords=[0.0, 0.0],
        )

        cls.two_photon_series_metadata = dict(
            name=cls.photon_series_name,
            description="Imaging data acquired from the Bruker Two-Photon Microscope.",
            unit="n.a.",
            dimension=[512, 512],
            imaging_plane=cls.imaging_plane_metadata["name"],
            scan_line_rate=15835.56350852745,
            field_of_view=[0.0005672, 0.0005672],
        )

        cls.ophys_metadata = dict(
            Device=[cls.device_metadata],
            ImagingPlane=[cls.imaging_plane_metadata],
            TwoPhotonSeries=[cls.two_photon_series_metadata],
        )

    def run_custom_checks(self):
        # check stream names
        streams = self.data_interface_cls.get_streams(folder_path=self.interface_kwargs["folder_path"])
        self.assertEqual(streams, self.available_streams)

    def check_extracted_metadata(self, metadata: dict):
        self.assertEqual(metadata["NWBFile"]["session_start_time"], datetime(2023, 7, 6, 15, 13, 58))
        self.assertDictEqual(metadata["Ophys"], self.ophys_metadata)

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()
            photon_series = nwbfile.acquisition[self.photon_series_name]
            self.assertEqual(photon_series.data.shape, (self.num_frames, *self.image_shape))
            assert_array_equal(photon_series.dimension[:], self.image_shape)
            self.assertEqual(photon_series.rate, 29.873615189896864)

    def check_nwbfile_temporal_alignment(self):
        nwbfile_path = str(
            self.save_directory / f"{self.data_interface_cls.__name__}_{self.case}_test_starting_time_alignment.nwb"
        )

        interface = self.data_interface_cls(**self.test_kwargs)

        aligned_starting_time = 1.23
        interface.set_aligned_starting_time(aligned_starting_time=aligned_starting_time)

        metadata = interface.get_metadata()
        interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert nwbfile.acquisition[self.photon_series_name].starting_time == aligned_starting_time


class TestMicroManagerTiffImagingInterface(ImagingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = MicroManagerTiffImagingInterface
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "MicroManagerTif" / "TS12_20220407_20hz_noteasy_1")
    )
    save_directory = OUTPUT_PATH

    @classmethod
    def setUpClass(cls) -> None:
        cls.device_metadata = dict(name="Microscope")
        cls.optical_channel_metadata = dict(
            name="OpticalChannelDefault",
            emission_lambda=np.NAN,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlane",
            description="The plane or volume being imaged by the microscope.",
            excitation_lambda=np.NAN,
            indicator="unknown",
            location="unknown",
            device=cls.device_metadata["name"],
            optical_channel=[cls.optical_channel_metadata],
            imaging_rate=20.0,
        )
        cls.two_photon_series_metadata = dict(
            name="TwoPhotonSeries",
            description="Imaging data from two-photon excitation microscopy.",
            unit="px",
            dimension=[1024, 1024],
            format="tiff",
            imaging_plane=cls.imaging_plane_metadata["name"],
        )

        cls.ophys_metadata = dict(
            Device=[cls.device_metadata],
            ImagingPlane=[cls.imaging_plane_metadata],
            TwoPhotonSeries=[cls.two_photon_series_metadata],
        )

    def check_extracted_metadata(self, metadata: dict):
        self.assertEqual(
            metadata["NWBFile"]["session_start_time"],
            datetime(2022, 4, 7, 15, 6, 56, 842000, tzinfo=tzoffset(None, -18000)),
        )
        self.assertDictEqual(metadata["Ophys"], self.ophys_metadata)

    def check_read_nwb(self, nwbfile_path: str):
        """Check the ophys metadata made it to the NWB file"""

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            self.assertIn(self.imaging_plane_metadata["name"], nwbfile.imaging_planes)
            imaging_plane = nwbfile.imaging_planes[self.imaging_plane_metadata["name"]]
            optical_channel = imaging_plane.optical_channel[0]
            self.assertEqual(optical_channel.name, self.optical_channel_metadata["name"])
            self.assertEqual(optical_channel.description, self.optical_channel_metadata["description"])
            self.assertEqual(imaging_plane.description, self.imaging_plane_metadata["description"])
            self.assertEqual(imaging_plane.imaging_rate, self.imaging_plane_metadata["imaging_rate"])
            self.assertIn(self.two_photon_series_metadata["name"], nwbfile.acquisition)
            two_photon_series = nwbfile.acquisition[self.two_photon_series_metadata["name"]]
            self.assertEqual(two_photon_series.description, self.two_photon_series_metadata["description"])
            self.assertEqual(two_photon_series.unit, self.two_photon_series_metadata["unit"])
            self.assertEqual(two_photon_series.format, self.two_photon_series_metadata["format"])
            assert_array_equal(two_photon_series.dimension[:], self.two_photon_series_metadata["dimension"])

        super().check_read_nwb(nwbfile_path=nwbfile_path)


class TestMiniscopeImagingInterface(MiniscopeImagingInterfaceMixin, hdmf_TestCase):
    data_interface_cls = MiniscopeImagingInterface
    interface_kwargs = dict(folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "C6-J588_Disc5"))
    save_directory = OUTPUT_PATH

    @classmethod
    def setUpClass(cls) -> None:
        cls.device_name = "Miniscope"
        cls.imaging_plane_name = "ImagingPlane"
        cls.photon_series_name = "OnePhotonSeries"

        cls.device_metadata = dict(
            name=cls.device_name,
            compression="FFV1",
            deviceType="Miniscope_V3",
            frameRate="15FPS",
            framesPerFile=1000,
            gain="High",
            led0=47,
        )

    def check_extracted_metadata(self, metadata: dict):
        self.assertEqual(
            metadata["NWBFile"]["session_start_time"],
            datetime(2021, 10, 7, 15, 3, 28, 635),
        )
        self.assertEqual(metadata["Ophys"]["Device"][0], self.device_metadata)
        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
        self.assertEqual(imaging_plane_metadata["name"], self.imaging_plane_name)
        self.assertEqual(imaging_plane_metadata["device"], self.device_name)
        self.assertEqual(imaging_plane_metadata["imaging_rate"], 15.0)

        one_photon_series_metadata = metadata["Ophys"]["OnePhotonSeries"][0]
        self.assertEqual(one_photon_series_metadata["name"], self.photon_series_name)
        self.assertEqual(one_photon_series_metadata["unit"], "px")

    def run_custom_checks(self):
        self.check_incorrect_folder_structure_raises()

    def check_incorrect_folder_structure_raises(self):
        folder_path = Path(self.interface_kwargs["folder_path"]) / "15_03_28/BehavCam_2/"
        with self.assertRaisesWith(
            exc_type=AssertionError, exc_msg="The main folder should contain at least one subfolder named 'Miniscope'."
        ):
            self.data_interface_cls(folder_path=folder_path)
