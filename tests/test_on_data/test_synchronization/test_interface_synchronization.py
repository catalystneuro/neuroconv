import numpy as np
from numpy.testing import assert_array_equal
from hdmf.testing import TestCase
from spikeinterface.extractors import NumpyRecording

from neuroconv import ConverterPipe
from neuroconv.datainterfaces import SpikeGLXNIDQInterface, SpikeGLXRecordingInterface, DeepLabCutInterface
from neuroconv.tools.testing import MockBehaviorEventInterface, generate_mock_ttl_signal

from ..setup_paths import ECEPHY_DATA_PATH, BEHAVIOR_DATA_PATH


class TestNIDQSynchronization(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.unsynchronized_dlc_timestamps = np.arange(
            start=0.0,  # First DLC pulse sent when device turns on
            stop=17.0,  # Was acquiring for 17 seconds
            step=1 / 30.0,  # Sent a TTL pulse every on every frame at a rate of 30 fps
        )
        cls.synchronized_dlc_timestamps = np.arange(
            start=3.23,  # DLC device starts acquiring 3.23 seconds after SpikeGLX
            stop=20.23,
            step=1 / 30 + 0.00001,  # Synchronization reveals slight drift compared with the SpikeGLX times
        )

        cls.spikeglx_subpath = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"

    def setUp(self):
        self.spikeglx_interface = SpikeGLXRecordingInterface(
            file_path=self.spikeglx_subpath / "Noise4Sam_g0_imec0" / "Noise4Sam_g0_t0.imec0.ap.bin"
        )

        self.nidq_interface = SpikeGLXNIDQInterface(file_path=self.spikeglx_subpath / "Noise4Sam_g0_t0.imec0.nidq.bin")
        self.nidq_interface.recording_extractor = NumpyRecording(
            traces_list=generate_mock_ttl_signal(
                signal_duration=23.0, ttl_times=self.synchronized_dlc_timestamps, ttl_duration=0.01
            )[..., np.newaxis],
            sampling_frequency=self.nidq_interface.recording_extractor.get_sampling_frequency(),
        )

        self.dlc_interface = DeepLabCutInterface(
            file_path=BEHAVIOR_DATA_PATH / "DLC" / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5",
            config_file_path=BEHAVIOR_DATA_PATH / "DLC" / "config.yaml",
            subject_name="ind1",
        )
        self.dlc_interface.timestamps = self.unsynchronized_dlc_timestamps

        self.behavior_interface = MockBehaviorEventInterface()

    def test_nidq_interface_synchronized(self):
        synchronized_dlc_timestamps = (
            self.nidq_interface.get_event_starting_times_from_ttl(
                channel_name="nidq#XA2"  # The channel receiving pulses from the DLC system
            ),
        )

        self.dlc_interface.synchronize_timestamps(timestamps=synchronized_dlc_timestamps)
        self.behavior_interface.synchronize_between_systems(
            primary_reference_timestamps=self.nidq_interface.get_times(),
            secondary_reference_timestamps=synchronized_dlc_timestamps,
        )

        assert_array_equal(x=self.dlc_interface.get_timestamps(), y=synchronized_dlc_timestamps)

        expected_behavior_timestamps = np.array([])  # TODO
        assert_array_equal(x=self.behavior_interface.get_timestamps(), y=expected_behavior_timestamps)

    def test_nidq_interface_synchronized_converter_pipe(self):
        synchronized_dlc_timestamps = (
            self.nidq_interface.get_event_starting_times_from_ttl(
                channel_name="nidq#XA2"  # the channel receiving pulses from the DLC system
            ),
        )

        self.dlc_interface.synchronize_timestamps(timestamps=synchronized_dlc_timestamps)
        self.behavior_interface.synchronize_between_systems(
            primary_reference_timestamps=self.unsynchronized_secondary_timestamps,
            secondary_reference_timestamps=synchronized_dlc_timestamps,
        )

        converter = ConverterPipe(
            [self.spikeglx_interface, self.dlc_interface, self.nidq_interface, self.behavior_interface]
        )
        metadata = converter.get_metadata()
        converter.run_conversion(metadata=metadata)

        # TODO, test output in written nwbfile


class TestExternalSynchronization(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.unsynchronized_dlc_timestamps = np.arange(
            start=0.0,  # First DLC pulse sent when device turns on
            stop=17.0,  # Was acquiring for 17 seconds
            step=1 / 30.0,  # Sent a TTL pulse every on every frame at a rate of 30 fps
        )
        cls.externally_synchronized_timestamps = np.arange(
            start=3.23,  # DLC device starts acquiring 3.23 seconds after SpikeGLX
            stop=20.23,
            step=1 / 30 + 0.00001,  # Synchronization reveals slight drift compared with the SpikeGLX times
        )

        cls.spikeglx_subpath = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"

    def setUp(self):
        self.spikeglx_interface = SpikeGLXRecordingInterface(
            file_path=self.spikeglx_subpath / "Noise4Sam_g0_imec0" / "Noise4Sam_g0_t0.imec0.ap.bin"
        )
        self.nidq_interface = SpikeGLXNIDQInterface(file_path=self.spikeglx_subpath / "Noise4Sam_g0_t0.imec0.nidq.bin")

        self.dlc_interface = DeepLabCutInterface(
            file_path=BEHAVIOR_DATA_PATH / "DLC" / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5",
            config_file_path=BEHAVIOR_DATA_PATH / "DLC" / "config.yaml",
            subject_name="ind1",
        )
        self.dlc_interface.timestamps = self.unsynchronized_dlc_timestamps

        self.behavior_interface = MockBehaviorEventInterface()

    def test_externally_synchronized(self):
        """
        Some labs already have workflows put together for handling synchronization.

        In this case, they simply store the timestamps in separate files and load them in during the conversion.
        """
        # For example, if the synchronization is performed ahead of time and timestamps stored in a CSV or similar file
        # Then we just need to read in the pulse times instead of having to parse NIDQ signals
        self.dlc_interface.synchronize_timestamps(timestamps=self.externally_synchronized_timestamps)
        self.behavior_interface.synchronize_between_systems(
            primary_reference_timestamps=self.unsynchronized_secondary_timestamps,
            secondary_reference_timestamps=self.externally_synchronized_timestamps,
        )

        assert_array_equal(x=self.dlc_interface.get_timestamps(), y=self.synchronized_dlc_timestamps)

        expected_behavior_timestamps = np.array([])
        assert_array_equal(x=self.behavior_interface.get_timestamps(), y=expected_behavior_timestamps)

    def test_nidq_interface_synchronized_converter_pipe(self):
        self.dlc_interface.synchronize_timestamps(timestamps=self.externally_synchronized_timestamps)
        self.behavior_interface.synchronize_between_systems(
            primary_reference_timestamps=self.unsynchronized_secondary_timestamps,
            secondary_reference_timestamps=self.externally_synchronized_timestamps,
        )

        converter = ConverterPipe(
            [self.spikeglx_interface, self.dlc_interface, self.nidq_interface, self.behavior_interface]
        )
        metadata = converter.get_metadata()
        converter.run_conversion(metadata=metadata)

        # TODO, test output in written nwbfile
