import datetime

import probeinterface as pi
from numpy.testing import assert_array_equal
from spikeinterface.extractors import SpikeGLXRecordingExtractor

from neuroconv.datainterfaces import SpikeGLXRecordingInterface
from neuroconv.datainterfaces.ecephys.spikeglx.spikeglx_utils import (
    get_session_start_time,
)

from ..setup_paths import ECEPHY_DATA_PATH

SPIKEGLX_PATH = ECEPHY_DATA_PATH / "spikeglx"


def test_spikelgx_session_start_time_lf():
    folder_path = SPIKEGLX_PATH / "Noise4Sam_g0" / "Noise4Sam_g0_imec0"
    stream_id = "imec0.lf"
    recording = SpikeGLXRecordingExtractor(folder_path=folder_path, stream_id=stream_id)
    recording_metadata = recording.neo_reader.signals_info_dict[(0, stream_id)]["meta"]

    assert get_session_start_time(recording_metadata) == datetime.datetime(2020, 11, 3, 10, 35, 10)


def test_spikelgx_recording_property_addition():
    """Test that the properties added in the electrodes match the ones in the metafile"""
    ap_file_path = SPIKEGLX_PATH / "TEST_20210920_0_g0" / "TEST_20210920_0_g0_t0.imec0.ap.bin"
    meta_filename = str(ap_file_path).replace(".bin", ".meta")
    probe = pi.read_spikeglx(meta_filename)
    n_channels = probe.device_channel_indices.size
    probe_name = "Imec0"

    expected_shank_ids = probe.shank_ids
    expected_group_name = [f"Neuropixels{probe_name}Shank{shank_id}" for shank_id in expected_shank_ids]

    expected_contact_shapes = ["square"] * n_channels
    expected_contact_ids = probe.contact_ids

    # Initialize the interface and get the added properties
    folder_path = ap_file_path.parent
    interface = SpikeGLXRecordingInterface(folder_path=folder_path, stream_id="imec0.ap")
    group_name = interface.recording_extractor.get_property("group_name")
    contact_shapes = interface.recording_extractor.get_property("contact_shapes")
    shank_ids = interface.recording_extractor.get_property("shank_ids")
    contact_ids = interface.recording_extractor.get_property("contact_ids")

    assert_array_equal(group_name, expected_group_name)
    assert_array_equal(contact_shapes, expected_contact_shapes)
    assert_array_equal(shank_ids, expected_shank_ids)
    assert_array_equal(contact_ids, expected_contact_ids)
