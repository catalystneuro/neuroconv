from tempfile import mkdtemp
import unittest
from pathlib import Path
from datetime import datetime

import numpy as np
from numpy.testing import assert_array_equal
from parameterized import parameterized, param

from pynwb import NWBFile, NWBHDF5IO
from pynwb.device import Device
from roiextractors.testing import (
    generate_dummy_imaging_extractor,
    generate_dummy_segmentation_extractor,
)

from neuroconv.tools.nwb_helpers import get_module
from neuroconv.tools.roiextractors import (
    add_devices,
    add_imaging_plane,
    add_two_photon_series,
    add_plane_segmentation,
    add_image_segmentation,
    add_summary_images,
)


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
        manufacturer = "manufactuer"

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


class TestAddImagingPlane(unittest.TestCase):
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

        add_imaging_plane(nwbfile=self.nwbfile, metadata=self.metadata)

        imaging_planes = self.nwbfile.imaging_planes
        assert len(imaging_planes) == 1
        assert self.imaging_plane_name in imaging_planes

        imaging_plane = imaging_planes[self.imaging_plane_name]
        assert imaging_plane.description == self.imaging_plane_description

    def test_not_overwriting_imaging_plane_if_same_name(self):

        add_imaging_plane(nwbfile=self.nwbfile, metadata=self.metadata)

        self.imaging_plane_metadata["description"] = "modified description"
        add_imaging_plane(nwbfile=self.nwbfile, metadata=self.metadata)

        imaging_planes = self.nwbfile.imaging_planes
        assert len(imaging_planes) == 1
        assert self.imaging_plane_name in imaging_planes

    def test_add_two_imaging_planes(self):

        # Add the first imaging plane
        first_imaging_plane_name = "first_imaging_plane_name"
        first_imaging_plane_description = "first_imaging_plane_description"
        self.imaging_plane_metadata["name"] = first_imaging_plane_name
        self.imaging_plane_metadata["description"] = first_imaging_plane_description
        add_imaging_plane(nwbfile=self.nwbfile, metadata=self.metadata)

        # Add the second imaging plane
        second_imaging_plane_name = "second_imaging_plane_name"
        second_imaging_plane_description = "second_imaging_plane_description"
        self.imaging_plane_metadata["name"] = second_imaging_plane_name
        self.imaging_plane_metadata["description"] = second_imaging_plane_description
        add_imaging_plane(nwbfile=self.nwbfile, metadata=self.metadata)

        # Test expected values
        imaging_planes = self.nwbfile.imaging_planes
        assert len(imaging_planes) == 2

        first_imaging_plane = imaging_planes[first_imaging_plane_name]
        assert first_imaging_plane.name == first_imaging_plane_name
        assert first_imaging_plane.description == first_imaging_plane_description

        second_imaging_plane = imaging_planes[second_imaging_plane_name]
        assert second_imaging_plane.name == second_imaging_plane_name
        assert second_imaging_plane.description == second_imaging_plane_description


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


class TestAddPlaneSegmentation(unittest.TestCase):
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
            name=self.plane_segmentation_name,
            description="Segmented ROIs",
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
        )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)
        plane_segmentations = image_segmentation.plane_segmentations

        self.assertEqual(len(plane_segmentations), 1)

        plane_segmentation = plane_segmentations[self.plane_segmentation_name]

        self.assertEqual(plane_segmentation.name, self.plane_segmentation_name)
        self.assertEqual(plane_segmentation.description, self.plane_segmentation_metadata["description"])

        plane_segmentation_num_rois = len(plane_segmentation.id)
        self.assertEqual(plane_segmentation_num_rois, self.num_rois)

        plane_segmentation_roi_centroid_data = plane_segmentation["RoiCentroid"].data
        expected_roi_centroid_data = self.segmentation_extractor.get_roi_locations().T

        assert_array_equal(plane_segmentation_roi_centroid_data, expected_roi_centroid_data)

        image_mask_iterator = plane_segmentation["image_mask"].data

        data_chunks = np.zeros((self.num_rois, self.num_columns, self.num_rows))
        for data_chunk in image_mask_iterator:
            data_chunks[data_chunk.selection] = data_chunk.data

        # transpose to num_rois x image_width x image_height
        expected_image_masks = self.segmentation_extractor.get_roi_image_masks().T
        assert_array_equal(data_chunks, expected_image_masks)

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
        )

        image_segmentation = self.nwbfile.processing["ophys"].get(self.image_segmentation_name)
        plane_segmentations = image_segmentation.plane_segmentations

        plane_segmentation = plane_segmentations[self.plane_segmentation_name]

        plane_segmentation_rejected_roi_ids = plane_segmentation["Rejected"].data
        assert_array_equal(plane_segmentation_rejected_roi_ids, expected_rejected_roi_ids)

        accepted_roi_ids = list(np.logical_not(np.array(expected_rejected_roi_ids)).astype(int))
        plane_segmentation_accepted_roi_ids = plane_segmentation["Accepted"].data
        assert_array_equal(plane_segmentation_accepted_roi_ids, accepted_roi_ids)

    def test_not_overwriting_plane_segmentation_if_same_name(self):
        """Test that adding a plane segmentation with the same name will not overwrite
        the existing plane segmentation."""

        add_plane_segmentation(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
        )

        self.plane_segmentation_metadata["description"] = "modified description"

        add_plane_segmentation(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=self.nwbfile,
            metadata=self.metadata,
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


class TestAddTwoPhotonSeries(unittest.TestCase):
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
        self.imaging_plane_metadata = dict(
            name=self.imaging_plane_name,
            optical_channel=[self.optical_channel_metadata],
            description="image_plane_description",
            device=self.device_name,
            excitation_lambda=np.nan,
            indicator="unknown",
            location="unknown",
        )

        self.metadata["Ophys"].update(ImagingPlane=[self.imaging_plane_metadata])

        self.two_photon_series_name = "two_photon_series_name"
        self.two_photon_series_metadata = dict(
            name=self.two_photon_series_name, imaging_plane=self.imaging_plane_name, unit="unknown"
        )
        self.metadata["Ophys"].update(TwoPhotonSeries=[self.two_photon_series_metadata])

        self.num_frames = 30
        self.num_rows = 10
        self.num_columns = 15
        self.imaging_extractor = generate_dummy_imaging_extractor(
            self.num_frames, num_rows=self.num_rows, num_columns=self.num_columns
        )

    def test_add_two_photon_series(self):

        metadata = self.metadata

        add_two_photon_series(imaging=self.imaging_extractor, nwbfile=self.nwbfile, metadata=metadata)

        # Check data
        acquisition_modules = self.nwbfile.acquisition
        self.two_photon_series_name in acquisition_modules
        data_in_hdfm_data_io = acquisition_modules[self.two_photon_series_name].data
        data_chunk_iterator = data_in_hdfm_data_io.data
        two_photon_series_extracted = np.concatenate([data_chunk.data for data_chunk in data_chunk_iterator])

        # NWB stores images as num_columns x num_rows
        expected_two_photon_series_shape = (self.num_frames, self.num_columns, self.num_rows)
        assert two_photon_series_extracted.shape == expected_two_photon_series_shape

        # Check device
        devices = self.nwbfile.devices
        assert self.device_name in devices
        assert len(devices) == 1

        # Check imaging planes
        imaging_planes_in_file = self.nwbfile.imaging_planes
        assert self.imaging_plane_name in imaging_planes_in_file
        assert len(imaging_planes_in_file) == 1

    def test_add_two_photon_series_roundtrip(self):

        metadata = self.metadata

        add_two_photon_series(imaging=self.imaging_extractor, nwbfile=self.nwbfile, metadata=metadata)

        # Write the data to disk
        nwbfile_path = Path(mkdtemp()) / "two_photon_roundtrip.nwb"
        with NWBHDF5IO(nwbfile_path, "w") as io:
            io.write(self.nwbfile)

        with NWBHDF5IO(nwbfile_path, "r") as io:
            read_nwbfile = io.read()

            # Check data
            acquisition_modules = read_nwbfile.acquisition
            self.two_photon_series_name in acquisition_modules
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


class TestAddSummaryImages(unittest.TestCase):
    def setUp(self):
        self.session_start_time = datetime.now().astimezone()
        self.nwbfile = NWBFile(
            session_description="session_description",
            identifier="file_id",
            session_start_time=self.session_start_time,
        )

    def test_add_sumary_images(self):

        segmentation_extractor = generate_dummy_segmentation_extractor(num_rows=10, num_columns=15)

        images_set_name = "images_set_name"
        add_summary_images(
            nwbfile=self.nwbfile, segmentation_extractor=segmentation_extractor, images_set_name=images_set_name
        )

        ophys = self.nwbfile.get_processing_module("ophys")
        images_collection = ophys.data_interfaces[images_set_name]

        extracted_images_dict = images_collection.images

        extracted_images_dict = {img_name: img.data.T for img_name, img in extracted_images_dict.items()}
        expected_images_dict = segmentation_extractor.get_images_dict()

        assert expected_images_dict.keys() == extracted_images_dict.keys()
        for image_name in expected_images_dict.keys():
            np.testing.assert_almost_equal(expected_images_dict[image_name], extracted_images_dict[image_name])

    def test_extractor_with_one_summary_image_suppressed(self):

        segmentation_extractor = generate_dummy_segmentation_extractor(num_rows=10, num_columns=15)
        segmentation_extractor._image_correlation = None

        images_set_name = "images_set_name"
        add_summary_images(
            nwbfile=self.nwbfile, segmentation_extractor=segmentation_extractor, images_set_name=images_set_name
        )

        ophys = self.nwbfile.get_processing_module("ophys")
        images_collection = ophys.data_interfaces[images_set_name]

        extracted_images_number = len(images_collection.images)
        expected_images_number = len(
            {img_name: img for img_name, img in segmentation_extractor.get_images_dict().items() if img is not None}
        )
        assert extracted_images_number == expected_images_number

    def test_extractor_with_no_summary_images(self):

        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rows=10, num_columns=15, has_summary_images=False
        )

        images_set_name = "images_set_name"
        self.nwbfile.create_processing_module("ophys", "contains optical physiology processed data")

        add_summary_images(
            nwbfile=self.nwbfile, segmentation_extractor=segmentation_extractor, images_set_name=images_set_name
        )

        ophys = self.nwbfile.get_processing_module("ophys")
        assert images_set_name not in ophys.data_interfaces

    def test_extractor_with_no_summary_images_and_no_ophys_module(self):

        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_rows=10, num_columns=15, has_summary_images=False
        )

        images_set_name = "images_set_name"

        add_summary_images(
            nwbfile=self.nwbfile, segmentation_extractor=segmentation_extractor, images_set_name=images_set_name
        )

        assert len(self.nwbfile.processing) == 0


if __name__ == "__main__":
    unittest.main()
