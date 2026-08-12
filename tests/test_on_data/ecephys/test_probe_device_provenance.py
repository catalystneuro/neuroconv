"""What an interface writes for its own probe is asserted with the other interface tests. This file holds
what a single interface cannot show: how two of them merge, and a branch no fixture reaches."""

from neuroconv.datainterfaces import SpikeGLXRecordingInterface
from neuroconv.utils import dict_deep_update

from ..setup_paths import ECEPHY_DATA_PATH

SPIKEGLX_PATH = ECEPHY_DATA_PATH / "spikeglx"


def test_a_probe_without_a_model_number_writes_no_model(monkeypatch):
    """A manufacturer on its own does not earn a ``DeviceModel``: it would have to be named after its
    maker, and ``Device.manufacturer`` is deprecated. A reader with no part number to report clears the
    field by assigning the empty string rather than dropping it, which is the case this guards, and is
    what ``read_spikegadgets_neuropixels`` does upstream."""
    interface = SpikeGLXRecordingInterface(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0", stream_id="imec0.ap")
    probe_without_model = interface.recording_extractor.get_probe()
    probe_without_model.model_name = ""
    monkeypatch.setattr(interface.recording_extractor, "get_probe", lambda: probe_without_model)

    metadata = interface.get_metadata(use_new_metadata_format=True)
    assert "DeviceModels" not in metadata
    assert "device_model_metadata_key" not in metadata["Devices"]["neuropixels_18194809281"]

    nwbfile = interface.create_nwbfile(metadata=metadata, stub_test=True)
    assert nwbfile.devices["NeuropixelsImec0"].model is None
    assert len(nwbfile.device_models) == 0


def test_the_two_streams_of_one_probe_converge_on_one_device():
    """The key names the probe rather than the stream, so the AP and LF interfaces of one probe merge
    into a single entry instead of writing the probe twice."""
    interfaces = [
        SpikeGLXRecordingInterface(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0", stream_id=stream_id)
        for stream_id in ("imec0.ap", "imec0.lf")
    ]

    metadata = interfaces[0].get_metadata(use_new_metadata_format=True)
    metadata = dict_deep_update(metadata, interfaces[1].get_metadata(use_new_metadata_format=True))

    assert set(metadata["Devices"]) == {"neuropixels_18194809281"}


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
