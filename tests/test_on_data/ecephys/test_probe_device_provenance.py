"""What an interface writes for its own probe is asserted with the other interface tests, and what the
write path derives is asserted against constructed probes in ``tests/test_modalities/test_ecephys``. This
file holds what neither can show: what two interfaces holding different probes merge into."""

from neuroconv.datainterfaces import SpikeGLXRecordingInterface
from neuroconv.utils import dict_deep_update

from ..setup_paths import ECEPHY_DATA_PATH

SPIKEGLX_PATH = ECEPHY_DATA_PATH / "spikeglx"


def test_two_probes_of_the_same_model_share_one_model_and_keep_separate_devices():
    """Distinct units stay distinct, since the key is the serial number, while the catalogue entry they
    share is written once."""
    folder_path = SPIKEGLX_PATH / "multi_trigger_multi_gate" / "SpikeGLX" / "5-19-2022-CI0"
    interfaces = [
        SpikeGLXRecordingInterface(folder_path=folder_path, stream_id=stream_id)
        for stream_id in ("imec0.ap", "imec1.ap")
    ]

    metadata = interfaces[0].get_metadata(use_new_metadata_format=True)
    metadata = dict_deep_update(metadata, interfaces[1].get_metadata(use_new_metadata_format=True))

    assert len(metadata["Devices"]) == 2
    assert len(metadata["DeviceModels"]) == 1
