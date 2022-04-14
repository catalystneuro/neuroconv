import datetime

from spikeinterface.extractors import SpikeGLXRecordingExtractor

from nwb_conversion_tools.datainterfaces.ecephys.spikeglx.spikeglx_utils import get_session_start_time
from nwb_conversion_tools import SpikeGLXLFPInterface, SpikeGLXRecordingInterface

from ..setup_paths import ECEPHY_DATA_PATH

SPIKEGLX_PATH = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0" / "Noise4Sam_g0_imec0"


ap_file_path = SPIKEGLX_PATH / "Noise4Sam_g0_t0.imec0.ap.bin"
lf_file_path = SPIKEGLX_PATH / "Noise4Sam_g0_t0.imec0.lf.bin"

def test_spikelgx_session_start_time_ap():
    
    folder_path = SPIKEGLX_PATH
    stream_id = "imec0.ap"
    recording = SpikeGLXRecordingExtractor(folder_path=folder_path, stream_id=stream_id)
    meta = recording.neo_reader.signals_info_dict[(0, stream_id)]["meta"]

    assert get_session_start_time(meta) == datetime.datetime(2020, 11, 3, 10, 35, 10)
    
def test_spikelgx_session_start_time_lf():
    
    folder_path = SPIKEGLX_PATH
    stream_id = "imec0.lf"
    recording = SpikeGLXRecordingExtractor(folder_path=folder_path, stream_id=stream_id)
    meta = recording.neo_reader.signals_info_dict[(0, stream_id)]["meta"]

    assert get_session_start_time(meta) == datetime.datetime(2020, 11, 3, 10, 35, 10)
    
