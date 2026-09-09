"""The ecephys metadata template published in the user guide, checked against the method it documents.

``docs/user_guide/metadata_templates/ecephys_recording.yaml`` is written by hand rather than generated,
because the published block shows two rows while the method returns one per channel. These tests are
what keeps the two from drifting apart, and what backs the claim the page makes: that you can copy the
block, fill it in and convert with it.
"""

import json
from pathlib import Path

import numpy as np
import yaml
from probeinterface import Probe
from pynwb import read_nwb

from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

PUBLISHED_TEMPLATES = Path(__file__).parents[3] / "docs" / "user_guide" / "metadata_templates"


def _key_paths(metadata: dict, prefix: tuple = ()) -> set:
    """Every path through a nested dictionary, so two structures compare by shape rather than value."""
    paths = set()
    for key, value in metadata.items():
        paths.add(prefix + (key,))
        if isinstance(value, dict):
            paths |= _key_paths(value, prefix + (key,))
    return paths


def _interface_with_a_probe(num_channels: int) -> MockRecordingInterface:
    """A recording whose format names its contacts, so the rows carry ``electrode_name`` and the geometry."""
    interface = MockRecordingInterface(num_channels=num_channels, durations=[0.1], metadata_key="ecephys_recording")
    probe = Probe(ndim=2, si_units="um")
    probe.set_contacts(
        positions=np.array([[0, 20 * index] for index in range(num_channels)]),
        shapes="circle",
        shape_params={"radius": 5},
    )
    probe.set_contact_ids([f"e{index}" for index in range(num_channels)])
    probe.set_device_channel_indices(np.arange(num_channels))
    interface.set_probe(probe, group_mode="by_probe")
    return interface


def test_published_ecephys_template_matches_the_method():
    # The page promises the two tabs are the same content, and that what it prints is the shape the
    # method returns. The rows and the column descriptions scale with the recording, so those two blocks
    # are compared one entry at a time and the rest by key path.
    published_yaml = yaml.safe_load((PUBLISHED_TEMPLATES / "ecephys_recording.yaml").read_text(encoding="utf-8"))
    published_json = json.loads((PUBLISHED_TEMPLATES / "ecephys_recording.json").read_text(encoding="utf-8"))
    assert published_yaml == published_json

    interface = _interface_with_a_probe(num_channels=2)
    template = interface.get_metadata_template()
    template.pop("NWBFile")  # Session-level, and not what this block illustrates.

    def structure(metadata):
        metadata = json.loads(json.dumps(metadata, default=str))
        table = metadata["Ecephys"]["ElectrodesTable"]
        table["rows"] = {"row": next(iter(table["rows"].values()))}
        table["columns"] = {"column": {"column_name": None, "description": None, "dtype": None}}
        metadata["Ecephys"]["ElectrodeGroups"] = {"group": next(iter(metadata["Ecephys"]["ElectrodeGroups"].values()))}
        metadata["Ecephys"]["ElectricalSeries"]["ecephys_recording"]["channel_to_electrode"] = {}
        return metadata

    assert _key_paths(structure(published_yaml)) == _key_paths(structure(template))
    assert set(published_yaml["Ecephys"]["ElectricalSeries"]["ecephys_recording"]["channel_to_electrode"]) == {
        str(channel_id) for channel_id in interface.channel_ids
    }


def test_published_ecephys_template_converts_once_filled(tmp_path):
    # The page's actual promise: copy this, fill in the blanks that apply, delete what does not, convert.
    metadata = yaml.safe_load((PUBLISHED_TEMPLATES / "ecephys_recording.yaml").read_text(encoding="utf-8"))
    interface = MockRecordingInterface(num_channels=2, durations=[0.1], metadata_key="ecephys_recording")
    metadata["NWBFile"] = interface.get_metadata()["NWBFile"]

    metadata["DeviceModels"]["probe_model"].update(
        name="ASSY-156-P-1",
        manufacturer="Cambridge NeuroTech",
        model_number="ASSY-156-P-1",
        description="Silicon probe.",
    )
    metadata["Devices"]["probe"].update(
        name="ProbeDorsalCA1", description="Implanted 2020-01-01.", serial_number="1234"
    )
    groups = metadata["Ecephys"]["ElectrodeGroups"]
    groups["shank_0"].update(name="Shank0", description="Shank 0, coordinates from bregma.", location="CA1")
    groups["shank_1"].update(name="Shank1", description="Shank 1, coordinates from bregma.", location="CA1")

    rows = metadata["Ecephys"]["ElectrodesTable"]["rows"]
    rows["shank_0_e0"].update(location="CA1", x=2000.0, y=2100.0, z=1500.0, rel_x=0.0, rel_y=0.0, rel_z=0.0, imp=1.0e6)
    rows["shank_1_e0"].update(location="CA3", x=2000.0, y=2600.0, z=1500.0, rel_x=0.0, rel_y=0.0, rel_z=0.0, imp=1.2e6)
    for row in rows.values():
        # This mock names no contacts and no hardware filter, so the two go rather than being guessed at.
        del row["electrode_name"]
        del row["filtering"]
    metadata["Ecephys"]["ElectrodesTable"]["columns"]["imp"]["description"] = "Electrode impedance in ohms."
    metadata["Ecephys"]["ElectricalSeries"]["ecephys_recording"].update(
        name="ElectricalSeriesRaw", description="Raw broadband traces."
    )

    nwbfile_path = tmp_path / "published_ecephys_template.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

    read_nwbfile = read_nwb(nwbfile_path)
    electrodes = read_nwbfile.electrodes.to_dataframe()
    assert electrodes["location"].tolist() == ["CA1", "CA3"]
    assert electrodes["group_name"].tolist() == ["Shank0", "Shank1"]
    assert electrodes["impedance"].tolist() == [1.0e6, 1.2e6]
    assert electrodes["y"].tolist() == [2100.0, 2600.0]
    probe = read_nwbfile.devices["ProbeDorsalCA1"]
    assert probe.model.manufacturer == "Cambridge NeuroTech"
    series = read_nwbfile.acquisition["ElectricalSeriesRaw"]
    assert series.description == "Raw broadband traces."
    assert series.electrodes.data[:].tolist() == [0, 1]
