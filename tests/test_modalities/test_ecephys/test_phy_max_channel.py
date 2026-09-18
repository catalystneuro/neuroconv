import numpy as np
import pytest
from numpy.testing import assert_array_equal
from pynwb.core import DynamicTableRegion

from neuroconv.datainterfaces import PhySortingInterface
from neuroconv.tools.testing import MockRecordingInterface


@pytest.fixture(scope="module")
def phy_export(tmp_path_factory):
    """A Phy folder exported by spikeinterface from a synthetic ground-truth recording."""
    import spikeinterface.full as si
    from spikeinterface.core import get_template_extremum_channel
    from spikeinterface.exporters import export_to_phy

    recording, sorting = si.generate_ground_truth_recording(durations=[10.0], num_channels=16, num_units=6, seed=0)
    analyzer = si.create_sorting_analyzer(sorting, recording, sparse=False)
    analyzer.compute(["random_spikes", "waveforms", "templates", "noise_levels"])
    folder = tmp_path_factory.mktemp("phy")
    # `compute_pc_features` is on by default and is the only step that needs scikit-learn
    export_to_phy(analyzer, folder, remove_if_exists=True, copy_binary=False, compute_pc_features=False, verbose=False)
    expected = get_template_extremum_channel(analyzer, peak_sign="both", mode="peak_to_peak", outputs="index")
    return folder, recording, expected


def test_get_max_channel_matches_spikeinterface(phy_export):
    folder, _, expected = phy_export
    interface = PhySortingInterface(folder_path=folder)
    cluster_ids = interface.sorting_extractor.get_property("original_cluster_id")
    # export_to_phy numbers clusters by position in the analyzer's unit list
    expected_by_unit = np.array([list(expected.values())[cluster_id] for cluster_id in cluster_ids])
    assert_array_equal(interface.get_max_channel(), expected_by_unit)


def test_max_channel_is_written_as_electrode_reference(phy_export):
    folder, recording, _ = phy_export
    recording_interface = MockRecordingInterface(num_channels=recording.get_num_channels(), durations=[1.0])
    nwbfile = recording_interface.create_nwbfile()
    interface = PhySortingInterface(folder_path=folder)
    interface.add_to_nwbfile(nwbfile=nwbfile)
    column = nwbfile.units["max_channel"]
    assert isinstance(column, DynamicTableRegion)
    assert column.table is nwbfile.electrodes
    assert_array_equal(column.data[:], interface.get_max_channel())


def test_max_channel_skipped_when_electrodes_do_not_match(phy_export):
    folder, _, _ = phy_export
    recording_interface = MockRecordingInterface(num_channels=2, durations=[1.0])
    nwbfile = recording_interface.create_nwbfile()
    interface = PhySortingInterface(folder_path=folder)
    with pytest.warns(UserWarning, match="Not adding 'max_channel'"):
        interface.add_to_nwbfile(nwbfile=nwbfile)
    assert "max_channel" not in nwbfile.units.colnames


def test_max_channel_can_be_turned_off(phy_export):
    folder, _, _ = phy_export
    nwbfile = MockRecordingInterface(num_channels=16, durations=[1.0]).create_nwbfile()
    PhySortingInterface(folder_path=folder).add_to_nwbfile(nwbfile=nwbfile, include_max_channel=False)
    assert "max_channel" not in nwbfile.units.colnames
