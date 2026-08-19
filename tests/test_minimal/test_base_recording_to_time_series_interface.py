"""Data-free tests of the base the TimeSeries-writing interfaces share."""

import pytest
from pynwb.testing.mock.file import mock_NWBFile
from spikeinterface.core.generate import generate_recording

from neuroconv.datainterfaces.ecephys.baserecordingtotimeseriesinterface import (
    BaseRecordingToTimeSeriesInterface,
)
from neuroconv.utils import DeepDict


def _scaled_recording(num_channels: int):
    """A recording whose channels agree on a unit, so the writer keeps the scaling it was given."""
    recording = generate_recording(num_channels=num_channels, durations=[0.1])
    recording.set_property("physical_unit", ["volts"] * num_channels)
    recording.set_property("gain_to_physical_unit", [1.0] * num_channels)
    recording.set_property("offset_to_physical_unit", [0.0] * num_channels)
    return recording


class MinimalTimeSeriesInterface(BaseRecordingToTimeSeriesInterface):
    """The least a subclass can state: where its recording came from and what to call the series."""

    def __init__(self, metadata_key: str = "minimal_time_series"):
        self.metadata_key = metadata_key
        self.recording_extractor = _scaled_recording(num_channels=3)
        super().__init__()

    def _get_time_series_name(self) -> str:
        return "TimeSeriesMinimal"

    def _get_time_series_description(self) -> str:
        return f"Channels are {self.get_channel_names()} in that order."


class StimulusTimeSeriesInterface(MinimalTimeSeriesInterface):
    """A signal applied to the preparation rather than recorded from it."""

    parent_container = "stimulus"

    def _get_time_series_name(self) -> str:
        return "TimeSeriesStimulus"


class DeviceCarryingTimeSeriesInterface(MinimalTimeSeriesInterface):
    """A subclass whose metadata carries more than the series."""

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        metadata["Devices"] = {"a_device": dict(name="ADevice")}
        return metadata


class UnnamedTimeSeriesInterface(BaseRecordingToTimeSeriesInterface):
    """A subclass that forgot to name its series."""

    def __init__(self):
        self.metadata_key = "unnamed"
        self.recording_extractor = _scaled_recording(num_channels=1)
        super().__init__()


def test_metadata_states_the_series_the_subclass_names():
    interface = MinimalTimeSeriesInterface()

    metadata = interface.get_metadata()

    assert metadata["TimeSeries"]["minimal_time_series"] == dict(
        name="TimeSeriesMinimal",
        description=f"Channels are {interface.get_channel_names()} in that order.",
    )


def test_metadata_key_addresses_the_entry():
    """The key indexes the entry and the entry's name is what the object is called, so the two differ."""
    interface = MinimalTimeSeriesInterface(metadata_key="a_key_of_my_own")

    metadata = interface.get_metadata()

    assert list(metadata["TimeSeries"]) == ["a_key_of_my_own"]
    assert metadata["TimeSeries"]["a_key_of_my_own"]["name"] == "TimeSeriesMinimal"


def test_the_series_is_written_to_acquisition_by_default():
    interface = MinimalTimeSeriesInterface()
    nwbfile = mock_NWBFile()

    interface.add_to_nwbfile(nwbfile=nwbfile)

    assert "TimeSeriesMinimal" in nwbfile.acquisition
    assert "TimeSeriesMinimal" not in nwbfile.stimulus


def test_a_stimulus_interface_writes_to_stimulus():
    interface = StimulusTimeSeriesInterface()
    nwbfile = mock_NWBFile()

    interface.add_to_nwbfile(nwbfile=nwbfile)

    assert "TimeSeriesStimulus" in nwbfile.stimulus
    assert "TimeSeriesStimulus" not in nwbfile.acquisition


def test_a_subclass_keeps_what_it_adds_to_the_metadata():
    interface = DeviceCarryingTimeSeriesInterface()

    metadata = interface.get_metadata()

    assert metadata["Devices"] == {"a_device": dict(name="ADevice")}
    assert metadata["TimeSeries"]["minimal_time_series"]["name"] == "TimeSeriesMinimal"


def test_channel_names_come_from_the_recording():
    interface = MinimalTimeSeriesInterface()

    assert list(interface.channel_ids) == interface.get_channel_names()
    assert len(interface.get_channel_names()) == 3


def test_a_subclass_that_names_no_series_says_so():
    interface = UnnamedTimeSeriesInterface()

    with pytest.raises(NotImplementedError, match="UnnamedTimeSeriesInterface"):
        interface.get_metadata()


def test_stub_test_writes_less_than_the_whole_recording():
    interface = MinimalTimeSeriesInterface()
    full_nwbfile = mock_NWBFile()
    stub_nwbfile = mock_NWBFile()

    interface.add_to_nwbfile(nwbfile=full_nwbfile)
    interface.add_to_nwbfile(nwbfile=stub_nwbfile, stub_test=True)

    full_samples = full_nwbfile.acquisition["TimeSeriesMinimal"].data.shape[0]
    stub_samples = stub_nwbfile.acquisition["TimeSeriesMinimal"].data.shape[0]
    assert stub_samples < full_samples
