import shutil
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
from warnings import warn

import jsonschema
import numpy as np
from dateutil.tz import gettz
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO
from scipy.io.wavfile import read, write

from neuroconv import NWBConverter
from neuroconv.datainterfaces.behavior.audio.audiointerface import AudioInterface
from neuroconv.tools.testing.data_interface_mixins import AudioInterfaceTestMixin
from neuroconv.utils import FilePathType


def create_audio_files(
    test_dir: FilePathType,
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


class TestAudioInterface(AudioInterfaceTestMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session_start_time = datetime.now(tz=gettz(name="US/Pacific"))
        cls.num_frames = 10000
        cls.num_audio_files = 3
        cls.sampling_rate = 500
        cls.starting_times = [0.0, 20.0, 40.0]

        cls.test_dir = Path(mkdtemp())
        cls.file_paths = create_audio_files(
            test_dir=cls.test_dir,
            num_audio_files=cls.num_audio_files,
            sampling_rate=cls.sampling_rate,
            num_frames=cls.num_frames,
        )
        cls.data_interface_cls = AudioInterface
        cls.interface_kwargs = dict(file_paths=[cls.file_paths[0]])

    def setUp(self):
        self.nwbfile_path = str(self.test_dir / "audio_test.nwb")
        self.create_audio_converter()
        self.metadata = self.nwb_converter.get_metadata()
        self.metadata["NWBFile"].update(session_start_time=self.session_start_time)

    @classmethod
    def tearDownClass(cls):
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:  # Windows CI bug
            warn(f"Unable to fully clean the temporary directory: {cls.test_dir}\n\nPlease remove it manually.")

    def create_audio_converter(self):
        class AudioTestNWBConverter(NWBConverter):
            data_interface_classes = dict(Audio=AudioInterface)

        source_data = dict(Audio=dict(file_paths=self.file_paths))
        self.nwb_converter = AudioTestNWBConverter(source_data)
        self.interface = self.nwb_converter.data_interface_objects["Audio"]
        self.interface.align_starting_times(starting_times=self.starting_times)

    def test_unsupported_format(self):
        exc_msg = "The currently supported file format for audio is WAV file. Some of the provided files does not match this format: ['.test']."
        with self.assertRaisesWith(ValueError, exc_msg=exc_msg):
            AudioInterface(file_paths=["test.test"])

    def test_get_metadata(self):
        audio_interface = AudioInterface(file_paths=self.file_paths)
        metadata = audio_interface.get_metadata()
        audio_metadata = metadata["Behavior"]["Audio"]

        self.assertEqual(len(audio_metadata), self.num_audio_files)

    def test_incorrect_write_as(self):
        expected_error_message = """'bad_option' is not one of ['stimulus', 'acquisition']

Failed validating 'enum' in schema['properties']['Audio']['properties']['write_as']:
    {'default': 'stimulus', 'enum': ['stimulus', 'acquisition']}

On instance['Audio']['write_as']:
    'bad_option'"""
        with self.assertRaisesWith(exc_type=jsonschema.exceptions.ValidationError, exc_msg=expected_error_message):
            self.nwb_converter.run_conversion(
                nwbfile_path=self.nwbfile_path,
                metadata=self.metadata,
                conversion_options=dict(Audio=dict(write_as="bad_option")),
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
        with self.assertRaisesWith(exc_type=AssertionError, exc_msg=expected_error_message):
            self.nwb_converter.run_conversion(nwbfile_path=self.nwbfile_path, metadata=metadata)

    def test_metadata_update(self):
        metadata = deepcopy(self.metadata)
        metadata["Behavior"]["Audio"][0].update(description="New description for Acoustic waveform series.")
        nwbfile_path = str(self.test_dir / "audio_with_updated_metadata.nwb")
        self.nwb_converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            container = nwbfile.stimulus
            audio_name = metadata["Behavior"]["Audio"][0]["name"]
            self.assertEqual("New description for Acoustic waveform series.", container[audio_name].description)

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
        with self.assertRaisesWith(exc_type=AssertionError, exc_msg=expected_error_message):
            self.interface.run_conversion(nwbfile_path=self.nwbfile_path, metadata=metadata)

    def test_starting_times_are_floats(self):
        with self.assertRaisesWith(
            exc_type=AssertionError, exc_msg="Argument 'starting_times' must be a list of floats."
        ):
            self.interface.align_starting_times(starting_times=[0, 1, 2])

    def test_starting_times_length_mismatch(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg="The number of entries in 'starting_times' (4) must be equal to the number of audio file paths (3).",
        ):
            self.interface.align_starting_times(starting_times=[0.0, 1.0, 2.0, 4.0])

    def check_align_starting_times(self):
        fresh_interface = self.data_interface_cls(**self.file_paths[:1])

        starting_times = [0.0, 1.0]
        fresh_interface.align_starting_times(starting_times=starting_times)

        assert_array_equal(x=self.interface._starting_times, y=self.starting_times)

    def check_align_global_starting_time(self):
        fresh_interface = self.data_interface_cls(**self.file_paths[:1])

        global_starting_time = 1.23
        relative_starting_times = [0.0, 1.0]
        fresh_interface.align_starting_times(starting_times=relative_starting_times)
        fresh_interface.align_global_starting_time(global_starting_time=global_starting_time)

        expecting_starting_times = [starting_time + global_starting_time for starting_time in relative_starting_times]
        assert_array_equal(x=self._starting_times, y=expected_timestamps)

    def test_run_conversion(self):
        file_paths = self.nwb_converter.data_interface_objects["Audio"].source_data["file_paths"]
        audio_test_data = [read(filename=file_path, mmap=True)[1] for file_path in file_paths]

        nwbfile_path = str(self.test_dir / "audio_test_data.nwb")
        self.nwb_converter.run_conversion(nwbfile_path=nwbfile_path, metadata=self.metadata)

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            container = nwbfile.stimulus
            metadata = self.nwb_converter.get_metadata()
            self.assertEqual(3, len(container))
            for audio_ind, audio_metadata in enumerate(metadata["Behavior"]["Audio"]):
                audio_interface_name = audio_metadata["name"]
                assert audio_interface_name in container
                self.assertEqual(self.starting_times[audio_ind], container[audio_interface_name].starting_time)
                self.assertEqual(self.sampling_rate, container[audio_interface_name].rate)
                assert_array_equal(audio_test_data[audio_ind], container[audio_interface_name].data)
