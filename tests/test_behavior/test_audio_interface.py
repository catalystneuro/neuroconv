import os
import shutil
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp

import numpy as np
from dateutil.tz import gettz
from hdmf.testing import TestCase
from pynwb import NWBFile, NWBHDF5IO

from neuroconv import NWBConverter
from neuroconv.datainterfaces.behavior.audio.audiointerface import (
    AudioInterface,
)

try:
    import soundfile as sf

    skip_test = False
except ImportError:
    skip_test = True


@unittest.skipIf(skip_test, "soundfile not installed")
class TestAudioInterface(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session_start_time = datetime.now(tz=gettz(name="US/Pacific"))
        cls.num_frames = 10000
        cls.num_audio_files = 3
        cls.sampling_rate = 500

    def setUp(self):
        self.test_dir = Path(mkdtemp())

        self.create_audio_files()
        self.file_paths = [self.test_dir / file for file in os.listdir(self.test_dir) if file.endswith(".wav")]

        self.nwbfile_path = str(self.test_dir / "audio_test.nwb")
        self.nwbfile = NWBFile(
            session_description="session_description",
            identifier="file_id",
            session_start_time=self.session_start_time,
        )
        self.nwb_converter = self.create_audio_converter()
        self.metadata = self.nwb_converter.get_metadata()
        self.metadata["NWBFile"].update(session_start_time=self.session_start_time)
        self.starting_times = [0.0, 20.0, 40.0]

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def create_audio_files(self):
        for audio_file_ind in range(self.num_audio_files):
            sf.write(
                file=self.test_dir / f"test_audio_file_{audio_file_ind}.wav",
                data=np.random.randn(self.num_frames, 2),
                samplerate=self.sampling_rate,
            )

    def create_audio_converter(self):
        class AudioTestNWBConverter(NWBConverter):
            data_interface_classes = dict(Audio=AudioInterface)

        source_data = dict(Audio=dict(file_paths=self.file_paths))
        return AudioTestNWBConverter(source_data)

    def test_unsupported_format(self):
        exc_msg = (
            "Some of the file formats are not supported by soundfile. "
            "The supported formats are: AIFF, AU, AVR, CAF, FLAC, HTK, SVX, MAT4,"
            " MAT5, MPC2K, MP3, OGG, PAF, PVF, RAW, RF64, SD2, SDS, IRCAM, VOC, "
            "W64, WAV, NIST, WAVEX, WVE, XI."
        )
        with self.assertRaisesWith(AssertionError, exc_msg=exc_msg):
            AudioInterface(file_paths=["test.test"])

    def test_get_metadata(self):
        audio_interface = AudioInterface(file_paths=self.file_paths)
        metadata = audio_interface.get_metadata()
        audio_metadata = metadata["Behavior"]["Audio"]

        self.assertEqual(len(audio_metadata), self.num_audio_files)

    def test_run_conversion(self):
        conversion_opts = dict(Audio=dict(starting_times=self.starting_times))
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            metadata=self.metadata,
            conversion_options=conversion_opts,
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            container = nwbfile.stimulus
            metadata = self.nwb_converter.get_metadata()
            for audio_ind, audio_metadata in enumerate(metadata["Behavior"]["Audio"]):
                audio_interface_name = audio_metadata["name"]
                assert audio_interface_name in container
                assert self.starting_times[audio_ind] == container[audio_interface_name].starting_time
