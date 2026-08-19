"""The electrodes registry against real probes, where contact identity is something the format states."""

from neuroconv.converters import SpikeGLXConverterPipe
from neuroconv.datainterfaces import SpikeGLXRecordingInterface
from neuroconv.tools.nwb_helpers import make_nwbfile_from_metadata
from neuroconv.utils import dict_deep_update

from ..setup_paths import ECEPHY_DATA_PATH

SPIKEGLX_PATH = ECEPHY_DATA_PATH / "spikeglx"


def test_the_two_bands_of_one_probe_land_on_one_set_of_rows():
    """384 rows for 768 channels, because AP and LF are the same 384 contacts.

    The file already comes out this way, but only because the SpikeGLX interface detects its companion
    stream at construction and writes a joined ``AP0,LF0`` into both recordings' ``channel_name`` so that
    the row identities collide on purpose. Through the registry the sharing is a consequence of the keys,
    which derive from the probe's contact ids, and the same mechanism would serve any two-band format.
    """
    converter = SpikeGLXConverterPipe(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0", streams=["imec0.ap", "imec0.lf"])
    metadata = converter.get_metadata()
    for interface in converter.data_interface_objects.values():
        metadata = dict_deep_update(metadata, interface.get_metadata_template())

    ap_keys = converter.data_interface_objects["imec0.ap"].get_metadata_template()["Ecephys"]["ElectrodesTable"]["rows"]
    lf_keys = converter.data_interface_objects["imec0.lf"].get_metadata_template()["Ecephys"]["ElectrodesTable"]["rows"]
    assert list(ap_keys) == list(lf_keys)
    assert list(ap_keys)[:3] == ["NeuropixelsImec0_e0", "NeuropixelsImec0_e1", "NeuropixelsImec0_e2"]

    converter.validate_metadata(metadata=metadata)
    nwbfile = converter.create_nwbfile(metadata=metadata)

    assert len(nwbfile.electrodes) == 384
    assert sorted(nwbfile.acquisition) == ["ElectricalSeriesAP", "ElectricalSeriesLF"]
    for series in nwbfile.acquisition.values():
        assert list(series.electrodes.data) == list(range(384))
    assert list(nwbfile.electrodes["electrode_name"][:3]) == ["e0", "e1", "e2"]


def test_two_probes_sharing_contact_ids_keep_their_electrodes_apart():
    """Contact ids are unique per probe, not per file.

    These two probes carry 70 identical ``contact_id`` values between them, so a key derived from the
    contact alone would merge unrelated electrodes. The group qualifies the key, and the group names are
    already probe-qualified, which is what keeps the 1152 channels on 768 distinct rows.
    """
    folder = SPIKEGLX_PATH / "multi_probe_multi_dock_multi_shank_filename_without_info"
    first = SpikeGLXRecordingInterface(folder_path=folder, stream_id="imec0.ap", metadata_key="imec0")
    second = SpikeGLXRecordingInterface(folder_path=folder, stream_id="imec1.ap", metadata_key="imec1")

    first_metadata = first.get_metadata_template()
    second_metadata = second.get_metadata_template()
    first_contacts = {
        entry["electrode_name"] for entry in first_metadata["Ecephys"]["ElectrodesTable"]["rows"].values()
    }
    second_contacts = {
        entry["electrode_name"] for entry in second_metadata["Ecephys"]["ElectrodesTable"]["rows"].values()
    }
    assert len(first_contacts & second_contacts) == 70
    assert not set(first_metadata["Ecephys"]["ElectrodesTable"]["rows"]) & set(
        second_metadata["Ecephys"]["ElectrodesTable"]["rows"]
    )

    metadata = dict_deep_update(dict(first_metadata), dict(second_metadata))
    metadata["Ecephys"]["ElectricalSeries"]["imec0"]["name"] = "ElectricalSeriesImec0"
    metadata["Ecephys"]["ElectricalSeries"]["imec1"]["name"] = "ElectricalSeriesImec1"
    nwbfile = make_nwbfile_from_metadata(metadata=metadata)
    first.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
    second.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    assert len(nwbfile.electrodes) == 768
    assert len(nwbfile.electrode_groups) == 5
