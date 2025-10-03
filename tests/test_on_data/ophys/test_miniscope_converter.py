import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from warnings import warn

import pytest
from pynwb import NWBHDF5IO
from pynwb.image import ImageSeries
from pynwb.ophys import OnePhotonSeries

from neuroconv import ConverterPipe, NWBConverter
from neuroconv.converters import MiniscopeConverter
from tests.test_on_data.setup_paths import OPHYS_DATA_PATH


class TestMiniscopeConverter:
    @classmethod
    def setup_class(cls) -> None:
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
        cls.one_photon_series_name = "OnePhotonSeriesMiniscope"

    @classmethod
    def teardown_class(cls) -> None:
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

        num_frames = nwbfile.acquisition[self.one_photon_series_name].data.shape[0]
        assert num_frames == self.stub_frames

    def assertNWBFileStructure(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert nwbfile.session_start_time.replace(tzinfo=None) == datetime(2021, 10, 7, 15, 3, 28, 635)
            assert self.device_name in nwbfile.devices
            assert self.behavcam_name in nwbfile.devices

            assert self.one_photon_series_name in nwbfile.acquisition
            assert isinstance(nwbfile.acquisition[self.one_photon_series_name], OnePhotonSeries)
            assert self.image_series_name in nwbfile.acquisition
            assert isinstance(nwbfile.acquisition[self.image_series_name], ImageSeries)


class TestMiniscopeConverterWithUserConfig:
    stub_root_path = Path("/home/heberto/data/miniscope/NWB_data_share/stub/dual_miniscope_with_config")

    @classmethod
    def setup_class(cls) -> None:
        if not cls.stub_root_path.exists():
            pytest.skip(
                f"Stub dataset not available at {cls.stub_root_path}; skipping user-config Miniscope tests.",
                allow_module_level=True,
            )

        cls.folder_path = str(cls.stub_root_path)
        cls.user_config_path = cls.stub_root_path / "UserConfigFile.json"
        cls.converter = MiniscopeConverter(
            folder_path=cls.folder_path,
            user_configuration_file_path=str(cls.user_config_path),
            verbose=False,
        )
        cls.test_dir = Path(tempfile.mkdtemp())
        cls.stub_frames = 3

        cls.image_series_name = "BehavCamImageSeries"
        cls.expected_devices = {"ACC_miniscope2", "HPC_miniscope1"}
        cls.expected_imaging_keys = {
            "MiniscopeImaging/ACC_miniscope2/Segment00",
            "MiniscopeImaging/ACC_miniscope2/Segment01",
            "MiniscopeImaging/HPC_miniscope1/Segment00",
            "MiniscopeImaging/HPC_miniscope1/Segment01",
        }
        cls.expected_series_names = {
            "OnePhotonSeriesACC_miniscope2Segment00",
            "OnePhotonSeriesACC_miniscope2Segment01",
            "OnePhotonSeriesHPC_miniscope1Segment00",
            "OnePhotonSeriesHPC_miniscope1Segment01",
        }
        cls.conversion_options = dict(stub_test=True, stub_frames=cls.stub_frames)
        cls.interface_conversion_options = {
            key: dict(stub_test=True, stub_frames=cls.stub_frames) for key in cls.expected_imaging_keys
        }

    @classmethod
    def teardown_class(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_data_interfaces_initialized(self):
        imaging_keys = {key for key in self.converter.data_interface_objects if key.startswith("MiniscopeImaging")}
        assert imaging_keys == self.expected_imaging_keys
        assert "MiniscopeBehavCam" not in self.converter.data_interface_objects

    def test_run_conversion_with_user_config(self):
        nwbfile_path = str(self.test_dir / "test_miniscope_converter_user_config.nwb")
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            stub_test=True,
            stub_frames=self.stub_frames,
        )

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert nwbfile.session_start_time is not None
            assert self.expected_series_names.issubset(set(nwbfile.acquisition))

            for series_name in self.expected_series_names:
                series = nwbfile.acquisition[series_name]
                assert isinstance(series, OnePhotonSeries)
                assert series.data.shape[0] <= self.stub_frames

    def test_run_conversion_updated_metadata(self):
        metadata = self.converter.get_metadata()

        test_device_name = "TestMiniscope"
        metadata["Ophys"]["Device"][0].update(name=test_device_name)
        metadata["Ophys"]["ImagingPlane"][0].update(
            name=f"ImagingPlane{test_device_name}",
            device=test_device_name,
        )

        behavior_metadata = metadata.get("Behavior")
        test_behavcam_name = None
        if behavior_metadata:
            test_behavcam_name = "TestBehavCam"
            behavior_metadata["Device"][0].update(name=test_behavcam_name)
            behavior_metadata["ImageSeries"][0].update(device=test_behavcam_name)

        nwbfile_path = str(self.test_dir / "test_miniscope_converter_updated_metadata.nwb")
        self.converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert test_device_name in nwbfile.devices
            imaging_plane_device_names = {plane.device.name for plane in nwbfile.imaging_planes.values()}
            assert test_device_name in imaging_plane_device_names

            if test_behavcam_name:
                assert test_behavcam_name in nwbfile.devices
                assert nwbfile.acquisition[self.image_series_name].device.name == test_behavcam_name

    def test_converter_in_converter(self):
        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestMiniscopeConverter=MiniscopeConverter)

        converter = TestConverter(
            source_data=dict(
                TestMiniscopeConverter=dict(
                    folder_path=self.folder_path,
                    user_configuration_file_path=str(self.user_config_path),
                ),
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
                TestMiniscopeConverter=dict(
                    folder_path=self.folder_path,
                    user_configuration_file_path=str(self.user_config_path),
                ),
            )
        )
        conversion_options = dict(TestMiniscopeConverter=self.conversion_options)
        converter.run_conversion(nwbfile_path=nwbfile_path, conversion_options=conversion_options)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

        for series_name in self.expected_series_names:
            assert nwbfile.acquisition[series_name].data.shape[0] <= self.stub_frames

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

        for series_name in self.expected_series_names:
            assert nwbfile.acquisition[series_name].data.shape[0] <= self.stub_frames

    def assertNWBFileStructure(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert self.expected_devices.issubset(set(nwbfile.devices))
            assert self.expected_series_names.issubset(set(nwbfile.acquisition))
            for series_name in self.expected_series_names:
                assert isinstance(nwbfile.acquisition[series_name], OnePhotonSeries)
