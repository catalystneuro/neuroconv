import re

import numpy as np
import pytest
from numpy.testing import assert_array_equal
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.audio import add_acoustic_waveform_series


class TestAddAcousticWaveformSeries:
    num_frames = 1000
    sampling_rate = 500.0
    audio_metadata = dict(name="AcousticWaveformSeries", description="test")
    data = np.random.randint(size=(num_frames,), low=np.iinfo("int16").min, high=np.iinfo("int16").max, dtype="int16")

    def test_add_series_with_default_parent_container(self):
        nwbfile = mock_NWBFile()
        returned_nwbfile = add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=nwbfile,
            metadata=self.audio_metadata,
        )

        assert returned_nwbfile is nwbfile
        assert self.audio_metadata["name"] in nwbfile.stimulus
        assert self.audio_metadata["name"] not in nwbfile.acquisition

    def test_add_series_as_acquisition(self):
        nwbfile = mock_NWBFile()
        add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=nwbfile,
            metadata=self.audio_metadata,
            parent_container="acquisition",
        )

        assert self.audio_metadata["name"] in nwbfile.acquisition

    def test_add_series_with_incorrect_parent_container(self):
        nwbfile = mock_NWBFile()
        expected_error_message = "Acoustic series can be written either as 'stimulus' or 'acquisition'."
        with pytest.raises(AssertionError, match=re.escape(expected_error_message)):
            add_acoustic_waveform_series(
                acoustic_series=self.data,
                rate=self.sampling_rate,
                nwbfile=nwbfile,
                metadata=self.audio_metadata,
                parent_container="test",
            )

    def test_add_series_under_same_name(self):
        nwbfile = mock_NWBFile()
        add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=nwbfile,
            metadata=self.audio_metadata,
        )

        assert self.audio_metadata["name"] in nwbfile.stimulus

        with pytest.warns(UserWarning, match="AcousticWaveformSeries already in nwbfile"):
            add_acoustic_waveform_series(
                acoustic_series=self.data,
                rate=self.sampling_rate,
                nwbfile=nwbfile,
                metadata=self.audio_metadata,
            )

        assert len(nwbfile.stimulus) == 1

    def test_add_two_acoustic_waveform_series(self):
        nwbfile = mock_NWBFile()
        add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=nwbfile,
            metadata=self.audio_metadata,
        )
        audio_metadata = dict(name="AcousticWaveformSeries1", description="Test")
        add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=nwbfile,
            metadata=audio_metadata,
        )

        assert len(nwbfile.stimulus) == 2
        assert self.audio_metadata["name"] in nwbfile.stimulus
        assert audio_metadata["name"] in nwbfile.stimulus

    def test_add_series_with_different_starting_time(self):
        nwbfile = mock_NWBFile()
        starting_time = 2.0
        add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=nwbfile,
            metadata=self.audio_metadata,
            starting_time=starting_time,
        )

        acoustic_waveform_series = nwbfile.stimulus[self.audio_metadata["name"]]
        assert acoustic_waveform_series.starting_time == starting_time

    def test_add_series_with_timestamps(self):
        nwbfile = mock_NWBFile()
        # A one second gap halfway through, which no rate and starting time can express
        timestamps = 2.0 + np.arange(self.num_frames) / self.sampling_rate
        timestamps[self.num_frames // 2 :] += 1.0
        add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=nwbfile,
            metadata=self.audio_metadata,
            timestamps=timestamps,
        )

        acoustic_waveform_series = nwbfile.stimulus[self.audio_metadata["name"]]
        assert_array_equal(acoustic_waveform_series.timestamps, timestamps)
        assert acoustic_waveform_series.rate is None
        assert acoustic_waveform_series.starting_time is None

    def test_acoustic_waveform_series_data(self):
        nwbfile = mock_NWBFile()
        add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=nwbfile,
            metadata=self.audio_metadata,
        )
        acoustic_waveform_series = nwbfile.stimulus[self.audio_metadata["name"]]

        data_chunks = np.zeros(self.num_frames)
        for data_chunk in acoustic_waveform_series.data:
            data_chunks[data_chunk.selection] = data_chunk.data
        assert_array_equal(data_chunks, self.data)
