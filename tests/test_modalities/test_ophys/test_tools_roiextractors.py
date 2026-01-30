import math
import re
import unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
from types import MethodType
from typing import Literal
from unittest.mock import Mock

import numpy as np
import psutil
import pytest
from hdmf.data_utils import DataChunkIterator
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal
from numpy.typing import ArrayLike
from parameterized import param, parameterized
from pynwb import NWBHDF5IO, NWBFile
from pynwb.ophys import OnePhotonSeries
from pynwb.testing.mock.file import mock_NWBFile
from roiextractors.testing import (
    generate_dummy_imaging_extractor,
    generate_dummy_segmentation_extractor,
)

from neuroconv.tools.nwb_helpers import get_module
from neuroconv.tools.roiextractors import (
    _check_if_imaging_fits_into_memory,
    add_devices_to_nwbfile,
)
from neuroconv.tools.roiextractors.imagingextractordatachunkiterator import (
    ImagingExtractorDataChunkIterator,
)
from neuroconv.tools.roiextractors.roiextractors import (
    _add_image_segmentation_to_nwbfile,
    _add_imaging_plane_to_nwbfile,
    _add_photon_series_to_nwbfile,
    _add_plane_segmentation_to_nwbfile,
    _add_summary_images_to_nwbfile,
    _get_default_ophys_metadata,
)


class TestAddDevices(unittest.TestCase):
    def setUp(self):
        self.session_start_time = datetime.now().astimezone()
        self.nwbfile = mock_NWBFile()

        # Use top-level Devices structure (new dictionary-based format)
        self.metadata = dict(Devices=dict(), Ophys=dict())

    def test_add_device(self):
        device_name = "new_device"
        self.metadata["Devices"]["new_device_key"] = dict(name=device_name)
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 1
        assert device_name in devices

    def test_add_device_with_further_metadata(self):
        device_name = "new_device"
        description = "device_description"
        manufacturer = "manufacturer"

        self.metadata["Devices"]["new_device_key"] = dict(
            name=device_name, description=description, manufacturer=manufacturer
        )
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices
        device = devices["new_device"]

        assert len(devices) == 1
        assert device.name == device_name
        assert device.description == description
        assert device.manufacturer == manufacturer

    def test_add_two_devices(self):
        device_name_list = ["device1", "device2"]
        for index, device_name in enumerate(device_name_list):
            self.metadata["Devices"][f"device_key_{index}"] = dict(name=device_name)
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 2
        assert all(device_name in devices for device_name in device_name_list)

    def test_add_one_device_and_then_another(self):
        device_name1 = "new_device"
        self.metadata["Devices"]["device_key_1"] = dict(name=device_name1)
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        device_name2 = "another_device"
        self.metadata["Devices"]["device_key_2"] = dict(name=device_name2)
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 2
        assert device_name1 in devices
        assert device_name2 in devices

    def test_not_overwriting_devices(self):
        device_name1 = "same_device"
        self.metadata["Devices"]["device_key_1"] = dict(name=device_name1)
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        device_name2 = "same_device"
        self.metadata["Devices"]["device_key_2"] = dict(name=device_name2)
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 1
        assert device_name1 in devices

    def test_add_device_defaults(self):
        # With empty Devices dict, add_devices_to_nwbfile does not add default device
        # The default device is only added when needed by imaging plane
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices
        assert len(devices) == 0

    def test_add_empty_device_list_in_metadata(self):
        # With empty Devices dict, no devices are added
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 0


class TestAddImagingPlane(TestCase):
    def setUp(self):
        self.session_start_time = datetime.now().astimezone()
        self.nwbfile = NWBFile(
            session_description="session_description",
            identifier="file_id",
            session_start_time=self.session_start_time,
        )

        # Use new dictionary-based structure
        self.device_name = "optical_device"
        self.device_metadata_key = "optical_device_key"

        self.optical_channel_metadata = dict(
            name="optical_channel",
            emission_lambda=np.nan,
            description="description",
        )

        self.imaging_plane_name = "imaging_plane_name"
        self.imaging_plane_description = "imaging_plane_description"
        self.imaging_plane_metadata_key = "imaging_plane_key"

        self.metadata = dict(
            Devices={self.device_metadata_key: dict(name=self.device_name)},
            Ophys=dict(
                ImagingPlanes={
                    self.imaging_plane_metadata_key: dict(
                        name=self.imaging_plane_name,
                        optical_channel=[self.optical_channel_metadata],
                        description=self.imaging_plane_description,
                        device_metadata_key=self.device_metadata_key,
                        excitation_lambda=np.nan,
                        indicator="unknown",
                        location="unknown",
                    )
                }
            ),
        )

    def test_add_imaging_plane_to_nwbfile(self):
        _add_imaging_plane_to_nwbfile(
            nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_metadata_key=self.imaging_plane_metadata_key
        )

        imaging_planes = self.nwbfile.imaging_planes
        assert len(imaging_planes) == 1
        assert self.imaging_plane_name in imaging_planes

        imaging_plane = imaging_planes[self.imaging_plane_name]
        assert imaging_plane.description == self.imaging_plane_description

    def test_not_overwriting_imaging_plane_if_same_name(self):
        _add_imaging_plane_to_nwbfile(
            nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_metadata_key=self.imaging_plane_metadata_key
        )

        self.metadata["Ophys"]["ImagingPlanes"][self.imaging_plane_metadata_key]["description"] = "modified description"
        _add_imaging_plane_to_nwbfile(
            nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_metadata_key=self.imaging_plane_metadata_key
        )

        imaging_planes = self.nwbfile.imaging_planes
        assert len(imaging_planes) == 1
        assert self.imaging_plane_name in imaging_planes

    def test_add_two_imaging_planes(self):
        # Add the first imaging plane
        first_imaging_plane_name = "first_imaging_plane_name"
        first_imaging_plane_description = "first_imaging_plane_description"
        first_key = "first_imaging_plane_key"
        self.metadata["Ophys"]["ImagingPlanes"][first_key] = dict(
            name=first_imaging_plane_name,
            optical_channel=[self.optical_channel_metadata],
            description=first_imaging_plane_description,
            device_metadata_key=self.device_metadata_key,
            excitation_lambda=np.nan,
            indicator="unknown",
            location="unknown",
        )
        _add_imaging_plane_to_nwbfile(
            nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_metadata_key=first_key
        )

        # Add the second imaging plane
        second_imaging_plane_name = "second_imaging_plane_name"
        second_imaging_plane_description = "second_imaging_plane_description"
        second_key = "second_imaging_plane_key"
        self.metadata["Ophys"]["ImagingPlanes"][second_key] = dict(
            name=second_imaging_plane_name,
            optical_channel=[self.optical_channel_metadata],
            description=second_imaging_plane_description,
            device_metadata_key=self.device_metadata_key,
            excitation_lambda=np.nan,
            indicator="unknown",
            location="unknown",
        )
        _add_imaging_plane_to_nwbfile(
            nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_metadata_key=second_key
        )

        # Test expected values
        imaging_planes = self.nwbfile.imaging_planes
        assert len(imaging_planes) == 2

        first_imaging_plane = imaging_planes[first_imaging_plane_name]
        assert first_imaging_plane.name == first_imaging_plane_name
        assert first_imaging_plane.description == first_imaging_plane_description

        second_imaging_plane = imaging_planes[second_imaging_plane_name]
        assert second_imaging_plane.name == second_imaging_plane_name
        assert second_imaging_plane.description == second_imaging_plane_description

    def test_add_imaging_plane_to_nwbfile_raises_when_name_not_found_in_metadata(self):
        """Test that adding an imaging plane with unknown key uses defaults instead of raising an error."""
        imaging_plane_metadata_key = "non_existing_key"
        # With the new structure, an unknown key uses defaults rather than raising
        _add_imaging_plane_to_nwbfile(
            nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_metadata_key=imaging_plane_metadata_key
        )

        # Default imaging plane should be created
        imaging_planes = self.nwbfile.imaging_planes
        assert len(imaging_planes) == 1
        assert "ImagingPlane" in imaging_planes  # Default name

    def test_add_two_imaging_planes_from_metadata(self):
        """Test adding two imaging planes when there are multiple imaging plane metadata."""

        second_imaging_plane_name = "second_imaging_plane_name"
        second_key = "second_imaging_plane_key"
        metadata = deepcopy(self.metadata)
        metadata["Ophys"]["ImagingPlanes"][second_key] = dict(
            name=second_imaging_plane_name,
            optical_channel=[self.optical_channel_metadata],
            description="Second imaging plane",
            device_metadata_key=self.device_metadata_key,
            excitation_lambda=np.nan,
            indicator="unknown",
            location="unknown",
        )
        _add_imaging_plane_to_nwbfile(
            nwbfile=self.nwbfile, metadata=metadata, imaging_plane_metadata_key=self.imaging_plane_metadata_key
        )
        _add_imaging_plane_to_nwbfile(nwbfile=self.nwbfile, metadata=metadata, imaging_plane_metadata_key=second_key)

        # Test expected values
        imaging_planes = self.nwbfile.imaging_planes
        assert len(imaging_planes) == 2

        first_imaging_plane = imaging_planes[self.imaging_plane_name]
        assert first_imaging_plane.name == self.imaging_plane_name

        second_imaging_plane = imaging_planes[second_imaging_plane_name]
        assert second_imaging_plane.name == second_imaging_plane_name


class TestAddImageSegmentation(unittest.TestCase):
    def setUp(self):
        self.session_start_time = datetime.now().astimezone()
        self.nwbfile = NWBFile(
            session_description="session_description",
            identifier="file_id",
            session_start_time=self.session_start_time,
        )

        # Use new dictionary-based structure with PlaneSegmentations
        self.metadata = dict(
            Devices={"default_device_key": dict(name="Microscope")},
            Ophys=dict(
                ImagingPlanes={
                    "default_imaging_plane_key": dict(
                        name="ImagingPlane",
                        optical_channel=[
                            dict(name="OpticalChannel", emission_lambda=np.nan, description="description")
                        ],
                        description="description",
                        device_metadata_key="default_device_key",
                        excitation_lambda=np.nan,
                        indicator="unknown",
                        location="unknown",
                    )
                },
                PlaneSegmentations={},
            ),
        )

        self.image_segmentation_name = "ImageSegmentation"  # Default name

    def test_add_image_segmentation_to_nwbfile(self):
        """
        Test that _add_image_segmentation_to_nwbfile method adds an image segmentation to the nwbfile
        specified by the metadata.
        """

        _add_image_segmentation_to_nwbfile(nwbfile=self.nwbfile, metadata=self.metadata)

        ophys = get_module(self.nwbfile, "ophys")

        image_segmentation = ophys.data_interfaces.get(self.image_segmentation_name)
        self.assertEqual(image_segmentation.name, self.image_segmentation_name)


def _generate_test_masks(num_rois: int, mask_type: Literal["pixel", "voxel"]) -> list:
    masks = list()
    size = 3 if mask_type == "pixel" else 4
    for idx in range(1, num_rois + 1):
        masks.append(np.arange(idx, idx + size * idx, dtype=np.dtype("uint8")).reshape(-1, size))
    return masks


def _generate_casted_test_masks(num_rois: int, mask_type: Literal["pixel", "voxel"]) -> list:
    original_mask = _generate_test_masks(num_rois=num_rois, mask_type=mask_type)
    casted_masks = list()
    for per_roi_mask in original_mask:
        casted_masks.append([tuple(x) for x in per_roi_mask])
    return casted_masks


def assert_masks_equal(mask: list[list[tuple[int, int, int]]], expected_mask: list[list[tuple[int, int, int]]]):
    """
    Asserts that two lists of pixel masks of inhomogeneous shape are equal.
    """
    assert len(mask) == len(expected_mask)
    for mask_ind in range(len(mask)):
        assert_array_equal(mask[mask_ind], expected_mask[mask_ind])


class TestAddPlaneSegmentation(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.num_rois = 10
        cls.num_samples = 20
        cls.num_rows = 25
        cls.num_columns = 20

        cls.session_start_time = datetime.now().astimezone()

        cls.image_segmentation_name = "ImageSegmentation"  # Default name
        cls.plane_segmentation_name = "plane_segmentation_name"
        cls.plane_segmentation_metadata_key = "plane_segmentation_key"

    def setUp(self):
        self.segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_samples=self.num_samples,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )
        self.nwbfile = NWBFile(
            session_description="session_description",
            identifier="file_id",
            session_start_time=self.session_start_time,
        )

        # Use new dictionary-based structure
        self.device_metadata_key = "device_key"
        self.imaging_plane_metadata_key = "imaging_plane_key"

        self.metadata = dict(
            Devices={self.device_metadata_key: dict(name="Microscope")},
            Ophys=dict(
                ImagingPlanes={
                    self.imaging_plane_metadata_key: dict(
                        name="ImagingPlane",
                        optical_channel=[
                            dict(name="OpticalChannel", emission_lambda=np.nan, description="description")
                        ],
                        description="description",
                        device_metadata_key=self.device_metadata_key,
                        excitation_lambda=np.nan,
                        indicator="unknown",
                        location="unknown",
                    )
                },
                PlaneSegmentations={
                    self.plane_segmentation_metadata_key: dict(
                        name=self.plane_segmentation_name,
                        description="Segmented ROIs",
                        imaging_plane_metadata_key=self.imaging_plane_metadata_key,
                    )
                },
            ),
        )

    def test_add_plane_segmentation_to_nwbfile(self):
        """Test that _add_plane_segmentation_to_nwbfile method adds a plane segmentation to the nwbfile
        specified by the metadata."""
        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
        )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)
        plane_segmentations = image_segmentation.plane_segmentations

        self.assertEqual(len(plane_segmentations), 1)

        plane_segmentation = plane_segmentations[self.plane_segmentation_name]

        self.assertEqual(plane_segmentation.name, self.plane_segmentation_name)
        self.assertEqual(plane_segmentation.description, "Segmented ROIs")

        plane_segmentation_num_rois = len(plane_segmentation.id)
        self.assertEqual(plane_segmentation_num_rois, self.num_rois)

        plane_segmentation_roi_centroid_data = plane_segmentation["ROICentroids"].data
        expected_roi_centroid_data = self.segmentation_extractor.get_roi_locations()[(1, 0), :].T

        assert_array_equal(plane_segmentation_roi_centroid_data, expected_roi_centroid_data)

        # transpose to num_rois x image_width x image_height
        expected_image_masks = self.segmentation_extractor.get_roi_image_masks().T
        assert_array_equal(plane_segmentation["image_mask"], expected_image_masks)

    def test_do_not_include_roi_centroids(self):
        """Test that setting `include_roi_centroids=False` prevents the centroids from being calculated and added."""
        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            include_roi_centroids=False,
            plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
        )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)
        plane_segmentations = image_segmentation.plane_segmentations
        plane_segmentation = plane_segmentations[self.plane_segmentation_name]

        assert "ROICentroids" not in plane_segmentation

    def test_do_not_include_acceptance(self):
        """Test that setting `include_roi_acceptance=False` prevents the boolean acceptance columns from being added."""
        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            include_roi_acceptance=False,
            plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
        )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)
        plane_segmentations = image_segmentation.plane_segmentations
        plane_segmentation = plane_segmentations[self.plane_segmentation_name]

        assert "Accepted" not in plane_segmentation
        assert "Rejected" not in plane_segmentation

    @parameterized.expand(
        [
            param(
                rejected_list=[],
                expected_rejected_roi_ids=[0] * 10,
            ),
            param(
                rejected_list=[
                    "roi_0",
                    "roi_1",
                    "roi_2",
                    "roi_3",
                    "roi_4",
                    "roi_5",
                    "roi_6",
                    "roi_7",
                    "roi_8",
                    "roi_9",
                ],
                expected_rejected_roi_ids=[1] * 10,
            ),
            param(
                rejected_list=[
                    "roi_2",
                    "roi_6",
                    "roi_8",
                ],
                expected_rejected_roi_ids=[
                    0,
                    0,
                    1,
                    0,
                    0,
                    0,
                    1,
                    0,
                    1,
                    0,
                ],
            ),
        ],
    )
    def test_rejected_roi_ids(self, rejected_list, expected_rejected_roi_ids):
        """Test that the ROI ids that were rejected are correctly set in
        the plane segmentation ROI table."""
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_samples=self.num_samples,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
            rejected_list=rejected_list,
        )

        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
        )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)
        plane_segmentations = image_segmentation.plane_segmentations

        plane_segmentation = plane_segmentations[self.plane_segmentation_name]

        plane_segmentation_rejected_roi_ids = plane_segmentation["Rejected"].data
        assert_array_equal(plane_segmentation_rejected_roi_ids, expected_rejected_roi_ids)

        accepted_roi_ids = list(np.logical_not(np.array(expected_rejected_roi_ids)).astype(int))
        plane_segmentation_accepted_roi_ids = plane_segmentation["Accepted"].data
        assert_array_equal(plane_segmentation_accepted_roi_ids, accepted_roi_ids)

    def test_pixel_masks(self):
        """Test the voxel mask option for writing a plane segmentation table."""
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_samples=self.num_samples,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )

        def get_roi_pixel_masks(self, roi_ids: ArrayLike | None = None) -> list[np.ndarray]:
            roi_ids = roi_ids or range(self.get_num_rois())
            pixel_masks = _generate_test_masks(num_rois=len(roi_ids), mask_type="pixel")
            return pixel_masks

        segmentation_extractor.get_roi_pixel_masks = MethodType(get_roi_pixel_masks, segmentation_extractor)

        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            mask_type="pixel",
            plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
        )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)
        plane_segmentations = image_segmentation.plane_segmentations

        plane_segmentation = plane_segmentations[self.plane_segmentation_name]

        true_pixel_masks = _generate_casted_test_masks(num_rois=self.num_rois, mask_type="pixel")
        assert_masks_equal(plane_segmentation["pixel_mask"][:], true_pixel_masks)

    def test_voxel_masks(self):
        """Test the voxel mask option for writing a plane segmentation table."""
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_samples=self.num_samples,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )

        def get_roi_pixel_masks(self, roi_ids: ArrayLike | None = None) -> list[np.ndarray]:
            roi_ids = roi_ids or range(self.get_num_rois())
            voxel_masks = _generate_test_masks(num_rois=len(roi_ids), mask_type="voxel")
            return voxel_masks

        segmentation_extractor.get_roi_pixel_masks = MethodType(get_roi_pixel_masks, segmentation_extractor)

        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            mask_type="voxel",
            plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
        )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)
        plane_segmentations = image_segmentation.plane_segmentations

        plane_segmentation = plane_segmentations[self.plane_segmentation_name]

        true_voxel_masks = _generate_casted_test_masks(num_rois=self.num_rois, mask_type="voxel")
        assert_masks_equal(plane_segmentation["voxel_mask"][:], true_voxel_masks)

    def test_invalid_mask_type(self):
        """Test that an invalid mask_type raises a AssertionError."""
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_samples=self.num_samples,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )
        expected_error_message = re.escape(
            "Keyword argument 'mask_type' must be one of either 'image', 'pixel', 'voxel'. " "Received 'invalid'."
        )
        with pytest.raises(AssertionError, match=expected_error_message):
            _add_plane_segmentation_to_nwbfile(
                segmentation_extractor=segmentation_extractor,
                nwbfile=self.nwbfile,
                metadata=self.metadata,
                mask_type="invalid",
                plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
            )

    def test_pixel_masks_auto_switch(self):
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_samples=self.num_samples,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )

        def get_roi_pixel_masks(self, roi_ids: ArrayLike | None = None) -> list[np.ndarray]:
            roi_ids = roi_ids or range(self.get_num_rois())
            pixel_masks = _generate_test_masks(num_rois=len(roi_ids), mask_type="pixel")
            return pixel_masks

        segmentation_extractor.get_roi_pixel_masks = MethodType(get_roi_pixel_masks, segmentation_extractor)

        with self.assertWarnsRegex(
            expected_warning=UserWarning,
            expected_regex=(
                "Specified mask_type='voxel', but ROIExtractors returned 3-dimensional masks. "
                "Using mask_type='pixel' instead."
            ),
        ):
            _add_plane_segmentation_to_nwbfile(
                segmentation_extractor=segmentation_extractor,
                nwbfile=self.nwbfile,
                metadata=self.metadata,
                mask_type="voxel",
                plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
            )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)
        plane_segmentations = image_segmentation.plane_segmentations

        plane_segmentation = plane_segmentations[self.plane_segmentation_name]

        true_voxel_masks = _generate_casted_test_masks(num_rois=self.num_rois, mask_type="pixel")
        assert_masks_equal(plane_segmentation["pixel_mask"][:], true_voxel_masks)

    def test_voxel_masks_auto_switch(self):
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_samples=self.num_samples,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )

        def get_roi_pixel_masks(self, roi_ids: ArrayLike | None = None) -> list[np.ndarray]:
            roi_ids = roi_ids or range(self.get_num_rois())
            voxel_masks = _generate_test_masks(num_rois=len(roi_ids), mask_type="voxel")
            return voxel_masks

        segmentation_extractor.get_roi_pixel_masks = MethodType(get_roi_pixel_masks, segmentation_extractor)

        with self.assertWarnsRegex(
            expected_warning=UserWarning,
            expected_regex=(
                "Specified mask_type='pixel', but ROIExtractors returned 4-dimensional masks. "
                "Using mask_type='voxel' instead."
            ),
        ):
            _add_plane_segmentation_to_nwbfile(
                segmentation_extractor=segmentation_extractor,
                nwbfile=self.nwbfile,
                metadata=self.metadata,
                mask_type="pixel",
                plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
            )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)
        plane_segmentations = image_segmentation.plane_segmentations

        plane_segmentation = plane_segmentations[self.plane_segmentation_name]

        true_voxel_masks = _generate_casted_test_masks(num_rois=self.num_rois, mask_type="voxel")
        assert_masks_equal(plane_segmentation["voxel_mask"][:], true_voxel_masks)

    def test_not_overwriting_plane_segmentation_if_same_name(self):
        """Test that adding a plane segmentation with the same name will not overwrite
        the existing plane segmentation."""

        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
        )

        self.metadata["Ophys"]["PlaneSegmentations"][self.plane_segmentation_metadata_key][
            "description"
        ] = "modified description"

        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
        )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)

        assert len(image_segmentation.plane_segmentations) == 1
        assert self.plane_segmentation_name in image_segmentation.plane_segmentations

        plane_segmentation = image_segmentation.plane_segmentations[self.plane_segmentation_name]

        self.assertNotEqual(plane_segmentation.description, "modified description")

    def test_add_two_plane_segmentation(self):
        """Test adding two plane segmentations to the nwbfile."""

        # Add first plane segmentation
        first_plane_segmentation_name = "first_plane_segmentation_name"
        first_plane_segmentation_description = "first_plane_segmentation_description"
        first_key = "first_plane_seg_key"
        self.metadata["Ophys"]["PlaneSegmentations"][first_key] = dict(
            name=first_plane_segmentation_name,
            description=first_plane_segmentation_description,
            imaging_plane_metadata_key=self.imaging_plane_metadata_key,
        )
        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            plane_segmentation_metadata_key=first_key,
        )

        # Add second plane segmentation
        second_plane_segmentation_name = "second_plane_segmentation_name"
        second_plane_segmentation_description = "second_plane_segmentation_description"
        second_key = "second_plane_seg_key"
        self.metadata["Ophys"]["PlaneSegmentations"][second_key] = dict(
            name=second_plane_segmentation_name,
            description=second_plane_segmentation_description,
            imaging_plane_metadata_key=self.imaging_plane_metadata_key,
        )
        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            plane_segmentation_metadata_key=second_key,
        )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)

        assert len(image_segmentation.plane_segmentations) == 2
        assert second_plane_segmentation_name in image_segmentation.plane_segmentations
        assert first_plane_segmentation_name in image_segmentation.plane_segmentations

        first_plane_segmentation = image_segmentation.plane_segmentations[first_plane_segmentation_name]
        second_plane_segmentation = image_segmentation.plane_segmentations[second_plane_segmentation_name]

        assert first_plane_segmentation.name == first_plane_segmentation_name
        assert first_plane_segmentation.description == first_plane_segmentation_description

        assert second_plane_segmentation.name == second_plane_segmentation_name
        assert second_plane_segmentation.description == second_plane_segmentation_description

    def test_add_plane_segmentation_to_nwbfile_with_unknown_key_uses_defaults(self):
        """Test that adding a plane segmentation with an unknown key uses defaults."""
        unknown_key = "non_existing_key"
        # With the new structure, an unknown key uses defaults rather than raising
        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            plane_segmentation_metadata_key=unknown_key,
        )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)
        # Default plane segmentation should be created with default name "PlaneSegmentation"
        assert "PlaneSegmentation" in image_segmentation.plane_segmentations

    def test_add_plane_segmentation_with_custom_properties(self):
        """Test that custom properties of various dtypes are added as columns and values are correct."""
        # Create a dummy segmentation extractor with known ROI count
        num_rois = 5
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=num_rois,
            num_samples=self.num_samples,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )

        # Add custom properties with known values and types
        roi_ids = segmentation_extractor.get_roi_ids()
        custom_float = np.arange(num_rois, dtype=np.float32) * 0.5
        custom_bool = np.array([True, False, True, False, True])
        custom_label = np.array(["A", "B", "A", "C", "B"], dtype=object)

        segmentation_extractor.set_property("custom_float", custom_float, ids=roi_ids)
        segmentation_extractor.set_property("custom_bool", custom_bool, ids=roi_ids)
        segmentation_extractor.set_property("custom_label", custom_label, ids=roi_ids)

        # Add to NWB (metadata already configured in setUp with new structure)
        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
        )

        # Retrieve plane segmentation
        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)
        plane_segmentation = image_segmentation.plane_segmentations[self.plane_segmentation_name]

        # Check that properties are present and values match
        for prop, expected in [
            ("custom_float", custom_float),
            ("custom_bool", custom_bool),
            ("custom_label", custom_label),
        ]:
            assert prop in plane_segmentation
            np.testing.assert_array_equal(plane_segmentation[prop].data, expected)


class TestAddPhotonSeries(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session_start_time = datetime.now().astimezone()
        cls.num_samples = 30
        cls.num_rows = 10
        cls.num_columns = 15

        # Use new dictionary-based metadata structure
        cls.device_metadata_key = "test_device_key"
        cls.device_name = "optical_device"
        device_metadata = dict(name=cls.device_name)

        optical_channel_metadata = dict(
            name="optical_channel",
            emission_lambda=np.nan,
            description="description",
        )

        cls.imaging_plane_metadata_key = "test_plane_key"
        cls.imaging_plane_name = "imaging_plane_name"
        imaging_plane_metadata = dict(
            name=cls.imaging_plane_name,
            optical_channel=[optical_channel_metadata],
            description="image_plane_description",
            device_metadata_key=cls.device_metadata_key,
            excitation_lambda=np.nan,
            indicator="unknown",
            location="unknown",
        )

        # Base metadata with top-level Devices
        metadata = {
            "Devices": {cls.device_metadata_key: device_metadata},
            "Ophys": {
                "ImagingPlanes": {cls.imaging_plane_metadata_key: imaging_plane_metadata},
                "MicroscopySeries": {},
            },
        }

        # Two-photon series metadata
        cls.two_photon_series_metadata_key = "test_two_photon_key"
        cls.two_photon_series_name = "two_photon_series_name"
        cls.two_photon_series_metadata = deepcopy(metadata)
        cls.two_photon_series_metadata["Ophys"]["MicroscopySeries"][cls.two_photon_series_metadata_key] = {
            "name": cls.two_photon_series_name,
            "imaging_plane_metadata_key": cls.imaging_plane_metadata_key,
            "unit": "n.a.",
        }

        # One-photon series metadata
        cls.one_photon_series_metadata_key = "test_one_photon_key"
        cls.one_photon_series_name = "one_photon_series_name"
        cls.one_photon_series_metadata = deepcopy(metadata)
        cls.one_photon_series_metadata["Ophys"]["MicroscopySeries"][cls.one_photon_series_metadata_key] = {
            "name": cls.one_photon_series_name,
            "imaging_plane_metadata_key": cls.imaging_plane_metadata_key,
            "unit": "n.a.",
        }

    def setUp(self):
        self.nwbfile = NWBFile(
            session_description="session_description",
            identifier="file_id",
            session_start_time=self.session_start_time,
        )

        self.imaging_extractor = generate_dummy_imaging_extractor(
            num_samples=self.num_samples, num_rows=self.num_rows, num_columns=self.num_columns
        )

    def test_default_values(self):
        """Test adding two photon series with default values."""
        _add_photon_series_to_nwbfile(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
            microscopy_series_metadata_key=self.two_photon_series_metadata_key,
        )

        # Check data
        acquisition_modules = self.nwbfile.acquisition
        assert self.two_photon_series_name in acquisition_modules
        data_chunk_iterator = acquisition_modules[self.two_photon_series_name].data
        assert isinstance(data_chunk_iterator, ImagingExtractorDataChunkIterator)

        two_photon_series_extracted = np.concatenate([data_chunk.data for data_chunk in data_chunk_iterator])
        # NWB stores images as num_columns x num_rows
        expected_two_photon_series_shape = (self.num_samples, self.num_columns, self.num_rows)
        assert two_photon_series_extracted.shape == expected_two_photon_series_shape
        expected_two_photon_series_data = self.imaging_extractor.get_series().transpose((0, 2, 1))
        assert_array_equal(two_photon_series_extracted, expected_two_photon_series_data)

        # Check device
        devices = self.nwbfile.devices
        assert self.device_name in devices
        assert len(devices) == 1

        # Check imaging planes
        imaging_planes_in_file = self.nwbfile.imaging_planes
        assert self.imaging_plane_name in imaging_planes_in_file
        assert len(imaging_planes_in_file) == 1

    def test_invalid_iterator_type_raises_error(self):
        """Test error is raised when adding two photon series with invalid iterator type."""
        with self.assertRaisesWith(
            AssertionError,
            "'iterator_type' must be either 'v2' (recommended) or None.",
        ):
            _add_photon_series_to_nwbfile(
                imaging=self.imaging_extractor,
                nwbfile=self.nwbfile,
                metadata=self.two_photon_series_metadata,
                microscopy_series_metadata_key=self.two_photon_series_metadata_key,
                iterator_type="invalid",
            )

    def test_non_iterative_write_assertion(self):
        # Estimate num of frames required to exceed memory capabilities
        dtype = self.imaging_extractor.get_dtype()
        element_size_in_bytes = dtype.itemsize
        sample_shape = self.imaging_extractor.get_sample_shape()

        available_memory_in_bytes = psutil.virtual_memory().available

        excess = 1.5  # Of what is available in memory
        num_samples_to_overflow = (available_memory_in_bytes * excess) / (
            element_size_in_bytes * math.prod(sample_shape)
        )

        # Mock recording extractor with as many samples as necessary to overflow memory
        mock_imaging = Mock()
        mock_imaging.get_dtype.return_value = dtype
        mock_imaging.get_sample_shape.return_value = sample_shape
        mock_imaging.get_num_samples.return_value = num_samples_to_overflow

        reg_expression = "Memory error, full TwoPhotonSeries data is (.*?) are available! Please use iterator_type='v2'"

        with self.assertRaisesRegex(MemoryError, reg_expression):
            _check_if_imaging_fits_into_memory(imaging=mock_imaging)

    def test_non_iterative_two_photon(self):
        """Test adding two photon series without using DataChunkIterator."""
        _add_photon_series_to_nwbfile(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
            microscopy_series_metadata_key=self.two_photon_series_metadata_key,
            iterator_type=None,
        )

        # Check data
        acquisition_modules = self.nwbfile.acquisition
        assert self.two_photon_series_name in acquisition_modules
        two_photon_series_extracted = acquisition_modules[self.two_photon_series_name].data

        # NWB stores images as num_columns x num_rows
        expected_two_photon_series_shape = (self.num_samples, self.num_columns, self.num_rows)
        assert two_photon_series_extracted.shape == expected_two_photon_series_shape
        expected_two_photon_series_data = self.imaging_extractor.get_series().transpose((0, 2, 1))
        assert_array_equal(two_photon_series_extracted, expected_two_photon_series_data)

    def test_deprecated_v1_iterator_two_photon(self):
        """Test adding two photon series with deprecated v1 iterator type."""
        with self.assertWarns(FutureWarning):
            _add_photon_series_to_nwbfile(
                imaging=self.imaging_extractor,
                nwbfile=self.nwbfile,
                metadata=self.two_photon_series_metadata,
                microscopy_series_metadata_key=self.two_photon_series_metadata_key,
                iterator_type="v1",
            )

        # Check data
        acquisition_modules = self.nwbfile.acquisition
        assert self.two_photon_series_name in acquisition_modules
        data_chunk_iterator = acquisition_modules[self.two_photon_series_name].data
        assert isinstance(data_chunk_iterator, DataChunkIterator)
        self.assertEqual(data_chunk_iterator.buffer_size, 10)

        two_photon_series_extracted = np.concatenate([data_chunk.data for data_chunk in data_chunk_iterator])
        # NWB stores images as num_columns x num_rows
        expected_two_photon_series_shape = (self.num_samples, self.num_columns, self.num_rows)
        assert two_photon_series_extracted.shape == expected_two_photon_series_shape
        expected_two_photon_series_data = self.imaging_extractor.get_series().transpose((0, 2, 1))
        assert_array_equal(two_photon_series_extracted, expected_two_photon_series_data)

    def test_iterator_options_propagation(self):
        """Test that iterator options are propagated to the data chunk iterator."""
        buffer_shape = (20, 5, 5)
        chunk_shape = (10, 5, 5)
        _add_photon_series_to_nwbfile(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
            microscopy_series_metadata_key=self.two_photon_series_metadata_key,
            iterator_type="v2",
            iterator_options=dict(buffer_shape=buffer_shape, chunk_shape=chunk_shape),
        )

        acquisition_modules = self.nwbfile.acquisition
        assert self.two_photon_series_name in acquisition_modules
        data_chunk_iterator = acquisition_modules[self.two_photon_series_name].data
        self.assertEqual(data_chunk_iterator.buffer_shape, buffer_shape)
        self.assertEqual(data_chunk_iterator.chunk_shape, chunk_shape)

    def test_iterator_options_chunk_mb_propagation(self):
        """Test that chunk_mb is propagated to the data chunk iterator and the chunk shape is correctly set to fit."""
        chunk_mb = 10.0
        _add_photon_series_to_nwbfile(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
            microscopy_series_metadata_key=self.two_photon_series_metadata_key,
            iterator_type="v2",
            iterator_options=dict(chunk_mb=chunk_mb),
        )

        acquisition_modules = self.nwbfile.acquisition
        assert self.two_photon_series_name in acquisition_modules
        data_chunk_iterator = acquisition_modules[self.two_photon_series_name].data
        iterator_chunk_mb = math.prod(data_chunk_iterator.chunk_shape) * data_chunk_iterator.dtype.itemsize / 1e6
        assert iterator_chunk_mb <= chunk_mb

    def test_iterator_options_chunk_shape_is_at_least_one(self):
        """Test that when a small chunk_mb is selected the chunk shape is guaranteed to include at least one frame."""
        chunk_mb = 1.0
        _add_photon_series_to_nwbfile(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
            microscopy_series_metadata_key=self.two_photon_series_metadata_key,
            iterator_type="v2",
            iterator_options=dict(chunk_mb=chunk_mb),
        )
        acquisition_modules = self.nwbfile.acquisition
        assert self.two_photon_series_name in acquisition_modules
        data_chunk_iterator = acquisition_modules[self.two_photon_series_name].data
        chunk_shape = data_chunk_iterator.chunk_shape
        assert_array_equal(chunk_shape, (30, 15, 10))

    def test_iterator_options_chunk_shape_does_not_exceed_maxshape(self):
        """Test that when a large chunk_mb is selected the chunk shape is guaranteed to not exceed maxshape."""
        chunk_mb = 1000.0
        _add_photon_series_to_nwbfile(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
            microscopy_series_metadata_key=self.two_photon_series_metadata_key,
            iterator_type="v2",
            iterator_options=dict(chunk_mb=chunk_mb),
        )
        acquisition_modules = self.nwbfile.acquisition
        assert self.two_photon_series_name in acquisition_modules
        data_chunk_iterator = acquisition_modules[self.two_photon_series_name].data
        chunk_shape = data_chunk_iterator.chunk_shape
        assert_array_equal(chunk_shape, data_chunk_iterator.maxshape)

    def test_add_two_photon_series_roundtrip(self):
        _add_photon_series_to_nwbfile(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
            microscopy_series_metadata_key=self.two_photon_series_metadata_key,
        )

        # Write the data to disk
        nwbfile_path = Path(mkdtemp()) / "two_photon_roundtrip.nwb"
        with NWBHDF5IO(nwbfile_path, "w") as io:
            io.write(self.nwbfile)

        with NWBHDF5IO(nwbfile_path, "r") as io:
            read_nwbfile = io.read()

            # Check data
            acquisition_modules = read_nwbfile.acquisition
            assert self.two_photon_series_name in acquisition_modules
            two_photon_series = acquisition_modules[self.two_photon_series_name].data

            # NWB stores images as num_columns x num_rows
            expected_two_photon_series_shape = (self.num_samples, self.num_columns, self.num_rows)
            assert two_photon_series.shape == expected_two_photon_series_shape

            # Check device
            devices = read_nwbfile.devices
            assert self.device_name in devices
            assert len(devices) == 1

            # Check imaging planes
            imaging_planes_in_file = read_nwbfile.imaging_planes
            assert self.imaging_plane_name in imaging_planes_in_file
            assert len(imaging_planes_in_file) == 1

    def test_add_invalid_photon_series_type(self):
        """Test error is raised when adding photon series with invalid 'photon_series_type'."""
        with self.assertRaisesWith(
            AssertionError,
            "'photon_series_type' must be either 'OnePhotonSeries' or 'TwoPhotonSeries'.",
        ):
            _add_photon_series_to_nwbfile(
                imaging=self.imaging_extractor,
                nwbfile=self.nwbfile,
                metadata=self.two_photon_series_metadata,
                microscopy_series_metadata_key=self.two_photon_series_metadata_key,
                photon_series_type="invalid",
            )

    def test_add_one_photon_series(self):
        """Test adding one photon series with metadata."""

        metadata = deepcopy(self.one_photon_series_metadata)
        one_photon_series_metadata = metadata["Ophys"]["MicroscopySeries"][self.one_photon_series_metadata_key]
        one_photon_series_metadata.update(
            pmt_gain=60.0,
            binning=2,
            power=500.0,
        )
        _add_photon_series_to_nwbfile(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=metadata,
            microscopy_series_metadata_key=self.one_photon_series_metadata_key,
            photon_series_type="OnePhotonSeries",
        )
        self.assertIn(self.one_photon_series_name, self.nwbfile.acquisition)
        one_photon_series = self.nwbfile.acquisition[self.one_photon_series_name]
        self.assertIsInstance(one_photon_series, OnePhotonSeries)
        self.assertEqual(one_photon_series.pmt_gain, 60.0)
        self.assertEqual(one_photon_series.binning, 2)
        self.assertEqual(one_photon_series.power, 500.0)
        self.assertEqual(one_photon_series.unit, "n.a.")

    def test_add_one_photon_series_roundtrip(self):
        _add_photon_series_to_nwbfile(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.one_photon_series_metadata,
            microscopy_series_metadata_key=self.one_photon_series_metadata_key,
            photon_series_type="OnePhotonSeries",
        )

        # Write the data to disk
        nwbfile_path = Path(mkdtemp()) / "one_photon_roundtrip.nwb"
        with NWBHDF5IO(nwbfile_path, "w") as io:
            io.write(self.nwbfile)

        with NWBHDF5IO(nwbfile_path, "r") as io:
            read_nwbfile = io.read()

            # Check data
            acquisition_modules = read_nwbfile.acquisition
            assert self.one_photon_series_name in acquisition_modules
            one_photon_series = acquisition_modules[self.one_photon_series_name].data

            # NWB stores images as num_columns x num_rows
            expected_one_photon_series_shape = (self.num_samples, self.num_columns, self.num_rows)
            assert one_photon_series.shape == expected_one_photon_series_shape

    def test_add_photon_series_to_nwbfile_invalid_module_name_raises(self):
        """Test that adding photon series with invalid module name raises error."""
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg="'parent_container' must be either 'acquisition' or 'processing/ophys'.",
        ):
            _add_photon_series_to_nwbfile(
                imaging=self.imaging_extractor,
                nwbfile=self.nwbfile,
                metadata=self.two_photon_series_metadata,
                microscopy_series_metadata_key=self.two_photon_series_metadata_key,
                parent_container="test",
            )

    def test_add_one_photon_series_to_processing(self):
        """Test adding one photon series to ophys processing module."""
        metadata = deepcopy(self.one_photon_series_metadata)
        metadata["Ophys"]["MicroscopySeries"][self.one_photon_series_metadata_key]["name"] = "OnePhotonSeriesProcessed"

        _add_photon_series_to_nwbfile(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=metadata,
            microscopy_series_metadata_key=self.one_photon_series_metadata_key,
            photon_series_type="OnePhotonSeries",
            parent_container="processing/ophys",
        )
        ophys = self.nwbfile.processing["ophys"]
        self.assertIn("OnePhotonSeriesProcessed", ophys.data_interfaces)

    def test_ophys_module_not_created_when_photon_series_added_to_acquisition(self):
        """Test that ophys module is not created when photon series are added to nwbfile.acquisition."""
        _add_photon_series_to_nwbfile(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
            microscopy_series_metadata_key=self.two_photon_series_metadata_key,
        )
        self.assertNotIn("ophys", self.nwbfile.processing)
        self.assertEqual(len(self.nwbfile.processing), 0)

    def test_add_multiple_one_photon_series_with_same_imaging_plane(self):
        """Test adding two OnePhotonSeries that use the same ImagingPlane."""
        shared_imaging_plane_name = "same_imaging_plane_for_two_series"

        # Create metadata with shared imaging plane
        first_series_metadata = deepcopy(self.one_photon_series_metadata)
        first_series_metadata["Ophys"]["ImagingPlanes"][self.imaging_plane_metadata_key][
            "name"
        ] = shared_imaging_plane_name

        # Add first series
        _add_photon_series_to_nwbfile(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=first_series_metadata,
            microscopy_series_metadata_key=self.one_photon_series_metadata_key,
            photon_series_type="OnePhotonSeries",
        )

        # Add second series metadata with a different series key but same imaging plane
        second_series_key = "second_series_key"
        first_series_metadata["Ophys"]["MicroscopySeries"][second_series_key] = {
            "name": "second_photon_series",
            "imaging_plane_metadata_key": self.imaging_plane_metadata_key,
            "unit": "n.a.",
        }

        _add_photon_series_to_nwbfile(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=first_series_metadata,
            microscopy_series_metadata_key=second_series_key,
            photon_series_type="OnePhotonSeries",
        )

        self.assertIn("second_photon_series", self.nwbfile.acquisition)
        self.assertEqual(len(self.nwbfile.imaging_planes), 1)
        self.assertIn(shared_imaging_plane_name, self.nwbfile.imaging_planes)


class TestAddSummaryImages(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session_start_time = datetime.now().astimezone()

        cls.metadata = dict(Ophys=dict())

        cls.segmentation_images_name = "segmentation_images"
        cls.mean_image_name = "mean_image"
        cls.correlation_image_name = "correlation_image"
        cls.plane_segmentation_metadata_key = "test_plane_segmentation_key"

        # Use new dictionary-based SegmentationImages structure
        segmentation_images_metadata = dict(
            name=cls.segmentation_images_name,
            description="description",
        )
        segmentation_images_metadata[cls.plane_segmentation_metadata_key] = dict(
            correlation=dict(name=cls.correlation_image_name, description="test description for correlation image"),
            mean=dict(name=cls.mean_image_name, description="test description for mean image"),
        )

        cls.metadata["Ophys"].update(SegmentationImages=segmentation_images_metadata)

    def setUp(self):
        self.nwbfile = NWBFile(
            session_description="session_description",
            identifier="file_id",
            session_start_time=self.session_start_time,
        )

    def test_add_summary_images_to_nwbfile(self):
        segmentation_extractor = generate_dummy_segmentation_extractor(num_rows=10, num_columns=15)

        _add_summary_images_to_nwbfile(
            nwbfile=self.nwbfile,
            segmentation_extractor=segmentation_extractor,
            metadata=self.metadata,
            plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
        )

        ophys = self.nwbfile.get_processing_module("ophys")
        self.assertIn(self.segmentation_images_name, ophys.data_interfaces)
        images_collection = ophys.data_interfaces[self.segmentation_images_name]

        extracted_images_dict = images_collection.images
        self.assertEqual(extracted_images_dict[self.mean_image_name].description, "test description for mean image")
        self.assertEqual(
            extracted_images_dict[self.correlation_image_name].description, "test description for correlation image"
        )

        extracted_images_dict = {img_name: img.data.T for img_name, img in extracted_images_dict.items()}
        expected_images_dict = segmentation_extractor.get_images_dict()

        images_metadata = self.metadata["Ophys"]["SegmentationImages"][self.plane_segmentation_metadata_key]
        for image_name, image_data in expected_images_dict.items():
            image_name_from_metadata = images_metadata[image_name]["name"]
            np.testing.assert_almost_equal(image_data, extracted_images_dict[image_name_from_metadata])

    def test_extractor_with_one_summary_image_suppressed(self):
        segmentation_extractor = generate_dummy_segmentation_extractor(num_rows=10, num_columns=15)
        segmentation_extractor._image_correlation = None

        _add_summary_images_to_nwbfile(
            nwbfile=self.nwbfile,
            segmentation_extractor=segmentation_extractor,
            metadata=self.metadata,
            plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
        )

        ophys = self.nwbfile.get_processing_module("ophys")
        images_collection = ophys.data_interfaces[self.segmentation_images_name]

        extracted_images_number = len(images_collection.images)
        expected_images_number = len(
            {img_name: img for img_name, img in segmentation_extractor.get_images_dict().items() if img is not None}
        )
        assert extracted_images_number == expected_images_number

    def test_extractor_with_no_summary_images(self):
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rows=10, num_columns=15, has_summary_images=False
        )

        self.nwbfile.create_processing_module("ophys", "contains optical physiology processed data")

        _add_summary_images_to_nwbfile(
            nwbfile=self.nwbfile,
            segmentation_extractor=segmentation_extractor,
            metadata=self.metadata,
            plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
        )

        ophys = self.nwbfile.get_processing_module("ophys")
        assert self.segmentation_images_name not in ophys.data_interfaces

    def test_extractor_with_no_summary_images_and_no_ophys_module(self):
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rows=10, num_columns=15, has_summary_images=False
        )

        _add_summary_images_to_nwbfile(
            nwbfile=self.nwbfile,
            segmentation_extractor=segmentation_extractor,
            metadata=self.metadata,
            plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
        )

        assert len(self.nwbfile.processing) == 0

    def test_add_summary_images_to_nwbfile_invalid_plane_segmentation_name(self):
        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg="Plane segmentation 'invalid_plane_segmentation_key' not found in metadata['Ophys']['SegmentationImages']",
        ):
            _add_summary_images_to_nwbfile(
                nwbfile=self.nwbfile,
                segmentation_extractor=generate_dummy_segmentation_extractor(num_rows=10, num_columns=15),
                metadata=self.metadata,
                plane_segmentation_metadata_key="invalid_plane_segmentation_key",
            )

    def test_add_summary_images_to_nwbfile_from_two_planes(self):
        segmentation_extractor_first_plane = generate_dummy_segmentation_extractor(num_rows=10, num_columns=15)

        _add_summary_images_to_nwbfile(
            nwbfile=self.nwbfile,
            segmentation_extractor=segmentation_extractor_first_plane,
            metadata=self.metadata,
            plane_segmentation_metadata_key=self.plane_segmentation_metadata_key,
        )

        # Add a second plane with different image names
        metadata = deepcopy(self.metadata)
        segmentation_images_metadata = metadata["Ophys"]["SegmentationImages"]
        second_plane_metadata_key = "second_plane_key"
        segmentation_images_metadata[second_plane_metadata_key] = dict(
            mean=dict(name="test_mean_image_name", description="test description for mean image"),
            correlation=dict(name="test_correlation_image_name", description="test description for correlation image"),
        )

        segmentation_extractor_second_plane = generate_dummy_segmentation_extractor(num_rows=10, num_columns=15)

        _add_summary_images_to_nwbfile(
            nwbfile=self.nwbfile,
            segmentation_extractor=segmentation_extractor_second_plane,
            metadata=metadata,
            plane_segmentation_metadata_key=second_plane_metadata_key,
        )

        ophys = self.nwbfile.get_processing_module("ophys")
        images_collection = ophys.data_interfaces[self.segmentation_images_name]
        extracted_images_number = len(images_collection.images)
        self.assertEqual(extracted_images_number, 4)

        extracted_images_dict = {img_name: img.data.T for img_name, img in images_collection.images.items()}
        expected_images_second_plane = segmentation_extractor_second_plane.get_images_dict()

        images_metadata = metadata["Ophys"]["SegmentationImages"][second_plane_metadata_key]
        for image_name, image_data in expected_images_second_plane.items():
            image_name_from_metadata = images_metadata[image_name]["name"]
            np.testing.assert_almost_equal(image_data, extracted_images_dict[image_name_from_metadata])


class TestNoMetadataMutation:
    def test_get_default_ophys_metadata_returns_independent_instances(self):
        """Test that _get_default_ophys_metadata() returns independent instances that don't share mutable state."""
        # Get two instances
        metadata1 = _get_default_ophys_metadata()
        metadata2 = _get_default_ophys_metadata()

        # Store snapshots before mutating metadata1
        metadata2_devices_before = deepcopy(metadata2["Devices"])
        metadata2_ophys_before = deepcopy(metadata2["Ophys"])

        # Modify first instance deeply (modify nested dicts)
        metadata1["Devices"]["default_metadata_key"]["name"] = "ModifiedMicroscope"
        metadata1["Ophys"]["ImagingPlanes"]["default_metadata_key"]["name"] = "ModifiedImagingPlane"
        metadata1["Ophys"]["RoiResponses"]["default_metadata_key"]["raw"]["name"] = "ModifiedRoiResponseSeries"

        # Verify second instance was not affected by mutations to first instance
        assert (
            metadata2["Devices"] == metadata2_devices_before
        ), "Modifying metadata1 affected metadata2 - instances share mutable state"
        assert (
            metadata2["Ophys"] == metadata2_ophys_before
        ), "Modifying metadata1 affected metadata2 - instances share mutable state"

        # Get a third instance after modifications to ensure fresh defaults
        metadata3 = _get_default_ophys_metadata()
        assert (
            metadata3["Devices"] == metadata2_devices_before
        ), "New instance after mutations differs from original - not getting fresh defaults"
        assert (
            metadata3["Ophys"] == metadata2_ophys_before
        ), "New instance after mutations differs from original - not getting fresh defaults"

    def test_add_devices_to_nwbfile_does_not_mutate_metadata(self):
        """Test that add_devices_to_nwbfile does not mutate the input metadata."""
        nwbfile = mock_NWBFile()

        # Create metadata with devices (new dictionary-based structure)
        metadata = {"Devices": {"test_device_key": {"name": "TestMicroscope", "description": "Test description"}}}

        # Deep copy to compare entire structure before and after
        metadata_before = deepcopy(metadata)

        # Call function
        add_devices_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        # Verify metadata was not mutated - compare entire dict structure
        assert metadata == metadata_before, "Metadata was mutated"

    def test_add_imaging_plane_no_metadata_mutation(self):
        """Test that _add_imaging_plane_to_nwbfile does not mutate the input metadata."""
        nwbfile = mock_NWBFile()

        # Create metadata with imaging plane (new dictionary-based structure)
        metadata = {
            "Devices": {"test_device_key": {"name": "TestMicroscope"}},
            "Ophys": {
                "ImagingPlanes": {
                    "test_plane_key": {
                        "name": "TestImagingPlane",
                        "description": "Test imaging plane",
                        "excitation_lambda": 488.0,
                        "indicator": "GCaMP6f",
                        "location": "V1",
                        "device_metadata_key": "test_device_key",
                        "optical_channel": [
                            {
                                "name": "Green",
                                "emission_lambda": 510.0,
                                "description": "Green channel",
                            }
                        ],
                    }
                },
            },
        }

        # Deep copy to compare entire structure before and after
        metadata_before = deepcopy(metadata)

        # Call function
        _add_imaging_plane_to_nwbfile(nwbfile=nwbfile, metadata=metadata, imaging_plane_metadata_key="test_plane_key")

        # Verify metadata was not mutated - compare entire dict structure
        assert metadata == metadata_before, "Metadata was mutated"

    def test_add_imaging_plane_no_partial_metadata_mutation(self):
        """Test that _add_imaging_plane_to_nwbfile does not mutate partial user metadata when complemented with defaults."""
        nwbfile = mock_NWBFile()

        # Create metadata with minimal imaging plane (missing some fields that will be filled from defaults)
        metadata = {
            "Devices": {"test_device_key": {"name": "TestMicroscope"}},
            "Ophys": {
                "ImagingPlanes": {
                    "test_plane_key": {
                        "name": "TestImagingPlane",
                        "device_metadata_key": "test_device_key",
                        "optical_channel": [
                            {
                                "name": "Green",
                                "emission_lambda": 510.0,
                                "description": "Green channel",
                            }
                        ],
                        # Intentionally missing: description, excitation_lambda, indicator, location
                    }
                },
            },
        }

        # Deep copy to compare entire structure before and after
        metadata_before = deepcopy(metadata)

        # Call function (should fill in missing fields internally but not mutate the input)
        _add_imaging_plane_to_nwbfile(nwbfile=nwbfile, metadata=metadata, imaging_plane_metadata_key="test_plane_key")

        # Verify metadata was not mutated - compare entire dict structure
        assert metadata == metadata_before, "Metadata was mutated"

    def test_add_photon_series_no_metadata_mutation(self):
        """Test that _add_photon_series_to_nwbfile does not mutate the input metadata."""
        from roiextractors.testing import generate_dummy_imaging_extractor

        nwbfile = mock_NWBFile()
        imaging_extractor = generate_dummy_imaging_extractor(
            num_rows=10, num_columns=10, num_samples=30, sampling_frequency=30.0
        )

        # Create metadata with photon series (new dictionary-based structure)
        metadata = {
            "Devices": {"test_device_key": {"name": "TestMicroscope"}},
            "Ophys": {
                "ImagingPlanes": {
                    "test_plane_key": {
                        "name": "TestImagingPlane",
                        "description": "Test imaging plane",
                        "excitation_lambda": 488.0,
                        "indicator": "GCaMP6f",
                        "location": "V1",
                        "device_metadata_key": "test_device_key",
                        "optical_channel": [
                            {
                                "name": "Green",
                                "emission_lambda": 510.0,
                                "description": "Green channel",
                            }
                        ],
                    }
                },
                "MicroscopySeries": {
                    "test_series_key": {
                        "name": "TestTwoPhotonSeries",
                        "description": "Test two photon series",
                        "unit": "px",
                        "imaging_plane_metadata_key": "test_plane_key",
                    }
                },
            },
        }

        # Deep copy to compare entire structure before and after
        metadata_before = deepcopy(metadata)

        # Call function
        _add_photon_series_to_nwbfile(
            imaging=imaging_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type="TwoPhotonSeries",
            microscopy_series_metadata_key="test_series_key",
        )

        # Verify metadata was not mutated - compare entire dict structure
        assert metadata == metadata_before, "Metadata was mutated"

    def test_add_image_segmentation_no_metadata_mutation(self):
        """Test that _add_image_segmentation_to_nwbfile does not mutate the input metadata."""
        nwbfile = mock_NWBFile()

        # Create metadata with image segmentation
        metadata = {"Ophys": {"ImageSegmentation": {"name": "TestImageSegmentation"}}}

        # Deep copy to compare entire structure before and after
        metadata_before = deepcopy(metadata)

        # Call function
        _add_image_segmentation_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        # Verify metadata was not mutated - compare entire dict structure
        assert metadata == metadata_before, "Metadata was mutated"

    def test_add_plane_segmentation_no_metadata_mutation(self):
        """Test that _add_plane_segmentation_to_nwbfile does not mutate the input metadata."""
        from roiextractors.testing import generate_dummy_segmentation_extractor

        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor()

        # Create metadata with plane segmentation (new dictionary-based structure)
        metadata = {
            "Devices": {"test_device_key": {"name": "TestMicroscope"}},
            "Ophys": {
                "ImagingPlanes": {
                    "test_plane_key": {
                        "name": "TestImagingPlane",
                        "description": "Test imaging plane",
                        "excitation_lambda": 488.0,
                        "indicator": "GCaMP6f",
                        "location": "V1",
                        "device_metadata_key": "test_device_key",
                        "optical_channel": [
                            {
                                "name": "Green",
                                "emission_lambda": 510.0,
                                "description": "Green channel",
                            }
                        ],
                    }
                },
                "ImageSegmentation": {"name": "TestImageSegmentation"},
                "PlaneSegmentations": {
                    "test_segmentation_key": {
                        "name": "TestPlaneSegmentation",
                        "description": "Test plane segmentation",
                        "imaging_plane_metadata_key": "test_plane_key",
                    }
                },
            },
        }

        # Deep copy to compare entire structure before and after
        metadata_before = deepcopy(metadata)

        # Call function
        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            plane_segmentation_metadata_key="test_segmentation_key",
        )

        # Verify metadata was not mutated - compare entire dict structure
        assert metadata == metadata_before, "Metadata was mutated"
