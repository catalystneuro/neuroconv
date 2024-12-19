import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest import TestCase
from warnings import warn

from pynwb import NWBHDF5IO
from pynwb.image import ImageSeries
from pynwb.ophys import OnePhotonSeries

from neuroconv import ConverterPipe, NWBConverter
from neuroconv.converters import MiniscopeConverter
from tests.test_on_data.setup_paths import OPHYS_DATA_PATH


class TestMiniscopeConverter(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "C6-J588_Disc5")
        cls.converter = MiniscopeConverter(folder_path=cls.folder_path)
        cls.test_dir = Path(tempfile.mkdtemp())

        cls.stub_frames = 2
        cls.conversion_options = dict(stub_test=True, stub_frames=cls.stub_frames)

        cls.device_name = "Miniscope"
        cls.device_metadata = dict(
            name=cls.device_name,
            compression="FFV1",
            deviceType="Miniscope_V3",
            frameRate="15FPS",
            framesPerFile=1000,
            gain="High",
            led0=47,
        )

        cls.behavcam_name = "BehavCam2"
        cls.behavcam_metadata = dict(
            name=cls.behavcam_name,
            compression="MJPG",
            deviceType="WebCam-1920x1080",
            framesPerFile=1000,
            ROI={"height": 720, "leftEdge": 0, "topEdge": 0, "width": 1280},
        )

        cls.image_series_name = "BehavCamImageSeries"
        cls.photon_series_name = "OnePhotonSeries"

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_converter_metadata(self):
        metadata = self.converter.get_metadata()
        assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 10, 7, 15, 3, 28, 635)
        assert metadata["Ophys"]["Device"][0] == self.device_metadata
        assert metadata["Behavior"]["Device"][0] == self.behavcam_metadata

    def test_run_conversion(self):
        nwbfile_path = str(self.test_dir / "test_miniscope_converter.nwb")
        self.converter.run_conversion(nwbfile_path=nwbfile_path)

        self.assertNWBFileStructure(nwbfile_path=nwbfile_path)

    def test_run_conversion_add_conversion_options(self):
        nwbfile_path = str(self.test_dir / "test_miniscope_converter_conversion_options.nwb")
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            **self.conversion_options,
        )

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

        num_frames = nwbfile.acquisition[self.photon_series_name].data.shape[0]
        self.assertEqual(num_frames, self.stub_frames)

    def test_run_conversion_updated_metadata(self):
        metadata = self.converter.get_metadata()
        # Update device names and their links
        test_device_name = "TestMiniscope"
        test_behavcam_name = "TestBehavCam"
        metadata["Ophys"]["Device"][0].update(name=test_device_name)
        metadata["Ophys"]["ImagingPlane"][0].update(device=test_device_name)
        metadata["Behavior"]["Device"][0].update(name=test_behavcam_name)
        metadata["Behavior"]["ImageSeries"][0].update(device=test_behavcam_name)

        nwbfile_path = str(self.test_dir / "test_miniscope_converter_updated_metadata.nwb")
        self.converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            self.assertIn(test_device_name, nwbfile.devices)
            self.assertIn(test_behavcam_name, nwbfile.devices)
            self.assertEqual(nwbfile.devices[test_device_name], nwbfile.imaging_planes["ImagingPlane"].device)
            self.assertEqual(nwbfile.devices[test_behavcam_name], nwbfile.acquisition[self.image_series_name].device)

    def test_converter_in_converter(self):
        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestMiniscopeConverter=MiniscopeConverter)

        converter = TestConverter(
            source_data=dict(
                TestMiniscopeConverter=dict(folder_path=self.folder_path),
            )
        )

        nwbfile_path = str(self.test_dir / "test_miniscope_converter_in_nwbconverter.nwb")
        converter.run_conversion(nwbfile_path=nwbfile_path)

        self.assertNWBFileStructure(nwbfile_path)

    def test_converter_conversion_options(self):
        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestMiniscopeConverter=MiniscopeConverter)

        nwbfile_path = str(self.test_dir / "test_miniscope_converter_in_nwbconverter_conversion_options.nwb")
        converter = TestConverter(
            source_data=dict(
                TestMiniscopeConverter=dict(folder_path=self.folder_path),
            )
        )
        conversion_options = dict(TestMiniscopeConverter=self.conversion_options)
        converter.run_conversion(nwbfile_path=nwbfile_path, conversion_options=conversion_options)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

        num_frames = nwbfile.acquisition[self.photon_series_name].data.shape[0]
        self.assertEqual(num_frames, self.stub_frames)

    def test_converter_in_converter_pipe(self):
        converter_pipe = ConverterPipe(data_interfaces=[self.converter])

        nwbfile_path = self.test_dir / "test_miniscope_converter_in_converter_pipe.nwb"
        converter_pipe.run_conversion(nwbfile_path=nwbfile_path)

        self.assertNWBFileStructure(nwbfile_path=nwbfile_path)

    def test_converter_in_converter_pipe_conversion_options(self):
        converter_pipe = ConverterPipe(data_interfaces=[self.converter])

        nwbfile_path = self.test_dir / "test_miniscope_converter_in_converter_pipe_conversion_options.nwb"
        conversion_options = dict(MiniscopeConverter=self.conversion_options)
        converter_pipe.run_conversion(nwbfile_path=nwbfile_path, conversion_options=conversion_options)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()
        num_frames = nwbfile.acquisition[self.photon_series_name].data.shape[0]
        self.assertEqual(num_frames, self.stub_frames)

    def assertNWBFileStructure(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            self.assertEqual(
                nwbfile.session_start_time.replace(tzinfo=None),
                datetime(2021, 10, 7, 15, 3, 28, 635),
            )

            self.assertIn(self.device_name, nwbfile.devices)
            self.assertIn(self.behavcam_name, nwbfile.devices)
            self.assertIn(self.photon_series_name, nwbfile.acquisition)
            self.assertIsInstance(nwbfile.acquisition[self.photon_series_name], OnePhotonSeries)
            self.assertIn(self.image_series_name, nwbfile.acquisition)
            self.assertIsInstance(nwbfile.acquisition[self.image_series_name], ImageSeries)
