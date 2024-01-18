import math
import unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
from types import MethodType
from typing import List, Literal, Optional, Tuple
from unittest.mock import Mock

import numpy as np
import psutil
import pynwb.testing.mock.file
from hdmf.data_utils import DataChunkIterator
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal, assert_raises
from numpy.typing import ArrayLike
from parameterized import param, parameterized
from pynwb import NWBHDF5IO, H5DataIO, NWBFile
from pynwb.device import Device
from pynwb.ophys import OnePhotonSeries
from roiextractors.testing import (
    generate_dummy_imaging_extractor,
    generate_dummy_segmentation_extractor,
)

from neuroconv.tools.nwb_helpers import get_module
from neuroconv.tools.roiextractors import (
    add_devices,
    add_fluorescence_traces,
    add_image_segmentation,
    add_imaging_plane,
    add_photon_series,
    add_plane_segmentation,
    add_summary_images,
    check_if_imaging_fits_into_memory,
)
from neuroconv.tools.roiextractors.imagingextractordatachunkiterator import (
    ImagingExtractorDataChunkIterator,
)
from neuroconv.tools.roiextractors.roiextractors import (
    get_default_segmentation_metadata,
)
from neuroconv.utils import dict_deep_update


class TestAddDevices(unittest.TestCase):
    def setUp(self):
        self.session_start_time = datetime.now().astimezone()
        self.nwbfile = NWBFile(
            session_description="session_description",
            identifier="file_id",
            session_start_time=self.session_start_time,
        )

        self.metadata = dict(Ophys=dict())

    def test_add_device(self):
        device_name = "new_device"
        device_list = [dict(name=device_name)]
        self.metadata["Ophys"].update(Device=device_list)
        add_devices(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 1
        assert device_name in devices

    def test_add_device_with_further_metadata(self):
        device_name = "new_device"
        description = "device_description"
        manufacturer = "manufacturer"

        device_list = [dict(name=device_name, description=description, manufacturer=manufacturer)]
        self.metadata["Ophys"].update(Device=device_list)
        add_devices(self.nwbfile, metadata=self.metadata)

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
        add_devices(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 2
        assert all(device_name in devices for device_name in device_name_list)

    def test_add_one_device_and_then_another(self):
        device_name1 = "new_device"
        device_list = [dict(name=device_name1)]
        self.metadata["Ophys"].update(Device=device_list)
        add_devices(self.nwbfile, metadata=self.metadata)

        device_name2 = "another_device"
        device_list = [dict(name=device_name2)]
        self.metadata["Ophys"].update(Device=device_list)
        add_devices(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 2
        assert device_name1 in devices
        assert device_name2 in devices

    def test_not_overwriting_devices(self):
        device_name1 = "same_device"
        device_list = [dict(name=device_name1)]
        self.metadata["Ophys"].update(Device=device_list)
        add_devices(self.nwbfile, metadata=self.metadata)

        device_name2 = "same_device"
        device_list = [dict(name=device_name2)]
        self.metadata["Ophys"].update(Device=device_list)
        add_devices(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 1
        assert device_name1 in devices

    def test_add_device_defaults(self):
        add_devices(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 1
        assert "Microscope" in devices

    def test_add_empty_device_list_in_metadata(self):
        device_list = []
        self.metadata["Ophys"].update(Device=device_list)
        add_devices(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 0

    def test_device_object(self):
        device_name = "device_object"
        device_object = Device(name=device_name)
        device_list = [device_object]
        self.metadata["Ophys"].update(Device=device_list)
        add_devices(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 1
        assert device_name in devices

    def test_device_object_and_metadata_mix(self):
        device_object = Device(name="device_object")
        device_metadata = dict(name="device_metadata")
        device_list = [device_object, device_metadata]
        self.metadata["Ophys"].update(Device=device_list)
        add_devices(self.nwbfile, metadata=self.metadata)

        devices = self.nwbfile.devices

        assert len(devices) == 2
        assert "device_metadata" in devices
        assert "device_object" in devices


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

    def test_add_imaging_plane(self):
        add_imaging_plane(nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_name=self.imaging_plane_name)

        imaging_planes = self.nwbfile.imaging_planes
        assert len(imaging_planes) == 1
        assert self.imaging_plane_name in imaging_planes

        imaging_plane = imaging_planes[self.imaging_plane_name]
        assert imaging_plane.description == self.imaging_plane_description

    def test_not_overwriting_imaging_plane_if_same_name(self):
        add_imaging_plane(nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_name=self.imaging_plane_name)

        self.imaging_plane_metadata["description"] = "modified description"
        add_imaging_plane(nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_name=self.imaging_plane_name)

        imaging_planes = self.nwbfile.imaging_planes
        assert len(imaging_planes) == 1
        assert self.imaging_plane_name in imaging_planes

    def test_add_two_imaging_planes(self):
        # Add the first imaging plane
        first_imaging_plane_name = "first_imaging_plane_name"
        first_imaging_plane_description = "first_imaging_plane_description"
        self.imaging_plane_metadata["name"] = first_imaging_plane_name
        self.imaging_plane_metadata["description"] = first_imaging_plane_description
        add_imaging_plane(nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_name=first_imaging_plane_name)

        # Add the second imaging plane
        second_imaging_plane_name = "second_imaging_plane_name"
        second_imaging_plane_description = "second_imaging_plane_description"
        self.imaging_plane_metadata["name"] = second_imaging_plane_name
        self.imaging_plane_metadata["description"] = second_imaging_plane_description
        add_imaging_plane(nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_name=second_imaging_plane_name)

        # Test expected values
        imaging_planes = self.nwbfile.imaging_planes
        assert len(imaging_planes) == 2

        first_imaging_plane = imaging_planes[first_imaging_plane_name]
        assert first_imaging_plane.name == first_imaging_plane_name
        assert first_imaging_plane.description == first_imaging_plane_description

        second_imaging_plane = imaging_planes[second_imaging_plane_name]
        assert second_imaging_plane.name == second_imaging_plane_name
        assert second_imaging_plane.description == second_imaging_plane_description

    def test_add_imaging_plane_raises_when_name_not_found_in_metadata(self):
        """Test adding an imaging plane raises an error when the name is not found in the metadata."""
        imaging_plane_name = "imaging_plane_non_existing_in_the_metadata"
        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg=f"Metadata for Imaging Plane '{imaging_plane_name}' not found in metadata['Ophys']['ImagingPlane'].",
        ):
            add_imaging_plane(nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_name=imaging_plane_name)

    def test_add_two_imaging_planes_from_metadata(self):
        """Test adding two imaging planes when there are multiple imaging plane metadata."""

        second_imaging_plane_name = "second_imaging_plane_name"
        metadata = deepcopy(self.metadata)
        imaging_planes_metadata = metadata["Ophys"]["ImagingPlane"]
        second_imaging_plane_metadata = deepcopy(metadata["Ophys"]["ImagingPlane"][0])
        second_imaging_plane_metadata.update(name="second_imaging_plane_name")
        imaging_planes_metadata.append(second_imaging_plane_metadata)
        add_imaging_plane(nwbfile=self.nwbfile, metadata=metadata, imaging_plane_name=self.imaging_plane_name)
        add_imaging_plane(nwbfile=self.nwbfile, metadata=metadata, imaging_plane_name="second_imaging_plane_name")

        # Test expected values
        imaging_planes = self.nwbfile.imaging_planes
        assert len(imaging_planes) == 2

        first_imaging_plane = imaging_planes[self.imaging_plane_name]
        assert first_imaging_plane.name == self.imaging_plane_name

        second_imaging_plane = imaging_planes[second_imaging_plane_name]
        assert second_imaging_plane.name == second_imaging_plane_name

    def test_add_imaging_plane_warns_when_index_is_used(self):
        """Test adding an imaging plane with the index specified warns with DeprecationWarning."""
        exc_msg = "Keyword argument 'imaging_plane_index' is deprecated and will be removed on or after Dec 1st, 2023. Use 'imaging_plane_name' to specify which imaging plane to add by its name."
        with self.assertWarnsWith(warn_type=DeprecationWarning, exc_msg=exc_msg):
            add_imaging_plane(nwbfile=self.nwbfile, metadata=self.metadata, imaging_plane_index=0)
            # Test expected values
            imaging_planes = self.nwbfile.imaging_planes
            assert len(imaging_planes) == 1

            imaging_plane = imaging_planes[self.imaging_plane_name]
            assert imaging_plane.name == self.imaging_plane_name


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

    def test_add_image_segmentation(self):
        """
        Test that add_image_segmentation method adds an image segmentation to the nwbfile
        specified by the metadata.
        """

        add_image_segmentation(nwbfile=self.nwbfile, metadata=self.metadata)

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


def assert_masks_equal(mask: List[List[Tuple[int, int, int]]], expected_mask: List[List[Tuple[int, int, int]]]):
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
        cls.num_frames = 20
        cls.num_rows = 25
        cls.num_columns = 20

        cls.session_start_time = datetime.now().astimezone()

        cls.image_segmentation_name = "image_segmentation_name"
        cls.plane_segmentation_name = "plane_segmentation_name"

    def setUp(self):
        self.segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_frames=self.num_frames,
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

    def test_add_plane_segmentation(self):
        """Test that add_plane_segmentation method adds a plane segmentation to the nwbfile
        specified by the metadata."""
        add_plane_segmentation(
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
        add_plane_segmentation(
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
        add_plane_segmentation(
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
                rejected_list=list(np.arange(0, 10)),
                expected_rejected_roi_ids=[1] * 10,
            ),
            param(
                rejected_list=[
                    2,
                    6,
                    8,
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
            num_frames=self.num_frames,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
            rejected_list=rejected_list,
        )

        add_plane_segmentation(
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
            num_frames=self.num_frames,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )

        def get_roi_pixel_masks(self, roi_ids: Optional[ArrayLike] = None) -> List[np.ndarray]:
            roi_ids = roi_ids or range(self.get_num_rois())
            pixel_masks = _generate_test_masks(num_rois=len(roi_ids), mask_type="pixel")
            return pixel_masks

        segmentation_extractor.get_roi_pixel_masks = MethodType(get_roi_pixel_masks, segmentation_extractor)

        add_plane_segmentation(
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
            num_frames=self.num_frames,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )

        def get_roi_pixel_masks(self, roi_ids: Optional[ArrayLike] = None) -> List[np.ndarray]:
            roi_ids = roi_ids or range(self.get_num_rois())
            voxel_masks = _generate_test_masks(num_rois=len(roi_ids), mask_type="voxel")
            return voxel_masks

        segmentation_extractor.get_roi_pixel_masks = MethodType(get_roi_pixel_masks, segmentation_extractor)

        add_plane_segmentation(
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

    def test_none_masks(self):
        """Test the None mask_type option for writing a plane segmentation table."""
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_frames=self.num_frames,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )

        add_plane_segmentation(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            mask_type=None,
            plane_segmentation_name=self.plane_segmentation_name,
        )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)
        plane_segmentations = image_segmentation.plane_segmentations

        plane_segmentation = plane_segmentations[self.plane_segmentation_name]
        assert "image_mask" not in plane_segmentation
        assert "pixel_mask" not in plane_segmentation
        assert "voxel_mask" not in plane_segmentation

    def test_pixel_masks_auto_switch(self):
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_frames=self.num_frames,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )

        def get_roi_pixel_masks(self, roi_ids: Optional[ArrayLike] = None) -> List[np.ndarray]:
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
            add_plane_segmentation(
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
            num_frames=self.num_frames,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )

        def get_roi_pixel_masks(self, roi_ids: Optional[ArrayLike] = None) -> List[np.ndarray]:
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
            add_plane_segmentation(
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

        add_plane_segmentation(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
            plane_segmentation_name=self.plane_segmentation_name,
        )

        self.plane_segmentation_metadata["description"] = "modified description"

        add_plane_segmentation(
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
        add_plane_segmentation(
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
        add_plane_segmentation(
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

    def test_add_plane_segmentation_raises_when_name_not_found_in_metadata(self):
        """Test adding a plane segmentation raises an error when the name is not found in the metadata."""
        plane_segmentation_name = "plane_segmentation_non_existing_in_the_metadata"
        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg=f"Metadata for Plane Segmentation '{plane_segmentation_name}' not found in metadata['Ophys']['ImageSegmentation']['plane_segmentations'].",
        ):
            add_plane_segmentation(
                segmentation_extractor=self.segmentation_extractor,
                nwbfile=self.nwbfile,
                metadata=self.metadata,
                plane_segmentation_name=plane_segmentation_name,
            )


class TestAddFluorescenceTraces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.num_rois = 10
        cls.num_frames = 20
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
            num_frames=self.num_frames,
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

    def test_add_fluorescence_traces(self):
        """Test fluorescence traces are added correctly to the nwbfile."""

        add_fluorescence_traces(
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

            # Check compression options are set
            assert isinstance(series_outer_data, H5DataIO)

            compression_parameters = series_outer_data.get_io_params()
            assert compression_parameters["compression"] == "gzip"

        # Check that df/F trace data is not being written to the Fluorescence container
        df_over_f = ophys.get(self.df_over_f_name)
        assert_raises(
            AssertionError,
            assert_array_equal,
            fluorescence["RoiResponseSeries"].data,
            df_over_f["RoiResponseSeries"].data,
        )

    def test_add_df_over_f_trace(self):
        """Test df/f traces are added to the nwbfile."""

        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_frames=self.num_frames,
            num_rows=300,
            num_columns=400,
            has_raw_signal=True,
            has_deconvolved_signal=False,
            has_neuropil_signal=False,
        )
        segmentation_extractor._roi_response_raw = None

        add_fluorescence_traces(
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

        # Check compression options are set
        assert isinstance(series_outer_data, H5DataIO)

        compression_parameters = series_outer_data.get_io_params()
        assert compression_parameters["compression"] == "gzip"

    def test_add_fluorescence_one_of_the_traces_is_none(self):
        """Test that roi response series with None values are not added to the
        nwbfile."""

        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_frames=self.num_frames,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
            has_neuropil_signal=False,
        )

        add_fluorescence_traces(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        roi_response_series = ophys.get(self.fluorescence_name).roi_response_series

        assert "Neuropil" not in roi_response_series

        self.assertEqual(len(roi_response_series), 2)

    def test_add_fluorescence_one_of_the_traces_is_empty(self):
        """Test that roi response series with empty values are not added to the nwbfile."""

        self.segmentation_extractor._roi_response_deconvolved = np.empty((self.num_frames, 0))

        add_fluorescence_traces(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        roi_response_series = ophys.get(self.fluorescence_name).roi_response_series

        assert "Deconvolved" not in roi_response_series
        self.assertEqual(len(roi_response_series), 2)

    def test_add_fluorescence_one_of_the_traces_is_all_zeros(self):
        """Test that roi response series with all zero values are not added to the
        nwbfile."""

        self.segmentation_extractor._roi_response_deconvolved = np.zeros((self.num_rois, self.num_frames))

        add_fluorescence_traces(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        roi_response_series = ophys.get(self.fluorescence_name).roi_response_series

        # assert "Deconvolved" not in roi_response_series
        self.assertEqual(len(roi_response_series), 3)

    def test_no_traces_are_added(self):
        """Test that no traces are added to the nwbfile if they are all zeros or
        None."""
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_frames=self.num_frames,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
            has_raw_signal=True,
            has_dff_signal=False,
            has_deconvolved_signal=False,
            has_neuropil_signal=False,
        )

        segmentation_extractor._roi_response_raw = None

        add_fluorescence_traces(
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

        add_fluorescence_traces(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        self.deconvolved_roi_response_series_metadata["description"] = "second description"

        add_fluorescence_traces(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        roi_response_series = ophys.get(self.fluorescence_name).roi_response_series

        self.assertNotEqual(roi_response_series["Deconvolved"].description, "second description")

    def test_add_fluorescence_traces_to_existing_container(self):
        """Test that new traces can be added to an existing fluorescence container."""

        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois,
            num_frames=self.num_frames,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
            has_raw_signal=True,
            has_dff_signal=False,
            has_deconvolved_signal=False,
            has_neuropil_signal=False,
        )

        add_fluorescence_traces(
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
            num_frames=self.num_frames,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )

        add_fluorescence_traces(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        roi_response_series = ophys.get(self.fluorescence_name).roi_response_series

        self.assertEqual(len(roi_response_series), 3)

        # check that raw traces are not overwritten
        self.assertNotEqual(roi_response_series["RoiResponseSeries"].description, "second description")

    def test_add_fluorescence_traces_irregular_timestamps(self):
        """Test adding traces with irregular timestamps."""

        times = [0.0, 0.12, 0.15, 0.19, 0.1]
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=2,
            num_frames=5,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )
        segmentation_extractor.set_times(times)

        add_fluorescence_traces(
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

    def test_add_fluorescence_traces_regular_timestamps(self):
        """Test that adding traces with regular timestamps, the 'timestamps' are not added
        to the NWB file, instead 'rate' and 'starting_time' is used."""

        times = np.arange(0, 5)
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=2,
            num_frames=5,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )
        segmentation_extractor.set_times(times)

        add_fluorescence_traces(
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

    def test_add_fluorescence_traces_regular_timestamps_with_metadata(self):
        """Test adding traces with regular timestamps and also metadata-specified rate."""
        times = np.arange(0, 5)
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=2,
            num_frames=5,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )
        segmentation_extractor.set_times(times)

        metadata = deepcopy(self.metadata)
        metadata["Ophys"]["Fluorescence"]["PlaneSegmentation"]["raw"].update(rate=1.23)
        metadata["Ophys"]["DfOverF"]["PlaneSegmentation"]["dff"].update(rate=1.23)

        add_fluorescence_traces(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        roi_response_series = ophys.get(self.fluorescence_name).roi_response_series
        for series_name in roi_response_series.keys():
            self.assertEqual(roi_response_series[series_name].rate, 1.23)
            self.assertEqual(roi_response_series[series_name].starting_time, 0)
            self.assertEqual(roi_response_series[series_name].timestamps, None)

    def test_add_fluorescence_traces_irregular_timestamps_with_metadata(self):
        """Test adding traces with default timestamps and metadata rates (auto included in current segmentation interfaces)."""
        times = [0.0, 0.12, 0.15, 0.19, 0.1]
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rois=2,
            num_frames=5,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )
        segmentation_extractor.set_times(times)

        metadata = deepcopy(self.metadata)
        metadata["Ophys"]["Fluorescence"]["PlaneSegmentation"]["raw"].update(rate=1.23)

        add_fluorescence_traces(
            segmentation_extractor=segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=metadata,
        )

        ophys = get_module(self.nwbfile, "ophys")
        roi_response_series = ophys.get(self.fluorescence_name).roi_response_series
        for series_name in roi_response_series.keys():
            self.assertEqual(roi_response_series[series_name].rate, None)
            self.assertEqual(roi_response_series[series_name].starting_time, None)
            assert_array_equal(roi_response_series[series_name].timestamps.data, times)

    def test_add_fluorescence_traces_with_plane_segmentation_name_specified(self):
        plane_segmentation_name = "plane_segmentation_name"
        metadata = get_default_segmentation_metadata()
        metadata = dict_deep_update(metadata, self.metadata)

        metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0].update(name=plane_segmentation_name)
        metadata["Ophys"]["Fluorescence"][plane_segmentation_name] = metadata["Ophys"]["Fluorescence"].pop(
            "PlaneSegmentation"
        )
        metadata["Ophys"]["DfOverF"][plane_segmentation_name] = metadata["Ophys"]["DfOverF"].pop("PlaneSegmentation")

        add_fluorescence_traces(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=metadata,
            plane_segmentation_name=plane_segmentation_name,
        )

        ophys = get_module(self.nwbfile, "ophys")
        image_segmentation = ophys.get("ImageSegmentation")

        assert len(image_segmentation.plane_segmentations) == 1
        assert plane_segmentation_name in image_segmentation.plane_segmentations


class TestAddFluorescenceTracesMultiPlaneCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.num_rois_first_plane = 10
        cls.num_rois_second_plane = 5
        cls.num_frames = 20
        cls.num_rows = 25
        cls.num_columns = 20

        cls.session_start_time = datetime.now().astimezone()

        cls.metadata = get_default_segmentation_metadata()

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
            num_frames=self.num_frames,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )
        self.segmentation_extractor_second_plane = generate_dummy_segmentation_extractor(
            num_rois=self.num_rois_second_plane,
            num_frames=self.num_frames,
            num_rows=self.num_rows,
            num_columns=self.num_columns,
        )
        self.nwbfile = NWBFile(
            session_description="session_description",
            identifier="file_id",
            session_start_time=self.session_start_time,
        )

    def test_add_fluorescence_traces_for_two_plane_segmentations(self):
        add_fluorescence_traces(
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

        add_fluorescence_traces(
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
            (self.num_frames, self.num_rois_second_plane),
        )
        self.assertEqual(
            df_over_f.roi_response_series["RoiResponseSeriesSecondPlane"].data.maxshape,
            (self.num_frames, self.num_rois_second_plane),
        )


class TestAddPhotonSeries(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session_start_time = datetime.now().astimezone()
        cls.num_frames = 30
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
            self.num_frames, num_rows=self.num_rows, num_columns=self.num_columns
        )

    def test_default_values(self):
        """Test adding two photon series with default values."""
        add_photon_series(
            imaging=self.imaging_extractor, nwbfile=self.nwbfile, metadata=self.two_photon_series_metadata
        )

        # Check data
        acquisition_modules = self.nwbfile.acquisition
        assert self.two_photon_series_name in acquisition_modules
        data_in_hdfm_data_io = acquisition_modules[self.two_photon_series_name].data
        data_chunk_iterator = data_in_hdfm_data_io.data
        assert isinstance(data_chunk_iterator, ImagingExtractorDataChunkIterator)

        two_photon_series_extracted = np.concatenate([data_chunk.data for data_chunk in data_chunk_iterator])
        # NWB stores images as num_columns x num_rows
        expected_two_photon_series_shape = (self.num_frames, self.num_columns, self.num_rows)
        assert two_photon_series_extracted.shape == expected_two_photon_series_shape
        expected_two_photon_series_data = self.imaging_extractor.get_video().transpose((0, 2, 1))
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
            "'iterator_type' must be either 'v1', 'v2' (recommended), or None.",
        ):
            add_photon_series(
                imaging=self.imaging_extractor,
                nwbfile=self.nwbfile,
                metadata=self.two_photon_series_metadata,
                iterator_type="invalid",
            )

    def test_non_iterative_write_assertion(self):
        # Estimate num of frames required to exceed memory capabilities
        dtype = self.imaging_extractor.get_dtype()
        element_size_in_bytes = dtype.itemsize
        image_size = self.imaging_extractor.get_image_size()

        available_memory_in_bytes = psutil.virtual_memory().available

        excess = 1.5  # Of what is available in memory
        num_frames_to_overflow = (available_memory_in_bytes * excess) / (element_size_in_bytes * math.prod(image_size))

        # Mock recording extractor with as many frames as necessary to overflow memory
        mock_imaging = Mock()
        mock_imaging.get_dtype.return_value = dtype
        mock_imaging.get_image_size.return_value = image_size
        mock_imaging.get_num_frames.return_value = num_frames_to_overflow

        reg_expression = (
            "Memory error, full TwoPhotonSeries data is (.*?) GB are available! Please use iterator_type='v2'"
        )

        with self.assertRaisesRegex(MemoryError, reg_expression):
            check_if_imaging_fits_into_memory(imaging=mock_imaging)

    def test_non_iterative_two_photon(self):
        """Test adding two photon series with using DataChunkIterator as iterator type."""
        add_photon_series(
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
        expected_two_photon_series_shape = (self.num_frames, self.num_columns, self.num_rows)
        assert two_photon_series_extracted.shape == expected_two_photon_series_shape
        expected_two_photon_series_data = self.imaging_extractor.get_video().transpose((0, 2, 1))
        assert_array_equal(two_photon_series_extracted, expected_two_photon_series_data)

    def test_v1_iterator(self):
        """Test adding two photon series with using DataChunkIterator as iterator type."""
        add_photon_series(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
            iterator_type="v1",
        )

        # Check data
        acquisition_modules = self.nwbfile.acquisition
        assert self.two_photon_series_name in acquisition_modules
        data_in_hdfm_data_io = acquisition_modules[self.two_photon_series_name].data
        data_chunk_iterator = data_in_hdfm_data_io.data
        assert isinstance(data_chunk_iterator, DataChunkIterator)
        self.assertEqual(data_chunk_iterator.buffer_size, 10)

        two_photon_series_extracted = np.concatenate([data_chunk.data for data_chunk in data_chunk_iterator])
        # NWB stores images as num_columns x num_rows
        expected_two_photon_series_shape = (self.num_frames, self.num_columns, self.num_rows)
        assert two_photon_series_extracted.shape == expected_two_photon_series_shape
        expected_two_photon_series_data = self.imaging_extractor.get_video().transpose((0, 2, 1))
        assert_array_equal(two_photon_series_extracted, expected_two_photon_series_data)

    def test_iterator_options_propagation(self):
        """Test that iterator options are propagated to the data chunk iterator."""
        buffer_shape = (20, 5, 5)
        chunk_shape = (10, 5, 5)
        add_photon_series(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
            iterator_type="v2",
            iterator_options=dict(buffer_shape=buffer_shape, chunk_shape=chunk_shape),
        )

        acquisition_modules = self.nwbfile.acquisition
        assert self.two_photon_series_name in acquisition_modules
        data_in_hdfm_data_io = acquisition_modules[self.two_photon_series_name].data
        data_chunk_iterator = data_in_hdfm_data_io.data
        self.assertEqual(data_chunk_iterator.buffer_shape, buffer_shape)
        self.assertEqual(data_chunk_iterator.chunk_shape, chunk_shape)

    def test_iterator_options_chunk_mb_propagation(self):
        """Test that chunk_mb is propagated to the data chunk iterator and the chunk shape is correctly set to fit."""
        chunk_mb = 10.0
        add_photon_series(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
            iterator_type="v2",
            iterator_options=dict(chunk_mb=chunk_mb),
        )

        acquisition_modules = self.nwbfile.acquisition
        assert self.two_photon_series_name in acquisition_modules
        data_in_hdfm_data_io = acquisition_modules[self.two_photon_series_name].data
        data_chunk_iterator = data_in_hdfm_data_io.data
        iterator_chunk_mb = math.prod(data_chunk_iterator.chunk_shape) * data_chunk_iterator.dtype.itemsize / 1e6
        assert iterator_chunk_mb <= chunk_mb

    def test_iterator_options_chunk_shape_is_at_least_one(self):
        """Test that when a small chunk_mb is selected the chunk shape is guaranteed to include at least one frame."""
        chunk_mb = 1.0
        add_photon_series(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
            iterator_type="v2",
            iterator_options=dict(chunk_mb=chunk_mb),
        )
        acquisition_modules = self.nwbfile.acquisition
        assert self.two_photon_series_name in acquisition_modules
        data_in_hdfm_data_io = acquisition_modules[self.two_photon_series_name].data
        data_chunk_iterator = data_in_hdfm_data_io.data
        chunk_shape = data_chunk_iterator.chunk_shape
        assert_array_equal(chunk_shape, (30, 15, 10))

    def test_iterator_options_chunk_shape_does_not_exceed_maxshape(self):
        """Test that when a large chunk_mb is selected the chunk shape is guaranteed to not exceed maxshape."""
        chunk_mb = 1000.0
        add_photon_series(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.two_photon_series_metadata,
            iterator_type="v2",
            iterator_options=dict(chunk_mb=chunk_mb),
        )
        acquisition_modules = self.nwbfile.acquisition
        assert self.two_photon_series_name in acquisition_modules
        data_in_hdfm_data_io = acquisition_modules[self.two_photon_series_name].data
        data_chunk_iterator = data_in_hdfm_data_io.data
        chunk_shape = data_chunk_iterator.chunk_shape
        assert_array_equal(chunk_shape, data_chunk_iterator.maxshape)

    def test_add_two_photon_series_roundtrip(self):
        add_photon_series(
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
            expected_two_photon_series_shape = (self.num_frames, self.num_columns, self.num_rows)
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
            add_photon_series(
                imaging=self.imaging_extractor,
                nwbfile=self.nwbfile,
                metadata=self.two_photon_series_metadata,
                photon_series_type="invalid",
            )

    def test_add_photon_series_inconclusive_metadata(self):
        """Test error is raised when `photon_series_type` specifies 'TwoPhotonSeries' but metadata contains 'OnePhotonSeries'."""
        with self.assertRaisesWith(
            AssertionError,
            "Received metadata for 'OnePhotonSeries' but `photon_series_type` was not explicitly specified.",
        ):
            add_photon_series(
                imaging=self.imaging_extractor,
                nwbfile=self.nwbfile,
                metadata=self.one_photon_series_metadata,
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
        add_photon_series(
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
        add_photon_series(
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
            expected_one_photon_series_shape = (self.num_frames, self.num_columns, self.num_rows)
            assert one_photon_series.shape == expected_one_photon_series_shape

    def test_add_photon_series_invalid_module_name_raises(self):
        """Test that adding photon series with invalid module name raises error."""
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg="'parent_container' must be either 'acquisition' or 'processing/ophys'.",
        ):
            add_photon_series(
                imaging=self.imaging_extractor,
                nwbfile=self.nwbfile,
                metadata=self.two_photon_series_metadata,
                parent_container="test",
            )

    def test_add_one_photon_series_to_processing(self):
        """Test adding one photon series to ophys processing module."""
        metadata = self.one_photon_series_metadata
        metadata["Ophys"]["OnePhotonSeries"][0].update(name="OnePhotonSeriesProcessed")

        add_photon_series(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=self.one_photon_series_metadata,
            photon_series_type="OnePhotonSeries",
            photon_series_index=0,
            parent_container="processing/ophys",
        )
        ophys = self.nwbfile.processing["ophys"]
        self.assertIn("OnePhotonSeriesProcessed", ophys.data_interfaces)

    def test_photon_series_not_added_to_acquisition_with_same_name(self):
        """Test that photon series with the same name are not added to nwbfile.acquisition."""

        with self.assertRaisesWith(
            exc_type=ValueError, exc_msg=f"{self.two_photon_series_name} already added to nwbfile.acquisition."
        ):
            add_photon_series(
                imaging=self.imaging_extractor,
                nwbfile=self.nwbfile,
                metadata=self.two_photon_series_metadata,
            )
            add_photon_series(
                imaging=self.imaging_extractor,
                nwbfile=self.nwbfile,
                metadata=self.two_photon_series_metadata,
            )
        self.assertEqual(len(self.nwbfile.acquisition), 1)

    def test_photon_series_not_added_to_processing_with_same_name(self):
        """Test that photon series with the same name are not added to nwbfile.processing."""

        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg=f"{self.two_photon_series_name} already added to nwbfile.processing['ophys'].",
        ):
            add_photon_series(
                imaging=self.imaging_extractor,
                nwbfile=self.nwbfile,
                metadata=self.two_photon_series_metadata,
                parent_container="processing/ophys",
            )
            add_photon_series(
                imaging=self.imaging_extractor,
                nwbfile=self.nwbfile,
                metadata=self.two_photon_series_metadata,
                parent_container="processing/ophys",
            )
        self.assertEqual(len(self.nwbfile.processing["ophys"].data_interfaces), 1)

    def test_ophys_module_not_created_when_photon_series_added_to_acquisition(self):
        """Test that ophys module is not created when photon series are added to nwbfile.acquisition."""
        add_photon_series(
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

        add_photon_series(
            imaging=self.imaging_extractor,
            nwbfile=self.nwbfile,
            metadata=shared_photon_series_metadata,
            photon_series_type="OnePhotonSeries",
        )

        shared_photon_series_metadata["Ophys"]["OnePhotonSeries"][0]["name"] = "second_photon_series"
        add_photon_series(
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

    def test_add_summary_images(self):
        segmentation_extractor = generate_dummy_segmentation_extractor(num_rows=10, num_columns=15)

        add_summary_images(
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

        add_summary_images(
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

        add_summary_images(
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

        add_summary_images(nwbfile=self.nwbfile, segmentation_extractor=segmentation_extractor, metadata=self.metadata)

        assert len(self.nwbfile.processing) == 0

    def test_add_summary_images_invalid_plane_segmentation_name(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg="Plane segmentation 'invalid_plane_segmentation_name' not found in metadata['Ophys']['SegmentationImages']",
        ):
            add_summary_images(
                nwbfile=self.nwbfile,
                segmentation_extractor=generate_dummy_segmentation_extractor(num_rows=10, num_columns=15),
                metadata=self.metadata,
                plane_segmentation_name="invalid_plane_segmentation_name",
            )

    def test_add_summary_images_from_two_planes(self):
        segmentation_extractor_first_plane = generate_dummy_segmentation_extractor(num_rows=10, num_columns=15)

        add_summary_images(
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

        add_summary_images(
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


if __name__ == "__main__":
    unittest.main()
