from datetime import datetime, timezone

import numpy as np
import pytest
from jsonschema.validators import Draft7Validator
from pydantic import ValidationError
from pynwb import NWBHDF5IO
from pynwb.event import EventsTable
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import InscopixGpioEventsInterface

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH


class TestInscopixGpioOdorConcentrationStimulus:
    """InscopixGpioEventsInterface derives events from the channels of an Inscopix ``.gpio`` file.

    ``odor_concentration_stimulus.gpio`` is a four-level odor-concentration code on ``GPIO-2``
    (amplitudes 128/144/160/224, 164 change points) recorded beside ``BNC Sync Output``, a 0/1 frame
    clock with 9 rising edges. Between them they exercise both halves of the conditioning vocabulary:
    a derived midpoint on a two-level line, and a named cut per level on a coded channel.
    """

    FILE_PATH = str(OPHYS_DATA_PATH / "analog_datasets" / "inscopix" / "gpio" / "odor_concentration_stimulus.gpio")

    # ``BNC Sync Output`` is a 0/1 frame clock (9 rising edges), so its cut is the derived midpoint, which
    # lands between its two levels. ``GPIO-2`` is the odor-concentration code (amplitudes 128/144/160/224),
    # so each level it is worth distinguishing takes its own cut and its own event type; the three cut points
    # sit between consecutive levels and are used by ``TestCutsInsteadOfALevelColumn`` below.
    ODOR_CUTS = [136, 152, 192]
    DETECTION_CONFIGURATION = {
        "BNC Sync Output": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising"}],
        "GPIO-2": [{"signal_conditioning": {"binarize": ODOR_CUTS[0]}, "detection": "high_period"}],
    }

    CUT_PER_LEVEL_CONFIGURATION = {
        "GPIO-2": [
            {"signal_conditioning": {"binarize": cut}, "detection": "high_period", "event_name": name}
            for cut, name in zip(ODOR_CUTS, ("above_136", "above_152", "above_192"))
        ]
    }

    @pytest.fixture
    def interface(self):
        return InscopixGpioEventsInterface(
            file_path=self.FILE_PATH, detection_configuration=self.DETECTION_CONFIGURATION
        )

    def test_requires_detection_configuration(self):
        # Selection is explicit: the file records no analog-versus-digital flag, so there is no lossless
        # default to derive and the configuration is a required keyword.
        with pytest.raises(ValidationError, match="detection_configuration"):
            InscopixGpioEventsInterface(file_path=self.FILE_PATH)

    def test_get_available_channels(self):
        inventory = InscopixGpioEventsInterface.get_available_channels(self.FILE_PATH)
        by_name = {entry["name"]: entry for entry in inventory}
        assert by_name["BNC Sync Output"]["unique_values"] == [0.0, 1.0]  # a 0/1 line
        assert by_name["GPIO-2"]["unique_values"] == [128.0, 144.0, 160.0, 224.0]  # four levels, one cut each

    def test_metadata_schema_is_valid(self, interface):
        Draft7Validator.check_schema(interface.get_metadata_schema())

    def test_session_start_time(self, interface):
        session_start_time = interface.get_metadata()["NWBFile"]["session_start_time"]
        assert session_start_time == datetime(2025, 2, 27, 11, 25, 28, 935000, tzinfo=timezone.utc)

    def test_metadata_seeds_event_types(self, interface):
        event_types = interface.get_metadata()["Events"]["inscopix_gpio_events"]["event_types"]
        assert set(event_types) == {"BNC Sync Output", "GPIO-2"}
        # The channel name carries a space and a hyphen, neither of which survives as an NWB object name.
        assert event_types["BNC Sync Output"]["event_name"] == "bnc_sync_output"
        assert event_types["GPIO-2"]["event_name"] == "gpio_2"
        # No event type seeds a value column: nothing on the signal-encoded path carries a payload.
        assert all("columns" not in entry for entry in event_types.values())

    def test_metadata_key_default_and_override(self):
        interface = InscopixGpioEventsInterface(
            file_path=self.FILE_PATH, detection_configuration=self.DETECTION_CONFIGURATION
        )
        assert set(interface.get_metadata()["Events"]) == {"inscopix_gpio_events"}
        interface = InscopixGpioEventsInterface(
            file_path=self.FILE_PATH,
            detection_configuration=self.DETECTION_CONFIGURATION,
            metadata_key="odor_session",
        )
        assert set(interface.get_metadata()["Events"]) == {"odor_session"}

    def test_selection_by_inclusion(self, interface):
        # Only the two configured channels are written; the other 24 channels never appear.
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
        assert set(nwbfile.events) == {"BncSyncOutput", "Gpio2"}

    def test_a_line_is_cut_at_its_derived_midpoint(self, interface):
        # The 0/1 frame clock takes the derived cut, which lands between its two levels without the caller
        # knowing them. This is the interface whose signals have no declared kind, so nothing else could.
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
        table = nwbfile.get_events_table("BncSyncOutput")
        assert isinstance(table, EventsTable)
        assert table.colnames == ("timestamp",)
        assert len(table) == 9  # nine rising edges on the frame clock

    def test_a_named_cut_on_the_coded_channel_is_durative(self, interface):
        # GPIO-2's spec cuts at the lowest odor boundary and reads the span above it, so the table carries
        # durations rather than the pooled change points the multi-cut reading used to give.
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
        table = nwbfile.get_events_table("Gpio2")
        assert "duration" in table.colnames
        assert len(table) == 164

    def test_value_change_pools_both_edges_and_carries_no_column(self):
        # value_change means "this signal changed", so on the frame clock it is the nine rising edges and the
        # nine falling ones in one table rather than two, and it carries no value column.
        interface = InscopixGpioEventsInterface(
            file_path=self.FILE_PATH,
            detection_configuration={
                "BNC Sync Output": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "value_change"}]
            },
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
        table = nwbfile.get_events_table("BncSyncOutput")
        assert table.colnames == ("timestamp",)
        assert len(table) == 18

    def test_a_spec_must_say_how_its_channel_becomes_a_line(self):
        # There is no uncut spelling. On the one interface whose signals have no declared kind, this is the
        # only thing standing between a caller and a coded channel read as though it were a line.
        interface_arguments = dict(
            file_path=self.FILE_PATH, detection_configuration={"GPIO-2": [{"detection": "rising"}]}
        )
        with pytest.raises(ValueError, match="does not set 'signal_conditioning'"):
            InscopixGpioEventsInterface(**interface_arguments)

    def test_high_period_durations_use_the_change_point_clock(self):
        # Inscopix stores irregularly spaced change-points (this channel's gaps run from 10 ms to 171 ms), so
        # a duration has to be the elapsed clock time between the two edges. Estimating a frame period and
        # multiplying is what the interfaces used to do, and on this file it would report 19 ms per pulse
        # (the median gap) for pulses that are really 10 ms, so the fixture is a regression guard for it.
        interface = InscopixGpioEventsInterface(
            file_path=self.FILE_PATH,
            detection_configuration={
                "BNC Sync Output": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "high_period"}]
            },
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
        table = nwbfile.get_events_table("BncSyncOutput")
        assert "duration" in table.colnames
        assert np.allclose(np.asarray(table["duration"].data), 0.010)

    def test_unknown_channel_raises_at_construction(self):
        # The channel inventory is known at construction, so naming a channel the file does not have fails
        # there rather than at read time.
        with pytest.raises(ValueError, match="not one of the file's signals"):
            InscopixGpioEventsInterface(
                file_path=self.FILE_PATH, detection_configuration={"NotAChannel": [{"detection": "rising"}]}
            )

    def test_round_trip(self, interface, tmp_path):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
        nwbfile_path = tmp_path / "test_inscopix_gpio_events.nwb"
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_nwbfile = io.read()
            assert len(read_nwbfile.get_events_table("Gpio2")) == 164
            assert len(read_nwbfile.get_events_table("BncSyncOutput")) == 9

    def test_each_cut_is_its_own_named_durative_event_type(self):
        interface = InscopixGpioEventsInterface(
            file_path=self.FILE_PATH, detection_configuration=self.CUT_PER_LEVEL_CONFIGURATION
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
        assert set(nwbfile.events) == {"Above136", "Above152", "Above192"}
        for name in nwbfile.events:
            assert "duration" in nwbfile.get_events_table(name).colnames

    def test_the_cuts_reconstruct_the_band_the_column_used_to_hold(self):
        interface = InscopixGpioEventsInterface(
            file_path=self.FILE_PATH, detection_configuration=self.CUT_PER_LEVEL_CONFIGURATION
        )
        events = interface._get_events_data_dict()

        gpio = interface._get_available_signals(self.FILE_PATH)
        raw_timestamps, amplitudes = _read_channel(self.FILE_PATH, gpio["GPIO-2"]["channel_index"])
        bands = np.searchsorted(self.ODOR_CUTS, amplitudes, side="right")

        # The band at any instant is how many cut points are currently exceeded, so summing the open
        # intervals of the per-cut tables rebuilds the band trajectory.
        reconstructed = np.zeros(len(amplitudes), dtype="int64")
        for event in events.values():
            for onset, duration in zip(event.timestamps, event.durations):
                stop = len(amplitudes) if np.isnan(duration) else np.searchsorted(raw_timestamps, onset + duration)
                reconstructed[np.searchsorted(raw_timestamps, onset) : stop] += 1

        # Exact from the first change onwards. Frame 0 is the opening sample, which is not a transition
        # and so was never an event under the value-carrying reading either.
        assert np.array_equal(reconstructed[1:], bands[1:])


def _read_channel(file_path, channel_index):
    """Read one channel's change-points as (seconds, amplitudes), as the interface does."""
    from neuroconv.datainterfaces.ophys.inscopix.inscopixgpiodatainterface import (
        _read_gpio,
    )

    timestamps_microseconds, amplitudes = _read_gpio(file_path).get_channel_data(channel_index)
    return np.asarray(timestamps_microseconds, dtype="float64") / 1e6, np.asarray(amplitudes, dtype="float64")
