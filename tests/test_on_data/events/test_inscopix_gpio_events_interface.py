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

GPIO_FILE_PATH = str(OPHYS_DATA_PATH / "analog_datasets" / "inscopix" / "gpio" / "odor_concentration_stimulus.gpio")

# ``BNC Sync Output`` is a 0/1 frame clock (9 rising edges), so it is already a line and needs no
# conditioning. ``GPIO-2`` is the odor-concentration code (amplitudes 128/144/160/224), which is
# four-valued and therefore needs a cut before any edge reading; the three cut points separate its levels.
ODOR_CUTS = [136, 152, 192]
DETECTION_CONFIGURATION = {
    "BNC Sync Output": [{"detection": "rising"}],
    "GPIO-2": [{"signal_conditioning": {"thresholds": ODOR_CUTS}, "detection": "value_change"}],
}


@pytest.fixture
def interface():
    return InscopixGpioEventsInterface(file_path=GPIO_FILE_PATH, detection_configuration=DETECTION_CONFIGURATION)


def test_requires_detection_configuration():
    # Selection is explicit: the file records no analog-versus-digital flag, so there is no lossless
    # default to derive and the configuration is a required keyword.
    with pytest.raises(ValidationError, match="detection_configuration"):
        InscopixGpioEventsInterface(file_path=GPIO_FILE_PATH)


def test_get_available_channels():
    inventory = InscopixGpioEventsInterface.get_available_channels(GPIO_FILE_PATH)
    by_name = {entry["name"]: entry for entry in inventory}
    assert by_name["BNC Sync Output"]["unique_values"] == [0.0, 1.0]  # a 0/1 line
    assert by_name["GPIO-2"]["unique_values"] == [128.0, 144.0, 160.0, 224.0]  # four levels, needs a cut


def test_metadata_schema_is_valid(interface):
    Draft7Validator.check_schema(interface.get_metadata_schema())


def test_session_start_time(interface):
    session_start_time = interface.get_metadata()["NWBFile"]["session_start_time"]
    assert session_start_time == datetime(2025, 2, 27, 11, 25, 28, 935000, tzinfo=timezone.utc)


def test_metadata_seeds_event_types(interface):
    event_types = interface.get_metadata()["Events"]["inscopix_gpio_events"]["event_types"]
    assert set(event_types) == {"BNC Sync Output", "GPIO-2"}
    # The channel name carries a space and a hyphen, neither of which survives as an NWB object name.
    assert event_types["BNC Sync Output"]["event_name"] == "bnc_sync_output"
    assert event_types["GPIO-2"]["event_name"] == "gpio_2"
    # No event type seeds a value column: nothing on the signal-encoded path carries a payload.
    assert all("columns" not in entry for entry in event_types.values())


def test_metadata_key_default_and_override():
    interface = InscopixGpioEventsInterface(file_path=GPIO_FILE_PATH, detection_configuration=DETECTION_CONFIGURATION)
    assert set(interface.get_metadata()["Events"]) == {"inscopix_gpio_events"}
    interface = InscopixGpioEventsInterface(
        file_path=GPIO_FILE_PATH,
        detection_configuration=DETECTION_CONFIGURATION,
        metadata_key="odor_session",
    )
    assert set(interface.get_metadata()["Events"]) == {"odor_session"}


def test_selection_by_inclusion(interface):
    # Only the two configured channels are written; the other 24 channels never appear.
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
    assert set(nwbfile.events) == {"BncSyncOutput", "Gpio2"}


def test_a_line_needs_no_conditioning(interface):
    # The 0/1 frame clock reads correctly with no cut at all, which is the omission semantics on the one
    # interface whose signals have no declared kind.
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
    table = nwbfile.get_events_table("BncSyncOutput")
    assert isinstance(table, EventsTable)
    assert table.colnames == ("timestamp",)
    assert len(table) == 9  # nine rising edges on the frame clock


def test_value_change_on_a_cut_channel_is_timestamps_only(interface):
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
    table = nwbfile.get_events_table("Gpio2")
    # One event per level change, and nothing telling the levels apart: value_change means "this signal
    # changed", so it carries no value column.
    assert table.colnames == ("timestamp",)
    assert len(table) == 334


def test_an_edge_reading_on_an_uncut_coded_channel_raises():
    # GPIO-2 has four distinct values, so "which of them count as high" has no answer. Nothing structural
    # can catch this on a kind-unknown signal, so the read-time backstop is what does.
    interface = InscopixGpioEventsInterface(
        file_path=GPIO_FILE_PATH,
        detection_configuration={"GPIO-2": [{"detection": "rising"}]},
    )
    with pytest.raises(ValueError, match="needs a two-valued signal"):
        interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=interface.get_metadata())


def test_high_period_durations_use_the_change_point_clock():
    # Inscopix stores irregularly spaced change-points (this channel's gaps run from 10 ms to 171 ms), so
    # a duration has to be the elapsed clock time between the two edges. Estimating a frame period and
    # multiplying is what the interfaces used to do, and on this file it would report 19 ms per pulse
    # (the median gap) for pulses that are really 10 ms, so the fixture is a regression guard for it.
    interface = InscopixGpioEventsInterface(
        file_path=GPIO_FILE_PATH,
        detection_configuration={"BNC Sync Output": [{"detection": "high_period"}]},
    )
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
    table = nwbfile.get_events_table("BncSyncOutput")
    assert "duration" in table.colnames
    assert np.allclose(np.asarray(table["duration"].data), 0.010)


class TestCutsInsteadOfALevelColumn:
    """One spec per cut point replaces the categorical band column, losslessly.

    This is the one place the claim meets a real coded channel rather than a synthetic trace: ``GPIO-2``
    is a four-level odor-concentration code that used to be written as a band index in a value column.
    """

    configuration = {
        "GPIO-2": [
            {"signal_conditioning": {"thresholds": [cut]}, "detection": "high_period", "event_name": name}
            for cut, name in zip(ODOR_CUTS, ("above_136", "above_152", "above_192"))
        ]
    }

    def test_each_cut_is_its_own_named_durative_event_type(self):
        interface = InscopixGpioEventsInterface(file_path=GPIO_FILE_PATH, detection_configuration=self.configuration)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
        assert set(nwbfile.events) == {"Above136", "Above152", "Above192"}
        for name in nwbfile.events:
            assert "duration" in nwbfile.get_events_table(name).colnames

    def test_the_cuts_reconstruct_the_band_the_column_used_to_hold(self):
        interface = InscopixGpioEventsInterface(file_path=GPIO_FILE_PATH, detection_configuration=self.configuration)
        events = interface._get_events_data_dict()

        gpio = interface._get_available_signals(GPIO_FILE_PATH)
        raw_timestamps, amplitudes = _read_channel(GPIO_FILE_PATH, gpio["GPIO-2"]["channel_index"])
        bands = np.searchsorted(ODOR_CUTS, amplitudes, side="right")

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


def test_unknown_channel_raises_at_construction():
    # The channel inventory is known at construction, so naming a channel the file does not have fails
    # there rather than at read time.
    with pytest.raises(ValueError, match="not one of the file's signals"):
        InscopixGpioEventsInterface(
            file_path=GPIO_FILE_PATH, detection_configuration={"NotAChannel": [{"detection": "rising"}]}
        )


def test_round_trip(interface, tmp_path):
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
    nwbfile_path = tmp_path / "test_inscopix_gpio_events.nwb"
    with NWBHDF5IO(nwbfile_path, mode="w") as io:
        io.write(nwbfile)
    with NWBHDF5IO(nwbfile_path, mode="r") as io:
        read_nwbfile = io.read()
        assert len(read_nwbfile.get_events_table("Gpio2")) == 334
        assert len(read_nwbfile.get_events_table("BncSyncOutput")) == 9
