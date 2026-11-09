import unittest

from pynwb import read_nwb

from neuroconv.datainterfaces import AudioInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH


class TestAudioInterfaceWavIEEEFloat(DataInterfaceTestMixin):
    data_interface_cls = AudioInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "audio" / "generated_audio_files" / "Stereo_32bit_Float_PCM.wav")
    )
    save_directory = OUTPUT_PATH
    expected_temporal_alignment_keys = ("audio_Stereo_32bit_Float_PCM",)

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        # Verify the acoustic waveform series exists in the file
        assert "AcousticWaveformSeries" in nwbfile.stimulus
        # Verify we can read the data
        data = nwbfile.stimulus["AcousticWaveformSeries"].data[:]
        assert len(data) > 0
        assert data.dtype == "float32"
        nwbfile.read_io.close()


if __name__ == "__main__":
    unittest.main()
