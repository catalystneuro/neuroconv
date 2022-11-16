from datetime import datetime

import numpy as np
from dateutil.tz import gettz
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal

from neuroconv.tools.audio import add_acoustic_waveform_series
from neuroconv.tools.nwb_helpers import make_nwbfile_from_metadata


class TestAddAcousticWaveformSeries(TestCase):
    @classmethod
    def setUpClass(cls):
        session_start_time = datetime.now(tz=gettz(name="US/Pacific"))
        cls.num_frames = 1000
        cls.sampling_rate = 500.0

        metadata = dict()
        metadata["NWBFile"] = dict(session_start_time=session_start_time)
        audio_metadata = dict(name="AcousticWaveformSeries", description="test")
        metadata["Behavior"] = dict(Audio=[audio_metadata])
        cls.metadata = metadata
        cls.audio_metadata = audio_metadata

    def setUp(self):
        self.nwbfile = make_nwbfile_from_metadata(metadata=self.metadata)
        dtype = "int16"
        self.data = np.random.randint(
            size=(self.num_frames,), low=np.iinfo(dtype).min, high=np.iinfo(dtype).max, dtype=dtype
        )

    def test_add_series_with_default_write_as(self):
        add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=self.nwbfile,
            metadata=self.audio_metadata,
        )

        self.assertIn(self.audio_metadata["name"], self.nwbfile.stimulus)
        self.assertNotIn(self.audio_metadata["name"], self.nwbfile.acquisition)

    def test_add_series_as_acquisition(self):
        add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=self.nwbfile,
            metadata=self.audio_metadata,
            write_as="acquisition",
        )

        self.assertIn(self.audio_metadata["name"], self.nwbfile.acquisition)

    def test_add_series_with_incorrect_write_as(self):
        expected_error_message = "Acoustic series can be written either as 'stimulus' or 'acquisition'."
        with self.assertRaisesWith(exc_type=AssertionError, exc_msg=expected_error_message):
            add_acoustic_waveform_series(
                acoustic_series=self.data,
                rate=self.sampling_rate,
                nwbfile=self.nwbfile,
                metadata=self.audio_metadata,
                write_as="test",
            )

    def test_add_series_under_same_name(self):
        add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=self.nwbfile,
            metadata=self.audio_metadata,
        )

        self.assertIn(self.audio_metadata["name"], self.nwbfile.stimulus)

        add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=self.nwbfile,
            metadata=self.audio_metadata,
        )

        self.assertEqual(1, len(self.nwbfile.stimulus))

    def test_add_two_acoustic_waveform_series(self):
        add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=self.nwbfile,
            metadata=self.audio_metadata,
        )
        audio_metadata = dict(name="AcousticWaveformSeries1", description="Test")
        add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=self.nwbfile,
            metadata=audio_metadata,
        )

        self.assertEqual(2, len(self.nwbfile.stimulus))
        self.assertIn(self.audio_metadata["name"], self.nwbfile.stimulus)
        self.assertIn(audio_metadata["name"], self.nwbfile.stimulus)

    def test_add_series_with_different_starting_time(self):
        starting_time = 2.0
        add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=self.nwbfile,
            metadata=self.audio_metadata,
            starting_time=starting_time,
        )

        acoustic_waveform_series = self.nwbfile.stimulus[self.audio_metadata["name"]]
        self.assertEqual(starting_time, acoustic_waveform_series.starting_time)

    def test_acoustic_waveform_series_data(self):
        add_acoustic_waveform_series(
            acoustic_series=self.data,
            rate=self.sampling_rate,
            nwbfile=self.nwbfile,
            metadata=self.audio_metadata,
        )
        acoustic_waveform_series = self.nwbfile.stimulus[self.audio_metadata["name"]]

        data_chunks = np.zeros(self.num_frames)
        for data_chunk in acoustic_waveform_series.data:
            data_chunks[data_chunk.selection] = data_chunk.data
        assert_array_equal(self.data, data_chunks)
