import math
import re
import unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import Mock

import numpy as np
import psutil
import pytest
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO, NWBFile
from pynwb.ophys import OnePhotonSeries
from pynwb.testing.mock.file import mock_NWBFile
from roiextractors.testing import (
    generate_dummy_imaging_extractor,
    generate_dummy_segmentation_extractor,
)

from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.roiextractors import (
    _check_if_imaging_fits_into_memory,
    add_devices_to_nwbfile,
    add_imaging_to_nwbfile,
    add_segmentation_to_nwbfile,
)
from neuroconv.tools.roiextractors.imagingextractordatachunkiterator import (
    ImagingExtractorDataChunkIterator,
)
from neuroconv.tools.roiextractors.roiextractors import (
    _get_ophys_metadata_placeholders,
    _trace_is_all_zero,
    get_full_ophys_metadata,
)
from neuroconv.tools.roiextractors.roiextractors_pending_deprecation import (
    _add_imaging_plane_to_nwbfile_old_list_format,
    _add_photon_series_to_nwbfile_old_list_format,
    _get_default_ophys_metadata_old_metadata_list,
)
from neuroconv.utils import DeepDict


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


# TODO: Drop this test class once support for list-based metadata is removed (September 2026).
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

    def test_device_model_is_written_and_linked(self):
        """A device reached from an imaging plane can name its model with ``device_model_metadata_key``.
        The model is resolved against ``metadata["DeviceModels"]``, so the whole metadata has to reach the
        device writer, not just the ``Devices`` registry."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        metadata = {
            "DeviceModels": {
                "microscope_model": {"name": "Bergamo III", "manufacturer": "Thorlabs"},
            },
            "Devices": {
                "my_device": {"name": "Microscope", "device_model_metadata_key": "microscope_model"},
            },
            "Ophys": {
                "ImagingPlanes": {
                    "my_plane": {
                        "name": "ImagingPlane",
                        "excitation_lambda": 920.0,
                        "indicator": "GCaMP6s",
                        "location": "V1",
                        "device_metadata_key": "my_device",
                        "optical_channel": [{"name": "Green", "description": "GCaMP", "emission_lambda": 510.0}],
                    },
                },
                "MicroscopySeries": {
                    "my_series": {
                        "name": "TwoPhotonSeries",
                        "unit": "n.a.",
                        "imaging_plane_metadata_key": "my_plane",
                    },
                },
            },
        }

        add_imaging_to_nwbfile(imaging=imaging, nwbfile=nwbfile, metadata=metadata, metadata_key="my_series")

        device = nwbfile.devices["Microscope"]
        assert nwbfile.imaging_planes["ImagingPlane"].device is device
        assert device.model is nwbfile.device_models["Bergamo III"]
        assert device.model.manufacturer == "Thorlabs"

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

    def test_missing_required_imaging_plane_fields_are_defaulted(self):
        """An imaging plane entry that omits schema-required optics fields is not rejected; the write path
        fills them from the placeholder template instead of raising, so an interface can provide just a
        name and a device link."""
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
                        # excitation_lambda, indicator, location and optical_channel intentionally
                        # omitted -> defaulted at write time
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

        add_imaging_to_nwbfile(imaging=imaging, nwbfile=nwbfile, metadata=metadata, metadata_key=metadata_key)

        imaging_plane = nwbfile.imaging_planes["ImagingPlane"]
        assert np.isnan(imaging_plane.excitation_lambda)
        assert imaging_plane.indicator == "unknown"
        assert imaging_plane.location == "unknown"
        assert imaging_plane.device.name == "Microscope"
        optical_channel = imaging_plane.optical_channel[0]
        assert optical_channel.name == "OpticalChannel"
        assert np.isnan(optical_channel.emission_lambda)

    def test_partially_stated_optical_channel_is_defaulted(self):
        """An interface that knows a channel's name but not its emission wavelength states the name alone.
        The entry is completed from the placeholder template rather than rejected by ``OpticalChannel``,
        so knowing more about the source cannot produce a worse outcome than knowing nothing."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        metadata = {
            "Ophys": {
                "ImagingPlanes": {
                    "my_plane": {
                        "name": "ImagingPlane",
                        # Only the channel name is known; description and emission_lambda are not.
                        "optical_channel": [{"name": "ChanA"}],
                    },
                },
                "MicroscopySeries": {
                    "my_series": {"name": "TwoPhotonSeries", "imaging_plane_metadata_key": "my_plane"},
                },
            },
        }

        add_imaging_to_nwbfile(imaging=imaging, nwbfile=nwbfile, metadata=metadata, metadata_key="my_series")

        optical_channel = nwbfile.imaging_planes["ImagingPlane"].optical_channel[0]
        assert optical_channel.name == "ChanA"
        assert np.isnan(optical_channel.emission_lambda)
        assert optical_channel.description == "An optical channel of the microscope."

    def test_several_partially_stated_optical_channels_keep_their_own_names(self):
        """The default name is withheld when the list holds several entries, since two channels defaulted
        to one name would collide inside the imaging plane."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        metadata = {
            "Ophys": {
                "ImagingPlanes": {
                    "my_plane": {
                        "name": "ImagingPlane",
                        "optical_channel": [{"name": "ChanA"}, {"name": "ChanB"}],
                    },
                },
                "MicroscopySeries": {
                    "my_series": {"name": "TwoPhotonSeries", "imaging_plane_metadata_key": "my_plane"},
                },
            },
        }

        add_imaging_to_nwbfile(imaging=imaging, nwbfile=nwbfile, metadata=metadata, metadata_key="my_series")

        optical_channels = nwbfile.imaging_planes["ImagingPlane"].optical_channel
        assert [channel.name for channel in optical_channels] == ["ChanA", "ChanB"]
        assert all(np.isnan(channel.emission_lambda) for channel in optical_channels)

    def test_registered_device_is_written_rather_than_shadowed(self):
        """A device the interface registers is only reached through an imaging plane that links it. An
        entry nothing references is replaced by the placeholder, and its description is lost, so the link
        is what makes the registered device the one in the file."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        metadata = {
            "Devices": {"my_device": {"name": "Microscope", "description": "Scanbox imaging"}},
            "Ophys": {
                "ImagingPlanes": {
                    "my_plane": {"name": "ImagingPlane", "device_metadata_key": "my_device"},
                },
                "MicroscopySeries": {
                    "my_series": {"name": "TwoPhotonSeries", "imaging_plane_metadata_key": "my_plane"},
                },
            },
        }

        add_imaging_to_nwbfile(imaging=imaging, nwbfile=nwbfile, metadata=metadata, metadata_key="my_series")

        assert len(nwbfile.devices) == 1
        device = nwbfile.imaging_planes["ImagingPlane"].device
        assert device.name == "Microscope"
        assert device.description == "Scanbox imaging"

    def test_missing_required_series_fields_are_defaulted(self):
        """A series entry that omits `unit` is not rejected; the write path fills it from the placeholder
        template instead of raising."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)

        metadata_key = "my_series"
        metadata = {
            "Ophys": {
                "MicroscopySeries": {
                    metadata_key: {
                        "name": "TwoPhotonSeries",
                        # unit intentionally omitted -> defaulted at write time
                    },
                },
            },
        }

        add_imaging_to_nwbfile(imaging=imaging, nwbfile=nwbfile, metadata=metadata, metadata_key=metadata_key)

        assert nwbfile.acquisition["TwoPhotonSeries"].unit == "n.a."

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

    def test_non_iterative_write_of_volumetric_data(self):
        """`get_series` is 4D for a volumetric extractor, so the planar three-axis transpose does not
        apply to it and used to raise `ValueError: axes don't match array`. Nothing here is
        format-specific: it broke `iterator_type=None` for every volumetric extractor."""
        nwbfile = mock_NWBFile()
        num_samples = 10
        num_rows = 5
        num_columns = 4
        num_planes = 3
        imaging = generate_dummy_imaging_extractor(
            num_samples=num_samples, num_rows=num_rows, num_columns=num_columns, num_planes=num_planes
        )

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
        # The planes axis stays last, which is the layout the v2 iterator advertises.
        assert series.data.shape == (num_samples, num_columns, num_rows, num_planes)

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

    def test_misspelled_metadata_key_raises(self):
        """A metadata_key missing from MicroscopySeries raises instead of writing the placeholders."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)
        metadata = {"Ophys": {"MicroscopySeries": {"my_series": {}}}}

        expected = (
            "metadata_key 'my_seires' was not found in metadata['Ophys']['MicroscopySeries'] "
            "(available keys: ['my_series'])."
        )
        with pytest.raises(ValueError, match=re.escape(expected)):
            add_imaging_to_nwbfile(imaging=imaging, nwbfile=nwbfile, metadata=metadata, metadata_key="my_seires")

    def test_misspelled_imaging_plane_metadata_key_raises(self):
        """An imaging_plane_metadata_key missing from ImagingPlanes raises instead of using the default plane."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)
        metadata = {
            "Ophys": {
                "ImagingPlanes": {"my_plane": {}},
                "MicroscopySeries": {"my_series": {"imaging_plane_metadata_key": "my_plnae"}},
            }
        }

        expected = (
            "imaging_plane_metadata_key 'my_plnae' was not found in metadata['Ophys']['ImagingPlanes'] "
            "(available keys: ['my_plane'])."
        )
        with pytest.raises(ValueError, match=re.escape(expected)):
            add_imaging_to_nwbfile(imaging=imaging, nwbfile=nwbfile, metadata=metadata, metadata_key="my_series")

    def test_missing_ophys_section_in_deep_dict_raises(self):
        """On a DeepDict, a missing Ophys section raises instead of being created and filled with placeholders."""
        nwbfile = mock_NWBFile()
        imaging = generate_dummy_imaging_extractor(num_samples=10, num_rows=5, num_columns=5)
        metadata = DeepDict()
        metadata["NWBFile"]["session_description"] = "A session."
        metadata_before = deepcopy(metadata)

        expected = (
            "metadata_key 'my_series' was not found in metadata['Ophys']['MicroscopySeries'] "
            "because metadata has no 'Ophys' (available keys: ['NWBFile'])."
        )
        with pytest.raises(ValueError, match=re.escape(expected)):
            add_imaging_to_nwbfile(imaging=imaging, nwbfile=nwbfile, metadata=metadata, metadata_key="my_series")
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

        # Summary images
        default_images_metadata = placeholders["Ophys"]["SegmentationImages"][default_key]
        assert "SegmentationImages" in ophys_module.data_interfaces
        image_collection = ophys_module.data_interfaces["SegmentationImages"]

        expected_images = {k: v for k, v in segmentation_extractor.get_images_dict().items() if v is not None}
        assert len(image_collection.images) == len(expected_images)

        for img_type, img_data in expected_images.items():
            nwb_name = default_images_metadata[img_type]["name"]
            nwb_image = image_collection.images[nwb_name]
            assert nwb_image.name == nwb_name
            np.testing.assert_array_equal(nwb_image.data, img_data.T)

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

        # Summary images
        images_metadata = metadata["Ophys"]["SegmentationImages"][metadata_key]
        image_collection = ophys_module.data_interfaces["SegmentationImages"]
        images_dict = segmentation_extractor.get_images_dict()
        expected_images = {k: v for k, v in images_dict.items() if v is not None}
        assert len(image_collection.images) == len(expected_images)

        for img_type, img_data in expected_images.items():
            img_meta = images_metadata[img_type]
            nwb_image = image_collection.images[img_meta["name"]]
            assert nwb_image.name == img_meta["name"]
            assert nwb_image.description == img_meta["description"]
            np.testing.assert_array_equal(nwb_image.data, img_data.T)

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

    def test_misspelled_metadata_key_raises(self):
        """A metadata_key missing from PlaneSegmentations raises instead of writing the placeholders."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor()
        metadata = {"Ophys": {"PlaneSegmentations": {"my_segmentation": {}}}}

        expected = (
            "metadata_key 'my_segmnetation' was not found in metadata['Ophys']['PlaneSegmentations'] "
            "(available keys: ['my_segmentation'])."
        )
        with pytest.raises(ValueError, match=re.escape(expected)):
            add_segmentation_to_nwbfile(
                segmentation_extractor=segmentation_extractor,
                nwbfile=nwbfile,
                metadata=metadata,
                metadata_key="my_segmnetation",
            )

    def test_misspelled_imaging_plane_metadata_key_raises(self):
        """An imaging_plane_metadata_key missing from ImagingPlanes raises instead of using the default plane."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor()
        metadata = {
            "Ophys": {
                "ImagingPlanes": {"my_plane": {}},
                "PlaneSegmentations": {"my_segmentation": {"imaging_plane_metadata_key": "my_plnae"}},
            }
        }

        expected = (
            "imaging_plane_metadata_key 'my_plnae' was not found in metadata['Ophys']['ImagingPlanes'] "
            "(available keys: ['my_plane'])."
        )
        with pytest.raises(ValueError, match=re.escape(expected)):
            add_segmentation_to_nwbfile(
                segmentation_extractor=segmentation_extractor,
                nwbfile=nwbfile,
                metadata=metadata,
                metadata_key="my_segmentation",
            )

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

    def test_default_metadata_no_traces(self):
        """With no metadata at all, an extractor holding ROIs but no traces writes its PlaneSegmentation.

        The placeholder metadata carries a RoiResponses entry under the default key, which must not be taken
        for metadata the caller wrote.
        """
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

        add_segmentation_to_nwbfile(segmentation_extractor=segmentation_extractor, nwbfile=nwbfile)

        ophys_module = nwbfile.processing["ophys"]
        plane_seg = ophys_module["ImageSegmentation"].plane_segmentations["PlaneSegmentation"]
        assert len(plane_seg.id) == num_rois
        assert "Fluorescence" not in ophys_module.data_interfaces

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

    def test_missing_required_plane_segmentation_fields_are_defaulted(self):
        """A PlaneSegmentation entry that omits `name` and `description` is not rejected; the write path
        fills both from the placeholder template instead of raising, and leaves the caller's dict alone."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor()

        metadata = {
            "Ophys": {
                "PlaneSegmentations": {
                    # name and description intentionally omitted -> defaulted at write time
                    "my_seg": {},
                },
            },
        }

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key="my_seg",
        )

        plane_segmentation = nwbfile.processing["ophys"]["ImageSegmentation"]["PlaneSegmentation"]
        assert plane_segmentation.name == "PlaneSegmentation"
        assert plane_segmentation.description == "Segmented ROIs"
        # The traces resolve the same defaulted name rather than raising on the missing key.
        fluorescence = nwbfile.processing["ophys"]["Fluorescence"]
        assert fluorescence.roi_response_series["RoiResponseSeries"].rois.table is plane_segmentation
        assert metadata["Ophys"]["PlaneSegmentations"]["my_seg"] == {}

    def test_second_unnamed_plane_segmentation_raises(self):
        """Two entries that both leave `name` to the default would collapse onto one PlaneSegmentation and
        silently drop the second one's ROIs, so the second write raises instead. A name the caller states
        is how two interfaces deliberately share one, and that stays allowed."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor()

        metadata = {
            "Ophys": {
                "PlaneSegmentations": {
                    "first_seg": {"description": "First segmentation"},
                    "second_seg": {"description": "Second segmentation"},
                },
            },
        }

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key="first_seg",
        )

        with pytest.raises(ValueError, match="does not name its own"):
            add_segmentation_to_nwbfile(
                segmentation_extractor=segmentation_extractor,
                nwbfile=nwbfile,
                metadata=metadata,
                metadata_key="second_seg",
            )

    def test_quality_metric_properties_are_described(self):
        """The quality metrics every segmenter names identically are written with the descriptions the old
        list-based path gives them; any other extractor property keeps an empty one."""
        nwbfile = mock_NWBFile()
        num_rois = 5
        segmentation_extractor = generate_dummy_segmentation_extractor(num_rois=num_rois)

        roi_ids = segmentation_extractor.get_roi_ids()
        for property_key in ("snr", "r_values", "cnn_preds"):
            segmentation_extractor.set_property(property_key, np.arange(num_rois, dtype=np.float32), ids=roi_ids)
        segmentation_extractor.set_property("accepted", np.ones(num_rois, dtype=bool), ids=roi_ids)

        metadata = {"Ophys": {"PlaneSegmentations": {"my_seg": {"name": "PlaneSegmentation"}}}}

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key="my_seg",
        )

        plane_segmentation = nwbfile.processing["ophys"]["ImageSegmentation"]["PlaneSegmentation"]
        assert plane_segmentation["snr"].description == "Signal-to-noise ratio for each component"
        assert plane_segmentation["r_values"].description == "Spatial correlation values for each component"
        assert plane_segmentation["cnn_preds"].description == "CNN classifier predictions for component quality"
        assert plane_segmentation["accepted"].description == ""

    def test_missing_required_roi_response_fields_are_defaulted(self):
        """An ROI response entry that omits `unit` is not rejected; the write path fills it from the
        placeholder template instead of raising, and the caller's metadata dict is left untouched."""
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
                        # unit intentionally omitted -> defaulted at write time
                        "raw": {"name": "RoiResponseSeries"},
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

        fluorescence = nwbfile.processing["ophys"]["Fluorescence"]
        assert fluorescence.roi_response_series["RoiResponseSeries"].unit == "n.a."
        # The write path defaults onto a copy, so the entry the caller passed in is unchanged.
        assert "unit" not in metadata["Ophys"]["RoiResponses"]["my_seg"]["raw"]

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

    def test_warns_when_metadata_specifies_missing_images(self):
        """Warning is emitted when SegmentationImages metadata references image types the extractor doesn't have."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_samples=10, num_rois=5, num_rows=15, num_columns=20, has_summary_images=False
        )
        # Add only mean, not correlation
        segmentation_extractor._summary_images["mean"] = np.random.rand(15, 20)

        metadata = {
            "Ophys": {
                "PlaneSegmentations": {
                    "my_seg": {
                        "name": "PlaneSegmentation",
                        "description": "Segmented ROIs",
                    },
                },
                "SegmentationImages": {
                    "my_seg": {
                        "correlation": {"name": "corr_img", "description": "Correlation"},
                        "mean": {"name": "mean_img", "description": "Mean"},
                    },
                },
            },
        }

        with pytest.warns(UserWarning, match="SegmentationImages metadata specifies images"):
            add_segmentation_to_nwbfile(
                segmentation_extractor=segmentation_extractor,
                nwbfile=nwbfile,
                metadata=metadata,
                metadata_key="my_seg",
            )

        ophys_module = nwbfile.processing["ophys"]
        image_collection = ophys_module.data_interfaces["SegmentationImages"]
        assert len(image_collection.images) == 1
        assert "mean_img" in image_collection.images

    def test_summary_image_outside_the_placeholders_is_written(self):
        """An image the placeholders do not name is still written when no metadata entry is given."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_samples=10, num_rois=5, num_rows=15, num_columns=20, has_summary_images=False
        )
        # Minian's only summary image, and one the placeholders do not name.
        segmentation_extractor._summary_images["maximum_projection"] = np.random.rand(15, 20)

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
        )

        ophys_module = nwbfile.processing["ophys"]
        image_collection = ophys_module.data_interfaces["SegmentationImages"]
        assert list(image_collection.images) == ["maximum_projection"]

    def test_no_container_when_metadata_names_no_available_image(self):
        """``Images`` requires at least one image, so a container that would be empty is not created."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_samples=10, num_rois=5, num_rows=15, num_columns=20, has_summary_images=False
        )
        segmentation_extractor._summary_images["mean"] = np.random.rand(15, 20)

        metadata = {
            "Ophys": {
                "PlaneSegmentations": {"my_seg": {"name": "PlaneSegmentation", "description": "Segmented ROIs"}},
                "SegmentationImages": {"my_seg": {"correlation": {"name": "corr_img"}}},
            },
        }

        with pytest.warns(UserWarning, match="SegmentationImages metadata specifies images"):
            add_segmentation_to_nwbfile(
                segmentation_extractor=segmentation_extractor,
                nwbfile=nwbfile,
                metadata=metadata,
                metadata_key="my_seg",
            )

        ophys_module = nwbfile.processing["ophys"]
        assert "SegmentationImages" not in ophys_module.data_interfaces

    def test_all_zero_trace_is_not_written(self):
        """A trace holding only zeros carries no information, so it is dropped with a warning."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor(num_samples=10, num_rois=5)
        for roi_response in segmentation_extractor._roi_responses:
            if roi_response.response_type == "deconvolved":
                roi_response.data = np.zeros_like(np.asarray(roi_response.data))

        with pytest.warns(UserWarning, match="These traces hold only zeros"):
            add_segmentation_to_nwbfile(segmentation_extractor=segmentation_extractor, nwbfile=nwbfile)

        fluorescence = nwbfile.processing["ophys"]["Fluorescence"]
        assert "Deconvolved" not in fluorescence.roi_response_series
        assert "RoiResponseSeries" in fluorescence.roi_response_series

    def test_all_zero_trace_named_in_metadata_is_written(self):
        """A trace the caller named is written whatever it holds."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor(num_samples=10, num_rois=5)
        for roi_response in segmentation_extractor._roi_responses:
            if roi_response.response_type == "deconvolved":
                roi_response.data = np.zeros_like(np.asarray(roi_response.data))

        metadata = {
            "Ophys": {
                "PlaneSegmentations": {"my_seg": {"name": "PlaneSegmentation", "description": "Segmented ROIs"}},
                "RoiResponses": {"my_seg": {"deconvolved": {"name": "Deconvolved", "unit": "n.a."}}},
            },
        }

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key="my_seg",
        )

        fluorescence = nwbfile.processing["ophys"]["Fluorescence"]
        assert "Deconvolved" in fluorescence.roi_response_series

    def test_all_zero_check_on_a_lazily_backed_trace(self, tmp_path):
        """The scan reads a memmap in buffers, which is what a transposed memmap cannot survive otherwise.

        ``np.ravel`` on the transposed memmap suite2p hands over cannot return a view, so the check that
        used to live here copied the whole trace onto the heap before looking at it.
        """
        file_path = tmp_path / "spks.npy"
        np.save(file_path, np.zeros((5, 10_000), dtype="float32"))
        all_zero_trace = np.load(file_path, mmap_mode="r").T

        with_data = np.array(all_zero_trace)
        with_data[-1, -1] = 1.0

        iterator_options = dict(chunk_mb=0.02, buffer_gb=1e-4)  # forces several buffers over a small array
        assert _trace_is_all_zero(trace=all_zero_trace, iterator_options=iterator_options)
        assert not _trace_is_all_zero(trace=with_data, iterator_options=iterator_options)

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

    def test_summary_images_one_suppressed(self):
        """One image is None in extractor, only the other is written."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_samples=10, num_rois=5, num_rows=15, num_columns=20
        )
        segmentation_extractor._summary_images["correlation"] = None

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
        )

        ophys_module = nwbfile.processing["ophys"]
        image_collection = ophys_module.data_interfaces["SegmentationImages"]
        assert len(image_collection.images) == 1

        placeholders = _get_ophys_metadata_placeholders()
        mean_name = placeholders["Ophys"]["SegmentationImages"]["default_metadata_key"]["mean"]["name"]
        assert mean_name in image_collection.images

    def test_summary_images_none(self):
        """Extractor has no summary images: no Images container created."""
        nwbfile = mock_NWBFile()
        segmentation_extractor = generate_dummy_segmentation_extractor(
            num_samples=10, num_rois=5, num_rows=15, num_columns=20, has_summary_images=False
        )

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
        )

        ophys_module = nwbfile.processing["ophys"]
        assert "SegmentationImages" not in ophys_module.data_interfaces

    def test_summary_images_two_segmentations_shared_container(self):
        """Two segmentation pipelines add images to the same container."""
        nwbfile = mock_NWBFile()
        seg_a = generate_dummy_segmentation_extractor(num_samples=10, num_rois=5, num_rows=15, num_columns=20)
        seg_b = generate_dummy_segmentation_extractor(num_samples=10, num_rois=3, num_rows=15, num_columns=20)

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
                        "name": "PlaneSegA",
                        "description": "First segmentation",
                        "imaging_plane_metadata_key": shared_plane_key,
                    },
                    "seg_b": {
                        "name": "PlaneSegB",
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
                "SegmentationImages": {
                    "seg_a": {
                        "correlation": {"name": "corr_a", "description": "Correlation A"},
                        "mean": {"name": "mean_a", "description": "Mean A"},
                    },
                    "seg_b": {
                        "correlation": {"name": "corr_b", "description": "Correlation B"},
                        "mean": {"name": "mean_b", "description": "Mean B"},
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
        image_collection = ophys_module.data_interfaces["SegmentationImages"]
        assert len(image_collection.images) == 4
        assert "corr_a" in image_collection.images
        assert "mean_a" in image_collection.images
        assert "corr_b" in image_collection.images
        assert "mean_b" in image_collection.images
