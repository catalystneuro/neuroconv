import platform
import sys
from datetime import datetime

import numpy as np
import pytest

from neuroconv.datainterfaces import (
    CaimanSegmentationInterface,
    CnmfeSegmentationInterface,
    ExtractSegmentationInterface,
    InscopixSegmentationInterface,
    Suite2pSegmentationInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    SegmentationExtractorInterfaceTestMixin,
)

try:
    from ..setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from ..setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH


class TestCaimanSegmentationInterface(SegmentationExtractorInterfaceTestMixin):
    data_interface_cls = CaimanSegmentationInterface
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "caiman" / "caiman_analysis.hdf5")
    )
    save_directory = OUTPUT_PATH

    @pytest.fixture(
        params=[
            {"mask_type": "image", "include_background_segmentation": True},
            {"mask_type": "pixel", "include_background_segmentation": True},
            {"mask_type": "voxel", "include_background_segmentation": True},
            # {"mask_type": None, "include_background_segmentation": True}, # Uncomment when https://github.com/catalystneuro/neuroconv/issues/530 is resolved
            {"include_roi_centroids": False, "include_background_segmentation": True},
            {"include_roi_acceptance": False, "include_background_segmentation": True},
            {"include_background_segmentation": False},
        ],
        ids=[
            "mask_type_image",
            "mask_type_pixel",
            "mask_type_voxel",
            "exclude_roi_centroids",
            "exclude_roi_acceptance",
            "exclude_background_segmentation",
        ],
    )
    def setup_interface(self, request):

        test_id = request.node.callspec.id
        self.test_name = test_id
        self.interface_kwargs = self.interface_kwargs
        self.conversion_options = request.param
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name


class TestCnmfeSegmentationInterface(SegmentationExtractorInterfaceTestMixin):
    data_interface_cls = CnmfeSegmentationInterface
    interface_kwargs = dict(
        file_path=str(
            OPHYS_DATA_PATH / "segmentation_datasets" / "cnmfe" / "2014_04_01_p203_m19_check01_cnmfeAnalysis.mat"
        )
    )
    save_directory = OUTPUT_PATH


class TestExtractSegmentationInterface(SegmentationExtractorInterfaceTestMixin):
    data_interface_cls = ExtractSegmentationInterface
    save_directory = OUTPUT_PATH

    @pytest.fixture(
        params=[
            dict(
                file_path=str(
                    OPHYS_DATA_PATH
                    / "segmentation_datasets"
                    / "extract"
                    / "2014_04_01_p203_m19_check01_extractAnalysis.mat"
                ),
                sampling_frequency=15.0,  # typically provided by user
            ),
            dict(
                file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "extract" / "extract_public_output.mat"),
                sampling_frequency=15.0,  # typically provided by user
            ),
        ],
        ids=["dataset_1", "dataset_2"],
    )
    def setup_interface(self, request):
        test_id = request.node.callspec.id
        self.test_name = test_id
        self.interface_kwargs = request.param
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name


def test_extract_segmentation_interface_non_default_output_struct_name():
    """Test that the value for 'output_struct_name' is propagated to the extractor level
    where an error is raised."""
    file_path = OPHYS_DATA_PATH / "segmentation_datasets" / "extract" / "extract_public_output.mat"

    with pytest.raises(AssertionError, match="Output struct name 'not_output' not found in file."):
        ExtractSegmentationInterface(
            file_path=str(file_path),
            sampling_frequency=15.0,
            output_struct_name="not_output",
        )


class TestSuite2pSegmentationInterfaceChan1Plane0(SegmentationExtractorInterfaceTestMixin):
    data_interface_cls = Suite2pSegmentationInterface
    save_directory = OUTPUT_PATH
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"),
        channel_name="chan1",
        plane_name="plane0",
    )

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(self, request):
        cls = request.cls
        plane_suffix = "Chan1Plane0"
        cls.imaging_plane_names = "ImagingPlane" + plane_suffix
        cls.plane_segmentation_names = "PlaneSegmentation" + plane_suffix
        cls.mean_image_names = "MeanImage" + plane_suffix
        cls.correlation_image_names = "CorrelationImage" + plane_suffix
        cls.raw_traces_names = "RoiResponseSeries" + plane_suffix
        cls.neuropil_traces_names = "Neuropil" + plane_suffix
        cls.deconvolved_trace_name = "Deconvolved" + plane_suffix

    def test_check_extracted_metadata(self):
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        metadata = self.interface.get_metadata()

        assert metadata["Ophys"]["ImagingPlane"][0]["name"] == self.imaging_plane_names
        plane_segmentation_metadata = metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]
        plane_segmentation_name = self.plane_segmentation_names
        assert plane_segmentation_metadata["name"] == plane_segmentation_name
        summary_images_metadata = metadata["Ophys"]["SegmentationImages"][plane_segmentation_name]
        assert summary_images_metadata["correlation"]["name"] == self.correlation_image_names
        assert summary_images_metadata["mean"]["name"] == self.mean_image_names

        raw_traces_metadata = metadata["Ophys"]["Fluorescence"][plane_segmentation_name]["raw"]
        assert raw_traces_metadata["name"] == self.raw_traces_names
        neuropil_traces_metadata = metadata["Ophys"]["Fluorescence"][plane_segmentation_name]["neuropil"]
        assert neuropil_traces_metadata["name"] == self.neuropil_traces_names

        deconvolved_trace_metadata = metadata["Ophys"]["Fluorescence"][plane_segmentation_name]["deconvolved"]
        assert deconvolved_trace_metadata["name"] == self.deconvolved_trace_name


class TestSuite2pSegmentationInterfaceChan2Plane0(SegmentationExtractorInterfaceTestMixin):
    data_interface_cls = Suite2pSegmentationInterface
    save_directory = OUTPUT_PATH
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"),
        channel_name="chan2",
        plane_name="plane0",
    )

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(self, request):
        cls = request.cls

        plane_suffix = "Chan2Plane0"
        cls.imaging_plane_names = "ImagingPlane" + plane_suffix
        cls.plane_segmentation_names = "PlaneSegmentation" + plane_suffix
        cls.mean_image_names = "MeanImage" + plane_suffix
        cls.correlation_image_names = "CorrelationImage" + plane_suffix
        cls.raw_traces_names = "RoiResponseSeries" + plane_suffix
        cls.neuropil_traces_names = "Neuropil" + plane_suffix
        cls.deconvolved_trace_name = None

    def test_check_extracted_metadata(self):
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        metadata = self.interface.get_metadata()

        assert metadata["Ophys"]["ImagingPlane"][0]["name"] == self.imaging_plane_names
        plane_segmentation_metadata = metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]
        plane_segmentation_name = self.plane_segmentation_names
        assert plane_segmentation_metadata["name"] == plane_segmentation_name
        summary_images_metadata = metadata["Ophys"]["SegmentationImages"][plane_segmentation_name]
        assert summary_images_metadata["correlation"]["name"] == self.correlation_image_names
        assert summary_images_metadata["mean"]["name"] == self.mean_image_names

        raw_traces_metadata = metadata["Ophys"]["Fluorescence"][plane_segmentation_name]["raw"]
        assert raw_traces_metadata["name"] == self.raw_traces_names
        neuropil_traces_metadata = metadata["Ophys"]["Fluorescence"][plane_segmentation_name]["neuropil"]
        assert neuropil_traces_metadata["name"] == self.neuropil_traces_names

        if self.deconvolved_trace_name:
            deconvolved_trace_metadata = metadata["Ophys"]["Fluorescence"][plane_segmentation_name]["deconvolved"]
            assert deconvolved_trace_metadata["name"] == self.deconvolved_trace_name


class TestSuite2pSegmentationInterfaceWithStubTest(SegmentationExtractorInterfaceTestMixin):
    data_interface_cls = Suite2pSegmentationInterface
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"),
        channel_name="chan1",
        plane_name="plane0",
    )
    save_directory = OUTPUT_PATH
    conversion_options = dict(stub_test=True)


skip_on_darwin_arm64 = pytest.mark.skipif(
    platform.system() == "Darwin" and platform.machine() == "arm64",
    reason="The isx package is currently not natively supported on macOS with Apple Silicon. "
    "Installation instructions can be found at: "
    "https://github.com/inscopix/pyisx?tab=readme-ov-file#install",
)
skip_on_python_313 = pytest.mark.skipif(
    sys.version_info >= (3, 13),
    reason="Tests are skipped on Python 3.13 because of incompatibility with the 'isx' module "
    "Requires: Python <3.13, >=3.9)"
    "See:https://github.com/inscopix/pyisx/issues",
)
@skip_on_darwin_arm64
@skip_on_python_313
class TestInscopixSegmentationInterfaceCellSet(SegmentationExtractorInterfaceTestMixin):
    """Tests for InscopixSegmentationInterface."""

    data_interface_cls = InscopixSegmentationInterface
    interface_kwargs = dict(file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "inscopix" / "cellset.isxd"))
    save_directory = OUTPUT_PATH
    conversion_options = dict(mask_type="pixel")

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(self, request):
        """Set up expected metadata values."""
        cls = request.cls

        # Expected session and device metadata from Inscopix file
        cls.expected_session_name = "FV4581_Ret"
        cls.expected_experimenter_name = "Bei-Xuan"
        cls.expected_device_name = "NVista3"  # Actual device name from metadata
        cls.expected_device_serial = "11132301"
        cls.expected_animal_id = "FV4581"
        cls.expected_species = "Unknown species"  # This gets processed into strain
        cls.expected_strain = "CaMKIICre"
        cls.expected_sex = "M"  
        cls.expected_sampling_rate = 9.998700168978033

        # NWB component names
        cls.imaging_plane_name = "ImagingPlane"
        cls.plane_segmentation_name = "PlaneSegmentation"
        cls.roi_response_series_name = "RoiResponseSeries"

    def check_extracted_metadata(self, metadata):
        """Check that the extracted metadata contains expected Inscopix-specific items."""

        # Check session start time extraction
        assert "session_start_time" in metadata["NWBFile"]
        session_start_time = metadata["NWBFile"]["session_start_time"]
        assert isinstance(session_start_time, datetime)
        assert session_start_time.year == 2021
        assert session_start_time.month == 4
        assert session_start_time.day == 1

        # Check session description includes key information
        assert "session_description" in metadata["NWBFile"]
        session_desc = metadata["NWBFile"]["session_description"]
        assert self.expected_session_name in session_desc

        # Check experimenter information
        assert "experimenter" in metadata["NWBFile"]
        experimenter = metadata["NWBFile"]["experimenter"]
        if isinstance(experimenter, list):
            assert self.expected_experimenter_name in experimenter
        else:
            assert experimenter == self.expected_experimenter_name

        # Check device information extraction
        device_list = metadata["Ophys"]["Device"]
        if isinstance(device_list, list):
            device_metadata = device_list[0]
        else:
            device_metadata = device_list

        assert device_metadata["name"] == self.expected_device_name
        assert "description" in device_metadata
        assert "Inscopix" in device_metadata["description"]
        assert self.expected_device_serial in device_metadata["description"]

        # Check subject information extraction
        assert "Subject" in metadata
        subject = metadata["Subject"]
        assert subject["subject_id"] == self.expected_animal_id
        assert subject["species"] == self.expected_species
        assert "strain" in subject
        assert subject["strain"] == self.expected_strain
        assert subject["sex"] == self.expected_sex

        # Check imaging plane metadata
        assert "ImagingPlane" in metadata["Ophys"]
        assert len(metadata["Ophys"]["ImagingPlane"]) == 1

        imaging_plane = metadata["Ophys"]["ImagingPlane"][0]

        assert imaging_plane["name"] == self.imaging_plane_name
        assert "optical_channel" in imaging_plane
        assert "device" in imaging_plane
        assert imaging_plane["device"] == self.expected_device_name

        # Check imaging rate extraction
        assert "imaging_rate" in imaging_plane
        np.testing.assert_allclose(imaging_plane["imaging_rate"], self.expected_sampling_rate, rtol=1e-3)

        # Check field of view is included in description
        assert "field of view" in imaging_plane["description"]
        assert "398x366 pixels" in imaging_plane["description"]

        # Check optical channel information
        optical_channels = imaging_plane["optical_channel"]
        if isinstance(optical_channels, list):
            assert len(optical_channels) == 1
            optical_channel = optical_channels[0]
        else:
            optical_channel = optical_channels

        assert "description" in optical_channel
        assert optical_channel["name"] == "OpticalChannelGreen"
        assert "LED power" in optical_channel["description"]

        # Check plane segmentation naming
        assert "plane_segmentations" in metadata["Ophys"]["ImageSegmentation"]
        plane_segmentation_metadata = metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]
        assert plane_segmentation_metadata["name"] == self.plane_segmentation_name

        # Check segmentation description includes method and ROI count
        segmentation_desc = metadata["Ophys"]["ImageSegmentation"]["description"]
        assert "Inscopix cell segmentation" in segmentation_desc
        assert "cnmfe" in segmentation_desc
        assert "4 ROIs" in segmentation_desc

        # Check fluorescence metadata
        assert "Fluorescence" in metadata["Ophys"]
        assert self.plane_segmentation_name in metadata["Ophys"]["Fluorescence"]
        assert "raw" in metadata["Ophys"]["Fluorescence"][self.plane_segmentation_name]
        raw_traces_metadata = metadata["Ophys"]["Fluorescence"][self.plane_segmentation_name]["raw"]
        assert raw_traces_metadata["name"] == self.roi_response_series_name


@skip_on_darwin_arm64
@skip_on_python_313
class TestInscopixSegmentationInterfaceCellSetPart1(SegmentationExtractorInterfaceTestMixin):
    """Tests for InscopixSegmentationInterface with the cellset_series_part1 dataset."""

    data_interface_cls = InscopixSegmentationInterface
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "inscopix" / "cellset_series_part1.isxd")
    )
    save_directory = OUTPUT_PATH
    conversion_options = dict(mask_type="pixel")

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(self, request):
        """Set up expected metadata values."""
        cls = request.cls

        # Expected sampling rate for this dataset
        cls.expected_sampling_rate = 10.0
        cls.expected_device_name = "Microscope" 
        cls.expected_roi_count = 6

        # Expected session and device metadata from Inscopix file
        cls.expected_subject_id = "Unknown"
        cls.expected_species = "Unknown species"
        cls.expected_sex = "U"  

        # NWB component names
        cls.imaging_plane_name = "ImagingPlane"
        cls.plane_segmentation_name = "PlaneSegmentation"
        cls.roi_response_series_name = "RoiResponseSeries"

    def check_extracted_metadata(self, metadata):
        """Check that the extracted metadata contains expected items."""

        # Check device has proper default name
        device_list = metadata["Ophys"]["Device"]
        if isinstance(device_list, list):
            device_metadata = device_list[0]
        else:
            device_metadata = device_list
        assert device_metadata["name"] == self.expected_device_name

        # Check subject has defaults
        assert "Subject" in metadata
        subject = metadata["Subject"]
        assert subject["subject_id"] == self.expected_subject_id
        assert subject["species"] == self.expected_species
        assert subject["sex"] == self.expected_sex

        # Check imaging plane metadata
        assert "ImagingPlane" in metadata["Ophys"]
        assert len(metadata["Ophys"]["ImagingPlane"]) == 1
        imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
        assert imaging_plane["name"] == self.imaging_plane_name
        assert imaging_plane["device"] == self.expected_device_name

        # Check field of view is included in description
        assert "field of view" in imaging_plane["description"]
        assert "21x21 pixels" in imaging_plane["description"]

        # Check sampling rate extraction
        assert "imaging_rate" in imaging_plane
        np.testing.assert_allclose(imaging_plane["imaging_rate"], self.expected_sampling_rate, rtol=1e-3)

        # Check optical channel has default name
        optical_channels = imaging_plane["optical_channel"]
        if isinstance(optical_channels, list):
            optical_channel = optical_channels[0]
        else:
            optical_channel = optical_channels
        assert optical_channel["name"] == "OpticalChannelDefault"

        # Check plane segmentation naming
        assert "plane_segmentations" in metadata["Ophys"]["ImageSegmentation"]
        plane_segmentation_metadata = metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]
        assert plane_segmentation_metadata["name"] == self.plane_segmentation_name

        # Check segmentation description includes ROI count
        segmentation_desc = metadata["Ophys"]["ImageSegmentation"]["description"]
        assert "Inscopix cell segmentation" in segmentation_desc
        assert f"{self.expected_roi_count}" in segmentation_desc

        # Check fluorescence metadata
        assert "Fluorescence" in metadata["Ophys"]
        assert self.plane_segmentation_name in metadata["Ophys"]["Fluorescence"]
        assert "raw" in metadata["Ophys"]["Fluorescence"][self.plane_segmentation_name]
        raw_traces_metadata = metadata["Ophys"]["Fluorescence"][self.plane_segmentation_name]["raw"]
        assert raw_traces_metadata["name"] == self.roi_response_series_name

 
@skip_on_darwin_arm64
@skip_on_python_313
class TestInscopixSegmentationInterfaceEmptyCellSet(SegmentationExtractorInterfaceTestMixin):
    """Tests for InscopixSegmentationInterface with an empty cellset dataset."""

    data_interface_cls = InscopixSegmentationInterface
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "inscopix" / "empty_cellset.isxd")
    )
    save_directory = OUTPUT_PATH
    conversion_options = dict(mask_type="pixel")

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(self, request):
        """Set up expected metadata values."""
        cls = request.cls
        
        # Expected sampling rate for this empty dataset
        cls.expected_sampling_rate = 40.0

    def check_extracted_metadata(self, metadata):
        """Check that the extracted metadata contains expected items for empty dataset."""
        # Basic structure validation - should work even for empty datasets
        assert "NWBFile" in metadata
        assert "Ophys" in metadata
        assert "Device" in metadata["Ophys"]
        assert "ImageSegmentation" in metadata["Ophys"]

        # Check that we still have imaging plane metadata even with no ROIs
        assert "ImagingPlane" in metadata["Ophys"]
        assert len(metadata["Ophys"]["ImagingPlane"]) == 1
        imaging_plane = metadata["Ophys"]["ImagingPlane"][0]

        # Check sampling rate extraction even for empty dataset
        assert "imaging_rate" in imaging_plane
        np.testing.assert_allclose(imaging_plane["imaging_rate"], self.expected_sampling_rate, rtol=1e-3)

    def test_no_metadata_mutation(self, setup_interface):
        """Override test_no_metadata_mutation to handle the expected ValueError."""
        from copy import deepcopy

        from pynwb.testing.mock.file import mock_NWBFile

        nwbfile = mock_NWBFile()
        metadata = self.interface.get_metadata()
        metadata_before_add_method = deepcopy(metadata)

        # We expect ValueError when trying to add segmentation with no ROIs
        with pytest.raises(ValueError, match="need at least one array to stack"):
            self.interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **self.conversion_options)

        # Check that metadata wasn't modified even though an error was raised
        assert metadata == metadata_before_add_method

    def test_run_conversion_with_backend(self, setup_interface, tmp_path, backend="hdf5"):
        """Override test_run_conversion_with_backend to handle the expected ValueError."""
        nwbfile_path = str(tmp_path / f"conversion_with_backend{backend}-{self.test_name}.nwb")

        metadata = self.interface.get_metadata()
        if "session_start_time" not in metadata["NWBFile"]:
            metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())

        # We expect ValueError when trying to convert with no ROIs
        with pytest.raises(ValueError, match="need at least one array to stack"):
            self.interface.run_conversion(
                nwbfile_path=nwbfile_path,
                overwrite=True,
                metadata=metadata,
                backend=backend,
                **self.conversion_options,
            )

    # Override tests that would fail with ValueError for empty datasets
    def test_run_conversion_with_backend_configuration(self, setup_interface, tmp_path, backend="hdf5"):
        pytest.skip("Test not applicable for empty datasets expected to raise ValueError")

    def test_configure_backend_for_equivalent_nwbfiles(self, setup_interface, backend="hdf5"):
        pytest.skip("Test not applicable for empty datasets expected to raise ValueError")

    def test_all_conversion_checks(self, setup_interface, tmp_path):
        pytest.skip("Test not applicable for empty datasets expected to raise ValueError")

    def check_read_nwb(self, nwbfile_path: str):
        """Override to skip NWB read check for empty datasets."""
        pytest.skip("Cannot read NWB file for empty datasets that raise ValueError during conversion")
