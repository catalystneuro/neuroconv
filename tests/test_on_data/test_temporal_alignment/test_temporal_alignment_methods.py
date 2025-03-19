from datetime import datetime
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from typing import Dict, Optional, Union

import numpy as np
from hdmf.testing import TestCase
from numpy.testing import assert_array_almost_equal, assert_array_equal
from pandas import DataFrame
from pynwb import NWBHDF5IO

from neuroconv import ConverterPipe, NWBConverter
from neuroconv.datainterfaces import CsvTimeIntervalsInterface
from neuroconv.tools.testing import (
    MockBehaviorEventInterface,
    MockSpikeGLXNIDQInterface,
)


class TestNIDQInterfacePulseTimesAlignment(TestCase):
    @classmethod
    def setUpClass(cls):
        trial_system_delayed_start = 3.23  # Trial tracking system starts 3.23 seconds after SpikeGLX
        trial_system_total_time = 10.0  # Was tracking trials for 10 seconds, according to trial tracking system
        cls.regular_trial_length = (
            1.0  # For simplicity, each trial lasts 1 second according to the trial tracking system
        )
        trial_system_average_delay_per_second = 0.0001  # Clock on trial tracking system is slightly slower than NIDQ

        # The drift from the trial tracking system adds up over time
        trial_system_total_drift = trial_system_total_time * trial_system_average_delay_per_second

        cls.expected_unaligned_trial_start_times = np.arange(
            start=0.0, stop=trial_system_total_time, step=cls.regular_trial_length
        )
        cls.aligned_trial_start_times = (
            cls.expected_unaligned_trial_start_times
            + trial_system_delayed_start
            + np.linspace(  # use linspace to match the exact length of timestamps
                start=0.0, stop=trial_system_total_drift, num=len(cls.expected_unaligned_trial_start_times)
            )
        )

        # Timing of events according to trial system
        cls.unaligned_behavior_event_timestamps = [5.6, 7.3, 8.7]  # Timing of events according to trial tracking system

        # Timing of events when interpolated by aligned trial times
        cls.aligned_behavior_event_timestamps = [8.830632, 10.530796, 11.930964]

        cls.tmpdir = Path(mkdtemp())
        cls.csv_file_path = cls.tmpdir / "testing_nidq_pulse_times_alignment_trial_table.csv"
        dataframe = DataFrame(
            data=dict(
                start_time=cls.expected_unaligned_trial_start_times,
                stop_time=cls.expected_unaligned_trial_start_times + cls.regular_trial_length,
            )
        )
        dataframe.to_csv(path_or_buf=cls.csv_file_path, index=False)

    @classmethod
    def tearDownClass(cls):
        rmtree(cls.tmpdir)

    def setUp(self):
        self.nidq_interface = MockSpikeGLXNIDQInterface(
            signal_duration=23.0, ttl_times=[self.aligned_trial_start_times], ttl_duration=0.1
        )
        self.trial_interface = CsvTimeIntervalsInterface(file_path=self.csv_file_path)
        self.behavior_interface = MockBehaviorEventInterface(event_times=self.unaligned_behavior_event_timestamps)

    def assertNWBFileTimesAligned(self, nwbfile_path: Union[str, Path]):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            # High level groups were written to file
            assert "BehaviorEvents" in nwbfile.acquisition
            assert "trials" in nwbfile.intervals

            # Aligned data was written
            assert_array_almost_equal(
                nwbfile.acquisition["BehaviorEvents"]["event_time"][:],
                self.aligned_behavior_event_timestamps,
            )
            assert_array_almost_equal(
                nwbfile.intervals["trials"]["start_time"][:], self.aligned_trial_start_times, decimal=4
            )
            assert_array_almost_equal(
                nwbfile.intervals["trials"]["stop_time"][:],
                self.aligned_trial_start_times + self.regular_trial_length,
                decimal=4,
            )

    def test_alignment_interfaces(self):
        unaligned_trial_start_times = self.trial_interface.get_original_timestamps(column="start_time")
        inferred_aligned_trial_start_timestamps = self.nidq_interface.get_event_times_from_ttl(
            channel_name="nidq#XA0"  # The channel receiving pulses from the DLC system
        )

        self.trial_interface.set_aligned_timestamps(
            aligned_timestamps=inferred_aligned_trial_start_timestamps,
            column="start_time",
            interpolate_other_columns=True,
        )

        self.behavior_interface.align_by_interpolation(
            unaligned_timestamps=unaligned_trial_start_times,
            aligned_timestamps=inferred_aligned_trial_start_timestamps,
        )

        assert_array_equal(
            self.trial_interface.get_timestamps(column="start_time"), inferred_aligned_trial_start_timestamps
        )
        assert_array_almost_equal(
            self.trial_interface.get_timestamps(column="stop_time"),
            inferred_aligned_trial_start_timestamps + self.regular_trial_length,
            decimal=2,
        )
        assert_array_almost_equal(self.behavior_interface.get_timestamps(), self.aligned_behavior_event_timestamps)

        # Check original unaltered timestamps are the same
        assert_array_equal(
            self.trial_interface.get_original_timestamps(column="start_time"),
            self.expected_unaligned_trial_start_times,
        )
        assert_array_equal(
            self.trial_interface.get_original_timestamps(column="stop_time"),
            self.expected_unaligned_trial_start_times + self.regular_trial_length,
        )
        assert_array_equal(
            self.behavior_interface.get_original_timestamps(),
            self.unaligned_behavior_event_timestamps,
        )

        converter = ConverterPipe(data_interfaces=[self.nidq_interface, self.trial_interface, self.behavior_interface])
        metadata = converter.get_metadata()

        nwbfile_path = self.tmpdir / "test_nidq_pulse_times_alignment_converter_pipe.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        self.assertNWBFileTimesAligned(nwbfile_path=nwbfile_path)

    def test_alignment_nwbconverter_direct_modification(self):
        class TestAlignmentConverter(NWBConverter):
            data_interface_classes = dict(
                NIDQ=MockSpikeGLXNIDQInterface, Trials=CsvTimeIntervalsInterface, Behavior=MockBehaviorEventInterface
            )

        source_data = dict(
            NIDQ=dict(signal_duration=23.0, ttl_times=[self.aligned_trial_start_times], ttl_duration=0.1),
            Trials=dict(file_path=str(self.csv_file_path)),
            Behavior=dict(event_times=self.unaligned_behavior_event_timestamps),
        )
        converter = TestAlignmentConverter(source_data=source_data)
        metadata = converter.get_metadata()

        unaligned_trial_start_times = converter.data_interface_objects["Trials"].get_original_timestamps(
            column="start_time"
        )
        inferred_aligned_trial_start_timestamps = converter.data_interface_objects["NIDQ"].get_event_times_from_ttl(
            channel_name="nidq#XA0"  # The channel receiving pulses from the DLC system
        )

        converter.data_interface_objects["Trials"].set_aligned_timestamps(
            aligned_timestamps=inferred_aligned_trial_start_timestamps, column="start_time"
        )

        # True stop times are not tracked, so estimate them from using the known regular trial length
        converter.data_interface_objects["Trials"].set_aligned_timestamps(
            aligned_timestamps=inferred_aligned_trial_start_timestamps + self.regular_trial_length, column="stop_time"
        )

        converter.data_interface_objects["Behavior"].align_by_interpolation(
            unaligned_timestamps=unaligned_trial_start_times,
            aligned_timestamps=inferred_aligned_trial_start_timestamps,
        )

        nwbfile_path = self.tmpdir / "test_nidq_pulse_times_alignment_nwbconverter_direct_modification.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        self.assertNWBFileTimesAligned(nwbfile_path=nwbfile_path)

    def test_alignment_nwbconverter_internal_modification(self):
        class TestAlignmentConverter(NWBConverter):
            data_interface_classes = dict(
                NIDQ=MockSpikeGLXNIDQInterface, Trials=CsvTimeIntervalsInterface, Behavior=MockBehaviorEventInterface
            )

            def temporally_align_data_interfaces(
                self, metadata: Optional[dict] = None, conversion_options: Optional[dict] = None
            ):
                unaligned_trial_start_times = self.data_interface_objects["Trials"].get_original_timestamps(
                    column="start_time"
                )
                inferred_aligned_trial_start_timestamps = self.data_interface_objects["NIDQ"].get_event_times_from_ttl(
                    channel_name="nidq#XA0"  # The channel receiving pulses from the DLC system
                )

                self.data_interface_objects["Trials"].set_aligned_timestamps(
                    aligned_timestamps=inferred_aligned_trial_start_timestamps, column="start_time"
                )

                # True stop times are not tracked, so estimate them from using the known regular trial length
                self.data_interface_objects["Trials"].set_aligned_timestamps(
                    # for this usage, the regular trial length would be hard-coded
                    aligned_timestamps=inferred_aligned_trial_start_timestamps + 1.0,
                    column="stop_time",
                )

                self.data_interface_objects["Behavior"].align_by_interpolation(
                    unaligned_timestamps=unaligned_trial_start_times,
                    aligned_timestamps=inferred_aligned_trial_start_timestamps,
                )

        source_data = dict(
            NIDQ=dict(signal_duration=23.0, ttl_times=[self.aligned_trial_start_times], ttl_duration=0.1),
            Trials=dict(file_path=str(self.csv_file_path)),
            Behavior=dict(event_times=self.unaligned_behavior_event_timestamps),
        )
        converter = TestAlignmentConverter(source_data=source_data)
        metadata = converter.get_metadata()

        nwbfile_path = self.tmpdir / "test_nidq_alignment_pulse_times_nwbconverter_internal_modification.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        self.assertNWBFileTimesAligned(nwbfile_path=nwbfile_path)


class TestExternalPulseTimesAlignment(TestNIDQInterfacePulseTimesAlignment):
    """
    This test case is less about ensuring the functionality (which is identical to above) and more about depicting
    the intended usage in practice.

    Some labs already have workflows put together for handling synchronization.

    In this case, they simply store the timestamps in separate files and load them in during the conversion.
    """

    def setUp(self):
        self.trial_interface = CsvTimeIntervalsInterface(file_path=self.csv_file_path)
        self.behavior_interface = MockBehaviorEventInterface(event_times=self.unaligned_behavior_event_timestamps)

    def assertNWBFileTimesAligned(self, nwbfile_path: Union[str, Path]):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            # High level groups were written to file
            assert "BehaviorEvents" in nwbfile.acquisition
            assert "trials" in nwbfile.intervals

            # Aligned data was written
            assert_array_almost_equal(
                nwbfile.acquisition["BehaviorEvents"]["event_time"][:],
                self.aligned_behavior_event_timestamps,
                decimal=4,
            )
            assert_array_almost_equal(
                nwbfile.intervals["trials"]["start_time"][:], self.aligned_trial_start_times, decimal=5
            )
            assert_array_almost_equal(
                nwbfile.intervals["trials"]["stop_time"][:],
                self.aligned_trial_start_times + self.regular_trial_length,
                decimal=5,
            )

    def test_alignment_interfaces(self):
        unaligned_trial_start_timestamps = self.trial_interface.get_original_timestamps(column="start_time")
        externally_aligned_timestamps = self.aligned_trial_start_times

        self.trial_interface.set_aligned_timestamps(
            aligned_timestamps=externally_aligned_timestamps, column="start_time"
        )

        # True stop times are not tracked, so estimate them from using the known regular trial length
        self.trial_interface.set_aligned_timestamps(
            aligned_timestamps=externally_aligned_timestamps + self.regular_trial_length, column="stop_time"
        )

        self.behavior_interface.align_by_interpolation(
            unaligned_timestamps=unaligned_trial_start_timestamps,
            aligned_timestamps=externally_aligned_timestamps,
        )

        assert_array_equal(self.trial_interface.get_timestamps(column="start_time"), externally_aligned_timestamps)
        assert_array_equal(
            self.trial_interface.get_timestamps(column="stop_time"),
            externally_aligned_timestamps + self.regular_trial_length,
        )
        assert_array_almost_equal(
            self.behavior_interface.get_timestamps(), self.aligned_behavior_event_timestamps, decimal=4
        )

        # Check original unaltered timestamps are the same
        assert_array_equal(
            self.trial_interface.get_original_timestamps(column="start_time"),
            self.expected_unaligned_trial_start_times,
        )
        assert_array_equal(
            self.trial_interface.get_original_timestamps(column="stop_time"),
            self.expected_unaligned_trial_start_times + self.regular_trial_length,
        )
        assert_array_equal(
            self.behavior_interface.get_original_timestamps(),
            self.unaligned_behavior_event_timestamps,
        )

        converter = ConverterPipe(data_interfaces=[self.trial_interface, self.behavior_interface])
        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime(1970, 1, 1)  # No NIDQ to automatically include star time

        nwbfile_path = self.tmpdir / "test_external_pulse_times_alignment_converter_pipe.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        self.assertNWBFileTimesAligned(nwbfile_path=nwbfile_path)

    def test_alignment_nwbconverter_direct_modification(self):
        class TestAlignmentConverter(NWBConverter):
            data_interface_classes = dict(Trials=CsvTimeIntervalsInterface, Behavior=MockBehaviorEventInterface)

        source_data = dict(
            Trials=dict(file_path=str(self.csv_file_path)),
            Behavior=dict(event_times=self.unaligned_behavior_event_timestamps),
        )
        converter = TestAlignmentConverter(source_data=source_data)
        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime(1970, 1, 1)  # No NIDQ to automatically include star time

        unaligned_trial_start_timestamps = converter.data_interface_objects["Trials"].get_timestamps(
            column="start_time"
        )
        externally_aligned_timestamps = self.aligned_trial_start_times

        converter.data_interface_objects["Trials"].set_aligned_timestamps(
            aligned_timestamps=externally_aligned_timestamps, column="start_time"
        )

        # True stop times are not tracked, so estimate them from using the known regular trial length
        converter.data_interface_objects["Trials"].set_aligned_timestamps(
            aligned_timestamps=externally_aligned_timestamps + self.regular_trial_length, column="stop_time"
        )

        converter.data_interface_objects["Behavior"].align_by_interpolation(
            unaligned_timestamps=unaligned_trial_start_timestamps,
            aligned_timestamps=externally_aligned_timestamps,
        )

        nwbfile_path = self.tmpdir / "test_external_pulse_times_alignment_nwbconverter_direct_modification.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        self.assertNWBFileTimesAligned(nwbfile_path=nwbfile_path)

    def test_alignment_nwbconverter_internal_modification(self):
        def mimic_reading_externally_aligned_timestamps():
            """Needed to define small function here to allow proper namespace references inside class scope."""
            return self.aligned_trial_start_times

        class TestAlignmentConverter(NWBConverter):
            data_interface_classes = dict(Trials=CsvTimeIntervalsInterface, Behavior=MockBehaviorEventInterface)

            def __init__(self, source_data: Dict[str, dict], verbose: bool = False):
                super().__init__(source_data=source_data, verbose=verbose)

                unaligned_trial_start_timestamps = self.data_interface_objects["Trials"].get_timestamps(
                    column="start_time"
                )
                externally_aligned_timestamps = mimic_reading_externally_aligned_timestamps()

                self.data_interface_objects["Trials"].set_aligned_timestamps(
                    aligned_timestamps=externally_aligned_timestamps, column="start_time"
                )

                # True stop times are not tracked, so estimate them from using the known regular trial length
                self.data_interface_objects["Trials"].set_aligned_timestamps(
                    # for this usage, the regular trial length would be hard-coded
                    aligned_timestamps=externally_aligned_timestamps + 1.0,
                    column="stop_time",
                )

                self.data_interface_objects["Behavior"].align_by_interpolation(
                    unaligned_timestamps=unaligned_trial_start_timestamps,
                    aligned_timestamps=externally_aligned_timestamps,
                )

        source_data = dict(
            Trials=dict(file_path=str(self.csv_file_path)),
            Behavior=dict(event_times=self.unaligned_behavior_event_timestamps),
        )
        converter = TestAlignmentConverter(source_data=source_data)
        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime(1970, 1, 1)  # No NIDQ to automatically include star time

        nwbfile_path = self.tmpdir / "test_external_pulse_times_alignment_nwbconverter_internal_modification.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        self.assertNWBFileTimesAligned(nwbfile_path=nwbfile_path)


class TestNIDQInterfaceOnSignalAlignment(TestNIDQInterfacePulseTimesAlignment):
    @classmethod
    def setUpClass(cls):
        cls.trial_system_delayed_start = 3.23  # Trial tracking system starts 3.23 seconds after SpikeGLX
        trial_system_total_time = 10.0  # Was tracking trials for 10 seconds, according to trial tracking system
        cls.regular_trial_length = (
            1.0  # For simplicity, each trial lasts 1 second according to the trial tracking system
        )

        cls.expected_unaligned_trial_start_times = np.arange(
            start=0.0, stop=trial_system_total_time, step=cls.regular_trial_length
        )
        cls.aligned_trial_start_times = cls.expected_unaligned_trial_start_times + cls.trial_system_delayed_start

        # Timing of events according to trial system
        cls.unaligned_behavior_event_timestamps = [5.6, 7.3, 8.7]  # Timing of events according to trial tracking system

        # Timing of events when interpolated by aligned trial times
        cls.aligned_behavior_event_timestamps = [8.83, 10.53, 11.93]

        cls.tmpdir = Path(mkdtemp())
        cls.csv_file_path = cls.tmpdir / "testing_nidq_single_pulse_alignment_trial_table.csv"
        dataframe = DataFrame(
            data=dict(
                start_time=cls.expected_unaligned_trial_start_times,
                stop_time=cls.expected_unaligned_trial_start_times + cls.regular_trial_length,
            )
        )
        dataframe.to_csv(path_or_buf=cls.csv_file_path, index=False)

    def setUp(self):
        self.nidq_interface = MockSpikeGLXNIDQInterface(
            signal_duration=23.0, ttl_times=[[self.trial_system_delayed_start]], ttl_duration=0.1
        )
        self.trial_interface = CsvTimeIntervalsInterface(file_path=self.csv_file_path)
        self.behavior_interface = MockBehaviorEventInterface(event_times=self.unaligned_behavior_event_timestamps)

    def test_alignment_interfaces(self):
        inferred_aligned_trial_start_time = self.nidq_interface.get_event_times_from_ttl(
            channel_name="nidq#XA0"  # The channel receiving pulses from the DLC system
        )[0]

        self.trial_interface.set_aligned_starting_time(aligned_starting_time=inferred_aligned_trial_start_time)
        self.behavior_interface.set_aligned_starting_time(aligned_starting_time=inferred_aligned_trial_start_time)

        assert_array_equal(self.trial_interface.get_timestamps(column="start_time"), self.aligned_trial_start_times)
        assert_array_equal(
            self.trial_interface.get_timestamps(column="stop_time"),
            self.aligned_trial_start_times + self.regular_trial_length,
        )
        assert_array_almost_equal(self.behavior_interface.get_timestamps(), self.aligned_behavior_event_timestamps)

        # Check original unaltered timestamps are the same
        assert_array_equal(
            self.trial_interface.get_original_timestamps(column="start_time"),
            self.expected_unaligned_trial_start_times,
        )
        assert_array_equal(
            self.trial_interface.get_original_timestamps(column="stop_time"),
            self.expected_unaligned_trial_start_times + self.regular_trial_length,
        )
        assert_array_equal(
            self.behavior_interface.get_original_timestamps(),
            self.unaligned_behavior_event_timestamps,
        )

        converter = ConverterPipe(data_interfaces=[self.nidq_interface, self.trial_interface, self.behavior_interface])
        metadata = converter.get_metadata()

        nwbfile_path = self.tmpdir / "test_nidq_on_signal_alignment_converter_pipe.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        self.assertNWBFileTimesAligned(nwbfile_path=nwbfile_path)

    def test_alignment_nwbconverter_direct_modification(self):
        class TestAlignmentConverter(NWBConverter):
            data_interface_classes = dict(
                NIDQ=MockSpikeGLXNIDQInterface, Trials=CsvTimeIntervalsInterface, Behavior=MockBehaviorEventInterface
            )

        source_data = dict(
            NIDQ=dict(signal_duration=23.0, ttl_times=[self.aligned_trial_start_times], ttl_duration=0.1),
            Trials=dict(file_path=str(self.csv_file_path)),
            Behavior=dict(event_times=self.unaligned_behavior_event_timestamps),
        )
        converter = TestAlignmentConverter(source_data=source_data)
        metadata = converter.get_metadata()

        inferred_aligned_trial_start_time = converter.data_interface_objects["NIDQ"].get_event_times_from_ttl(
            channel_name="nidq#XA0"  # The channel receiving pulses from the DLC system
        )[0]

        converter.data_interface_objects["Trials"].set_aligned_starting_time(
            aligned_starting_time=inferred_aligned_trial_start_time
        )
        converter.data_interface_objects["Behavior"].set_aligned_starting_time(
            aligned_starting_time=inferred_aligned_trial_start_time
        )

        nwbfile_path = self.tmpdir / "test_nidq_on_signal_alignment_nwbconverter_direct_modification.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        self.assertNWBFileTimesAligned(nwbfile_path=nwbfile_path)

    def test_alignment_nwbconverter_internal_modification(self):
        class TestAlignmentConverter(NWBConverter):
            data_interface_classes = dict(
                NIDQ=MockSpikeGLXNIDQInterface, Trials=CsvTimeIntervalsInterface, Behavior=MockBehaviorEventInterface
            )

            def __init__(self, source_data: Dict[str, dict], verbose: bool = False):
                super().__init__(source_data=source_data, verbose=verbose)

                inferred_aligned_trial_start_time = self.data_interface_objects["NIDQ"].get_event_times_from_ttl(
                    channel_name="nidq#XA0"  # The channel receiving pulses from the DLC system
                )[0]

                self.data_interface_objects["Trials"].set_aligned_starting_time(
                    aligned_starting_time=inferred_aligned_trial_start_time
                )
                self.data_interface_objects["Behavior"].set_aligned_starting_time(
                    aligned_starting_time=inferred_aligned_trial_start_time
                )

        source_data = dict(
            NIDQ=dict(signal_duration=23.0, ttl_times=[self.aligned_trial_start_times], ttl_duration=0.1),
            Trials=dict(file_path=str(self.csv_file_path)),
            Behavior=dict(event_times=self.unaligned_behavior_event_timestamps),
        )
        converter = TestAlignmentConverter(source_data=source_data)
        metadata = converter.get_metadata()

        nwbfile_path = self.tmpdir / "test_nidq_on_signal_alignment_nwbconverter_internal_modification.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        self.assertNWBFileTimesAligned(nwbfile_path=nwbfile_path)
