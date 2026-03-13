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
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal, assert_raises
from numpy.typing import ArrayLike
from parameterized import param, parameterized
from pynwb import NWBHDF5IO, NWBFile
from pynwb.ophys import OnePhotonSeries
from pynwb.testing.mock.file import mock_NWBFile
from roiextractors.testing import (
    generate_dummy_imaging_extractor,
    generate_dummy_segmentation_extractor,
)

from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.tools.roiextractors import (
    _check_if_imaging_fits_into_memory,
    add_devices_to_nwbfile,
    add_fluorescence_traces_to_nwbfile,
    add_imaging_to_nwbfile,
    add_segmentation_to_nwbfile,
)
from neuroconv.tools.roiextractors.imagingextractordatachunkiterator import (
    ImagingExtractorDataChunkIterator,
)
from neuroconv.tools.roiextractors.roiextractors import (
    _get_ophys_metadata_placeholders,
    get_full_ophys_metadata,
)
from neuroconv.tools.roiextractors.roiextractors_pending_deprecation import (
    _add_image_segmentation_to_nwbfile,
    _add_imaging_plane_to_nwbfile_old_list_format,
    _add_photon_series_to_nwbfile_old_list_format,
    _add_plane_segmentation_to_nwbfile,
    _add_summary_images_to_nwbfile,
    _get_default_ophys_metadata_old_metadata_list,
)
from neuroconv.utils import dict_deep_update


class TestAddDevices(unittest.TestCase):
    def setUp(self):
        self.session_start_time = datetime.now().astimezone()
        self.nwbfile = mock_NWBFile()

        self.metadata = dict(Ophys=dict())

    def test_add_device(self):
        device_name = "new_device"
        device_list = [dict(name=device_name)]
        self.metadata["Ophys"].update(Device=device_list)
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 1
        assert device_name in devices

    def test_add_device_with_further_metadata(self):
        device_name = "new_device"
        description = "device_description"
        manufacturer = "manufacturer"

        device_list = [dict(name=device_name, description=description, manufacturer=manufacturer)]
        self.metadata["Ophys"].update(Device=device_list)
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices
        device = devices["new_device"]

        assert len(devices) == 1
        assert device.name == device_name
        assert device.description == description
        assert device.manufacturer == manufacturer

    def test_add_two_devices(self):
        device_name_list = ["device1", "device2"]
        device_list = [dict(name=device_name) for device_name in device_name_list]
        self.metadata["Ophys"].update(Device=device_list)
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 2
        assert all(device_name in devices for device_name in device_name_list)

    def test_add_one_device_and_then_another(self):
        device_name1 = "new_device"
        device_list = [dict(name=device_name1)]
        self.metadata["Ophys"].update(Device=device_list)
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        device_name2 = "another_device"
        device_list = [dict(name=device_name2)]
        self.metadata["Ophys"].update(Device=device_list)
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 2
        assert device_name1 in devices
        assert device_name2 in devices

    def test_not_overwriting_devices(self):
        device_name1 = "same_device"
        device_list = [dict(name=device_name1)]
        self.metadata["Ophys"].update(Device=device_list)
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        device_name2 = "same_device"
        device_list = [dict(name=device_name2)]
        self.metadata["Ophys"].update(Device=device_list)
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 1
        assert device_name1 in devices

    def test_add_device_defaults(self):
        add_devices_to_nwbfile(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 1
        assert "Microscope" in devices

    def test_add_empty_device_list_in_metadata(self):
        device_list = []
        self.metadata["Ophys"].update(Device=device_list)
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

        self.metadata = dict(Ophys=dict())

        self.device_name = "optical_device"
        self.device_metadata = dict(name=self.device_name)
        self.metadata["Ophys"].update(Device=[self.device_metadata])

        self.optical_channel_metadata = dict(
            name="optical_channel",
            emission_lambda=np.nan,
            description="description",
        )

        self.imaging_plane_name = "imaging_plane_name"
        self.imaging_plane_description = "imaging_plane_description"
        self.imaging_plane_metadata = dict(
            name=self.imaging_plane_name,
            optical_channel=[self.optical_channel_metadata],
            description=self.imaging_plane_description,
            device=self.device_name,
            excitation_lambda=np.nan,
            indicator="unknown",
            location="unknown",
        )

        self.metadata["Ophys"].update(ImagingPlane=[self.imaging_plane_metadata])

    def test_add_imaging_plane_to_nwbfile_old_list_format(self):
        _add_imaging_plane_to_nwbfile_old_list_format(
            nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_name=self.imaging_plane_name
        )

        imaging_planes = self.nwbfile.imaging_planes
        assert len(imaging_planes) == 1
        assert self.imaging_plane_name in imaging_planes

        imaging_plane = imaging_planes[self.imaging_plane_name]
        assert imaging_plane.description == self.imaging_plane_description

    def test_not_overwriting_imaging_plane_if_same_name(self):
        _add_imaging_plane_to_nwbfile_old_list_format(
            nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_name=self.imaging_plane_name
        )

        self.imaging_plane_metadata["description"] = "modified description"
        _add_imaging_plane_to_nwbfile_old_list_format(
            nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_name=self.imaging_plane_name
        )

        imaging_planes = self.nwbfile.imaging_planes
        assert len(imaging_planes) == 1
        assert self.imaging_plane_name in imaging_planes

    def test_add_two_imaging_planes(self):
        # Add the first imaging plane
        first_imaging_plane_name = "first_imaging_plane_name"
        first_imaging_plane_description = "first_imaging_plane_description"
        self.imaging_plane_metadata["name"] = first_imaging_plane_name
        self.imaging_plane_metadata["description"] = first_imaging_plane_description
        _add_imaging_plane_to_nwbfile_old_list_format(
            nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_name=first_imaging_plane_name
        )

        # Add the second imaging plane
        second_imaging_plane_name = "second_imaging_plane_name"
        second_imaging_plane_description = "second_imaging_plane_description"
        self.imaging_plane_metadata["name"] = second_imaging_plane_name
        self.imaging_plane_metadata["description"] = second_imaging_plane_description
        _add_imaging_plane_to_nwbfile_old_list_format(
            nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_name=second_imaging_plane_name
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

    def test_add_imaging_plane_to_nwbfile_old_list_format_raises_when_name_not_found_in_metadata(self):
        """Test adding an imaging plane raises an error when the name is not found in the metadata."""
        imaging_plane_name = "imaging_plane_non_existing_in_the_metadata"
        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg=f"Metadata for Imaging Plane '{imaging_plane_name}' not found in metadata['Ophys']['ImagingPlane'].",
        ):
            _add_imaging_plane_to_nwbfile_old_list_format(
                nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_name=imaging_plane_name
            )

    def test_add_two_imaging_planes_from_metadata(self):
        """Test adding two imaging planes when there are multiple imaging plane metadata."""

        second_imaging_plane_name = "second_imaging_plane_name"
        metadata = deepcopy(self.metadata)
        imaging_planes_metadata = metadata["Ophys"]["ImagingPlane"]
        second_imaging_plane_metadata = deepcopy(metadata["Ophys"]["ImagingPlane"][0])
        second_imaging_plane_metadata.update(name="second_imaging_plane_name")
        imaging_planes_metadata.append(second_imaging_plane_metadata)
        _add_imaging_plane_to_nwbfile_old_list_format(
            nwbfile=self.nwbfile, metadata=metadata, imaging_plane_name=self.imaging_plane_name
        )
        _add_imaging_plane_to_nwbfile_old_list_format(
            nwbfile=self.nwbfile, metadata=metadata, imaging_plane_name="second_imaging_plane_name"
        )

        # Test expected values
        imaging_planes = self.nwbfile.imaging_planes
        assert len(imaging_planes) == 2

        first_imaging_plane = imaging_planes[self.imaging_plane_name]
        assert first_imaging_plane.name == self.imaging_plane_name

        second_imaging_plane = imaging_planes[second_imaging_plane_name]
        assert second_imaging_plane.name == second_imaging_plane_name


# TODO: Drop this test class once support for list-based metadata is removed (September 2026).
# The dict-based equivalent is TestAddSegmentation.
class TestAddImageSegmentation(unittest.TestCase):
    def setUp(self):
        self.session_start_time = datetime.now().astimezone()
        self.nwbfile = NWBFile(
            session_description="session_description",
            identifier="file_id",
            session_start_time=self.session_start_time,
        )

        self.metadata = dict(Ophys=dict())

        self.image_segmentation_name = "image_segmentation_name"
        image_segmentation_metadata = dict(ImageSegmentation=dict(name=self.image_segmentation_name))

        self.metadata["Ophys"].update(image_segmentation_metadata)

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


# TODO: Drop this test class once support for list-based metadata is removed (September 2026).
# The dict-based equivalent is TestAddSegmentation.
class TestAddPlaneSegmentation(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.num_rois = 10
        cls.num_samples = 20
        cls.num_rows = 25
        cls.num_columns = 20

        cls.session_start_time = datetime.now().astimezone()

        cls.image_segmentation_name = "image_segmentation_name"
        cls.plane_segmentation_name = "plane_segmentation_name"

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

        self.metadata = dict(Ophys=dict())

        self.plane_segmentation_metadata = dict(
            name=self.plane_segmentation_name, description="Segmented ROIs", imaging_plane="ImagingPlane"
        )

        image_segmentation_metadata = dict(
            ImageSegmentation=dict(
                name=self.image_segmentation_name,
                plane_segmentations=[
                    self.plane_segmentation_metadata,
                ],
            )
        )

        self.metadata["Ophys"].update(image_segmentation_metadata)

    def test_add_plane_segmentation_to_nwbfile(self):
        """Test that _add_plane_segmentation_to_nwbfile method adds a plane segmentation to the nwbfile
        specified by the metadata."""
        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            plane_segmentation_name=self.plane_segmentation_name,
        )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)
        plane_segmentations = image_segmentation.plane_segmentations

        self.assertEqual(len(plane_segmentations), 1)

        plane_segmentation = plane_segmentations[self.plane_segmentation_name]

        self.assertEqual(plane_segmentation.name, self.plane_segmentation_name)
        self.assertEqual(plane_segmentation.description, self.plane_segmentation_metadata["description"])

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
            plane_segmentation_name=self.plane_segmentation_name,
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
            plane_segmentation_name=self.plane_segmentation_name,
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
            plane_segmentation_name=self.plane_segmentation_name,
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
            plane_segmentation_name=self.plane_segmentation_name,
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
            plane_segmentation_name=self.plane_segmentation_name,
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
                plane_segmentation_name=self.plane_segmentation_name,
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
                plane_segmentation_name=self.plane_segmentation_name,
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
                plane_segmentation_name=self.plane_segmentation_name,
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
            plane_segmentation_name=self.plane_segmentation_name,
        )

        self.plane_segmentation_metadata["description"] = "modified description"

        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            plane_segmentation_name=self.plane_segmentation_name,
        )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)

        assert len(image_segmentation.plane_segmentations) == 1
        assert self.plane_segmentation_name in image_segmentation.plane_segmentations

        plane_segmentation = image_segmentation.plane_segmentations[self.plane_segmentation_name]

        self.assertNotEqual(plane_segmentation.description, self.plane_segmentation_metadata["description"])

    def test_add_two_plane_segmentation(self):
        """Test adding two plane segmentations to the nwbfile."""

        # Add first plane segmentation
        first_plane_segmentation_name = "first_plane_segmentation_name"
        first_plane_segmentation_description = "first_plane_segmentation_description"
        self.plane_segmentation_metadata["name"] = first_plane_segmentation_name
        self.plane_segmentation_metadata["description"] = first_plane_segmentation_description
        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            plane_segmentation_name=first_plane_segmentation_name,
        )

        # Add second plane segmentation
        second_plane_segmentation_name = "second_plane_segmentation_name"
        second_plane_segmentation_description = "second_plane_segmentation_description"
        self.plane_segmentation_metadata["name"] = second_plane_segmentation_name
        self.plane_segmentation_metadata["description"] = second_plane_segmentation_description
        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            plane_segmentation_name=second_plane_segmentation_name,
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

    def test_add_plane_segmentation_to_nwbfile_raises_when_name_not_found_in_metadata(self):
        """Test adding a plane segmentation raises an error when the name is not found in the metadata."""
        plane_segmentation_name = "plane_segmentation_non_existing_in_the_metadata"
        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg=f"Metadata for Plane Segmentation '{plane_segmentation_name}' not found in metadata['Ophys']['ImageSegmentation']['plane_segmentations'].",
        ):
            _add_plane_segmentation_to_nwbfile(
                segmentation_extractor=self.segmentation_extractor,
                nwbfile=self.nwbfile,
                metadata=self.metadata,
                plane_segmentation_name=plane_segmentation_name,
            )

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

        # Ensure metadata contains the correct plane segmentation name
        plane_segmentation_metadata = dict(
            name=self.plane_segmentation_name, description="Segmented ROIs", imaging_plane="ImagingPlane"
        )
        image_segmentation_metadata = dict(
            ImageSegmentation=dict(
                name=self.image_segmentation_name,
                plane_segmentations=[plane_segmentation_metadata],
            )
        )
        self.metadata["Ophys"].update(image_segmentation_metadata)

        # Add to NWB
        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            plane_segmentation_name=self.plane_segmentation_name,
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


# TODO: Drop this test class once support for list-based metadata is removed (September 2026).
# The dict-based equivalent is TestAddSegmentation.
class TestAddFluorescenceTraces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.num_rois = 10
        cls.num_samples = 20
        cls.num_rows = 25
        cls.num_columns = 20

        cls.session_start_time = datetime.now().astimezone()

        cls.fluorescence_name = "Fluorescence"
        cls.df_over_f_name = "DfOverF"

        cls.raw_roi_response_series_metadata = dict(
            name="RoiResponseSeries",
            description="raw fluorescence signal",
        )

        cls.dff_roi_response_series_metadata = dict(
            name="RoiResponseSeries",
            description="relative (df/f) fluorescence signal",
        )

        cls.deconvolved_roi_response_series_metadata = dict(
            name="Deconvolved",
            description="deconvolved fluorescence signal",
        )

        cls.neuropil_roi_response_series_metadata = dict(
            name="Neuropil",
            description="neuropil fluorescence signal",
            unit="test_unit",
        )

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

        self.metadata = dict(Ophys=dict())

        fluorescence_metadata = dict(
            Fluorescence=dict(
                PlaneSegmentation=dict(
                    name=self.fluorescence_name,
                    raw=self.raw_roi_response_series_metadata,
                    deconvolved=self.deconvolved_roi_response_series_metadata,
                    neuropil=self.neuropil_roi_response_series_metadata,
                )
            )
        )

        dff_metadata = dict(
            DfOverF=dict(
                PlaneSegmentation=dict(
                    name=self.df_over_f_name,
                    dff=self.dff_roi_response_series_metadata,
                )
            )
        )

        self.metadata["Ophys"].update(fluorescence_metadata)
        self.metadata["Ophys"].update(dff_metadata)

    def test_add_fluorescence_traces_to_nwbfile(self):
        """Test fluorescence traces are added correctly to the nwbfile."""

        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        assert self.fluorescence_name in ophys.data_interfaces

        fluorescence = ophys.get(self.fluorescence_name)

        self.assertEqual(fluorescence.name, self.fluorescence_name)
        self.assertEqual(len(fluorescence.roi_response_series), 3)

        self.assertEqual(
            fluorescence["RoiResponseSeries"].description,
            self.raw_roi_response_series_metadata["description"],
        )

        self.assertNotEqual(
            fluorescence["RoiResponseSeries"].description,
            self.dff_roi_response_series_metadata["description"],
        )

        self.assertEqual(
            fluorescence["Deconvolved"].description,
            self.deconvolved_roi_response_series_metadata["description"],
        )

        self.assertEqual(
            fluorescence["Neuropil"].unit,
            self.neuropil_roi_response_series_metadata["unit"],
        )

        self.assertAlmostEqual(
            fluorescence["Neuropil"].rate,
            self.segmentation_extractor.get_sampling_frequency(),
            places=3,
        )

        traces = self.segmentation_extractor.get_traces_dict()

        for nwb_series_name, roiextractors_name in zip(
            ["RoiResponseSeries", "Deconvolved", "Neuropil"], ["raw", "deconvolved", "neuropil"]
        ):
            series_outer_data = fluorescence[nwb_series_name].data
            assert_array_equal(series_outer_data.data.data, traces[roiextractors_name])

        # Check that df/F trace data is not being written to the Fluorescence container
        df_over_f = ophys.get(self.df_over_f_name)
        assert_raises(
            AssertionError,
            assert_array_equal,
            fluorescence["RoiResponseSeries"].data,
            df_over_f["RoiResponseSeries"].data,
        )

    # TODO: Temporarily disabled - requires fix in roiextractors main for raw=None handling
    # See: https://github.com/catalystneuro/roiextractors/pull/508
    def _test_add_df_over_f_trace(self):
        """Test df/f traces are added to the nwbfile."""

        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_samples=self.num_samples,
            num_rows=300,
            num_columns=400,
            has_raw_signal=False,  # Only dff signal, no raw
            has_dff_signal=True,
            has_deconvolved_signal=False,
            has_neuropil_signal=False,
        )

        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        assert self.df_over_f_name in ophys.data_interfaces

        assert self.fluorescence_name not in ophys.data_interfaces

        df_over_f = ophys.get(self.df_over_f_name)

        self.assertEqual(df_over_f.name, self.df_over_f_name)
        self.assertEqual(len(df_over_f.roi_response_series), 1)

        trace_name = self.dff_roi_response_series_metadata["name"]
        self.assertEqual(
            df_over_f[trace_name].description,
            self.dff_roi_response_series_metadata["description"],
        )

        self.assertEqual(df_over_f[trace_name].unit, "n.a.")

        self.assertAlmostEqual(
            df_over_f[trace_name].rate,
            segmentation_extractor.get_sampling_frequency(),
            places=3,
        )

        traces = segmentation_extractor.get_traces_dict()

        series_outer_data = df_over_f[trace_name].data
        assert_array_equal(series_outer_data.data.data, traces["dff"])

    def test_add_fluorescence_one_of_the_traces_is_none(self):
        """Test that roi response series with None values are not added to the
        nwbfile."""

        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_samples=self.num_samples,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
            has_neuropil_signal=False,
        )

        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        roi_response_series = ophys.get(self.fluorescence_name).roi_response_series

        assert "Neuropil" not in roi_response_series

        self.assertEqual(len(roi_response_series), 2)

    def test_add_fluorescence_one_of_the_traces_is_empty(self):
        """Test that roi response series with empty/None values are not added to the nwbfile."""

        # Use the public API to create an extractor without deconvolved trace
        # (passing None for deconvolved is equivalent to empty in the filtering logic)
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_samples=self.num_samples,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
            has_raw_signal=True,
            has_dff_signal=False,
            has_deconvolved_signal=False,  # No deconvolved signal
            has_neuropil_signal=True,
        )
        self.segmentation_extractor = segmentation_extractor

        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        roi_response_series = ophys.get(self.fluorescence_name).roi_response_series

        assert "Deconvolved" not in roi_response_series
        self.assertEqual(len(roi_response_series), 2)

    def test_add_fluorescence_one_of_the_traces_is_all_zeros(self):
        """Test that roi response series with all zero values ARE added to the
        nwbfile (zeros are valid data with size > 0, different from None/empty)."""

        # Zeros have size > 0, so they pass the filtering and are added
        # This is the correct behavior - zeros are valid data!
        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        roi_response_series = ophys.get(self.fluorescence_name).roi_response_series

        # All traces from dummy extractor are added (including if any were zeros)
        self.assertEqual(len(roi_response_series), 3)

    # TODO: Temporarily disabled - requires fix in roiextractors main for raw=None handling
    # See: https://github.com/catalystneuro/roiextractors/pull/508
    def _test_no_traces_are_added(self):
        """Test that no traces are added to the nwbfile if they are all zeros or
        None."""
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_samples=self.num_samples,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
            has_raw_signal=False,  # No signals at all
            has_dff_signal=False,
            has_deconvolved_signal=False,
            has_neuropil_signal=False,
        )

        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        assert self.fluorescence_name not in ophys.data_interfaces
        assert self.df_over_f_name not in ophys.data_interfaces

    def test_not_overwriting_fluorescence_if_same_name(self):
        """Test that adding fluorescence traces container with the same name will not
        overwrite the existing fluorescence container in nwbfile."""

        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        self.deconvolved_roi_response_series_metadata["description"] = "second description"

        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        roi_response_series = ophys.get(self.fluorescence_name).roi_response_series

        self.assertNotEqual(roi_response_series["Deconvolved"].description, "second description")

    def test_add_fluorescence_traces_to_nwbfile_to_existing_container(self):
        """Test that new traces can be added to an existing fluorescence container."""

        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_samples=self.num_samples,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
            has_raw_signal=True,
            has_dff_signal=False,
            has_deconvolved_signal=False,
            has_neuropil_signal=False,
        )

        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        roi_response_series = ophys.get(self.fluorescence_name).roi_response_series

        self.assertEqual(len(roi_response_series), 1)

        self.raw_roi_response_series_metadata["description"] = "second description"

        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_samples=self.num_samples,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )

        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        roi_response_series = ophys.get(self.fluorescence_name).roi_response_series

        self.assertEqual(len(roi_response_series), 3)

        # check that raw traces are not overwritten
        self.assertNotEqual(roi_response_series["RoiResponseSeries"].description, "second description")

    def test_add_fluorescence_traces_to_nwbfile_irregular_timestamps(self):
        """Test adding traces with irregular timestamps."""

        times = [0.0, 0.12, 0.15, 0.19, 0.1]
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=2,
            num_samples=5,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )
        segmentation_extractor.set_times(times)

        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        roi_response_series = ophys.get(self.fluorescence_name).roi_response_series
        for series_name in roi_response_series.keys():
            self.assertEqual(roi_response_series[series_name].rate, None)
            self.assertEqual(roi_response_series[series_name].starting_time, None)
            assert_array_equal(roi_response_series[series_name].timestamps.data, times)

    def test_add_fluorescence_traces_to_nwbfile_regular_timestamps(self):
        """Test that adding traces with regular timestamps, the 'timestamps' are not added
        to the NWB file, instead 'rate' and 'starting_time' is used."""

        times = np.arange(0, 5)
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=2,
            num_samples=5,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )
        segmentation_extractor.set_times(times)

        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        roi_response_series = ophys.get(self.fluorescence_name).roi_response_series
        for series_name in roi_response_series.keys():
            self.assertEqual(roi_response_series[series_name].rate, 1.0)
            self.assertEqual(roi_response_series[series_name].starting_time, times[0])
            self.assertEqual(roi_response_series[series_name].timestamps, None)

    def test_add_fluorescence_traces_to_nwbfile_with_plane_segmentation_name_specified(self):
        plane_segmentation_name = "plane_segmentation_name"
        metadata = _get_default_ophys_metadata_old_metadata_list()
        metadata = dict_deep_update(metadata, self.metadata)

        metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0].update(name=plane_segmentation_name)
        metadata["Ophys"]["Fluorescence"][plane_segmentation_name] = metadata["Ophys"]["Fluorescence"].pop(
            "PlaneSegmentation"
        )
        metadata["Ophys"]["DfOverF"][plane_segmentation_name] = metadata["Ophys"]["DfOverF"].pop("PlaneSegmentation")

        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=metadata,
            plane_segmentation_name=plane_segmentation_name,
        )

        ophys = get_module(self.nwbfile, "ophys")
        image_segmentation = ophys.get("ImageSegmentation")

        assert len(image_segmentation.plane_segmentations) == 1
        assert plane_segmentation_name in image_segmentation.plane_segmentations


# TODO: Drop this test class once support for list-based metadata is removed (September 2026).
# The dict-based equivalent is TestAddSegmentation.
class TestAddFluorescenceTracesMultiPlaneCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.num_rois_first_plane = 10
        cls.num_rois_second_plane = 5
        cls.num_samples = 20
        cls.num_rows = 25
        cls.num_columns = 20

        cls.session_start_time = datetime.now().astimezone()

        cls.metadata = _get_default_ophys_metadata_old_metadata_list()

        cls.plane_segmentation_first_plane_name = "PlaneSegmentationFirstPlane"
        cls.metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0].update(
            name=cls.plane_segmentation_first_plane_name
        )

        cls.fluorescence_name = "Fluorescence"
        cls.df_over_f_name = "DfOverF"

        cls.raw_roi_response_series_metadata = dict(
            name="RoiResponseSeries",
            description="raw fluorescence signal",
        )

        cls.dff_roi_response_series_metadata = dict(
            name="RoiResponseSeries",
            description="relative (df/f) fluorescence signal",
        )

        cls.deconvolved_roi_response_series_metadata = dict(
            name="Deconvolved",
            description="deconvolved fluorescence signal",
        )

        cls.neuropil_roi_response_series_metadata = dict(
            name="Neuropil",
            description="neuropil fluorescence signal",
            unit="test_unit",
        )

        cls.metadata["Ophys"]["Fluorescence"].update(
            {
                cls.plane_segmentation_first_plane_name: dict(
                    name=cls.fluorescence_name,
                    raw=cls.raw_roi_response_series_metadata,
                    deconvolved=cls.deconvolved_roi_response_series_metadata,
                    neuropil=cls.neuropil_roi_response_series_metadata,
                )
            }
        )
        cls.metadata["Ophys"]["DfOverF"].update(
            {
                cls.plane_segmentation_first_plane_name: dict(
                    name=cls.df_over_f_name,
                    dff=cls.dff_roi_response_series_metadata,
                )
            }
        )

    def setUp(self):
        self.segmentation_extractor_first_plane = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois_first_plane,
            num_samples=self.num_samples,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )
        self.segmentation_extractor_second_plane = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois_second_plane,
            num_samples=self.num_samples,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )
        self.nwbfile = NWBFile(
            session_description="session_description",
            identifier="file_id",
            session_start_time=self.session_start_time,
        )

    def test_add_fluorescence_traces_to_nwbfile_for_two_plane_segmentations(self):
        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor_first_plane,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            plane_segmentation_name=self.plane_segmentation_first_plane_name,
        )

        # Add second plane segmentation metadata
        metadata = deepcopy(self.metadata)
        second_imaging_plane_name = "ImagingPlaneSecondPlane"
        metadata["Ophys"]["ImagingPlane"][0].update(name=second_imaging_plane_name)

        second_plane_segmentation_name = "PlaneSegmentationSecondPlane"
        metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0].update(
            name=second_plane_segmentation_name,
            description="second plane segmentation description",
            imaging_plane=second_imaging_plane_name,
        )

        metadata["Ophys"]["Fluorescence"][second_plane_segmentation_name] = deepcopy(
            metadata["Ophys"]["Fluorescence"][self.plane_segmentation_first_plane_name]
        )
        metadata["Ophys"]["DfOverF"][second_plane_segmentation_name] = deepcopy(
            metadata["Ophys"]["DfOverF"][self.plane_segmentation_first_plane_name]
        )

        metadata["Ophys"]["Fluorescence"][second_plane_segmentation_name]["raw"].update(
            name="RoiResponseSeriesSecondPlane"
        )
        metadata["Ophys"]["Fluorescence"][second_plane_segmentation_name]["deconvolved"].update(
            name="DeconvolvedSecondPlane"
        )
        metadata["Ophys"]["Fluorescence"][second_plane_segmentation_name]["neuropil"].update(name="NeuropilSecondPlane")
        metadata["Ophys"]["DfOverF"][second_plane_segmentation_name]["dff"].update(name="RoiResponseSeriesSecondPlane")

        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor_second_plane,
            nwbfile=self.nwbfile,
            metadata=metadata,
            plane_segmentation_name=second_plane_segmentation_name,
        )

        ophys = get_module(self.nwbfile, "ophys")
        image_segmentation = ophys.get("ImageSegmentation")

        self.assertEqual(len(image_segmentation.plane_segmentations), 2)
        self.assertIn(self.plane_segmentation_first_plane_name, image_segmentation.plane_segmentations)
        self.assertIn(second_plane_segmentation_name, image_segmentation.plane_segmentations)
        second_plane_segmentation = image_segmentation.plane_segmentations[second_plane_segmentation_name]
        self.assertEqual(second_plane_segmentation.name, second_plane_segmentation_name)
        self.assertEqual(second_plane_segmentation.description, "second plane segmentation description")

        fluorescence = ophys.get(self.fluorescence_name)
        self.assertEqual(fluorescence.name, self.fluorescence_name)
        self.assertEqual(len(fluorescence.roi_response_series), 6)

        df_over_f = ophys.get(self.df_over_f_name)
        self.assertEqual(df_over_f.name, self.df_over_f_name)
        self.assertEqual(len(df_over_f.roi_response_series), 2)

        self.assertEqual(
            fluorescence.roi_response_series["RoiResponseSeriesSecondPlane"].data.maxshape,
            (self.num_samples, self.num_rois_second_plane),
        )
        self.assertEqual(
            df_over_f.roi_response_series["RoiResponseSeriesSecondPlane"].data.maxshape,
            (self.num_samples, self.num_rois_second_plane),
        )


# TODO: Drop this test class once support for list-based metadata is removed (September 2026).
# The dict-based equivalent is TestAddImaging.
class TestAddPhotonSeries(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session_start_time = datetime.now().astimezone()
        cls.num_samples = 30
        cls.num_rows = 10
        cls.num_columns = 15

        metadata = dict(Ophys=dict())

        cls.device_name = "optical_device"
        device_metadata = dict(name=cls.device_name)

        optical_channel_metadata = dict(
            name="optical_channel",
            emission_lambda=np.nan,
            description="description",
        )

        cls.imaging_plane_name = "imaging_plane_name"
        imaging_plane_metadata = dict(
            name=cls.imaging_plane_name,
            optical_channel=[optical_channel_metadata],
            description="image_plane_description",
            device=cls.device_name,
            excitation_lambda=np.nan,
            indicator="unknown",
            location="unknown",
        )

        metadata["Ophys"].update(
            Device=[device_metadata],
            ImagingPlane=[imaging_plane_metadata],
        )

        photon_series_metadata = dict(imaging_plane=cls.imaging_plane_name, unit="n.a.")

        cls.two_photon_series_metadata = deepcopy(metadata)
        cls.two_photon_series_name = "two_photon_series_name"
        cls.two_photon_series_metadata["Ophys"].update(
            dict(TwoPhotonSeries=[dict(name=cls.two_photon_series_name, **photon_series_metadata)])
        )

        cls.one_photon_series_metadata = deepcopy(metadata)
        cls.one_photon_series_name = "one_photon_series_name"
        cls.one_photon_series_metadata["Ophys"].update(
            dict(OnePhotonSeries=[dict(name=cls.one_photon_series_name, **photon_series_metadata)])
        )

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
        _add_photon_series_to_nwbfile_old_list_format(
            imaging=self.imaging_extractor, nwbfile=self.nwbfile, metadata=self.two_photon_series_metadata
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
            _add_photon_series_to_nwbfile_old_list_format(
                imaging=self.imaging_extractor,
                nwbfile=self.nwbfile,
                metadata=self.two_photon_series_metadata,
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
        _add_photon_series_to_nwbfile_old_list_format(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
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

    def test_iterator_options_propagation(self):
        """Test that iterator options are propagated to the data chunk iterator."""
        buffer_shape = (20, 5, 5)
        chunk_shape = (10, 5, 5)
        _add_photon_series_to_nwbfile_old_list_format(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
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
        _add_photon_series_to_nwbfile_old_list_format(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
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
        _add_photon_series_to_nwbfile_old_list_format(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
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
        _add_photon_series_to_nwbfile_old_list_format(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
            iterator_type="v2",
            iterator_options=dict(chunk_mb=chunk_mb),
        )
        acquisition_modules = self.nwbfile.acquisition
        assert self.two_photon_series_name in acquisition_modules
        data_chunk_iterator = acquisition_modules[self.two_photon_series_name].data
        chunk_shape = data_chunk_iterator.chunk_shape
        assert_array_equal(chunk_shape, data_chunk_iterator.maxshape)

    def test_add_two_photon_series_roundtrip(self):
        _add_photon_series_to_nwbfile_old_list_format(
            imaging=self.imaging_extractor, nwbfile=self.nwbfile, metadata=self.two_photon_series_metadata
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
            _add_photon_series_to_nwbfile_old_list_format(
                imaging=self.imaging_extractor,
                nwbfile=self.nwbfile,
                metadata=self.two_photon_series_metadata,
                photon_series_type="invalid",
            )

    def test_add_one_photon_series(self):
        """Test adding one photon series with metadata."""

        metadata = deepcopy(self.one_photon_series_metadata)
        one_photon_series_metadata = metadata["Ophys"]["OnePhotonSeries"][0]
        one_photon_series_metadata.update(
            pmt_gain=60.0,
            binning=2,
            power=500.0,
        )
        _add_photon_series_to_nwbfile_old_list_format(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=metadata,
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
        _add_photon_series_to_nwbfile_old_list_format(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.one_photon_series_metadata,
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

    def test_add_photon_series_to_nwbfile_old_list_format_invalid_module_name_raises(self):
        """Test that adding photon series with invalid module name raises error."""
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg="'parent_container' must be either 'acquisition' or 'processing/ophys'.",
        ):
            _add_photon_series_to_nwbfile_old_list_format(
                imaging=self.imaging_extractor,
                nwbfile=self.nwbfile,
                metadata=self.two_photon_series_metadata,
                parent_container="test",
            )

    def test_add_one_photon_series_to_processing(self):
        """Test adding one photon series to ophys processing module."""
        metadata = self.one_photon_series_metadata
        metadata["Ophys"]["OnePhotonSeries"][0].update(name="OnePhotonSeriesProcessed")

        _add_photon_series_to_nwbfile_old_list_format(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.one_photon_series_metadata,
            photon_series_type="OnePhotonSeries",
            photon_series_index=0,
            parent_container="processing/ophys",
        )
        ophys = self.nwbfile.processing["ophys"]
        self.assertIn("OnePhotonSeriesProcessed", ophys.data_interfaces)

    def test_ophys_module_not_created_when_photon_series_added_to_acquisition(self):
        """Test that ophys module is not created when photon series are added to nwbfile.acquisition."""
        _add_photon_series_to_nwbfile_old_list_format(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
        )
        self.assertNotIn("ophys", self.nwbfile.processing)
        self.assertEqual(len(self.nwbfile.processing), 0)

    def test_add_multiple_one_photon_series_with_same_imaging_plane(self):
        """Test adding two OnePhotonSeries that use the same ImagingPlane."""
        shared_photon_series_metadata = deepcopy(self.one_photon_series_metadata)
        shared_imaging_plane_name = "same_imaging_plane_for_two_series"

        shared_photon_series_metadata["Ophys"]["ImagingPlane"][0]["name"] = shared_imaging_plane_name
        shared_photon_series_metadata["Ophys"]["OnePhotonSeries"][0]["imaging_plane"] = shared_imaging_plane_name

        _add_photon_series_to_nwbfile_old_list_format(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=shared_photon_series_metadata,
            photon_series_type="OnePhotonSeries",
        )

        shared_photon_series_metadata["Ophys"]["OnePhotonSeries"][0]["name"] = "second_photon_series"
        _add_photon_series_to_nwbfile_old_list_format(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=shared_photon_series_metadata,
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
        segmentation_images_metadata = dict(
            name=cls.segmentation_images_name,
            description="description",
            PlaneSegmentation=dict(
                correlation=dict(name=cls.correlation_image_name, description="test description for correlation image"),
                mean=dict(name=cls.mean_image_name, description="test description for mean image"),
            ),
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

        images_metadata = self.metadata["Ophys"]["SegmentationImages"]["PlaneSegmentation"]
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
        )

        ophys = self.nwbfile.get_processing_module("ophys")
        assert self.segmentation_images_name not in ophys.data_interfaces

    def test_extractor_with_no_summary_images_and_no_ophys_module(self):
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rows=10, num_columns=15, has_summary_images=False
        )

        _add_summary_images_to_nwbfile(
            nwbfile=self.nwbfile, segmentation_extractor=segmentation_extractor, metadata=self.metadata
        )

        assert len(self.nwbfile.processing) == 0

    def test_add_summary_images_to_nwbfile_invalid_plane_segmentation_name(self):
        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg="Plane segmentation 'invalid_plane_segmentation_name' not found in metadata['Ophys']['SegmentationImages']",
        ):
            _add_summary_images_to_nwbfile(
                nwbfile=self.nwbfile,
                segmentation_extractor=generate_dummy_segmentation_extractor(num_rows=10, num_columns=15),
                metadata=self.metadata,
                plane_segmentation_name="invalid_plane_segmentation_name",
            )

    def test_add_summary_images_to_nwbfile_from_two_planes(self):
        segmentation_extractor_first_plane = generate_dummy_segmentation_extractor(num_rows=10, num_columns=15)

        _add_summary_images_to_nwbfile(
            nwbfile=self.nwbfile,
            segmentation_extractor=segmentation_extractor_first_plane,
            metadata=self.metadata,
            plane_segmentation_name="PlaneSegmentation",
        )

        metadata = deepcopy(self.metadata)
        segmentation_images_metadata = metadata["Ophys"]["SegmentationImages"]
        images_metadata = segmentation_images_metadata["PlaneSegmentation"]
        images_metadata["mean"].update(name="test_mean_image_name")
        images_metadata["correlation"].update(name="test_correlation_image_name")
        plane_segmentation_name = "test_plane_segmentation_name"
        segmentation_images_metadata.update(
            {plane_segmentation_name: segmentation_images_metadata["PlaneSegmentation"]}
        )

        segmentation_extractor_second_plane = generate_dummy_segmentation_extractor(num_rows=10, num_columns=15)

        _add_summary_images_to_nwbfile(
            nwbfile=self.nwbfile,
            segmentation_extractor=segmentation_extractor_second_plane,
            metadata=metadata,
            plane_segmentation_name=plane_segmentation_name,
        )

        ophys = self.nwbfile.get_processing_module("ophys")
        images_collection = ophys.data_interfaces[self.segmentation_images_name]
        extracted_images_number = len(images_collection.images)
        self.assertEqual(extracted_images_number, 4)

        extracted_images_dict = {img_name: img.data.T for img_name, img in images_collection.images.items()}
        expected_images_second_plane = segmentation_extractor_second_plane.get_images_dict()

        images_metadata = metadata["Ophys"]["SegmentationImages"][plane_segmentation_name]
        for image_name, image_data in expected_images_second_plane.items():
            image_name_from_metadata = images_metadata[image_name]["name"]
            np.testing.assert_almost_equal(image_data, extracted_images_dict[image_name_from_metadata])


class TestNoMetadataMutation:
    def test_get_default_ophys_metadata_old_metadata_list_returns_independent_instances(self):
        """Test that _get_default_ophys_metadata_old_metadata_list() returns independent instances that don't share mutable state."""
        # Get two instances
        metadata1 = _get_default_ophys_metadata_old_metadata_list()
        metadata2 = _get_default_ophys_metadata_old_metadata_list()

        # Store a snapshot of metadata2's Ophys section before mutating metadata1
        metadata2_ophys_before = deepcopy(metadata2["Ophys"])

        # Modify first instance deeply (modify nested dicts and lists)
        metadata1["Ophys"]["Device"][0]["name"] = "ModifiedMicroscope"
        metadata1["Ophys"]["ImagingPlane"][0]["name"] = "ModifiedImagingPlane"
        metadata1["Ophys"]["Fluorescence"]["PlaneSegmentation"]["raw"]["name"] = "ModifiedRoiResponseSeries"

        # Verify second instance's Ophys section was not affected by mutations to first instance
        assert (
            metadata2["Ophys"] == metadata2_ophys_before
        ), "Modifying metadata1 affected metadata2 - instances share mutable state"

        # Get a third instance after modifications to ensure fresh defaults
        metadata3 = _get_default_ophys_metadata_old_metadata_list()
        assert (
            metadata3["Ophys"] == metadata2_ophys_before
        ), "New instance after mutations differs from original - not getting fresh defaults"

    def test_add_devices_to_nwbfile_does_not_mutate_metadata(self):
        """Test that add_devices_to_nwbfile does not mutate the input metadata."""
        nwbfile = mock_NWBFile()

        # Create metadata with devices
        metadata = {"Ophys": {"Device": [{"name": "TestMicroscope", "description": "Test description"}]}}

        # Deep copy to compare entire structure before and after
        metadata_before = deepcopy(metadata)

        # Call function
        add_devices_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        # Verify metadata was not mutated - compare entire dict structure
        assert metadata == metadata_before, "Metadata was mutated"

    def test_add_imaging_plane_no_metadata_mutation(self):
        """Test that _add_imaging_plane_to_nwbfile_old_list_format does not mutate the input metadata."""
        nwbfile = mock_NWBFile()

        # Create metadata with imaging plane (all fields provided)
        metadata = {
            "Ophys": {
                "Device": [{"name": "TestMicroscope"}],
                "ImagingPlane": [
                    {
                        "name": "TestImagingPlane",
                        "description": "Test imaging plane",
                        "excitation_lambda": 488.0,
                        "indicator": "GCaMP6f",
                        "location": "V1",
                        "device": "TestMicroscope",
                        "optical_channel": [
                            {
                                "name": "Green",
                                "emission_lambda": 510.0,
                                "description": "Green channel",
                            }
                        ],
                    }
                ],
            }
        }

        # Deep copy to compare entire structure before and after
        metadata_before = deepcopy(metadata)

        # Call function
        _add_imaging_plane_to_nwbfile_old_list_format(
            nwbfile=nwbfile, metadata=metadata, imaging_plane_name="TestImagingPlane"
        )

        # Verify metadata was not mutated - compare entire dict structure
        assert metadata == metadata_before, "Metadata was mutated"

    def test_add_imaging_plane_no_partial_metadata_mutation(self):
        """Test that _add_imaging_plane_to_nwbfile_old_list_format does not mutate partial user metadata when complemented with defaults."""
        nwbfile = mock_NWBFile()

        # Create metadata with minimal imaging plane (missing some fields that will be filled from defaults)
        metadata = {
            "Ophys": {
                "Device": [{"name": "TestMicroscope"}],
                "ImagingPlane": [
                    {
                        "name": "TestImagingPlane",
                        "device": "TestMicroscope",
                        "optical_channel": [
                            {
                                "name": "Green",
                                "emission_lambda": 510.0,
                                "description": "Green channel",
                            }
                        ],
                        # Intentionally missing: description, excitation_lambda, indicator, location
                    }
                ],
            }
        }

        # Deep copy to compare entire structure before and after
        metadata_before = deepcopy(metadata)

        # Call function (should fill in missing fields internally but not mutate the input)
        _add_imaging_plane_to_nwbfile_old_list_format(
            nwbfile=nwbfile, metadata=metadata, imaging_plane_name="TestImagingPlane"
        )

        # Verify metadata was not mutated - compare entire dict structure
        assert metadata == metadata_before, "Metadata was mutated"

    def test_add_photon_series_no_metadata_mutation(self):
        """Test that _add_photon_series_to_nwbfile_old_list_format does not mutate the input metadata."""
        from roiextractors.testing import generate_dummy_imaging_extractor

        nwbfile = mock_NWBFile()
        imaging_extractor = generate_dummy_imaging_extractor(
            num_rows=10, num_columns=10, num_samples=30, sampling_frequency=30.0
        )

        # Create metadata with photon series
        metadata = {
            "Ophys": {
                "Device": [{"name": "TestMicroscope"}],
                "ImagingPlane": [
                    {
                        "name": "TestImagingPlane",
                        "description": "Test imaging plane",
                        "excitation_lambda": 488.0,
                        "indicator": "GCaMP6f",
                        "location": "V1",
                        "device": "TestMicroscope",
                        "optical_channel": [
                            {
                                "name": "Green",
                                "emission_lambda": 510.0,
                                "description": "Green channel",
                            }
                        ],
                    }
                ],
                "TwoPhotonSeries": [
                    {
                        "name": "TestTwoPhotonSeries",
                        "description": "Test two photon series",
                        "unit": "px",
                        "imaging_plane": "TestImagingPlane",
                    }
                ],
            }
        }

        # Deep copy to compare entire structure before and after
        metadata_before = deepcopy(metadata)

        # Call function
        _add_photon_series_to_nwbfile_old_list_format(
            imaging=imaging_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type="TwoPhotonSeries",
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

        # Create metadata with plane segmentation
        metadata = {
            "Ophys": {
                "Device": [{"name": "TestMicroscope"}],
                "ImagingPlane": [
                    {
                        "name": "TestImagingPlane",
                        "description": "Test imaging plane",
                        "excitation_lambda": 488.0,
                        "indicator": "GCaMP6f",
                        "location": "V1",
                        "device": "TestMicroscope",
                        "optical_channel": [
                            {
                                "name": "Green",
                                "emission_lambda": 510.0,
                                "description": "Green channel",
                            }
                        ],
                    }
                ],
                "ImageSegmentation": {
                    "name": "TestImageSegmentation",
                    "plane_segmentations": [
                        {
                            "name": "TestPlaneSegmentation",
                            "description": "Test plane segmentation",
                            "imaging_plane": "TestImagingPlane",
                        }
                    ],
                },
            }
        }

        # Deep copy to compare entire structure before and after
        metadata_before = deepcopy(metadata)

        # Call function
        _add_plane_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            plane_segmentation_name="TestPlaneSegmentation",
        )

        # Verify metadata was not mutated - compare entire dict structure
        assert metadata == metadata_before, "Metadata was mutated"

    def test_add_fluorescence_traces_no_metadata_mutation(self):
        """Test that add_fluorescence_traces_to_nwbfile does not mutate the input metadata."""
        from roiextractors.testing import generate_dummy_segmentation_extractor

        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor()

        # Create metadata with fluorescence traces
        metadata = {
            "Ophys": {
                "Device": [{"name": "TestMicroscope"}],
                "ImagingPlane": [
                    {
                        "name": "TestImagingPlane",
                        "description": "Test imaging plane",
                        "excitation_lambda": 488.0,
                        "indicator": "GCaMP6f",
                        "location": "V1",
                        "device": "TestMicroscope",
                        "optical_channel": [
                            {
                                "name": "Green",
                                "emission_lambda": 510.0,
                                "description": "Green channel",
                            }
                        ],
                    }
                ],
                "ImageSegmentation": {
                    "name": "TestImageSegmentation",
                    "plane_segmentations": [
                        {
                            "name": "PlaneSegmentation",
                            "description": "Test plane segmentation",
                            "imaging_plane": "TestImagingPlane",
                        }
                    ],
                },
                "Fluorescence": {
                    "PlaneSegmentation": {
                        "raw": {
                            "name": "RoiResponseSeries",
                            "description": "Raw fluorescence",
                            "unit": "n.a.",
                        },
                        "deconvolved": {
                            "name": "Deconvolved",
                            "description": "Deconvolved fluorescence",
                            "unit": "n.a.",
                        },
                        "neuropil": {
                            "name": "Neuropil",
                            "description": "Neuropil fluorescence",
                            "unit": "n.a.",
                        },
                    },
                },
                "DfOverF": {
                    "PlaneSegmentation": {
                        "dff": {
                            "name": "RoiResponseSeries",
                            "description": "DfOverF",
                            "unit": "n.a.",
                        }
                    },
                },
            }
        }

        # Deep copy to compare entire structure before and after
        metadata_before = deepcopy(metadata)

        # Call function
        add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
        )

        # Verify metadata was not mutated - compare entire dict structure
        assert metadata == metadata_before, "Metadata was mutated"


class TestAddImaging:
    """Tests for the dict-based metadata imaging pipeline (add_imaging_to_nwbfile)."""

    def test_basic(self):
        """Test expected values for no metadata specification."""
        nwbfile = mock_NWBFile()
        num_samples = 10
        num_rows = 5
        num_columns = 5
        imaging = generate_dummy_imaging_extractor(num_samples=num_samples, num_rows=num_rows, num_columns=num_columns)

        add_imaging_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
        )

        default_metadata = _get_ophys_metadata_placeholders()
        default_key = "default_metadata_key"
        default_device_metadata = default_metadata["Devices"][default_key]
        default_plane_metadata = default_metadata["Ophys"]["ImagingPlanes"][default_key]
        default_series_metadata = default_metadata["Ophys"]["MicroscopySeries"][default_key]

        # Default device
        assert len(nwbfile.devices) == 1
        device = nwbfile.devices[default_device_metadata["name"]]
        assert device.name == default_device_metadata["name"]

        # Default imaging plane
        assert len(nwbfile.imaging_planes) == 1
        plane = nwbfile.imaging_planes[default_plane_metadata["name"]]
        assert plane.name == default_plane_metadata["name"]
        assert np.isnan(plane.excitation_lambda)
        assert plane.indicator == default_plane_metadata["indicator"]
        assert plane.location == default_plane_metadata["location"]
        assert plane.device is device

        # Default series with correct data shape
        assert len(nwbfile.acquisition) == 1
        series = nwbfile.acquisition[default_series_metadata["name"]]
        assert series.name == default_series_metadata["name"]
        assert series.unit == default_series_metadata["unit"]
        assert series.imaging_plane is plane
        assert isinstance(series.data, ImagingExtractorDataChunkIterator)
        assert series.data.maxshape == (num_samples, num_rows, num_columns)

        # No ophys processing module created when series is in acquisition, no side effects
        assert "ophys" not in nwbfile.processing

    def test_full_metadata_specification(self):
        """Full metadata specification: device, imaging plane, and series are created from user metadata."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        metadata = get_full_ophys_metadata()
        metadata_key = "my_series"
        add_imaging_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key=metadata_key,
        )

        series_metadata = metadata["Ophys"]["MicroscopySeries"][metadata_key]
        plane_key = series_metadata["imaging_plane_metadata_key"]
        plane_metadata = metadata["Ophys"]["ImagingPlanes"][plane_key]
        device_key = plane_metadata["device_metadata_key"]
        device_metadata = metadata["Devices"][device_key]

        device = nwbfile.devices[device_metadata["name"]]
        assert device.description == device_metadata["description"]

        plane = nwbfile.imaging_planes[plane_metadata["name"]]
        assert plane.description == plane_metadata["description"]
        assert plane.indicator == plane_metadata["indicator"]
        assert plane.location == plane_metadata["location"]
        assert plane.device is device

        series = nwbfile.acquisition[series_metadata["name"]]
        assert series.description == series_metadata["description"]
        assert series.imaging_plane is plane

    def test_no_imaging_plane_metadata_key(self):
        """When microscopy series has no imaging_plane_metadata_key, a default imaging plane is created."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        metadata = {
            "Ophys": {
                "MicroscopySeries": {
                    "my_series": {
                        "name": "TwoPhotonSeries",
                        "description": "Imaging data",
                        "unit": "n.a.",
                    },
                },
            },
        }

        add_imaging_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type="TwoPhotonSeries",
            metadata_key="my_series",
        )

        default_metadata = _get_ophys_metadata_placeholders()
        default_key = "default_metadata_key"
        default_plane_metadata = default_metadata["Ophys"]["ImagingPlanes"][default_key]
        default_device_metadata = default_metadata["Devices"][default_key]

        # Default imaging plane
        plane = nwbfile.imaging_planes[default_plane_metadata["name"]]
        assert plane.name == default_plane_metadata["name"]

        # Default device
        device = nwbfile.devices[default_device_metadata["name"]]
        assert device.name == default_device_metadata["name"]
        assert plane.device is device

    def test_no_device_metadata_key(self):
        """When imaging plane has no device_metadata_key, a default device is created."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        metadata = {
            "Ophys": {
                "ImagingPlanes": {
                    "my_plane": {
                        "name": "ImagingPlane",
                        "description": "A plane",
                        "excitation_lambda": 920.0,
                        "indicator": "GCaMP6s",
                        "location": "V1",
                        "optical_channel": [
                            {
                                "name": "Green",
                                "description": "GCaMP emission",
                                "emission_lambda": 510.0,
                            }
                        ],
                    },
                },
                "MicroscopySeries": {
                    "my_series": {
                        "name": "TwoPhotonSeries",
                        "description": "Imaging data",
                        "unit": "n.a.",
                        "imaging_plane_metadata_key": "my_plane",
                    },
                },
            },
        }

        add_imaging_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type="TwoPhotonSeries",
            metadata_key="my_series",
        )

        default_metadata = _get_ophys_metadata_placeholders()
        default_key = "default_metadata_key"
        default_device_metadata = default_metadata["Devices"][default_key]

        device = nwbfile.devices[default_device_metadata["name"]]
        assert device.name == default_device_metadata["name"]
        plane = nwbfile.imaging_planes["ImagingPlane"]
        assert plane.device is device

    def test_shared_imaging_plane_two_microscopy_series(self):
        """Two microscopy series referencing the same imaging plane via imaging_plane_metadata_key."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        shared_plane_key = "shared_plane"
        first_series_key = "series_a"
        second_series_key = "series_b"
        metadata = {
            "Devices": {
                "my_device": {
                    "name": "Microscope",
                    "description": "Two-photon microscope",
                },
            },
            "Ophys": {
                "ImagingPlanes": {
                    shared_plane_key: {
                        "name": "SharedImagingPlane",
                        "description": "Shared plane",
                        "excitation_lambda": 920.0,
                        "indicator": "GCaMP6s",
                        "location": "V1",
                        "device_metadata_key": "my_device",
                        "optical_channel": [{"name": "Green", "description": "GCaMP", "emission_lambda": 510.0}],
                    },
                },
                "MicroscopySeries": {
                    first_series_key: {
                        "name": "TwoPhotonSeriesA",
                        "description": "First series",
                        "unit": "n.a.",
                        "imaging_plane_metadata_key": shared_plane_key,
                    },
                    second_series_key: {
                        "name": "TwoPhotonSeriesB",
                        "description": "Second series",
                        "unit": "n.a.",
                        "imaging_plane_metadata_key": shared_plane_key,
                    },
                },
            },
        }

        add_imaging_to_nwbfile(imaging=imaging, nwbfile=nwbfile, metadata=metadata, metadata_key=first_series_key)
        add_imaging_to_nwbfile(imaging=imaging, nwbfile=nwbfile, metadata=metadata, metadata_key=second_series_key)

        device_metadata = metadata["Devices"]["my_device"]
        plane_metadata = metadata["Ophys"]["ImagingPlanes"][shared_plane_key]
        first_series_metadata = metadata["Ophys"]["MicroscopySeries"][first_series_key]
        second_series_metadata = metadata["Ophys"]["MicroscopySeries"][second_series_key]

        # One device, one plane, two series
        assert len(nwbfile.devices) == 1
        assert len(nwbfile.imaging_planes) == 1
        assert len(nwbfile.acquisition) == 2

        # Device
        device = nwbfile.devices[device_metadata["name"]]
        assert device.name == device_metadata["name"]
        assert device.description == device_metadata["description"]

        # Imaging plane
        plane = nwbfile.imaging_planes[plane_metadata["name"]]
        assert plane.name == plane_metadata["name"]
        assert plane.description == plane_metadata["description"]
        assert plane.excitation_lambda == plane_metadata["excitation_lambda"]
        assert plane.indicator == plane_metadata["indicator"]
        assert plane.location == plane_metadata["location"]
        assert plane.device is device

        # Both series share the same imaging plane
        series_a = nwbfile.acquisition[first_series_metadata["name"]]
        assert series_a.description == first_series_metadata["description"]
        assert series_a.unit == first_series_metadata["unit"]
        assert series_a.imaging_plane is plane

        series_b = nwbfile.acquisition[second_series_metadata["name"]]
        assert series_b.description == second_series_metadata["description"]
        assert series_b.unit == second_series_metadata["unit"]
        assert series_b.imaging_plane is plane

    def test_shared_device_two_imaging_planes(self):
        """Two imaging planes referencing the same device via device_metadata_key."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        metadata = {
            "Devices": {
                "shared_device_key": {
                    "name": "SharedMicroscope",
                    "description": "Shared two-photon microscope",
                },
            },
            "Ophys": {
                "ImagingPlanes": {
                    "plane_v1": {
                        "name": "ImagingPlaneV1",
                        "description": "Visual cortex V1",
                        "excitation_lambda": 920.0,
                        "indicator": "GCaMP6s",
                        "location": "V1",
                        "device_metadata_key": "shared_device_key",
                        "optical_channel": [{"name": "Green", "description": "GCaMP", "emission_lambda": 510.0}],
                    },
                    "plane_v2": {
                        "name": "ImagingPlaneV2",
                        "description": "Visual cortex V2",
                        "excitation_lambda": 920.0,
                        "indicator": "GCaMP6f",
                        "location": "V2",
                        "device_metadata_key": "shared_device_key",
                        "optical_channel": [{"name": "Green", "description": "GCaMP", "emission_lambda": 510.0}],
                    },
                },
                "MicroscopySeries": {
                    "series_v1": {
                        "name": "TwoPhotonSeriesV1",
                        "description": "V1 imaging",
                        "unit": "n.a.",
                        "imaging_plane_metadata_key": "plane_v1",
                    },
                    "series_v2": {
                        "name": "TwoPhotonSeriesV2",
                        "description": "V2 imaging",
                        "unit": "n.a.",
                        "imaging_plane_metadata_key": "plane_v2",
                    },
                },
            },
        }

        add_imaging_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type="TwoPhotonSeries",
            metadata_key="series_v1",
        )
        add_imaging_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type="TwoPhotonSeries",
            metadata_key="series_v2",
        )

        device_metadata = metadata["Devices"]["shared_device_key"]

        # One device, two planes, two series
        assert len(nwbfile.devices) == 1
        assert len(nwbfile.imaging_planes) == 2
        assert len(nwbfile.acquisition) == 2

        # Device matches metadata
        unique_device = nwbfile.devices[device_metadata["name"]]
        assert unique_device.name == device_metadata["name"]
        assert unique_device.description == device_metadata["description"]

        # Both planes share the same device
        assert nwbfile.imaging_planes["ImagingPlaneV1"].device is unique_device
        assert nwbfile.imaging_planes["ImagingPlaneV2"].device is unique_device

    def test_repeated_calls_reuse_default_metadata_placeholders(self):
        """Repeated calls reuse the same placeholder device and imaging plane.

        Default metadata values are placeholders, not real data. When the user does not provide
        metadata, neuroconv should not fabricate additional objects on each call. Instead, the
        same placeholder device and placeholder so downstream tools might identify can
        flag this.
        """
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        first_metadata_key = "first"
        second_metadata_key = "second"
        metadata = {
            "Ophys": {
                "MicroscopySeries": {
                    first_metadata_key: {
                        "name": "TwoPhotonSeriesFirst",
                        "unit": "n.a.",
                    },
                    second_metadata_key: {
                        "name": "TwoPhotonSeriesSecond",
                        "unit": "n.a.",
                    },
                },
            },
        }

        add_imaging_to_nwbfile(imaging=imaging, nwbfile=nwbfile, metadata=metadata, metadata_key=first_metadata_key)
        add_imaging_to_nwbfile(imaging=imaging, nwbfile=nwbfile, metadata=metadata, metadata_key=second_metadata_key)

        # Placeholder device and imaging plane are reused, not duplicated
        assert len(nwbfile.devices) == 1
        assert len(nwbfile.imaging_planes) == 1
        assert len(nwbfile.acquisition) == 2

    def test_missing_required_imaging_plane_fields_raises(self):
        """When an imaging plane entry is missing schema-required fields, a clear error is raised."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        metadata_key = "my_series"
        device_key = "my_device"
        plane_key = "my_plane"
        metadata = {
            "Devices": {device_key: {"name": "Microscope"}},
            "Ophys": {
                "ImagingPlanes": {
                    plane_key: {
                        "name": "ImagingPlane",
                        "device_metadata_key": device_key,
                    },
                },
                "MicroscopySeries": {
                    metadata_key: {
                        "name": "TwoPhotonSeries",
                        "unit": "n.a.",
                        "imaging_plane_metadata_key": plane_key,
                    },
                },
            },
        }

        expected_error = re.escape(
            "Imaging plane metadata is missing required fields.\n"
            "For a complete NWB file, the following fields should be provided. If missing, a placeholder can be used instead:\n"
            "  excitation_lambda: nan\n"
            "  indicator: 'unknown'\n"
            "  location: 'unknown'\n"
            "  optical_channel: [{'name': 'OpticalChannel', 'emission_lambda': nan, 'description': 'An optical channel of the microscope.'}]"
        )
        with pytest.raises(ValueError, match=expected_error):
            add_imaging_to_nwbfile(imaging=imaging, nwbfile=nwbfile, metadata=metadata, metadata_key=metadata_key)

    def test_missing_required_series_fields_raises(self):
        """When a series entry is missing schema-required fields, a clear error is raised."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        metadata_key = "my_series"
        metadata = {
            "Ophys": {
                "MicroscopySeries": {
                    metadata_key: {
                        "name": "TwoPhotonSeries",
                    },
                },
            },
        }

        expected_error = re.escape(
            "Microscopy series metadata is missing required fields.\n"
            "For a complete NWB file, the following fields should be provided. If missing, a placeholder can be used instead:\n"
            "  unit: 'n.a.'"
        )
        with pytest.raises(ValueError, match=expected_error):
            add_imaging_to_nwbfile(imaging=imaging, nwbfile=nwbfile, metadata=metadata, metadata_key=metadata_key)

    def test_one_photon_series(self):
        """OnePhotonSeries is created correctly with extra NWB fields."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        metadata = get_full_ophys_metadata()
        series_key = "my_series"
        metadata["Ophys"]["MicroscopySeries"][series_key]["pmt_gain"] = 60.0
        metadata["Ophys"]["MicroscopySeries"][series_key]["binning"] = 2
        metadata["Ophys"]["MicroscopySeries"][series_key]["power"] = 500.0

        add_imaging_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key=series_key,
            photon_series_type="OnePhotonSeries",
        )

        series_name = metadata["Ophys"]["MicroscopySeries"][series_key]["name"]
        series = nwbfile.acquisition[series_name]
        assert isinstance(series, OnePhotonSeries)
        assert series.pmt_gain == 60.0
        assert series.binning == 2
        assert series.power == 500.0
        assert series.unit == metadata["Ophys"]["MicroscopySeries"][series_key]["unit"]

    def test_photon_series_to_processing(self):
        """Photon series can be added to processing/ophys instead of acquisition."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        metadata = get_full_ophys_metadata()
        series_key = "my_series"

        add_imaging_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key=series_key,
            parent_container="processing/ophys",
        )

        series_name = metadata["Ophys"]["MicroscopySeries"][series_key]["name"]
        assert len(nwbfile.acquisition) == 0
        ophys_module = nwbfile.processing["ophys"]
        assert series_name in ophys_module.data_interfaces

    def test_iterator_options_propagation(self):
        """Iterator options are passed through to the data chunk iterator."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=30, num_rows=10, num_columns=15)

        metadata = get_full_ophys_metadata()
        series_key = "my_series"
        buffer_shape = (20, 5, 5)
        chunk_shape = (10, 5, 5)

        add_imaging_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key=series_key,
            iterator_options=dict(buffer_shape=buffer_shape, chunk_shape=chunk_shape),
        )

        series_name = metadata["Ophys"]["MicroscopySeries"][series_key]["name"]
        data_iterator = nwbfile.acquisition[series_name].data
        assert isinstance(data_iterator, ImagingExtractorDataChunkIterator)
        assert data_iterator.buffer_shape == buffer_shape
        assert data_iterator.chunk_shape == chunk_shape

    def test_non_iterative_write(self):
        """Data is written directly when iterator_type=None."""
        nwbfile = mock_NWBFile()
        num_samples = 10
        num_rows = 5
        num_columns = 5
        imaging = generate_dummy_imaging_extractor(num_samples=num_samples, num_rows=num_rows, num_columns=num_columns)

        metadata = get_full_ophys_metadata()
        series_key = "my_series"

        add_imaging_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key=series_key,
            iterator_type=None,
        )

        series_name = metadata["Ophys"]["MicroscopySeries"][series_key]["name"]
        series = nwbfile.acquisition[series_name]
        assert not isinstance(series.data, ImagingExtractorDataChunkIterator)
        assert series.data.shape == (num_samples, num_columns, num_rows)

    def test_metadata_not_mutated(self):
        """Dict-based metadata is not mutated by add_imaging_to_nwbfile."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        metadata = get_full_ophys_metadata()
        metadata_before = deepcopy(metadata)

        add_imaging_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key="my_series",
        )

        assert metadata == metadata_before, "Metadata was mutated"


class TestAddSegmentation:
    """Tests for the dict-based metadata segmentation pipeline (add_segmentation_to_nwbfile)."""

    def test_basic(self):
        """No metadata: defaults created (device, plane, PlaneSegmentation, traces)."""
        nwbfile = mock_NWBFile()
        num_samples = 20
        num_rois = 10
        num_rows = 25
        num_columns = 20
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_samples=num_samples, num_rois=num_rois, num_rows=num_rows, num_columns=num_columns
        )

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
        )

        # When no metadata is passed, _get_ophys_metadata_placeholders() is used internally.
        # The placeholders are dict-based, so _is_dict_based_metadata() returns True and the
        # new dict-based code path is used with metadata_key="default_metadata_key".
        placeholders = _get_ophys_metadata_placeholders()
        default_key = "default_metadata_key"
        default_device_metadata = placeholders["Devices"][default_key]
        default_plane_metadata = placeholders["Ophys"]["ImagingPlanes"][default_key]
        default_plane_seg_metadata = placeholders["Ophys"]["PlaneSegmentations"][default_key]

        # Default device
        assert len(nwbfile.devices) == 1
        device = nwbfile.devices[default_device_metadata["name"]]
        assert device.name == default_device_metadata["name"]

        # Default imaging plane
        assert len(nwbfile.imaging_planes) == 1
        plane = nwbfile.imaging_planes[default_plane_metadata["name"]]
        assert plane.name == default_plane_metadata["name"]
        assert np.isnan(plane.excitation_lambda)
        assert plane.indicator == default_plane_metadata["indicator"]
        assert plane.location == default_plane_metadata["location"]
        assert plane.device is device

        # PlaneSegmentation
        ophys_module = nwbfile.processing["ophys"]
        image_segmentation = ophys_module["ImageSegmentation"]
        assert default_plane_seg_metadata["name"] in image_segmentation.plane_segmentations
        plane_seg = image_segmentation.plane_segmentations[default_plane_seg_metadata["name"]]
        assert plane_seg.name == default_plane_seg_metadata["name"]
        assert plane_seg.description == default_plane_seg_metadata["description"]
        assert plane_seg.imaging_plane is plane
        assert len(plane_seg.id) == num_rois

        # All traces are added to a single Fluorescence container (no DfOverF split),
        # mirroring ndx-microscopy's single-container approach.
        assert "Fluorescence" in ophys_module.data_interfaces
        assert "DfOverF" not in ophys_module.data_interfaces

    def test_full_metadata_specification(self):
        """Full metadata specification: device, imaging plane, and segmentation are created from user metadata."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_samples=10, num_rois=5, num_rows=15, num_columns=15
        )

        metadata = get_full_ophys_metadata()
        metadata_key = "my_segmentation"

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key=metadata_key,
        )

        plane_seg_metadata = metadata["Ophys"]["PlaneSegmentations"][metadata_key]
        plane_key = plane_seg_metadata["imaging_plane_metadata_key"]
        plane_metadata = metadata["Ophys"]["ImagingPlanes"][plane_key]
        device_key = plane_metadata["device_metadata_key"]
        device_metadata = metadata["Devices"][device_key]

        device = nwbfile.devices[device_metadata["name"]]
        assert device.description == device_metadata["description"]

        plane = nwbfile.imaging_planes[plane_metadata["name"]]
        assert plane.description == plane_metadata["description"]
        assert plane.indicator == plane_metadata["indicator"]
        assert plane.location == plane_metadata["location"]
        assert plane.device is device

        ophys_module = nwbfile.processing["ophys"]
        image_segmentation = ophys_module["ImageSegmentation"]
        plane_seg = image_segmentation.plane_segmentations[plane_seg_metadata["name"]]
        assert plane_seg.description == plane_seg_metadata["description"]
        assert plane_seg.imaging_plane is plane

    def test_no_imaging_plane_metadata_key(self):
        """PlaneSegmentation without imaging_plane_metadata_key: default plane created."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_samples=10, num_rois=5, num_rows=15, num_columns=15
        )

        metadata = {
            "Ophys": {
                "PlaneSegmentations": {
                    "my_seg": {
                        "name": "PlaneSegmentation",
                        "description": "Segmented ROIs",
                    },
                },
                "RoiResponses": {
                    "my_seg": {
                        "raw": {"name": "RoiResponseSeries", "unit": "n.a."},
                    },
                },
            },
        }

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key="my_seg",
        )

        default_metadata = _get_ophys_metadata_placeholders()
        default_key = "default_metadata_key"
        default_plane_metadata = default_metadata["Ophys"]["ImagingPlanes"][default_key]
        default_device_metadata = default_metadata["Devices"][default_key]

        # Default imaging plane
        assert len(nwbfile.imaging_planes) == 1
        plane = nwbfile.imaging_planes[default_plane_metadata["name"]]
        assert plane.name == default_plane_metadata["name"]

        # Default device
        assert len(nwbfile.devices) == 1
        device = nwbfile.devices[default_device_metadata["name"]]
        assert device.name == default_device_metadata["name"]
        assert plane.device is device

    def test_no_device_metadata_key(self):
        """When imaging plane has no device_metadata_key, a default device is created."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_samples=10, num_rois=5, num_rows=15, num_columns=15
        )

        metadata = {
            "Ophys": {
                "ImagingPlanes": {
                    "my_plane": {
                        "name": "ImagingPlane",
                        "description": "A plane",
                        "excitation_lambda": 920.0,
                        "indicator": "GCaMP6s",
                        "location": "V1",
                        "optical_channel": [
                            {
                                "name": "Green",
                                "description": "GCaMP emission",
                                "emission_lambda": 510.0,
                            }
                        ],
                    },
                },
                "PlaneSegmentations": {
                    "my_seg": {
                        "name": "PlaneSegmentation",
                        "description": "Segmented ROIs",
                        "imaging_plane_metadata_key": "my_plane",
                    },
                },
                "RoiResponses": {
                    "my_seg": {
                        "raw": {"name": "RoiResponseSeries", "description": "Raw traces", "unit": "n.a."},
                    },
                },
            },
        }

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key="my_seg",
        )

        default_metadata = _get_ophys_metadata_placeholders()
        default_key = "default_metadata_key"
        default_device_metadata = default_metadata["Devices"][default_key]

        # Default device created and linked
        assert len(nwbfile.devices) == 1
        device = nwbfile.devices[default_device_metadata["name"]]
        assert device.name == default_device_metadata["name"]

        # User-specified imaging plane uses the default device
        plane_metadata = metadata["Ophys"]["ImagingPlanes"]["my_plane"]
        plane = nwbfile.imaging_planes[plane_metadata["name"]]
        assert plane.description == plane_metadata["description"]
        assert plane.excitation_lambda == plane_metadata["excitation_lambda"]
        assert plane.indicator == plane_metadata["indicator"]
        assert plane.location == plane_metadata["location"]
        assert plane.device is device

    def test_shared_imaging_plane_two_segmentations(self):
        """Two segmentations reference same ImagingPlane: 1 plane, 2 PlaneSegmentations."""
        nwbfile = mock_NWBFile()
        seg_a = generate_dummy_segmentation_extractor(num_samples=10, num_rois=5, num_rows=15, num_columns=15)
        seg_b = generate_dummy_segmentation_extractor(num_samples=10, num_rois=3, num_rows=15, num_columns=15)

        shared_plane_key = "shared_plane"
        metadata = {
            "Devices": {
                "dev": {"name": "MyDevice"},
            },
            "Ophys": {
                "ImagingPlanes": {
                    shared_plane_key: {
                        "name": "SharedPlane",
                        "excitation_lambda": 920.0,
                        "indicator": "GCaMP6f",
                        "location": "V1",
                        "device_metadata_key": "dev",
                        "optical_channel": [
                            {"name": "Green", "emission_lambda": 525.0, "description": "Green channel"},
                        ],
                    },
                },
                "PlaneSegmentations": {
                    "seg_a": {
                        "name": "PlaneSegmentationA",
                        "description": "First segmentation",
                        "imaging_plane_metadata_key": shared_plane_key,
                    },
                    "seg_b": {
                        "name": "PlaneSegmentationB",
                        "description": "Second segmentation",
                        "imaging_plane_metadata_key": shared_plane_key,
                    },
                },
                "RoiResponses": {
                    "seg_a": {
                        "raw": {"name": "RoiResponseSeriesA", "description": "Raw A", "unit": "n.a."},
                    },
                    "seg_b": {
                        "raw": {"name": "RoiResponseSeriesB", "description": "Raw B", "unit": "n.a."},
                    },
                },
            },
        }

        add_segmentation_to_nwbfile(
            segmentation_extractor=seg_a, nwbfile=nwbfile, metadata=metadata, metadata_key="seg_a"
        )
        add_segmentation_to_nwbfile(
            segmentation_extractor=seg_b, nwbfile=nwbfile, metadata=metadata, metadata_key="seg_b"
        )

        device_metadata = metadata["Devices"]["dev"]
        plane_metadata = metadata["Ophys"]["ImagingPlanes"][shared_plane_key]
        seg_a_metadata = metadata["Ophys"]["PlaneSegmentations"]["seg_a"]
        seg_b_metadata = metadata["Ophys"]["PlaneSegmentations"]["seg_b"]

        # 1 device, 1 imaging plane, 2 plane segmentations
        assert len(nwbfile.devices) == 1
        assert len(nwbfile.imaging_planes) == 1

        device = nwbfile.devices[device_metadata["name"]]
        assert device.name == device_metadata["name"]

        plane = nwbfile.imaging_planes[plane_metadata["name"]]
        assert plane.name == plane_metadata["name"]
        assert plane.excitation_lambda == plane_metadata["excitation_lambda"]
        assert plane.indicator == plane_metadata["indicator"]
        assert plane.location == plane_metadata["location"]
        assert plane.device is device

        ophys_module = nwbfile.processing["ophys"]
        image_segmentation = ophys_module["ImageSegmentation"]
        assert len(image_segmentation.plane_segmentations) == 2

        ps_a = image_segmentation.plane_segmentations[seg_a_metadata["name"]]
        assert ps_a.description == seg_a_metadata["description"]
        assert ps_a.imaging_plane is plane

        ps_b = image_segmentation.plane_segmentations[seg_b_metadata["name"]]
        assert ps_b.description == seg_b_metadata["description"]
        assert ps_b.imaging_plane is plane

    def test_metadata_not_mutated(self):
        """deepcopy metadata before call, assert equal after."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor()

        metadata = get_full_ophys_metadata()
        metadata_before = deepcopy(metadata)

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key="my_segmentation",
        )

        assert metadata == metadata_before, "Metadata was mutated"

    def test_no_roi_responses_metadata(self):
        """When no RoiResponses metadata is provided but extractor has traces, write with placeholder metadata."""
        nwbfile = mock_NWBFile()
        num_rois = 5
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_samples=10,
            num_rois=num_rois,
            num_rows=15,
            num_columns=15,
        )

        metadata = {
            "Ophys": {
                "PlaneSegmentations": {
                    "my_seg": {
                        "name": "PlaneSegmentation",
                        "description": "Cell ROIs",
                    },
                },
            },
        }

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key="my_seg",
        )

        # PlaneSegmentation exists with correct metadata
        ophys_module = nwbfile.processing["ophys"]
        image_segmentation = ophys_module["ImageSegmentation"]
        assert "PlaneSegmentation" in image_segmentation.plane_segmentations
        plane_seg = image_segmentation.plane_segmentations["PlaneSegmentation"]
        assert plane_seg.description == "Cell ROIs"
        assert len(plane_seg.id) == num_rois

        # Fluorescence container created with placeholder trace names
        fluorescence = ophys_module["Fluorescence"]
        expected_placeholder_names = {"RoiResponseSeries", "DfOverF", "Neuropil", "Deconvolved"}
        assert set(fluorescence.roi_response_series.keys()) == expected_placeholder_names

        # Verify traces are linked to the correct PlaneSegmentation
        for series in fluorescence.roi_response_series.values():
            roi_table_region = series.rois
            assert roi_table_region.table is plane_seg

    def test_no_roi_responses_no_traces(self):
        """When no RoiResponses metadata and no traces, only PlaneSegmentation is written."""
        nwbfile = mock_NWBFile()
        num_rois = 5
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_samples=10,
            num_rois=num_rois,
            num_rows=15,
            num_columns=15,
            has_raw_signal=False,
            has_dff_signal=False,
            has_deconvolved_signal=False,
            has_neuropil_signal=False,
        )

        metadata = {
            "Ophys": {
                "PlaneSegmentations": {
                    "my_seg": {
                        "name": "PlaneSegmentation",
                        "description": "Cell ROIs",
                    },
                },
            },
        }

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key="my_seg",
        )

        # PlaneSegmentation exists with correct metadata
        ophys_module = nwbfile.processing["ophys"]
        image_segmentation = ophys_module["ImageSegmentation"]
        assert "PlaneSegmentation" in image_segmentation.plane_segmentations
        plane_seg = image_segmentation.plane_segmentations["PlaneSegmentation"]
        assert plane_seg.description == "Cell ROIs"
        assert len(plane_seg.id) == num_rois

        # No Fluorescence container since no traces and no RoiResponses metadata
        assert "Fluorescence" not in ophys_module.data_interfaces

    def test_roi_responses_metadata_but_no_traces_raises(self):
        """When RoiResponses metadata is provided but extractor has no traces, raise an error."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_samples=10,
            num_rois=5,
            num_rows=15,
            num_columns=15,
            has_raw_signal=False,
            has_dff_signal=False,
            has_deconvolved_signal=False,
            has_neuropil_signal=False,
        )

        metadata = {
            "Ophys": {
                "PlaneSegmentations": {
                    "my_seg": {
                        "name": "PlaneSegmentation",
                        "description": "Segmented ROIs",
                    },
                },
                "RoiResponses": {
                    "my_seg": {
                        "raw": {"name": "RoiResponseSeries", "unit": "n.a."},
                    },
                },
            },
        }

        with pytest.raises(ValueError, match="no trace data"):
            add_segmentation_to_nwbfile(
                segmentation_extractor=segmentation_extractor,
                nwbfile=nwbfile,
                metadata=metadata,
                metadata_key="my_seg",
            )

    def test_shared_device_two_imaging_planes(self):
        """Two segmentations with different imaging planes that share the same device."""
        nwbfile = mock_NWBFile()
        seg_a = generate_dummy_segmentation_extractor(num_samples=10, num_rois=5, num_rows=15, num_columns=15)
        seg_b = generate_dummy_segmentation_extractor(num_samples=10, num_rois=3, num_rows=15, num_columns=15)

        metadata = {
            "Devices": {
                "shared_device_key": {
                    "name": "SharedMicroscope",
                    "description": "Shared two-photon microscope",
                },
            },
            "Ophys": {
                "ImagingPlanes": {
                    "plane_v1": {
                        "name": "ImagingPlaneV1",
                        "description": "Visual cortex V1",
                        "excitation_lambda": 920.0,
                        "indicator": "GCaMP6s",
                        "location": "V1",
                        "device_metadata_key": "shared_device_key",
                        "optical_channel": [{"name": "Green", "description": "GCaMP", "emission_lambda": 510.0}],
                    },
                    "plane_v2": {
                        "name": "ImagingPlaneV2",
                        "description": "Visual cortex V2",
                        "excitation_lambda": 920.0,
                        "indicator": "GCaMP6f",
                        "location": "V2",
                        "device_metadata_key": "shared_device_key",
                        "optical_channel": [{"name": "Green", "description": "GCaMP", "emission_lambda": 510.0}],
                    },
                },
                "PlaneSegmentations": {
                    "seg_a": {
                        "name": "PlaneSegmentationA",
                        "description": "First segmentation",
                        "imaging_plane_metadata_key": "plane_v1",
                    },
                    "seg_b": {
                        "name": "PlaneSegmentationB",
                        "description": "Second segmentation",
                        "imaging_plane_metadata_key": "plane_v2",
                    },
                },
                "RoiResponses": {
                    "seg_a": {
                        "raw": {"name": "RoiResponseSeriesA", "description": "Raw A", "unit": "n.a."},
                    },
                    "seg_b": {
                        "raw": {"name": "RoiResponseSeriesB", "description": "Raw B", "unit": "n.a."},
                    },
                },
            },
        }

        add_segmentation_to_nwbfile(
            segmentation_extractor=seg_a, nwbfile=nwbfile, metadata=metadata, metadata_key="seg_a"
        )
        add_segmentation_to_nwbfile(
            segmentation_extractor=seg_b, nwbfile=nwbfile, metadata=metadata, metadata_key="seg_b"
        )

        device_metadata = metadata["Devices"]["shared_device_key"]
        plane_v1_metadata = metadata["Ophys"]["ImagingPlanes"]["plane_v1"]
        plane_v2_metadata = metadata["Ophys"]["ImagingPlanes"]["plane_v2"]

        # One device, two planes, two segmentations
        assert len(nwbfile.devices) == 1
        assert len(nwbfile.imaging_planes) == 2

        device = nwbfile.devices[device_metadata["name"]]
        assert device.name == device_metadata["name"]
        assert device.description == device_metadata["description"]

        plane_v1 = nwbfile.imaging_planes[plane_v1_metadata["name"]]
        assert plane_v1.description == plane_v1_metadata["description"]
        assert plane_v1.indicator == plane_v1_metadata["indicator"]
        assert plane_v1.location == plane_v1_metadata["location"]
        assert plane_v1.device is device

        plane_v2 = nwbfile.imaging_planes[plane_v2_metadata["name"]]
        assert plane_v2.description == plane_v2_metadata["description"]
        assert plane_v2.indicator == plane_v2_metadata["indicator"]
        assert plane_v2.location == plane_v2_metadata["location"]
        assert plane_v2.device is device

    def test_repeated_calls_reuse_default_metadata_placeholders(self):
        """Repeated calls without metadata reuse the same placeholder device and imaging plane."""
        nwbfile = mock_NWBFile()
        seg_a = generate_dummy_segmentation_extractor(num_samples=10, num_rois=5, num_rows=15, num_columns=15)
        seg_b = generate_dummy_segmentation_extractor(num_samples=10, num_rois=3, num_rows=15, num_columns=15)

        metadata = {
            "Ophys": {
                "PlaneSegmentations": {
                    "first": {
                        "name": "PlaneSegmentationFirst",
                        "description": "First segmentation",
                    },
                    "second": {
                        "name": "PlaneSegmentationSecond",
                        "description": "Second segmentation",
                    },
                },
                "RoiResponses": {
                    "first": {
                        "raw": {"name": "RoiResponseSeriesFirst", "unit": "n.a."},
                    },
                    "second": {
                        "raw": {"name": "RoiResponseSeriesSecond", "unit": "n.a."},
                    },
                },
            },
        }

        add_segmentation_to_nwbfile(
            segmentation_extractor=seg_a, nwbfile=nwbfile, metadata=metadata, metadata_key="first"
        )
        add_segmentation_to_nwbfile(
            segmentation_extractor=seg_b, nwbfile=nwbfile, metadata=metadata, metadata_key="second"
        )

        default_metadata = _get_ophys_metadata_placeholders()
        default_key = "default_metadata_key"
        default_device_metadata = default_metadata["Devices"][default_key]
        default_plane_metadata = default_metadata["Ophys"]["ImagingPlanes"][default_key]

        # Placeholder device and imaging plane are reused, not duplicated
        assert len(nwbfile.devices) == 1
        device = nwbfile.devices[default_device_metadata["name"]]
        assert device.name == default_device_metadata["name"]

        assert len(nwbfile.imaging_planes) == 1
        plane = nwbfile.imaging_planes[default_plane_metadata["name"]]
        assert plane.name == default_plane_metadata["name"]
        assert plane.device is device

        # Both segmentations created with correct metadata
        ophys_module = nwbfile.processing["ophys"]
        image_segmentation = ophys_module["ImageSegmentation"]
        assert len(image_segmentation.plane_segmentations) == 2
        assert image_segmentation.plane_segmentations["PlaneSegmentationFirst"].description == "First segmentation"
        assert image_segmentation.plane_segmentations["PlaneSegmentationSecond"].description == "Second segmentation"

    def test_traces_linked_to_correct_plane_segmentation(self):
        """Two segmentations with different planes: each trace references the correct PlaneSegmentation."""
        nwbfile = mock_NWBFile()
        seg_a = generate_dummy_segmentation_extractor(num_samples=10, num_rois=5, num_rows=15, num_columns=15)
        seg_b = generate_dummy_segmentation_extractor(num_samples=10, num_rois=3, num_rows=15, num_columns=15)

        metadata = {
            "Devices": {
                "dev": {"name": "Microscope"},
            },
            "Ophys": {
                "ImagingPlanes": {
                    "plane_a": {
                        "name": "ImagingPlaneA",
                        "excitation_lambda": 920.0,
                        "indicator": "GCaMP6s",
                        "location": "V1",
                        "device_metadata_key": "dev",
                        "optical_channel": [{"name": "Green", "description": "GCaMP", "emission_lambda": 510.0}],
                    },
                    "plane_b": {
                        "name": "ImagingPlaneB",
                        "excitation_lambda": 920.0,
                        "indicator": "GCaMP6f",
                        "location": "V2",
                        "device_metadata_key": "dev",
                        "optical_channel": [{"name": "Green", "description": "GCaMP", "emission_lambda": 510.0}],
                    },
                },
                "PlaneSegmentations": {
                    "seg_a": {
                        "name": "PlaneSegmentationA",
                        "description": "First segmentation",
                        "imaging_plane_metadata_key": "plane_a",
                    },
                    "seg_b": {
                        "name": "PlaneSegmentationB",
                        "description": "Second segmentation",
                        "imaging_plane_metadata_key": "plane_b",
                    },
                },
                "RoiResponses": {
                    "seg_a": {
                        "raw": {"name": "RoiResponseSeriesA", "unit": "n.a."},
                    },
                    "seg_b": {
                        "raw": {"name": "RoiResponseSeriesB", "unit": "n.a."},
                    },
                },
            },
        }

        add_segmentation_to_nwbfile(
            segmentation_extractor=seg_a, nwbfile=nwbfile, metadata=metadata, metadata_key="seg_a"
        )
        add_segmentation_to_nwbfile(
            segmentation_extractor=seg_b, nwbfile=nwbfile, metadata=metadata, metadata_key="seg_b"
        )

        ophys_module = nwbfile.processing["ophys"]
        fluorescence = ophys_module["Fluorescence"]

        series_a = fluorescence.roi_response_series["RoiResponseSeriesA"]
        series_b = fluorescence.roi_response_series["RoiResponseSeriesB"]

        assert series_a.rois.table.name == "PlaneSegmentationA"
        assert series_b.rois.table.name == "PlaneSegmentationB"

    def test_missing_required_plane_segmentation_fields_raises(self):
        """When PlaneSegmentation metadata is missing required fields, a clear error is raised."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor()

        metadata = {
            "Ophys": {
                "PlaneSegmentations": {
                    "my_seg": {
                        "name": "PlaneSegmentation",
                    },
                },
            },
        }

        expected_error = re.escape(
            "Plane segmentation metadata is missing required fields.\n"
            "For a complete NWB file, the following fields should be provided. If missing, a placeholder can be used instead:\n"
            "  description: 'Segmented ROIs'"
        )
        with pytest.raises(ValueError, match=expected_error):
            add_segmentation_to_nwbfile(
                segmentation_extractor=segmentation_extractor,
                nwbfile=nwbfile,
                metadata=metadata,
                metadata_key="my_seg",
            )

    def test_missing_required_roi_response_fields_raises(self):
        """When ROI response series metadata is missing required fields, a clear error is raised."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor()

        metadata = {
            "Ophys": {
                "PlaneSegmentations": {
                    "my_seg": {
                        "name": "PlaneSegmentation",
                        "description": "Segmented ROIs",
                    },
                },
                "RoiResponses": {
                    "my_seg": {
                        "raw": {"name": "RoiResponseSeries"},
                    },
                },
            },
        }

        expected_error = re.escape(
            "ROI response series 'raw' metadata is missing required fields.\n"
            "For a complete NWB file, the following fields should be provided. If missing, a placeholder can be used instead:\n"
            "  unit: 'n.a.'"
        )
        with pytest.raises(ValueError, match=expected_error):
            add_segmentation_to_nwbfile(
                segmentation_extractor=segmentation_extractor,
                nwbfile=nwbfile,
                metadata=metadata,
                metadata_key="my_seg",
            )

    def test_warns_when_metadata_specifies_missing_traces(self):
        """Warning is emitted when RoiResponses metadata references traces the extractor doesn't have."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor(
            has_neuropil_signal=False,
            has_deconvolved_signal=False,
        )

        metadata = {
            "Ophys": {
                "PlaneSegmentations": {
                    "my_seg": {
                        "name": "PlaneSegmentation",
                        "description": "Segmented ROIs",
                    },
                },
                "RoiResponses": {
                    "my_seg": {
                        "raw": {"name": "RoiResponseSeries", "unit": "n.a."},
                        "neuropil": {"name": "Neuropil", "unit": "n.a."},
                        "deconvolved": {"name": "Deconvolved", "unit": "n.a."},
                    },
                },
            },
        }

        with pytest.warns(UserWarning, match="RoiResponses metadata specifies traces"):
            add_segmentation_to_nwbfile(
                segmentation_extractor=segmentation_extractor,
                nwbfile=nwbfile,
                metadata=metadata,
                metadata_key="my_seg",
            )

    def test_image_masks_written_correctly(self):
        """Mask data values match the extractor's get_roi_image_masks()."""
        nwbfile = mock_NWBFile()
        num_rois = 4
        segmentation_extractor = generate_dummy_segmentation_extractor(num_rois=num_rois)

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
        )

        ophys_module = nwbfile.processing["ophys"]
        image_segmentation = ophys_module["ImageSegmentation"]
        (plane_seg,) = image_segmentation.plane_segmentations.values()

        image_masks = segmentation_extractor.get_roi_image_masks().T
        for index in range(num_rois):
            assert_array_equal(plane_seg["image_mask"][index], image_masks[index])

    def test_roi_properties_written_as_columns(self):
        """Custom properties added via set_property() appear as PlaneSegmentation columns."""
        nwbfile = mock_NWBFile()
        num_rois = 5
        segmentation_extractor = generate_dummy_segmentation_extractor(num_rois=num_rois)

        roi_ids = segmentation_extractor.get_roi_ids()
        custom_float = np.arange(num_rois, dtype=np.float32) * 0.5
        custom_bool = np.array([True, False, True, False, True])
        custom_label = np.array(["A", "B", "A", "C", "B"], dtype=object)

        segmentation_extractor.set_property("custom_float", custom_float, ids=roi_ids)
        segmentation_extractor.set_property("custom_bool", custom_bool, ids=roi_ids)
        segmentation_extractor.set_property("custom_label", custom_label, ids=roi_ids)

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
        )

        ophys_module = nwbfile.processing["ophys"]
        image_segmentation = ophys_module["ImageSegmentation"]
        (plane_seg,) = image_segmentation.plane_segmentations.values()

        for prop, expected in [
            ("custom_float", custom_float),
            ("custom_bool", custom_bool),
            ("custom_label", custom_label),
        ]:
            assert prop in plane_seg
            np.testing.assert_array_equal(plane_seg[prop].data, expected)

    def test_traces_with_regular_timestamps(self):
        """Regular timestamps produce rate/starting_time, not timestamps."""
        nwbfile = mock_NWBFile()
        num_samples = 5
        times = np.arange(0, num_samples)
        segmentation_extractor = generate_dummy_segmentation_extractor(num_samples=num_samples)
        segmentation_extractor.set_times(times)

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
        )

        ophys_module = nwbfile.processing["ophys"]
        fluorescence = ophys_module["Fluorescence"]
        for series in fluorescence.roi_response_series.values():
            assert series.rate == 1.0
            assert series.starting_time == 0.0
            assert series.timestamps is None

    def test_traces_with_irregular_timestamps(self):
        """Irregular timestamps are stored directly on the series."""
        nwbfile = mock_NWBFile()
        num_samples = 5
        times = [0.0, 0.12, 0.15, 0.19, 0.1]
        segmentation_extractor = generate_dummy_segmentation_extractor(num_samples=num_samples)
        segmentation_extractor.set_times(times)

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
        )

        ophys_module = nwbfile.processing["ophys"]
        fluorescence = ophys_module["Fluorescence"]
        for series in fluorescence.roi_response_series.values():
            assert series.rate is None
            assert series.starting_time is None
            assert_array_equal(series.timestamps.data, times)

    def test_traces_without_timestamps_uses_sampling_frequency(self):
        """When no timestamps are set, sampling frequency from the extractor is used."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor()

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
        )

        ophys_module = nwbfile.processing["ophys"]
        fluorescence = ophys_module["Fluorescence"]
        expected_rate = segmentation_extractor.get_sampling_frequency()
        for series in fluorescence.roi_response_series.values():
            assert series.rate == expected_rate
            assert series.starting_time == 0.0
            assert series.timestamps is None

    def test_trace_data_values_match_extractor(self):
        """Trace data written to NWB matches the extractor's get_traces_dict()."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor()

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
        )

        ophys_module = nwbfile.processing["ophys"]
        fluorescence = ophys_module["Fluorescence"]
        traces_dict = segmentation_extractor.get_traces_dict()
        available_traces = [data for data in traces_dict.values() if data is not None]

        assert len(fluorescence.roi_response_series) == len(available_traces)
        for series in fluorescence.roi_response_series.values():
            written_data = series.data.data.data
            assert any(np.array_equal(written_data, trace) for trace in available_traces)

    def test_roi_table_region_covers_all_rois(self):
        """Each RoiResponseSeries references all ROIs and the correct PlaneSegmentation."""
        nwbfile = mock_NWBFile()
        num_rois = 7
        segmentation_extractor = generate_dummy_segmentation_extractor(num_rois=num_rois)

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
        )

        ophys_module = nwbfile.processing["ophys"]
        image_segmentation = ophys_module["ImageSegmentation"]
        (plane_seg,) = image_segmentation.plane_segmentations.values()
        fluorescence = ophys_module["Fluorescence"]

        for series in fluorescence.roi_response_series.values():
            assert len(series.rois) == num_rois
            assert series.rois.table is plane_seg

    def test_iterator_options_propagation(self):
        """Iterator options are passed through to the SliceableDataChunkIterator."""
        nwbfile = mock_NWBFile()
        num_rois = 3
        num_samples = 10
        segmentation_extractor = generate_dummy_segmentation_extractor(num_rois=num_rois, num_samples=num_samples)

        chunk_shape = (num_samples // 2, num_rois)
        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            iterator_options=dict(chunk_shape=chunk_shape),
        )

        ophys_module = nwbfile.processing["ophys"]
        fluorescence = ophys_module["Fluorescence"]
        for series in fluorescence.roi_response_series.values():
            assert isinstance(series.data, SliceableDataChunkIterator)
            assert series.data.chunk_shape == chunk_shape
