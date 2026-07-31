"""Data-free tests of the shared icephys tools, driven by ``MockIcephysInterface``.

These cover the format-independent machinery in ``neuroconv.tools.icephys``: the sweep ``TimeIntervals``
table and the hierarchy builder, both of which read back the per-sweep ``(start_index, count)`` rows any
icephys interface writes. No acquisition file is read. Format behaviour lives in the per-interface tests
on real data.
"""

import pytest
from pynwb import NWBHDF5IO, NWBFile
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv import ConverterPipe
from neuroconv.tools.icephys import (
    _add_sweep_time_intervals_to_nwbfile,
    _build_icephys_hierarchical_tables,
)
from neuroconv.tools.testing.mock_interfaces import MockIcephysInterface

SAMPLING_FREQUENCY = 10_000.0
SWEEP_DURATION = 1.0
# A sweep stops at the time of its last sample, which is one sample period short of its full duration.
LAST_SAMPLE_OFFSET = SWEEP_DURATION - 1 / SAMPLING_FREQUENCY


def create_finalized_nwbfile(interfaces: list, metadata: dict | None = None) -> NWBFile:
    """Run several interfaces into one file and build the hierarchy, as an icephys converter does at the end."""
    converter = ConverterPipe(data_interfaces=interfaces)
    nwbfile = converter.create_nwbfile(metadata=metadata)
    _build_icephys_hierarchical_tables(nwbfile)
    return nwbfile


def create_runs(repetitions: list | None = None, conditions: list | None = None, num_runs: int = 4) -> list:
    """One mock interface per run, each its own sequence and electrode, optionally labelled for grouping."""
    repetitions = repetitions or [None] * num_runs
    conditions = conditions or [None] * num_runs
    return [
        MockIcephysInterface(
            num_sweeps=2,
            starting_time=float(index * 10),
            sequence=f"run_{index}",
            repetition=repetition,
            condition=condition,
            metadata_key=f"run_{index}",
        )
        for index, (repetition, condition) in enumerate(zip(repetitions, conditions))
    ]


class TestSweepTimeIntervals:
    """The ``sweeps`` table: one row per distinct sweep interval, in time order, on either timing basis."""

    def test_series_written_with_a_rate(self):
        """Contiguous sweeps leave the samples regular, so the series carries a rate and no timestamps."""
        interface = MockIcephysInterface(
            num_sweeps=3, sweep_duration=SWEEP_DURATION, sampling_frequency=SAMPLING_FREQUENCY
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        _add_sweep_time_intervals_to_nwbfile(nwbfile)

        sweeps = nwbfile.intervals["sweeps"]
        assert len(sweeps) == 3
        expected_starts = [0.0, 1.0, 2.0]
        assert list(sweeps.start_time[:]) == pytest.approx(expected_starts)
        assert list(sweeps.stop_time[:]) == pytest.approx([start + LAST_SAMPLE_OFFSET for start in expected_starts])

    def test_series_written_with_timestamps(self):
        """Inter-sweep gaps make the samples irregular, so the series carries explicit timestamps and no rate."""
        interface = MockIcephysInterface(
            num_sweeps=3,
            sweep_duration=SWEEP_DURATION,
            sampling_frequency=SAMPLING_FREQUENCY,
            inter_sweep_interval=0.5,
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        _add_sweep_time_intervals_to_nwbfile(nwbfile)

        # The gap shows up between the sweeps, which each still span their own duration, and not inside them.
        sweeps = nwbfile.intervals["sweeps"]
        expected_starts = [0.0, 1.5, 3.0]
        assert list(sweeps.start_time[:]) == pytest.approx(expected_starts)
        assert list(sweeps.stop_time[:]) == pytest.approx([start + LAST_SAMPLE_OFFSET for start in expected_starts])

    def test_simultaneous_channels_are_one_row_each(self):
        """Two electrodes recorded together describe one sweep per range, not one per recordings row."""
        # Mirrors the real dual-patch fixture: one channel in current clamp, the other in voltage clamp.
        first_channel = MockIcephysInterface(num_sweeps=3, mode="current_clamp", metadata_key="a")
        second_channel = MockIcephysInterface(num_sweeps=3, mode="voltage_clamp", metadata_key="b")
        nwbfile = mock_NWBFile()
        first_channel.add_to_nwbfile(nwbfile=nwbfile)
        second_channel.add_to_nwbfile(nwbfile=nwbfile)

        _add_sweep_time_intervals_to_nwbfile(nwbfile)

        assert len(nwbfile.intracellular_recordings) == 6
        sweeps = nwbfile.intervals["sweeps"]
        assert len(sweeps) == 3
        assert list(sweeps.start_time[:]) == pytest.approx([0.0, 1.0, 2.0])

    def test_rows_are_sorted_and_keep_their_run(self):
        """Runs are written in interface order, so the intervals have to be sorted by time and labelled by run."""
        later_run = MockIcephysInterface(num_sweeps=2, starting_time=10.0, sequence="run_b", metadata_key="b")
        earlier_run = MockIcephysInterface(num_sweeps=2, starting_time=0.0, sequence="run_a", metadata_key="a")
        nwbfile = mock_NWBFile()
        # The later run is added first, so a table built in row order would come out unsorted.
        later_run.add_to_nwbfile(nwbfile=nwbfile)
        earlier_run.add_to_nwbfile(nwbfile=nwbfile)

        _add_sweep_time_intervals_to_nwbfile(nwbfile)

        sweeps = nwbfile.intervals["sweeps"]
        assert list(sweeps.start_time[:]) == pytest.approx([0.0, 1.0, 10.0, 11.0])
        assert list(sweeps.sequence[:]) == ["run_a", "run_a", "run_b", "run_b"]

    def test_round_trip(self, tmp_path):
        interface = MockIcephysInterface(num_sweeps=3)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        _add_sweep_time_intervals_to_nwbfile(nwbfile)

        nwbfile_path = tmp_path / "test_sweep_intervals.nwb"
        with NWBHDF5IO(path=nwbfile_path, mode="w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            read_nwbfile = io.read()
            sweeps = read_nwbfile.intervals["sweeps"]
            expected_starts = [0.0, 1.0, 2.0]
            assert list(sweeps.start_time[:]) == pytest.approx(expected_starts)
            assert list(sweeps.stop_time[:]) == pytest.approx([start + LAST_SAMPLE_OFFSET for start in expected_starts])
            assert list(sweeps.sequence[:]) == ["run", "run", "run"]

    def test_no_table_without_recordings(self):
        """A file with no intracellular recordings gets no table rather than an empty one."""
        nwbfile = mock_NWBFile()

        _add_sweep_time_intervals_to_nwbfile(nwbfile)

        assert nwbfile.intervals is None or "sweeps" not in nwbfile.intervals


class TestMockIcephysInterface:
    """The mock's own contract, since the tools above are only as faithful as what it writes."""

    @pytest.mark.parametrize(
        "mode, expected_series_name",
        [
            ("current_clamp", "CurrentClampSeriesMock"),
            ("voltage_clamp", "VoltageClampSeriesMock"),
            ("izero", "IZeroClampSeriesMock"),
        ],
    )
    def test_clamp_mode_selects_the_series_class(self, mode, expected_series_name):
        interface = MockIcephysInterface(mode=mode, num_sweeps=1)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        response_series = nwbfile.acquisition[expected_series_name]
        assert type(response_series).__name__ == expected_series_name.removesuffix("Mock")
        assert len(nwbfile.intracellular_recordings) == 1


class TestGroupingLevels:
    """Aggregation of the ``repetition`` / ``condition`` labels into the ``Repetitions`` and
    ``ExperimentalConditions`` tables. Every method drives the same four runs, varying only the labels to exercise
    one branch of the aggregator each. Migrated off the Axon converter's gin tests, which used real files only as
    a carrier for these format-independent branches."""

    def test_repetitions_without_conditions(self):
        """A protocol repeated several times, tagged by ``repetition`` with no ``condition``: runs sharing a label
        become one ``Repetitions`` entry, and the aggregator stops below the conditions table."""
        nwbfile = create_finalized_nwbfile(create_runs(repetitions=["r1", "r1", "r2", "r2"]))

        assert len(nwbfile.icephys_sequential_recordings) == 4
        # Two repetitions, each grouping two of the four sequential recordings.
        repetitions = nwbfile.icephys_repetitions
        assert len(repetitions) == 2
        assert all(len(repetitions["sequential_recordings"][index]) == 2 for index in range(2))
        # No condition column -> the experimental-conditions table is not built.
        assert nwbfile.icephys_experimental_conditions is None

    def test_conditions_without_repetition(self):
        """Runs grouped by ``condition`` alone: the conditions table sits above the repetitions rung, so the
        aggregator fills that rung with identity repetitions, one per run, then groups those by condition."""
        nwbfile = create_finalized_nwbfile(create_runs(conditions=["A", "A", "B", "B"]))

        repetitions = nwbfile.icephys_repetitions
        assert len(repetitions) == 4
        assert all(len(repetitions["sequential_recordings"][index]) == 1 for index in range(4))
        conditions = nwbfile.icephys_experimental_conditions
        assert len(conditions) == 2
        assert all(len(conditions["repetitions"][index]) == 2 for index in range(2))

    def test_repetition_label_reused_across_conditions(self):
        """The natural labelling of "first repeat of A, first repeat of B" reuses the same repetition names, so
        repetitions are keyed by ``(condition, label)`` and stay distinct instead of collapsing into two."""
        nwbfile = create_finalized_nwbfile(
            create_runs(repetitions=["r1", "r2", "r1", "r2"], conditions=["A", "A", "B", "B"])
        )

        assert len(nwbfile.icephys_repetitions) == 4
        conditions = nwbfile.icephys_experimental_conditions
        assert len(conditions) == 2
        assert all(len(conditions["repetitions"][index]) == 2 for index in range(2))

    def test_repetition_groups_runs_within_condition(self):
        """Two runs of one condition sharing a repetition label mean "these two runs are one repeat", so they land
        in a single ``Repetitions`` entry holding both sequential recordings."""
        nwbfile = create_finalized_nwbfile(
            create_runs(repetitions=["r1", "r1", "r2", "r2"], conditions=["A", "A", "B", "B"])
        )

        repetitions = nwbfile.icephys_repetitions
        assert len(repetitions) == 2
        assert all(len(repetitions["sequential_recordings"][index]) == 2 for index in range(2))
        # Two conditions, each holding one repetition.
        conditions = nwbfile.icephys_experimental_conditions
        assert len(conditions) == 2
        assert all(len(conditions["repetitions"][index]) == 1 for index in range(2))


class TestElectrodeSharingThroughMetadata:
    """Several runs of one cell each default to their own electrode, but the user knows they are the same physical
    pipette. Editing the metadata links collapses them onto one electrode without merging the runs. Migrated off
    the Axon converter's gin tests for the same reason as the class above."""

    def test_merge_electrodes_via_edited_links(self):
        interfaces = create_runs()
        converter = ConverterPipe(data_interfaces=interfaces)
        metadata = converter.get_metadata()

        # Default: one electrode entry per run.
        assert len(metadata["Icephys"]["IntracellularElectrodes"]) == len(interfaces)

        # Collapse to a single shared electrode and point every series at it.
        shared_key = "shared_cell"
        first_electrode = next(iter(metadata["Icephys"]["IntracellularElectrodes"].values()))
        metadata["Icephys"]["IntracellularElectrodes"] = {
            shared_key: {**first_electrode, "name": "IntracellularElectrodeSharedCell"}
        }
        for series_entry in metadata["Icephys"]["PatchClampSeries"].values():
            series_entry["electrode_metadata_key"] = shared_key

        nwbfile = create_finalized_nwbfile(interfaces, metadata=metadata)

        # The link edit took effect: the per-run electrodes collapsed onto the one shared electrode.
        assert len(nwbfile.icephys_electrodes) == 1
        # The invariant this test owns: merging electrodes does not merge runs. Run grouping follows the `sequence`
        # column, not electrode identity, so each run is still its own sequential recording.
        assert len(nwbfile.icephys_sequential_recordings) == len(interfaces)
