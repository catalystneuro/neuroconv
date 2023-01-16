from tempfile import mkdtemp
from shutil import rmtree
from pathlib import Path

import numpy as np
from numpy.testing import assert_array_equal, assert_array_almost_equal
from hdmf.testing import TestCase
from pandas import DataFrame
from pynwb import NWBHDF5IO

from neuroconv import NWBConverter, ConverterPipe
from neuroconv.datainterfaces import CsvTimeIntervalsInterface
from neuroconv.tools.testing import MockBehaviorEventInterface, MockSpikeGLXNIDQInterface


class TestNIDQInterfaceAlignment(TestCase):
    @classmethod
    def setUpClass(cls):
        trial_system_delayed_start = 3.23  # Trial tracking system starts 3.23 seconds after SpikeGLX
        trial_system_total_time = 10.0  # Was tracking trials for 10 seconds, according to trial tracking system
        cls.regular_trial_length = (
            1.0  # For simplicity, each trial lasts 1 second according to the trial tracking system
        )
        trial_system_average_delay_per_second = 0.0001  # Clock on trial tracking system is slightly slower than NIDQ

        # The drift from the trial tracking system adds up over time
        trial_system_delayed_stop = (
            trial_system_total_time + trial_system_average_delay_per_second * trial_system_total_time
        )

        cls.unaligned_trial_start_times = np.arange(
            start=0.0, stop=trial_system_total_time, step=cls.regular_trial_length
        )
        cls.aligned_trial_start_times = np.linspace(  # use linspace to match the exact length of timestamps
            start=trial_system_delayed_start, stop=trial_system_delayed_stop, num=len(cls.unaligned_trial_start_times)
        )

        # Timing of events according to trial system
        cls.unaligned_behavior_event_timestamps = [5.6, 7.3, 9.7]  # Timing of events according to trial tracking system

        # Timing of events when interpolated by aligned trial times
        cls.aligned_behavior_event_timestamps = [7.443072, 8.722028, 10.001]

        cls.tmpdir = Path(mkdtemp())
        cls.csv_file_path = cls.tmpdir / "testing_nidq_alignment_trial_table.csv"
        dataframe = DataFrame(
            data=dict(
                start_time=cls.unaligned_trial_start_times,
                stop_time=cls.unaligned_trial_start_times + cls.regular_trial_length,
            )
        )
        dataframe.to_csv(path_or_buf=cls.csv_file_path, index=False)

    @classmethod
    def tearDownClass(cls):
        rmtree(cls.tmpdir)

    def setUp(self):
        self.nidq_interface = MockSpikeGLXNIDQInterface(
            signal_duration=23.0, ttl_times=[self.aligned_trial_start_times], ttl_duration=0.01
        )
        self.trial_interface = CsvTimeIntervalsInterface(file_path=self.csv_file_path)
        self.behavior_interface = MockBehaviorEventInterface(event_times=self.unaligned_behavior_event_timestamps)

    def test_alignment_interfaces(self):
        inferred_aligned_trial_start_timestamps = self.nidq_interface.get_event_times_from_ttl(
            channel_name="nidq#XA0"  # The channel receiving pulses from the DLC system
        )

        self.trial_interface.align_timestamps(
            aligned_timestamps=inferred_aligned_trial_start_timestamps, column="start_time"
        )

        # True stop times are not tracked, so estimate them from using the known regular trial length
        self.trial_interface.align_timestamps(
            aligned_timestamps=inferred_aligned_trial_start_timestamps + self.regular_trial_length, column="stop_time"
        )

        self.behavior_interface.align_by_interpolation(
            aligned_timestamps=inferred_aligned_trial_start_timestamps,
            unaligned_timestamps=self.unaligned_trial_start_times,
        )

        assert_array_equal(
            x=self.trial_interface.get_timestamps(column="start_time"), y=inferred_aligned_trial_start_timestamps
        )
        assert_array_equal(
            x=self.trial_interface.get_timestamps(column="stop_time"),
            y=inferred_aligned_trial_start_timestamps + self.regular_trial_length,
        )
        assert_array_almost_equal(x=self.behavior_interface.get_timestamps(), y=self.aligned_behavior_event_timestamps)

    def test_alignment_nwbconverter(self):
        class TestAlignmentConverter(NWBConverter):
            data_interface_classes = dict(
                NIDQ=MockSpikeGLXNIDQInterface, Trials=CsvTimeIntervalsInterface, Behavior=MockBehaviorEventInterface
            )

        source_data = dict(NIDQ=dict(), Trials=dict(file_path=str(self.csv_file_path)), Behavior=dict())
        converter = TestAlignmentConverter(source_data=source_data)
        metadata = converter.get_metadata()

        inferred_aligned_trial_start_timestamps = self.nidq_interface.get_event_times_from_ttl(
            channel_name="nidq#XA0"  # The channel receiving pulses from the DLC system
        )
        unaligned_trial_start_timestamps = converter.data_interface_objects["Trials"].get_timestamps(
            column="start_time"
        )

        converter.data_interface_objects["Trials"].align_timestamps(
            aligned_timestamps=inferred_aligned_trial_start_timestamps, column="start_time"
        )

        # True stop times are not tracked, so estimate them from using the known regular trial length
        converter.data_interface_objects["Trials"].align_timestamps(
            aligned_timestamps=inferred_aligned_trial_start_timestamps + self.regular_trial_length, column="stop_time"
        )

        converter.data_interface_objects["Behavior"].align_by_interpolation(
            aligned_timestamps=inferred_aligned_trial_start_timestamps,
            unaligned_timestamps=unaligned_trial_start_timestamps,
        )

        nwbfile_path = self.tmpdir / "test_alignment_nwbconverter.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            # High level groups were written to file
            assert "BehaviorEvents" in nwbfile.acquisition
            assert "ElectricalSeriesNIDQ" in nwbfile.acquisition
            assert "trials" in nwbfile.intervals

            # Aligned data was written
            assert_array_almost_equal(
                x=nwbfile.acquisition["BehaviorEvents"]["event_time"][:],
                y=self.aligned_behavior_event_timestamps,
            )
            assert_array_almost_equal(
                x=nwbfile.intervals["trials"]["start_time"][:], y=self.aligned_trial_start_times, decimal=5
            )
            assert_array_almost_equal(
                x=nwbfile.intervals["trials"]["stop_time"][:],
                y=self.aligned_trial_start_times + self.regular_trial_length,
                decimal=5,
            )

    def test_alignment_converter_pipe(self):
        inferred_aligned_trial_start_timestamps = self.nidq_interface.get_event_times_from_ttl(
            channel_name="nidq#XA0"  # The channel receiving pulses from the DLC system
        )
        unaligned_trial_start_timestamps = self.trial_interface.get_timestamps(column="start_time")

        self.trial_interface.align_timestamps(
            aligned_timestamps=inferred_aligned_trial_start_timestamps, column="start_time"
        )

        # True stop times are not tracked, so estimate them from using the known regular trial length
        self.trial_interface.align_timestamps(
            aligned_timestamps=inferred_aligned_trial_start_timestamps + self.regular_trial_length, column="stop_time"
        )

        self.behavior_interface.align_by_interpolation(
            aligned_timestamps=inferred_aligned_trial_start_timestamps,
            unaligned_timestamps=unaligned_trial_start_timestamps,
        )

        converter = ConverterPipe(data_interfaces=[self.nidq_interface, self.trial_interface, self.behavior_interface])
        metadata = converter.get_metadata()

        nwbfile_path = self.tmpdir / "test_alignment_converter_pipe.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            # High level groups were written to file
            assert "BehaviorEvents" in nwbfile.acquisition
            assert "ElectricalSeriesNIDQ" in nwbfile.acquisition
            assert "trials" in nwbfile.intervals

            # Aligned data was written
            assert_array_almost_equal(
                x=nwbfile.acquisition["BehaviorEvents"]["event_time"][:],
                y=self.aligned_behavior_event_timestamps,
            )
            assert_array_almost_equal(
                x=nwbfile.intervals["trials"]["start_time"][:], y=self.aligned_trial_start_times, decimal=5
            )
            assert_array_almost_equal(
                x=nwbfile.intervals["trials"]["stop_time"][:],
                y=self.aligned_trial_start_times + self.regular_trial_length,
                decimal=5,
            )


class TestExternalAlignment(TestNIDQInterfaceAlignment):
    """
    This test case is less about ensuring the functionality (which is identical to above) and more about depicting
    the intended usage in practice.
    """

    def setUp(self):
        self.trial_interface = CsvTimeIntervalsInterface(file_path=self.csv_file_path)
        self.behavior_interface = MockBehaviorEventInterface()

    def test_alignment_interfaces(self):
        """
        Some labs already have workflows put together for handling synchronization.

        In this case, they simply store the timestamps in separate files and load them in during the conversion.
        """
        externally_aligned_timestamps = self.aligned_trial_start_times
        unaligned_trial_start_timestamps = np.array(self.trial_interface.get_timestamps(column="start_time"))

        self.trial_interface.align_timestamps(aligned_timestamps=externally_aligned_timestamps, column="start_time")

        # True stop times are not tracked, so estimate them from using the known regular trial length
        self.trial_interface.align_timestamps(
            aligned_timestamps=externally_aligned_timestamps + self.regular_trial_length, column="stop_time"
        )

        self.behavior_interface.align_by_interpolation(
            aligned_timestamps=externally_aligned_timestamps,
            unaligned_timestamps=unaligned_trial_start_timestamps,
        )

        assert_array_equal(x=self.trial_interface.get_timestamps(column="start_time"), y=externally_aligned_timestamps)
        assert_array_equal(
            x=self.trial_interface.get_timestamps(column="stop_time"),
            y=externally_aligned_timestamps + self.regular_trial_length,
        )
        assert_array_equal(x=self.behavior_interface.get_timestamps(), y=self.aligned_behavior_event_timestamps)

    def test_alignment_nwbconverter(self):
        pass  # TODO

    def test_alignment_converter_pipe(self):
        """
        Some labs already have workflows put together for handling synchronization.

        In this case, they simply store the timestamps in separate files and load them in during the conversion.
        """
        externally_aligned_timestamps = self.aligned_trial_start_times
        unaligned_trial_start_timestamps = self.trial_interface.get_timestamps(column="start_time")

        self.trial_interface.align_timestamps(aligned_timestamps=externally_aligned_timestamps, column="start_time")

        # True stop times are not tracked, so estimate them from using the known regular trial length
        self.trial_interface.align_timestamps(
            aligned_timestamps=externally_aligned_timestamps + self.regular_trial_length, column="stop_time"
        )

        self.behavior_interface.align_by_interpolation(
            aligned_timestamps=externally_aligned_timestamps,
            unaligned_timestamps=unaligned_trial_start_timestamps,
        )

        converter = ConverterPipe([self.trial_interface, self.behavior_interface])
        metadata = converter.get_metadata()
        converter.run_conversion(metadata=metadata)

        # TODO, test round-trip output in a written nwbfile
