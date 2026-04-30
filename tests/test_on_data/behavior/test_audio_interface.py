import unittest

from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import AudioInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH


class TestAudioInterfaceWavIEEEFloat(DataInterfaceTestMixin):
    data_interface_cls = AudioInterface
    interface_kwargs = dict(
        file_paths=[str(BEHAVIOR_DATA_PATH / "audio" / "generated_audio_files" / "Stereo_32bit_Float_PCM.wav")]
    )
    save_directory = OUTPUT_PATH

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            # Verify the acoustic waveform series exists in the file
            assert "AcousticWaveformSeries" in nwbfile.stimulus
            # Verify we can read the data
            data = nwbfile.stimulus["AcousticWaveformSeries"].data[:]
            assert len(data) > 0
            assert data.dtype == "float32"


if __name__ == "__main__":
    unittest.main()
