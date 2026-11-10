"""Writing a SortingAnalyzer with ndx-spikesorting through `add/write_sorting_analyzer_to_nwbfile`."""

import h5py
import numpy as np
import pytest
from packaging.version import Version
from pynwb.testing.mock.file import mock_NWBFile
from spikeinterface.core.generate import generate_ground_truth_recording

from neuroconv.tools.importing import get_package_version
from neuroconv.tools.spikeinterface import (
    add_recording_to_nwbfile,
    add_sorting_analyzer_to_nwbfile,
    write_sorting_analyzer_to_nwbfile,
)

ndx_spikesorting = pytest.importorskip("ndx_spikesorting")


def _make_analyzer(durations=(4.0,)):
    from spikeinterface import create_sorting_analyzer

    recording, sorting = generate_ground_truth_recording(num_channels=4, num_units=4, durations=list(durations), seed=0)
    recording.annotate(is_filtered=True)
    for key in ("gt_unit_locations", "main_channel_id"):
        if key in sorting.get_property_keys():
            sorting.delete_property(key)
    analyzer = create_sorting_analyzer(sorting, recording, sparse=False)
    analyzer.compute(["random_spikes", "waveforms", "templates", "noise_levels", "template_metrics", "quality_metrics"])
    return analyzer


@pytest.fixture(scope="module")
def analyzer():
    return _make_analyzer()


def test_default_writes_the_extension_and_round_trips(analyzer, tmp_path):
    nwbfile_path = tmp_path / "analyzer.nwb"
    nwbfile = write_sorting_analyzer_to_nwbfile(
        sorting_analyzer=analyzer, nwbfile=mock_NWBFile(), nwbfile_path=nwbfile_path, write_electrical_series=True
    )

    container = nwbfile.processing["ecephys"]["spike_sorting"]
    assert container.source_electrical_series is not None
    assert container.units_region.table is nwbfile.units
    # The units table keeps spike times, templates and every metric, the ones the extension types (firing_rate,
    # num_spikes) as its typed columns; the extension also holds the run-dependent metrics.
    units_columns = set(nwbfile.units.colnames)
    assert {"spike_times", "waveform_mean", "waveform_sd", "peak_to_trough_duration", "isi_violations_ratio"} <= (
        units_columns
    )
    assert isinstance(nwbfile.units["firing_rate"], ndx_spikesorting.FiringRate)
    assert isinstance(nwbfile.units["num_spikes"], ndx_spikesorting.NumSpikes)
    unit_metrics = container.spike_sorting_extensions.units_metrics["unit_metrics"]
    assert {"isi_violations_ratio", "peak_to_trough_duration"} <= set(unit_metrics.colnames)
    np.testing.assert_allclose(
        np.asarray(unit_metrics["isi_violations_ratio"].data, dtype=float),
        np.asarray(nwbfile.units["isi_violations_ratio"].data, dtype=float),
        equal_nan=True,
    )

    # The ragged arrays of the extension get the default backend configuration like any other dataset.
    with h5py.File(nwbfile_path, "r") as file:
        assert file["processing/ecephys/spike_sorting/extensions/waveforms/data"].compression == "gzip"

    restored = ndx_spikesorting.read_sorting_analyzer_from_nwb(nwbfile_path)
    assert [str(u) for u in restored.unit_ids] == [str(u) for u in analyzer.unit_ids]
    np.testing.assert_array_almost_equal(
        restored.get_extension("templates").data["average"],
        analyzer.get_extension("templates").data["average"],
        decimal=5,
    )
    restored_metrics = restored.get_metrics_extension_data()
    original_metrics = analyzer.get_metrics_extension_data()
    for column in ("firing_rate", "isi_violations_ratio", "peak_to_trough_duration"):
        np.testing.assert_allclose(
            restored_metrics[column].to_numpy(float), original_metrics[column].to_numpy(float), equal_nan=True
        )


@pytest.mark.skipif(
    get_package_version("ndx-spikesorting") < Version("0.1.2"),
    reason="Reading a container without an ElectricalSeries needs ndx-spikesorting>=0.1.2",
)
def test_default_without_electrical_series_round_trips(analyzer, tmp_path):
    """The default call writes no ElectricalSeries, so the file reads back as a recordingless analyzer."""
    nwbfile_path = tmp_path / "analyzer.nwb"
    nwbfile = write_sorting_analyzer_to_nwbfile(
        sorting_analyzer=analyzer, nwbfile=mock_NWBFile(), nwbfile_path=nwbfile_path
    )
    assert len(nwbfile.acquisition) == 0
    assert nwbfile.processing["ecephys"]["spike_sorting"].source_electrical_series is None

    restored = ndx_spikesorting.read_sorting_analyzer_from_nwb(nwbfile_path)
    assert not restored.has_recording()
    assert [str(c) for c in restored.channel_ids] == [str(c) for c in analyzer.channel_ids]
    np.testing.assert_allclose(restored.get_channel_locations(), analyzer.get_channel_locations())
    np.testing.assert_array_almost_equal(
        restored.get_extension("templates").data["average"],
        analyzer.get_extension("templates").data["average"],
        decimal=5,
    )
    np.testing.assert_allclose(
        restored.get_metrics_extension_data()["isi_violations_ratio"].to_numpy(float),
        analyzer.get_metrics_extension_data()["isi_violations_ratio"].to_numpy(float),
        equal_nan=True,
    )


def test_unit_ids_subset(analyzer):
    nwbfile = mock_NWBFile()
    unit_ids = analyzer.unit_ids[[2, 0]]
    add_sorting_analyzer_to_nwbfile(sorting_analyzer=analyzer, nwbfile=nwbfile, unit_ids=unit_ids)

    container = nwbfile.processing["ecephys"]["spike_sorting"]
    assert len(nwbfile.units) == 2
    assert [nwbfile.units["unit_name"][row] for row in container.units_region.data] == list(unit_ids)


def test_units_table_in_processing(analyzer):
    nwbfile = mock_NWBFile()
    metadata = {"Ecephys": {"Sortings": {"my_sorting": {"name": "sorted_units"}}}}
    add_sorting_analyzer_to_nwbfile(
        sorting_analyzer=analyzer, nwbfile=nwbfile, metadata=metadata, metadata_key="my_sorting"
    )

    units_table = nwbfile.processing["ecephys"]["sorted_units"]
    container = nwbfile.processing["ecephys"]["spike_sorting_sorted_units"]
    assert container.units_region.table is units_table
    assert "firing_rate" in units_table.colnames


def test_multi_segment_falls_back_with_a_warning_or_raises():
    analyzer = _make_analyzer(durations=(3.0, 2.0))

    nwbfile = mock_NWBFile()
    with pytest.warns(UserWarning, match="only supports single-segment"):
        add_sorting_analyzer_to_nwbfile(sorting_analyzer=analyzer, nwbfile=nwbfile)
    assert "ecephys" not in nwbfile.processing
    assert "isi_violations_ratio" in nwbfile.units.colnames

    with pytest.raises(ValueError, match="use_ndx_spikesorting=True, but"):
        add_sorting_analyzer_to_nwbfile(sorting_analyzer=analyzer, nwbfile=mock_NWBFile(), use_ndx_spikesorting=True)


def test_several_electrical_series_need_a_name(analyzer):
    nwbfile = mock_NWBFile()
    add_recording_to_nwbfile(recording=analyzer.recording, nwbfile=nwbfile, iterator_type=None)
    (series_name,) = nwbfile.acquisition
    series = nwbfile.acquisition[series_name]
    nwbfile.add_acquisition(
        type(series)(name="OtherSeries", data=np.zeros((10, 4)), electrodes=series.electrodes, rate=series.rate)
    )

    with pytest.raises(ValueError, match="electrical_series_name"):
        add_sorting_analyzer_to_nwbfile(sorting_analyzer=analyzer, nwbfile=nwbfile, use_ndx_spikesorting=True)

    add_sorting_analyzer_to_nwbfile(sorting_analyzer=analyzer, nwbfile=nwbfile, electrical_series_name=series_name)
    assert nwbfile.processing["ecephys"]["spike_sorting"].source_electrical_series is series
