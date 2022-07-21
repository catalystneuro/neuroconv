from tempfile import mkdtemp
import unittest
from pathlib import Path
from datetime import datetime

import numpy as np

from pynwb import NWBFile, NWBHDF5IO
from pynwb.device import Device
from roiextractors.testing import generate_dummy_imaging_extractor

from neuroconv.tools.roiextractors import add_devices, add_two_photon_series


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


if __name__ == "__main__":
    unittest.main()
