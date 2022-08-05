import datetime
from numpy.testing import assert_array_equal

import pytest
import probeinterface as pi
from spikeinterface.extractors import SpikeGLXRecordingExtractor

from neuroconv.datainterfaces.ecephys.spikeglx.spikeglx_utils import get_session_start_time
from neuroconv.datainterfaces.ecephys.spikeglx import SpikeGLXLFPInterface, SpikeGLXRecordingInterface

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


def test_get_device_metadata():
    """Test that the add device method of the spikeglx interface returns the right output"""
    folder_path = SPIKEGLX_PATH / "Noise4Sam_g0" / "Noise4Sam_g0_imec0"
    ap_file_path = folder_path / "Noise4Sam_g0_t0.imec0.ap.bin"
    spikeglx_interface = SpikeGLXRecordingInterface(file_path=ap_file_path)

    device = spikeglx_interface.get_device_metadata()

    description_string = (
        "{"
        '"probe_type": "0", '
        '"probe_type_description": "NP1.0", '
        '"flex_part_number": "NP2_FLEX_0", '
        '"connected_base_station_part_number": "NP2_QBSC_00"'
        "}"
    )
    expected_device = dict(name="Neuropixel-Imec", description=description_string, manufacturer="Imec")

    assert device["name"] == expected_device["name"]
    assert device["manufacturer"] == expected_device["manufacturer"]
    assert device["description"] == expected_device["description"]


def test_spikelgx_recording_property_addition():
    """Test that the properties added in the electrodes match the ones in the metafile"""
    ap_file_path = SPIKEGLX_PATH / "TEST_20210920_0_g0" / "TEST_20210920_0_g0_t0.imec0.ap.bin"
    meta_filename = str(ap_file_path).replace(".bin", ".meta")
    probe = pi.read_spikeglx(meta_filename)
    n_channels = probe.device_channel_indices.size

    expected_shank_electrode_number = [int(contact_id.split(":")[1][1:]) for contact_id in probe.contact_ids]
    expected_group_name = [contact_id.split(":")[0] for contact_id in probe.contact_ids]
    expected_contact_shapes = ["square"] * n_channels

    # Initialize the interface and get the added properties
    interface = SpikeGLXRecordingInterface(file_path=ap_file_path)
    shank_electrode_number = interface.recording_extractor.get_property("shank_electrode_number")
    group_name = interface.recording_extractor.get_property("group_name")
    contact_shapes = interface.recording_extractor.get_property("contact_shapes")

    assert_array_equal(shank_electrode_number, expected_shank_electrode_number)
    assert_array_equal(group_name, expected_group_name)
    assert_array_equal(contact_shapes, expected_contact_shapes)


@pytest.mark.skip(reason="Legacy spikeextractors cannot read new GIN file.")
def test_matching_recording_property_addition_between_backends():
    """Test that the extracted properties match with both backends"""
    folder_path = SPIKEGLX_PATH / "Noise4Sam_g0" / "Noise4Sam_g0_imec0"
    ap_file_path = folder_path / "Noise4Sam_g0_t0.imec0.ap.bin"

    interface_new = SpikeGLXRecordingInterface(file_path=ap_file_path)
    shank_electrode_number_new = interface_new.recording_extractor.get_property("shank_electrode_number")
    group_name_new = interface_new.recording_extractor.get_property("group_name")

    interface_old = SpikeGLXRecordingInterface(file_path=ap_file_path, spikeextractors_backend=True)
    shank_electrode_number_old = interface_old.recording_extractor.get_property("shank_electrode_number")
    group_name_old = interface_old.recording_extractor.get_property("group_name")

    assert_array_equal(shank_electrode_number_new, shank_electrode_number_old)
    assert_array_equal(group_name_new, group_name_old)
