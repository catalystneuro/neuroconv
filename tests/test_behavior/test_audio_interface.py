import re
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import jsonschema
import numpy as np
import pytest
from dateutil.tz import gettz
from numpy.testing import assert_array_equal
from pydantic import FilePath
from pynwb import NWBHDF5IO
from scipy.io.wavfile import read, write

from neuroconv import NWBConverter
from neuroconv.datainterfaces.behavior.audio.audiointerface import AudioInterface
from neuroconv.tools.testing.audio import create_24bit_wav_file
from neuroconv.tools.testing.data_interface_mixins import AudioInterfaceTestMixin


def create_audio_files(
    test_dir: FilePath,
    num_audio_files: int,
    sampling_rate: int,
    num_frames: int,
    dtype: str = "int16",
):
    audio_file_names = []
    for audio_file_ind in range(num_audio_files):
        audio_file_name = Path(test_dir) / f"test_audio_file_{audio_file_ind}.wav"
        write(
            filename=audio_file_name,
            rate=sampling_rate,
            data=np.random.randint(size=(num_frames,), low=np.iinfo(dtype).min, high=np.iinfo(dtype).max, dtype=dtype),
        )
        audio_file_names.append(audio_file_name)
    return audio_file_names


class TestAudioInterface(AudioInterfaceTestMixin):

    data_interface_cls = AudioInterface

    @pytest.fixture(scope="class", autouse=True)
    def setup_test(self, request, tmp_path_factory):

        cls = request.cls

        cls.session_start_time = datetime.now(tz=gettz(name="US/Pacific"))
        cls.num_frames = int(1e7)
        cls.num_audio_files = 3
        cls.sampling_rate = 500
        cls.aligned_segment_starting_times = [0.0, 20.0, 40.0]

        class_tmp_dir = tmp_path_factory.mktemp("class_tmp_dir")
        cls.test_dir = Path(class_tmp_dir)
        cls.file_paths = create_audio_files(
            test_dir=cls.test_dir,
            num_audio_files=cls.num_audio_files,
            sampling_rate=cls.sampling_rate,
            num_frames=cls.num_frames,
        )
        cls.interface_kwargs = dict(file_paths=[cls.file_paths[0]])

    @pytest.fixture(scope="function", autouse=True)
    def setup_converter(self):

        self.nwbfile_path = str(self.test_dir / "audio_test.nwb")
        self.create_audio_converter()
        self.metadata = self.nwb_converter.get_metadata()
        self.metadata["NWBFile"].update(session_start_time=self.session_start_time)

    def create_audio_converter(self):
        class AudioTestNWBConverter(NWBConverter):
            data_interface_classes = dict(Audio=AudioInterface)

        source_data = dict(Audio=dict(file_paths=self.file_paths))
        self.nwb_converter = AudioTestNWBConverter(source_data)
        self.interface = self.nwb_converter.data_interface_objects["Audio"]
        self.interface.set_aligned_segment_starting_times(
            aligned_segment_starting_times=self.aligned_segment_starting_times
        )

    def test_get_metadata(self):
        audio_interface = AudioInterface(file_paths=self.file_paths)
        metadata = audio_interface.get_metadata()
        audio_metadata = metadata["Behavior"]["Audio"]

        assert len(audio_metadata) == self.num_audio_files

    def test_incorrect_write_as(self):
        with pytest.raises(jsonschema.exceptions.ValidationError):
            self.nwb_converter.run_conversion(
                nwbfile_path=self.nwbfile_path,
                metadata=self.metadata,
                conversion_options=dict(Audio=dict(write_as="bad_option")),
                overwrite=True,
            )

    def test_write_as_acquisition(self):
        conversion_opts = dict(Audio=dict(write_as="acquisition"))
        nwbfile_path = str(self.test_dir / "audio_write_as_acquisition.nwb")
        self.nwb_converter.run_conversion(
            nwbfile_path=nwbfile_path,
            metadata=self.metadata,
            conversion_options=conversion_opts,
        )
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            container = nwbfile.acquisition
            metadata = self.nwb_converter.get_metadata()
            for audio_ind, audio_metadata in enumerate(metadata["Behavior"]["Audio"]):
                audio_interface_name = audio_metadata["name"]
                assert audio_interface_name in container
                assert audio_interface_name not in nwbfile.stimulus

    def test_incomplete_metadata(self):
        metadata = deepcopy(self.metadata)
        metadata["Behavior"].update(Audio=[dict(name="Audio", description="Acoustic waveform series.")])
        expected_error_message = (
            "The Audio metadata is incomplete (1 entry)! Expected 3 (one for each entry of 'file_paths')."
        )
        with pytest.raises(AssertionError, match=re.escape(expected_error_message)):
            self.nwb_converter.run_conversion(nwbfile_path=self.nwbfile_path, metadata=metadata, overwrite=True)

    def test_metadata_update(self):
        metadata = deepcopy(self.metadata)
        metadata["Behavior"]["Audio"][0].update(description="New description for Acoustic waveform series.")
        nwbfile_path = str(self.test_dir / "audio_with_updated_metadata.nwb")
        self.nwb_converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            container = nwbfile.stimulus
            audio_name = metadata["Behavior"]["Audio"][0]["name"]
            assert container[audio_name].description == "New description for Acoustic waveform series."

    def test_not_all_metadata_are_unique(self):
        metadata = deepcopy(self.metadata)
        metadata["Behavior"].update(
            Audio=[
                dict(name="Audio", description="Acoustic waveform series."),
                dict(name="Audio", description="Acoustic waveform series."),
                dict(name="Audio2", description="Acoustic waveform series."),
            ],
        )
        expected_error_message = "Some of the names for Audio metadata are not unique."
        with pytest.raises(AssertionError, match=re.escape(expected_error_message)):
            self.interface.run_conversion(nwbfile_path=self.nwbfile_path, metadata=metadata, overwrite=True)

    def test_segment_starting_times_are_floats(self):
        with pytest.raises(AssertionError, match="Argument 'aligned_segment_starting_times' must be a list of floats."):
            self.interface.set_aligned_segment_starting_times(aligned_segment_starting_times=[0, 1, 2])

    def test_segment_starting_times_length_mismatch(self):
        with pytest.raises(AssertionError) as exc_info:
            self.interface.set_aligned_segment_starting_times(aligned_segment_starting_times=[0.0, 1.0, 2.0, 4.0])
        exc_msg = "The number of entries in 'aligned_segment_starting_times' (4) must be equal to the number of audio file paths (3)."
        assert str(exc_info.value) == exc_msg

    def test_set_aligned_segment_starting_times(self):
        fresh_interface = AudioInterface(file_paths=self.file_paths[:2])

        aligned_segment_starting_times = [0.0, 1.0]
        fresh_interface.set_aligned_segment_starting_times(
            aligned_segment_starting_times=aligned_segment_starting_times
        )

        assert_array_equal(self.interface._segment_starting_times, self.aligned_segment_starting_times)

    def test_set_aligned_starting_time(self):
        fresh_interface = AudioInterface(file_paths=self.file_paths[:2])

        aligned_starting_time = 1.23
        relative_starting_times = [0.0, 1.0]
        fresh_interface.set_aligned_segment_starting_times(aligned_segment_starting_times=relative_starting_times)
        fresh_interface.set_aligned_starting_time(aligned_starting_time=aligned_starting_time)

        expecting_starting_times = [
            relative_starting_time + aligned_starting_time for relative_starting_time in relative_starting_times
        ]
        assert_array_equal(fresh_interface._segment_starting_times, expecting_starting_times)

    def test_run_conversion(self):
        file_paths = self.nwb_converter.data_interface_objects["Audio"].source_data["file_paths"]
        audio_test_data = [read(filename=file_path, mmap=True)[1] for file_path in file_paths]

        nwbfile_path = str(self.test_dir / "audio_test_data.nwb")
        self.nwb_converter.run_conversion(
            nwbfile_path=nwbfile_path,
            metadata=self.metadata,
            conversion_options=dict(
                Audio=dict(
                    iterator_options=dict(
                        buffer_gb=1e7 / 1e9,
                    )
                )
            ),  # use a low buffer_gb, so we can test the full GenericDataChunkIterator
            overwrite=True,
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            container = nwbfile.stimulus
            metadata = self.nwb_converter.get_metadata()
            assert len(container) == 3
            for audio_ind, audio_metadata in enumerate(metadata["Behavior"]["Audio"]):
                audio_interface_name = audio_metadata["name"]
                assert audio_interface_name in container
                assert self.aligned_segment_starting_times[audio_ind] == container[audio_interface_name].starting_time
                assert self.sampling_rate == container[audio_interface_name].rate
                assert_array_equal(audio_test_data[audio_ind], container[audio_interface_name].data)

    def test_get_wav_bit_depth(self):
        """Test that _get_wav_bit_depth correctly identifies the bit depth of WAV files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a 24-bit WAV file
            file_path = Path(temp_dir) / "test_24bit.wav"
            create_24bit_wav_file(file_path)

            # Check that the bit depth is correctly identified as 24
            bit_depth = AudioInterface._get_wav_bit_depth(file_path)
            assert bit_depth == 24, f"Expected bit depth of 24, got {bit_depth}"

    def test_24bit_wav_file(self):
        """Test that AudioInterface works with 24-bit WAV files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a 24-bit WAV file
            file_path = Path(temp_dir) / "test_24bit.wav"
            create_24bit_wav_file(file_path)

            # Create a converter with the AudioInterface
            class AudioTestNWBConverter(NWBConverter):
                data_interface_classes = dict(Audio=AudioInterface)

            # Initialize the converter with the 24-bit WAV file
            source_data = dict(Audio=dict(file_paths=[file_path]))
            nwb_converter = AudioTestNWBConverter(source_data)

            # Get metadata
            metadata = nwb_converter.get_metadata()
            metadata["NWBFile"].update(session_start_time=self.session_start_time)

            # Run conversion
            nwbfile_path = str(self.test_dir / "audio_24bit_test.nwb")

            # This will fail if the AudioInterface doesn't handle 24-bit WAV files correctly
            nwb_converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

            # Verify the file was created and can be read
            with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
                nwbfile = io.read()

                # Check that the acoustic waveform series exists
                audio_name = metadata["Behavior"]["Audio"][0]["name"]
                assert audio_name in nwbfile.stimulus

                # Try to read the data
                acoustic_series = nwbfile.stimulus[audio_name].data[:]
                assert len(acoustic_series) > 0
