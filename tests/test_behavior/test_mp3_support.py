import os
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from pydub import AudioSegment
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces.behavior.audio.audiointerface import AudioInterface
from neuroconv.tools.audio import read_mp3


def create_mp3_file(directory, filename="test_audio.mp3", duration_ms=1000, sample_rate=44100):
    """Create a test MP3 file with a sine wave."""
    # Generate a simple sine wave
    frequency = 440  # A4 note
    t = np.linspace(0, duration_ms / 1000, int(sample_rate * duration_ms / 1000))
    audio_data = np.sin(2 * np.pi * frequency * t) * 32767  # Scale to 16-bit range
    audio_data = audio_data.astype(np.int16)

    # Create an AudioSegment
    segment = AudioSegment(audio_data.tobytes(), frame_rate=sample_rate, sample_width=2, channels=1)  # 16-bit  # Mono

    # Export as MP3
    file_path = os.path.join(directory, filename)
    segment.export(file_path, format="mp3")

    return file_path, audio_data, sample_rate


class TestMP3Support:

    def test_read_mp3(self):
        """Test that the read_mp3 function works correctly."""
        with TemporaryDirectory() as temp_dir:
            file_path, original_data, original_rate = create_mp3_file(temp_dir)

            # Read the MP3 file
            rate, data = read_mp3(file_path)

            # Check that the sample rate is correct
            assert rate == original_rate

            # Check that the data has the right shape
            assert len(data) > 0

            # MP3 is lossy, so we can't compare the data directly
            # Just check that it's not all zeros or all the same value
            assert np.std(data) > 0

    def test_audio_interface_with_mp3(self):
        """Test that the AudioInterface can handle MP3 files."""
        with TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            file_path, _, _ = create_mp3_file(temp_dir)

            # Create an AudioInterface with the MP3 file
            interface = AudioInterface(file_paths=[file_path])

            # Get metadata
            metadata = interface.get_metadata()

            # Create an NWB file
            nwbfile_path = temp_dir_path / "test.nwb"

            # Run conversion
            from neuroconv import NWBConverter

            class TestConverter(NWBConverter):
                data_interface_classes = dict(Audio=AudioInterface)

            source_data = dict(Audio=dict(file_paths=[file_path]))
            converter = TestConverter(source_data)

            metadata = converter.get_metadata()
            metadata["NWBFile"].update(
                session_start_time="2023-01-01T00:00:00", session_description="Test session", identifier="TEST123"
            )

            converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata)

            # Check that the NWB file was created and contains the audio data
            with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
                nwbfile = io.read()

                # Check that the AcousticWaveformSeries is in the file
                assert "AcousticWaveformSeries" in nwbfile.stimulus

                # Get the AcousticWaveformSeries
                series = nwbfile.stimulus["AcousticWaveformSeries"]

                # Check that it has data
                assert series.data.shape[0] > 0
