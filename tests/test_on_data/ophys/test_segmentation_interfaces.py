import platform
import sys
import tempfile
from datetime import datetime

import numpy as np
import pytest
from numpy.testing import assert_array_almost_equal
from pynwb import NWBHDF5IO, NWBFile

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


class TestCaimanSegmentationInterfaceCaimanAnalysis(SegmentationExtractorInterfaceTestMixin):
    data_interface_cls = CaimanSegmentationInterface
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "caiman" / "caiman_analysis.hdf5")
    )
    save_directory = OUTPUT_PATH

    def test_quality_metrics_absent(self):
        """Test that interface handles missing quality metrics gracefully."""
        interface = self.data_interface_cls(**self.interface_kwargs)
        extractor = interface.segmentation_extractor

        # Check that no quality metrics properties are available
        property_keys = extractor.get_property_keys()
        assert "snr" not in property_keys
        assert "r_values" not in property_keys
        assert "cnn_preds" not in property_keys

        # Test that NWB file is created without quality metrics columns
        with tempfile.TemporaryDirectory() as temp_dir:
            nwbfile_path = f"{temp_dir}/test_caiman_no_quality_metrics.nwb"
            nwbfile = NWBFile(
                session_description="test session",
                identifier="test_id",
                session_start_time=datetime.now(),
            )

            # Add the interface data to NWB file with quality metrics enabled
            # (should not add any since none are available)
            interface.add_to_nwbfile(nwbfile, include_quality_metrics=True)

            # Write NWB file to disk
            with NWBHDF5IO(nwbfile_path, "w") as io:
                io.write(nwbfile)

            # Read back the NWB file and check PlaneSegmentation table
            with NWBHDF5IO(nwbfile_path, "r") as io:
                nwbfile = io.read()
                plane_segmentation = nwbfile.processing["ophys"]["ImageSegmentation"]["PlaneSegmentation"]

                # Check that NO quality metrics columns exist
                assert "snr" not in plane_segmentation.colnames
                assert "r_values" not in plane_segmentation.colnames
                assert "cnn_preds" not in plane_segmentation.colnames

                # But standard columns should still exist
                assert "roi_name" in plane_segmentation.colnames
                assert "Accepted" in plane_segmentation.colnames
                assert "Rejected" in plane_segmentation.colnames


class TestCaimanSegmentationInterface450(SegmentationExtractorInterfaceTestMixin):
    """Test class for CaImAn interface with a file containing quality metrics."""

    data_interface_cls = CaimanSegmentationInterface
    interface_kwargs = dict(
        file_path=(
            OPHYS_DATA_PATH
            / "segmentation_datasets"
            / "caiman"
            / "multi_plane_with_imaging_data"
            / "mini_450_caiman_stubbed_10units_5frames.hdf5"
        )
    )
    save_directory = OUTPUT_PATH

    def test_quality_metrics_values(self):
        """Test that PlaneSegmentation table is correctly populated with quality metrics."""
        interface = self.data_interface_cls(**self.interface_kwargs)
        extractor = interface.segmentation_extractor
        roi_ids = extractor.get_roi_ids()

        # Test quality metrics as properties
        property_keys = extractor.get_property_keys()
        assert "snr" == property_keys[property_keys.index("snr")]
        assert "r_values" == property_keys[property_keys.index("r_values")]
        assert "cnn_preds" not in property_keys

        # Test getting quality metrics via property interface
        expected_snr = np.array(
            [
                0.82003892,
                1.46365421,
                2.37001396,
                1.26491304,
                0.88042214,
                0.57378107,
                1.91813623,
                1.51477906,
                1.34824757,
                4.61553793,
            ]
        )
        snr_property = extractor.get_property(key="snr", ids=roi_ids)
        assert_array_almost_equal(snr_property, expected_snr, decimal=6)

        expected_r_values = np.array(
            [
                -0.09622008,
                0.75080916,
                0.46274736,
                0.14843417,
                -0.01086164,
                0.32011244,
                -0.06491879,
                -0.12745297,
                -0.10657519,
                -0.37634573,
            ]
        )
        r_values_property = extractor.get_property(key="r_values", ids=roi_ids)
        assert_array_almost_equal(r_values_property, expected_r_values, decimal=6)

        # Test that quality metrics are actually written to NWB PlaneSegmentation table using NWBHDF5IO
        with tempfile.TemporaryDirectory() as temp_dir:
            nwbfile_path = f"{temp_dir}/test_caiman_quality_metrics.nwb"
            nwbfile = NWBFile(
                session_description="test session",
                identifier="test_id",
                session_start_time=datetime.now(),
            )
            # Add the interface data to NWB file - this should populate PlaneSegmentation with quality metrics
            interface.add_to_nwbfile(nwbfile)
            # Write NWB file to disk
            with NWBHDF5IO(nwbfile_path, "w") as io:
                io.write(nwbfile)
            # Read back the NWB file and check PlaneSegmentation table
            with NWBHDF5IO(nwbfile_path, "r") as io:
                nwbfile = io.read()
                plane_segmentation = nwbfile.processing["ophys"]["ImageSegmentation"]["PlaneSegmentation"]
                # Check that the quality metrics columns exist in the actual NWB PlaneSegmentation table
                assert "snr" in plane_segmentation.colnames, "SNR column missing from PlaneSegmentation table"
                assert "r_values" in plane_segmentation.colnames, "r_values column missing from PlaneSegmentation table"
                assert (
                    "cnn_preds" not in plane_segmentation.colnames
                ), "cnn_preds should not be in PlaneSegmentation table"
                # Check that the values in the NWB PlaneSegmentation table match our expected values
                actual_snr_in_nwb = plane_segmentation["snr"][:]
                actual_r_values_in_nwb = plane_segmentation["r_values"][:]
                assert_array_almost_equal(
                    actual_snr_in_nwb,
                    expected_snr,
                    decimal=6,
                )
                assert_array_almost_equal(
                    actual_r_values_in_nwb,
                    expected_r_values,
                    decimal=6,
                )

    def test_quality_metrics_can_be_disabled(self):
        """Test that quality metrics can be disabled even when available."""
        interface = self.data_interface_cls(**self.interface_kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            nwbfile_path = f"{temp_dir}/test_caiman_no_quality_metrics.nwb"
            nwbfile = NWBFile(
                session_description="test session",
                identifier="test_id",
                session_start_time=datetime.now(),
            )

            # Add the interface data to NWB file WITHOUT quality metrics
            interface.add_to_nwbfile(nwbfile, include_quality_metrics=False)

            # Write NWB file to disk
            with NWBHDF5IO(nwbfile_path, "w") as io:
                io.write(nwbfile)

            # Read back the NWB file and check PlaneSegmentation table
            with NWBHDF5IO(nwbfile_path, "r") as io:
                nwbfile = io.read()
                plane_segmentation = nwbfile.processing["ophys"]["ImageSegmentation"]["PlaneSegmentation"]

                # Check that NO quality metrics columns exist
                assert "snr" not in plane_segmentation.colnames
                assert "r_values" not in plane_segmentation.colnames
                assert "cnn_preds" not in plane_segmentation.colnames

                # But standard columns should still exist
                assert "roi_name" in plane_segmentation.colnames


# class TestCaimanSegmentationInterface750(SegmentationExtractorInterfaceTestMixin):
#     """Test class for CaImAn interface with a file containing quality metrics."""

#     data_interface_cls = CaimanSegmentationInterface
#     interface_kwargs = dict(
#         file_path=(
#             OPHYS_DATA_PATH
#             / "segmentation_datasets"
#             / "caiman"
#             / "multi_plane_with_imaging_data"
#             / "mini_750_caiman_stubbed_10units_5frames.hdf5"
#         )
#     )
#     save_directory = OUTPUT_PATH

#     def test_quality_metrics_values(self):
#         """Test that interface returns correct quality metrics values."""
#         interface = self.data_interface_cls(**self.interface_kwargs)
#         extractor = interface.segmentation_extractor
#         roi_ids = extractor.get_roi_ids()

#         # Test quality metrics as properties
#         property_keys = extractor.get_property_keys()
#         assert "snr" == property_keys[property_keys.index("snr")]
#         assert "r_values" == property_keys[property_keys.index("r_values")]
#         assert "cnn_preds" not in property_keys

#         # Test getting quality metrics via property interface
#         expected_snr = np.array(
#             [
#                 3.83573586,
#                 0.99122825,
#                 1.42381208,
#                 2.2360468,
#                 5.05530997,
#                 2.82601472,
#                 3.39339375,
#                 1.27190148,
#                 4.47956692,
#                 2.43551304,
#             ]
#         )
#         snr_property = extractor.get_property(key="snr", ids=roi_ids)
#         assert_array_almost_equal(snr_property, expected_snr, decimal=6)

#         expected_r_values = np.array(
#             [
#                 0.1108782,
#                 -0.2044603,
#                 -0.30995306,
#                 0.13629865,
#                 0.39358738,
#                 0.33849331,
#                 -0.31045486,
#                 -0.64353179,
#                 0.31970047,
#                 0.58292105,
#             ]
#         )
#         r_values_property = extractor.get_property(key="r_values", ids=roi_ids)
#         assert_array_almost_equal(r_values_property, expected_r_values, decimal=6)

#         # Test that quality metrics are available in PlaneSegmentation table columns
#         columns = interface.get_plane_segmentation_columns()
#         assert "snr" in columns
#         assert "r_values" in columns
#         assert "cnn_preds" not in columns

#         # Test that PlaneSegmentation table contains the same values
#         assert_array_almost_equal(columns["snr"]["data"], expected_snr, decimal=6)
#         assert_array_almost_equal(columns["r_values"]["data"], expected_r_values, decimal=6)


# class TestCaimanSegmentationInterface1000(SegmentationExtractorInterfaceTestMixin):
#     """Test class for CaImAn interface with a file containing quality metrics."""

#     data_interface_cls = CaimanSegmentationInterface
#     interface_kwargs = dict(
#         file_path=(
#             OPHYS_DATA_PATH
#             / "segmentation_datasets"
#             / "caiman"
#             / "multi_plane_with_imaging_data"
#             / "mini_1000_caiman_stubbed_10units_5frames.hdf5"
#         )
#     )
#     save_directory = OUTPUT_PATH

#     def test_quality_metrics_values(self):
#         """Test that interface returns correct quality metrics values."""
#         interface = self.data_interface_cls(**self.interface_kwargs)
#         extractor = interface.segmentation_extractor
#         roi_ids = extractor.get_roi_ids()

#         # Test quality metrics as properties
#         property_keys = extractor.get_property_keys()
#         assert "snr" == property_keys[property_keys.index("snr")]
#         assert "r_values" == property_keys[property_keys.index("r_values")]
#         assert "cnn_preds" not in property_keys

#         # Test getting quality metrics via property interface
#         expected_snr = np.array(
#             [
#                 2.91673987,
#                 1.05541609,
#                 1.59315755,
#                 4.66348506,
#                 2.97824475,
#                 2.98275578,
#                 2.9776668,
#                 2.94389109,
#                 1.19369399,
#                 1.76922279,
#             ]
#         )
#         snr_property = extractor.get_property(key="snr", ids=roi_ids)
#         assert_array_almost_equal(snr_property, expected_snr, decimal=6)

#         expected_r_values = np.array(
#             [
#                 0.35878084,
#                 0.182326,
#                 0.34179541,
#                 0.45524581,
#                 0.13731668,
#                 0.58202635,
#                 0.26673053,
#                 0.29431159,
#                 0.3361319,
#                 0.34527933,
#             ]
#         )
#         r_values_property = extractor.get_property(key="r_values", ids=roi_ids)
#         assert_array_almost_equal(r_values_property, expected_r_values, decimal=6)

#         # Test that quality metrics are available in PlaneSegmentation table columns
#         columns = interface.get_plane_segmentation_columns()
#         assert "snr" in columns
#         assert "r_values" in columns
#         assert "cnn_preds" not in columns

#         # Test that PlaneSegmentation table contains the same values
#         assert_array_almost_equal(columns["snr"]["data"], expected_snr, decimal=6)
#         assert_array_almost_equal(columns["r_values"]["data"], expected_r_values, decimal=6)


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

    def check_extracted_metadata(self, metadata):
        """Check that the extracted metadata contains expected Inscopix-specific items."""
        # Check session start time extraction
        assert "session_start_time" in metadata["NWBFile"]
        session_start_time = metadata["NWBFile"]["session_start_time"]
        assert session_start_time == datetime(2021, 4, 1, 12, 3, 53, 290011)

        # Check session description exact match
        assert "session_description" in metadata["NWBFile"]
        session_desc = metadata["NWBFile"]["session_description"]
        assert session_desc == "Session: FV4581_Ret; Retrieval day"

        # Check experimenter information
        assert "experimenter" in metadata["NWBFile"]
        experimenter = metadata["NWBFile"]["experimenter"]
        assert experimenter == ["Bei-Xuan"]

        # Check device information extraction
        device_list = metadata["Ophys"]["Device"]
        device_metadata = device_list[0]
        assert device_metadata["name"] == "NVista3"
        assert "description" in device_metadata
        expected_device_desc = "Inscopix NVista3; SerialNumber: 11132301; Software version 1.5.2"
        assert device_metadata["description"] == expected_device_desc

        # Check subject information extraction
        assert "Subject" in metadata
        subject = metadata["Subject"]
        assert subject["subject_id"] == "FV4581"
        assert subject["species"] == "Unknown species"
        assert "strain" in subject
        assert subject["strain"] == "CaMKIICre"
        assert subject["sex"] == "M"

        # Check imaging plane metadata
        assert "ImagingPlane" in metadata["Ophys"]
        assert len(metadata["Ophys"]["ImagingPlane"]) == 1
        imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
        assert imaging_plane["name"] == "ImagingPlane"
        assert "optical_channel" in imaging_plane
        assert "device" in imaging_plane
        assert imaging_plane["device"] == "NVista3"

        # Check imaging rate extraction
        assert "imaging_rate" in imaging_plane
        np.testing.assert_allclose(imaging_plane["imaging_rate"], 9.998700168978033, rtol=1e-3)

        # Check field of view description exact match
        expected_plane_desc = (
            "Inscopix imaging plane with field of view 398x366 pixels; Focus: 1000 µm; Exposure: 33 ms; Gain: 6"
        )
        assert imaging_plane["description"] == expected_plane_desc

        # Check optical channel information
        optical_channels = imaging_plane["optical_channel"]
        assert len(optical_channels) == 1
        optical_channel = optical_channels[0]
        assert optical_channel["name"] == "OpticalChannelGreen"
        expected_optical_desc = "Inscopix green channel (LED power: 1.3 mW/mm²)"
        assert optical_channel["description"] == expected_optical_desc

        # Check plane segmentation naming
        assert "plane_segmentations" in metadata["Ophys"]["ImageSegmentation"]
        plane_segmentation_metadata = metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]
        assert plane_segmentation_metadata["name"] == "PlaneSegmentation"

        # Check segmentation description exact match
        segmentation_desc = metadata["Ophys"]["ImageSegmentation"]["description"]
        expected_seg_desc = "Inscopix cell segmentation using cnmfe with traces in dF over noise"
        assert segmentation_desc == expected_seg_desc

        # Check fluorescence metadata
        assert "Fluorescence" in metadata["Ophys"]
        assert "PlaneSegmentation" in metadata["Ophys"]["Fluorescence"]
        assert "raw" in metadata["Ophys"]["Fluorescence"]["PlaneSegmentation"]
        raw_traces_metadata = metadata["Ophys"]["Fluorescence"]["PlaneSegmentation"]["raw"]
        assert raw_traces_metadata["name"] == "RoiResponseSeries"


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

    def check_extracted_metadata(self, metadata):
        """Check that the extracted metadata contains expected items."""
        # Check device has proper default name
        device_list = metadata["Ophys"]["Device"]
        device_metadata = device_list[0]
        assert device_metadata["name"] == "Microscope"

        # Check subject has defaults (should not be present if no subject data)
        assert "Subject" not in metadata

        # Check imaging plane metadata
        assert "ImagingPlane" in metadata["Ophys"]
        assert len(metadata["Ophys"]["ImagingPlane"]) == 1
        imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
        assert imaging_plane["name"] == "ImagingPlane"
        assert imaging_plane["device"] == "Microscope"

        # Check field of view description exact match
        expected_plane_desc = "Inscopix imaging plane with field of view 21x21 pixels"
        assert imaging_plane["description"] == expected_plane_desc

        # Check sampling rate extraction
        assert "imaging_rate" in imaging_plane
        np.testing.assert_allclose(imaging_plane["imaging_rate"], 10.0, rtol=1e-3)

        # Check optical channel has default name
        optical_channels = imaging_plane["optical_channel"]
        optical_channel = optical_channels[0]
        assert optical_channel["name"] == "OpticalChannelDefault"
        assert optical_channel["description"] == "Inscopix optical channel"

        # Check plane segmentation naming
        assert "plane_segmentations" in metadata["Ophys"]["ImageSegmentation"]
        plane_segmentation_metadata = metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]
        assert plane_segmentation_metadata["name"] == "PlaneSegmentation"

        # Check segmentation description exact match (default case)
        segmentation_desc = metadata["Ophys"]["ImageSegmentation"]["description"]
        assert segmentation_desc == "Inscopix cell segmentation using cnmfe with traces in dF over noise"

        # Check fluorescence metadata
        assert "Fluorescence" in metadata["Ophys"]
        assert "PlaneSegmentation" in metadata["Ophys"]["Fluorescence"]
        assert "raw" in metadata["Ophys"]["Fluorescence"]["PlaneSegmentation"]
        raw_traces_metadata = metadata["Ophys"]["Fluorescence"]["PlaneSegmentation"]["raw"]
        assert raw_traces_metadata["name"] == "RoiResponseSeries"
