import datetime
from numpy.testing import assert_array_equal

import probeinterface as pi
from spikeinterface.extractors import SpikeGLXRecordingExtractor

from nwb_conversion_tools.datainterfaces.ecephys.spikeglx.spikeglx_utils import get_session_start_time
from nwb_conversion_tools import SpikeGLXLFPInterface, SpikeGLXRecordingInterface

from ..setup_paths import ECEPHY_DATA_PATH

SPIKEGLX_PATH = ECEPHY_DATA_PATH / "spikeglx" 



def test_spikelgx_session_start_time_ap():

    folder_path = SPIKEGLX_PATH / "Noise4Sam_g0" / "Noise4Sam_g0_imec0"
    stream_id = "imec0.ap"
    recording = SpikeGLXRecordingExtractor(folder_path=folder_path, stream_id=stream_id)
    recording_metadata = recording.neo_reader.signals_info_dict[(0, stream_id)]["meta"]

    assert get_session_start_time(recording_metadata) == datetime.datetime(2020, 11, 3, 10, 35, 10)


def test_spikelgx_session_start_time_lf():

    folder_path = SPIKEGLX_PATH / "Noise4Sam_g0" / "Noise4Sam_g0_imec0"
    stream_id = "imec0.lf"
    recording = SpikeGLXRecordingExtractor(folder_path=folder_path, stream_id=stream_id)
    recording_metadata = recording.neo_reader.signals_info_dict[(0, stream_id)]["meta"]

    assert get_session_start_time(recording_metadata) == datetime.datetime(2020, 11, 3, 10, 35, 10)

def test_spikelgx_recording_property_addition():
    ap_file_path = SPIKEGLX_PATH / "TEST_20210920_0_g0" / "TEST_20210920_0_g0_t0.imec0.ap.bin"
    meta_filename = str(ap_file_path).replace(".bin", ".meta")
    probe = pi.read_spikeglx(meta_filename)

    interface = SpikeGLXRecordingInterface(file_path=ap_file_path)
    shank_electrode_number = interface.recording_extractor.get_property("shank_electrode_number")
    shank_group_name = interface.recording_extractor.get_property("shank_group_name")
    
    expected_shank_electrode_number = [contact_id.split(":")[1] for contact_id in probe.contact_ids]
    expected_shank_group_name = [contact_id.split(":")[0] for contact_id in probe.contact_ids]
    
    
    assert_array_equal(shank_electrode_number, expected_shank_electrode_number)
    assert_array_equal(shank_group_name, expected_shank_group_name)
    
def test_matching_recording_property_addition_between_backends():
    folder_path = SPIKEGLX_PATH / "Noise4Sam_g0" / "Noise4Sam_g0_imec0"
    ap_file_path =  folder_path / "Noise4Sam_g0_t0.imec0.ap.bin"
    
    interface_new = SpikeGLXRecordingInterface(file_path=ap_file_path)
    shank_electrode_number_new = interface_new.recording_extractor.get_property("shank_electrode_number")
    shank_group_name_new = interface_new.recording_extractor.get_property("shank_group_name")
    
    interface_old = SpikeGLXRecordingInterface(file_path=ap_file_path, spikeextractors_backend=True)
    shank_electrode_number_old = interface_old.recording_extractor.get_property("shank_electrode_number")
    shank_group_name_old = interface_old.recording_extractor.get_property("shank_group_name")
    
    
    assert_array_equal(shank_electrode_number_new, shank_electrode_number_old)
    assert_array_equal(shank_group_name_new, shank_group_name_old)