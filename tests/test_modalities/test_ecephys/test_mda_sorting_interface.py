import numpy as np
import pytest
from hdmf.common import DynamicTableRegion
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.converters import SortedRecordingConverter
from neuroconv.datainterfaces import MdaSortingInterface
from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface


def _build_firings_mda(tmp_path, peak_indices_1based):
    """Synthesize a tiny firings.mda with a known per-unit peak channel.

    Mirrors the reference pattern in SpikeInterface's own tests for
    MdaSortingExtractor: build a ground-truth sorting, attach a ``max_channel``
    property (the name SpikeInterface's writer expects), and serialize with
    ``write_primary_channels=True``. The ``MdaSortingInterface`` renames this
    on load to ``mda_peak_channel`` to avoid neuroconv's auto-coercion of
    ``max_channel`` columns into a DynamicTableRegion.
    """
    from spikeinterface.core import generate_ground_truth_recording
    from spikeinterface.extractors.extractor_classes import MdaSortingExtractor

    sampling_frequency = 30_000.0
    num_units = 5
    num_channels = 8

    _, sorting = generate_ground_truth_recording(
        durations=[5.0],
        num_units=num_units,
        num_channels=num_channels,
        sampling_frequency=sampling_frequency,
        seed=0,
    )
    sorting = sorting.rename_units(new_unit_ids=list(range(num_units)))
    sorting.set_property(key="max_channel", values=peak_indices_1based)

    firings_path = tmp_path / "firings.mda"
    MdaSortingExtractor.write_sorting(
        sorting=sorting,
        save_path=str(firings_path),
        write_primary_channels=True,
    )
    return {
        "file_path": firings_path,
        "sampling_frequency": sampling_frequency,
        "num_units": num_units,
        "num_channels": num_channels,
        "peak_indices_1based": peak_indices_1based,
        "source_sorting": sorting,
    }


@pytest.fixture
def firings_mda_file(tmp_path):
    return _build_firings_mda(tmp_path, peak_indices_1based=[1, 2, 3, 4, 5])


class TestMdaSortingInterface:

    def test_spike_trains_round_trip(self, firings_mda_file):
        interface = MdaSortingInterface(
            file_path=firings_mda_file["file_path"],
            sampling_frequency=firings_mda_file["sampling_frequency"],
        )
        sorting = interface.sorting_extractor
        source = firings_mda_file["source_sorting"]

        assert sorting.get_num_units() == firings_mda_file["num_units"]
        assert sorting.get_sampling_frequency() == firings_mda_file["sampling_frequency"]

        for unit_id in sorting.get_unit_ids():
            np.testing.assert_array_equal(
                sorting.get_unit_spike_train(unit_id=unit_id),
                source.get_unit_spike_train(unit_id=unit_id),
            )

    def test_max_channel_property_is_renamed(self, firings_mda_file):
        """The interface renames the extractor property to avoid auto-coercion."""
        interface = MdaSortingInterface(
            file_path=firings_mda_file["file_path"],
            sampling_frequency=firings_mda_file["sampling_frequency"],
        )
        property_keys = interface.sorting_extractor.get_property_keys()
        assert "max_channel" not in property_keys
        assert "mda_peak_channel" in property_keys

    def test_mda_peak_channel_column_with_description(self, firings_mda_file):
        interface = MdaSortingInterface(
            file_path=firings_mda_file["file_path"],
            sampling_frequency=firings_mda_file["sampling_frequency"],
        )
        metadata = interface.get_metadata()

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert "mda_peak_channel" in nwbfile.units.colnames
        expected_values = firings_mda_file["peak_indices_1based"]
        np.testing.assert_array_equal(nwbfile.units["mda_peak_channel"][:], expected_values)

        description = nwbfile.units["mda_peak_channel"].description
        assert "1-indexed" in description
        assert "not a channel ID" in description
        assert "NOT a row index into the NWB electrodes table" in description

    def test_no_column_when_row_zero_all_zeros(self, tmp_path):
        """If MountainSort wrote firings.mda without peak-channel tracking,
        row 0 is all zeros and the column is not added."""
        fixture = _build_firings_mda(tmp_path, peak_indices_1based=[0, 0, 0, 0, 0])
        interface = MdaSortingInterface(
            file_path=fixture["file_path"],
            sampling_frequency=fixture["sampling_frequency"],
        )

        assert "mda_peak_channel" not in interface.sorting_extractor.get_property_keys()
        assert interface._has_peak_channel is False

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
        assert "mda_peak_channel" not in (nwbfile.units.colnames if nwbfile.units is not None else [])

    def test_linkage_via_sorted_recording_converter(self, firings_mda_file):
        """mda_peak_channel can be lifted into a units.electrodes DynamicTableRegion."""
        sorting_interface = MdaSortingInterface(
            file_path=firings_mda_file["file_path"],
            sampling_frequency=firings_mda_file["sampling_frequency"],
        )
        recording_interface = MockRecordingInterface(
            num_channels=firings_mda_file["num_channels"],
            durations=(5.0,),
            sampling_frequency=firings_mda_file["sampling_frequency"],
        )

        recording_channel_ids = list(recording_interface.recording_extractor.get_channel_ids())
        unit_ids = sorting_interface.sorting_extractor.get_unit_ids()
        peak_indices = sorting_interface.sorting_extractor.get_property("mda_peak_channel")

        unit_ids_to_channel_ids = {
            unit_id: [recording_channel_ids[int(peak_index) - 1]] for unit_id, peak_index in zip(unit_ids, peak_indices)
        }

        converter = SortedRecordingConverter(
            recording_interface=recording_interface,
            sorting_interface=sorting_interface,
            unit_ids_to_channel_ids=unit_ids_to_channel_ids,
        )
        nwbfile = converter.create_nwbfile()

        assert isinstance(nwbfile.units.electrodes, DynamicTableRegion)
        assert nwbfile.units.electrodes.table is nwbfile.electrodes

        expected_electrode_rows = [int(peak_index) - 1 for peak_index in peak_indices]
        actual_electrode_rows = list(nwbfile.units.electrodes.data[:])
        assert actual_electrode_rows == expected_electrode_rows
