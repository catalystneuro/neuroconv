from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile
from spikeinterface.core.numpyextractors import NumpyRecording

from neuroconv.tools.probeinterface import (
    add_probe_to_nwbfile,
    add_spikeglx_probe_to_nwbfile,
)
from neuroconv.tools.spikeinterface import add_recording_to_nwbfile
from neuroconv.tools.testing.mock_probes import generate_mock_probe


def test_add_probe_to_nwbfile_creates_electrodes_table():
    nwbfile = mock_NWBFile()
    probe = generate_mock_probe(num_channels=4, num_shanks=2)

    add_probe_to_nwbfile(probe=probe, nwbfile=nwbfile, group_mode="by_shank")

    assert len(nwbfile.devices) >= 1
    if hasattr(nwbfile, "device_models"):
        assert len(nwbfile.device_models) >= 1
        device = next(iter(nwbfile.devices.values()))
        assert getattr(device, "model", None) is not None
    electrodes_df = nwbfile.electrodes.to_dataframe()
    assert len(electrodes_df) == probe.get_contact_count()
    assert "electrode_name" in electrodes_df.columns
    assert electrodes_df["electrode_name"].is_unique
    assert len(set(electrodes_df["group_name"])) == 2


def test_add_probe_then_recording_does_not_duplicate_rows():
    probe = generate_mock_probe(num_channels=6, num_shanks=3)
    nwbfile = mock_NWBFile()

    add_probe_to_nwbfile(probe=probe, nwbfile=nwbfile, group_mode="by_shank")
    initial_row_count = len(nwbfile.electrodes)

    recording = NumpyRecording(np.zeros((10, probe.get_contact_count()), dtype=np.float32), sampling_frequency=30000.0)
    recording = recording.set_probe(probe, group_mode="by_shank", in_place=True)
    recording.set_property("group_name", recording.get_property("group").astype(str))
    channel_ids = recording.get_channel_ids()
    channel_names = np.array([f"AP{idx:03d}" for idx in range(len(channel_ids))], dtype="U")
    recording.set_property("channel_name", ids=channel_ids, values=channel_names)

    add_recording_to_nwbfile(recording=recording, nwbfile=nwbfile, write_electrical_series=False)

    assert len(nwbfile.electrodes) == initial_row_count


def test_add_spikeglx_probe_to_nwbfile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    probe = generate_mock_probe(num_channels=4, num_shanks=2)

    def _fake_read_spikeglx(_: Path):
        return probe

    def _fake_parse_spikeglx_meta(_: Path):
        return {"imDatPrb_type": "24"}

    monkeypatch.setattr("probeinterface.neuropixels_tools.read_spikeglx", _fake_read_spikeglx)
    monkeypatch.setattr("probeinterface.neuropixels_tools.parse_spikeglx_meta", _fake_parse_spikeglx_meta)

    meta_path = tmp_path / "test.meta"
    meta_path.write_text("test")

    nwbfile = mock_NWBFile()
    add_spikeglx_probe_to_nwbfile(meta_file=meta_path, nwbfile=nwbfile, group_mode="by_shank")

    assert "NeuropixelImec" in nwbfile.devices
    if hasattr(nwbfile, "device_models"):
        assert len(nwbfile.device_models) >= 1
        device = nwbfile.devices["NeuropixelImec"]
        assert getattr(device, "model", None) is not None
    assert len(nwbfile.electrodes) == probe.get_contact_count()
