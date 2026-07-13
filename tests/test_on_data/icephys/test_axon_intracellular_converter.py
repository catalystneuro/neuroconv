"""Tests for :class:`~neuroconv.datainterfaces.icephys.axon.axonintracellularconverter.AxonIntracellularConverter`.

The converter is the piece that builds the NWB icephys *hierarchy*. Each ``AxonIntracellularInterface`` writes
only the per-sweep rows of the intracellular-recordings table (one channel, one file), tagging each row with the
run-level grouping columns (``sequence``, ``stimulus_type``, and the optional ``repetition`` / ``condition``). The
converter reads those rows back and aggregates them: rows sharing a timing range within a run become one
``SimultaneousRecordings`` entry, rows sharing a ``sequence`` become one ``SequentialRecordings`` entry,
``repetition`` groups sequentials into ``Repetitions``, and ``condition`` groups repetitions into
``ExperimentalConditions``. When the interfaces come from several files, the converter also places them on one
timeline from each file's header start time (``rec_datetime``).

Each class below is one user-facing scenario and checks only the ``add_to_nwbfile`` result (the in-memory NWBFile
from ``create_nwbfile``). Most scenarios are a single test; the repetition / condition grouping is one class with a
method per branch, since those share the same fixture and differ only in the labels the user passes.

Fixtures live in the gin ``ephy_testing_data`` repo under ``axon/intracellular_data`` (the same purpose-built set
the interface tests use). The ``read_raw_protocol`` files are several runs recorded back-to-back on one rig
(ascending header start times, all ABF v2, recorded on ``IN0``), which is what the multi-file alignment and the
repetition / condition tests need; ``dual_patch_pairs/current_clamp.abf`` is a genuine dual patch (``IN0`` current
clamp, ``IN1`` voltage clamp).
"""

from neuroconv.converters import AxonIntracellularConverter
from neuroconv.datainterfaces import AxonIntracellularInterface

from ..setup_paths import ECEPHY_DATA_PATH

ICEPHYS_DATA_PATH = ECEPHY_DATA_PATH / "axon" / "intracellular_data"


class TestAxonConverterSingleCell:
    """The simplest use case: one cell recorded on one channel in a single ABF file, converted through the converter
    rather than the bare interface. Even with a single interface the converter builds the full icephys hierarchy, so
    the user gets one ``SimultaneousRecordings`` entry per sweep and one ``SequentialRecordings`` run instead of a
    loose pile of series. Also confirms the stimulus type read from the ABF protocol reaches the sequential table."""

    # One protocol-driven run: IN0 recorded in pA (voltage clamp) with a reconstructed Cmd 0 stimulus, 3 sweeps.
    file_path = ICEPHYS_DATA_PATH / "read_raw_protocol" / "user_list.abf"

    def test_add_to_nwbfile(self):
        interface = AxonIntracellularInterface(
            file_path=self.file_path, response_channel_name="IN0", mode="voltage_clamp", stimulus_command="Cmd 0"
        )
        nwbfile = AxonIntracellularConverter(data_interfaces=[interface]).create_nwbfile()

        n_sweeps = len(nwbfile.intracellular_recordings)
        assert n_sweeps > 1
        # One electrode: one simultaneous recording per sweep, one sequential run with a real stimulus type.
        assert len(nwbfile.icephys_simultaneous_recordings) == n_sweeps
        assert len(nwbfile.icephys_sequential_recordings) == 1
        stimulus_type = nwbfile.icephys_sequential_recordings["stimulus_type"][0]
        assert stimulus_type and stimulus_type != "not described"


class TestAxonConverterDualPatch:
    """A dual patch-clamp recording: two electrodes acquired together in one ABF file. The user passes one interface
    per channel (here IN0 in current clamp, IN1 in voltage clamp), and the converter recognizes that both electrodes
    are sampled on the same sweeps, grouping the two per-sweep rows into a single ``SimultaneousRecordings`` entry and
    keeping them one run. Because both channels come from one file, they share the one amplifier device."""

    # Genuine dual patch: IN0 (current clamp) and IN1 (voltage clamp) recorded together.
    file_path = ICEPHYS_DATA_PATH / "dual_patch_pairs" / "current_clamp.abf"

    def test_add_to_nwbfile(self):
        interfaces = [
            AxonIntracellularInterface(file_path=self.file_path, response_channel_name="IN0", mode="current_clamp"),
            AxonIntracellularInterface(file_path=self.file_path, response_channel_name="IN1", mode="voltage_clamp"),
        ]
        nwbfile = AxonIntracellularConverter(data_interfaces=interfaces).create_nwbfile()

        intracellular_recordings = nwbfile.intracellular_recordings
        simultaneous = nwbfile.icephys_simultaneous_recordings
        n_sweeps = len(simultaneous)
        assert n_sweeps > 1
        # Two electrodes recorded over the same sweeps: two rows per sweep, both in each simultaneous recording.
        assert len(intracellular_recordings) == 2 * n_sweeps
        assert all(len(simultaneous["recordings"][i]) == 2 for i in range(n_sweeps))
        # The two electrodes share one run, so a single sequential recording spans all sweeps.
        assert len(nwbfile.icephys_sequential_recordings) == 1
        assert len(nwbfile.icephys_electrodes) == 2
        # Both electrodes are on the same file, so they share one amplifier device (device dedup is by name).
        assert len(nwbfile.devices) == 1


class TestAxonConverterMultiFile:
    """One cell recorded across several protocol files back-to-back (the common Clampex pattern of one file per run),
    combined into a single NWB file. The user hands the converter one interface per file; each becomes its own
    ``SequentialRecordings`` run, and the converter reconstructs the real relative timing by placing every file on one
    timeline from its header start time, with the earliest file as the session origin. Files recorded on the same
    amplifier still share one device."""

    # Several runs recorded back-to-back (ascending header start times, all ABF v2): distinct protocols on the same
    # IN0 channel. Exercises multi-file alignment and the repetition / condition levels.
    run_files = [
        ICEPHYS_DATA_PATH / "read_raw_protocol" / "step.abf",
        ICEPHYS_DATA_PATH / "read_raw_protocol" / "ramp.abf",
        ICEPHYS_DATA_PATH / "read_raw_protocol" / "pulse_train.abf",
        ICEPHYS_DATA_PATH / "read_raw_protocol" / "biphasic_train.abf",
    ]

    def test_add_to_nwbfile(self):
        interfaces = [
            AxonIntracellularInterface(file_path=path, response_channel_name="IN0", mode="current_clamp")
            for path in self.run_files
        ]
        nwbfile = AxonIntracellularConverter(data_interfaces=interfaces).create_nwbfile()

        # One run per file: each distinct file is its own sequence, hence its own sequential recording.
        assert len(nwbfile.icephys_sequential_recordings) == len(self.run_files)
        # All runs are the same amplifier model, so the files share one device even across files (dedup by name).
        assert len(nwbfile.devices) == 1

        start_datetimes = [interface._recording_start_datetime for interface in interfaces]
        earliest = min(start_datetimes)
        # The session origin is the earliest file's header start time.
        assert abs((nwbfile.session_start_time.replace(tzinfo=None) - earliest).total_seconds()) < 1.0
        # The runs sit on one timeline: each series is offset by its file's header time relative to the earliest.
        series_starts = []
        for series in nwbfile.acquisition.values():
            t0 = series.timestamps[0] if series.timestamps is not None else series.starting_time
            series_starts.append(float(t0))
        expected_offsets = sorted((dt - earliest).total_seconds() for dt in start_datetimes)
        normalized_starts = sorted(start - min(series_starts) for start in series_starts)
        assert all(abs(observed - expected) < 1.0 for observed, expected in zip(normalized_starts, expected_offsets))


class TestAxonConverterDisambiguatesCollidingFilenames:
    """The realistic multi-file case where Clampex has named each cell's file per folder, so combining cells from
    different folders hands the converter several files that all share the filename ``0000.abf``. The converter
    disambiguates each run by its parent folder (``cellA_0000``, ``cellB_0000``) so the cells stay distinct runs with
    non-colliding series names. Without this the two cells would either be silently merged into one run or crash on a
    duplicate object name; the user does nothing beyond passing the paths."""

    # Two genuinely different protocol runs, staged below under a shared stem to force the collision.
    source_files = [
        ICEPHYS_DATA_PATH / "read_raw_protocol" / "step.abf",
        ICEPHYS_DATA_PATH / "read_raw_protocol" / "ramp.abf",
    ]

    def test_add_to_nwbfile(self, tmp_path):
        # Stage two genuinely different files under a shared stem "0000" in different folders (symlinks, no copy).
        cell_a = tmp_path / "cellA" / "0000.abf"
        cell_b = tmp_path / "cellB" / "0000.abf"
        cell_a.parent.mkdir()
        cell_b.parent.mkdir()
        cell_a.symlink_to(self.source_files[0])
        cell_b.symlink_to(self.source_files[1])

        interfaces = [
            AxonIntracellularInterface(file_path=cell_a, response_channel_name="IN0", mode="current_clamp"),
            AxonIntracellularInterface(file_path=cell_b, response_channel_name="IN0", mode="current_clamp"),
        ]
        nwbfile = AxonIntracellularConverter(data_interfaces=interfaces).create_nwbfile()

        # The shared stem "0000" is disambiguated by the parent folder, so the two cells carry distinct `sequence`s
        # (not one merged run identity).
        intracellular_recordings = nwbfile.intracellular_recordings
        sequences = {intracellular_recordings["sequence"][i] for i in range(len(intracellular_recordings))}
        assert sequences == {"cellA_0000", "cellB_0000"}
        # Two distinct response series (no duplicate-name collision) and two separate runs (not folded into one
        # SimultaneousRecordings as if they were a dual patch).
        assert len(nwbfile.acquisition) == 2
        assert len(nwbfile.icephys_sequential_recordings) == 2


class TestAxonConverterRepetitionsAndConditions:
    """Aggregation of the ``repetition`` / ``condition`` grouping labels into the ``Repetitions`` and
    ``ExperimentalConditions`` tables. Every method drives the same four back-to-back runs (one cell, one channel),
    varying only the labels to exercise one branch of the aggregator each: the conditions table is omitted when no
    condition is given, a missing ``repetition`` defaults to identity repetitions, repetitions are keyed by
    ``(condition, label)`` so a label reused across conditions stays distinct, and a label shared within one
    condition groups its runs into a single repetition."""

    # The four back-to-back protocol runs (one cell, ascending ABF v2 start times).
    run_files = [
        ICEPHYS_DATA_PATH / "read_raw_protocol" / "step.abf",
        ICEPHYS_DATA_PATH / "read_raw_protocol" / "ramp.abf",
        ICEPHYS_DATA_PATH / "read_raw_protocol" / "pulse_train.abf",
        ICEPHYS_DATA_PATH / "read_raw_protocol" / "biphasic_train.abf",
    ]

    def test_repetitions_without_conditions(self):
        """Use case: a protocol repeated several times, the user tagging runs by ``repetition`` but giving no
        ``condition``. Runs sharing a repetition label are grouped into one ``Repetitions`` entry, so two ``r1`` runs
        and two ``r2`` runs yield two repetitions of two sequentials each. With no condition given, the converter
        stops there and does not build an ``ExperimentalConditions`` table."""
        interfaces = [
            AxonIntracellularInterface(
                file_path=path, response_channel_name="IN0", mode="current_clamp", repetition=repetition
            )
            for path, repetition in zip(self.run_files, ["r1", "r1", "r2", "r2"])
        ]
        nwbfile = AxonIntracellularConverter(data_interfaces=interfaces).create_nwbfile()

        assert len(nwbfile.icephys_sequential_recordings) == 4
        # Two repetitions, each grouping two of the four sequential recordings.
        repetitions = nwbfile.icephys_repetitions
        assert len(repetitions) == 2
        assert all(len(repetitions["sequential_recordings"][i]) == 2 for i in range(2))
        # No condition column -> the experimental-conditions table is not built.
        assert nwbfile.icephys_experimental_conditions is None

    def test_conditions_without_repetition(self):
        """Use case: the user groups runs by experimental ``condition`` (for example drug versus control) but never
        labels repetitions. Because the conditions table sits above the repetitions rung, the converter fills that
        rung with identity repetitions, one per run, then groups those by condition. Four runs under conditions
        A, A, B, B thus give four single-run repetitions collected into two conditions."""
        interfaces = [
            AxonIntracellularInterface(
                file_path=path, response_channel_name="IN0", mode="current_clamp", condition=condition
            )
            for path, condition in zip(self.run_files, ["A", "A", "B", "B"])
        ]
        nwbfile = AxonIntracellularConverter(data_interfaces=interfaces).create_nwbfile()

        # Identity repetitions: one per run, each holding a single sequential recording.
        repetitions = nwbfile.icephys_repetitions
        assert len(repetitions) == len(self.run_files)
        assert all(len(repetitions["sequential_recordings"][i]) == 1 for i in range(len(self.run_files)))
        # Conditions group those identity repetitions: two conditions of two repetitions each.
        conditions = nwbfile.icephys_experimental_conditions
        assert len(conditions) == 2
        assert all(len(conditions["repetitions"][i]) == 2 for i in range(2))

    def test_repetition_label_reused_across_conditions(self):
        """Use case: the user reuses the same repetition names (``r1``, ``r2``) under each condition, the natural way
        to label "first repeat of A, first repeat of B". The converter keys repetitions by ``(condition, label)``, so
        ``r1`` under condition A and ``r1`` under condition B stay two separate repetitions rather than collapsing into
        one. Four runs therefore produce four distinct repetitions across the two conditions."""
        # "r1" and "r2" each appear under both condition "A" and condition "B".
        interfaces = [
            AxonIntracellularInterface(
                file_path=path,
                response_channel_name="IN0",
                mode="current_clamp",
                repetition=repetition,
                condition=condition,
            )
            for path, repetition, condition in zip(self.run_files, ["r1", "r2", "r1", "r2"], ["A", "A", "B", "B"])
        ]
        nwbfile = AxonIntracellularConverter(data_interfaces=interfaces).create_nwbfile()

        # Keyed by (condition, label) -> four distinct repetitions (A,r1), (A,r2), (B,r1), (B,r2); keyed by label
        # alone it would wrongly collapse to two. Each condition holds two of them.
        assert len(nwbfile.icephys_repetitions) == 4
        conditions = nwbfile.icephys_experimental_conditions
        assert len(conditions) == 2
        assert all(len(conditions["repetitions"][i]) == 2 for i in range(2))

    def test_repetition_groups_runs_within_condition(self):
        """Use case: within a single condition the user records the same protocol twice and gives both runs the same
        repetition label, meaning "these two runs are one repeat". The converter groups the two runs sharing a
        ``(condition, label)`` into one ``Repetitions`` entry holding both sequential recordings. The two conditions
        then each hold their one repetition."""
        # Runs 0,1 are condition "A" repetition "r1"; runs 2,3 are condition "B" repetition "r2".
        interfaces = [
            AxonIntracellularInterface(
                file_path=path,
                response_channel_name="IN0",
                mode="current_clamp",
                repetition=repetition,
                condition=condition,
            )
            for path, repetition, condition in zip(self.run_files, ["r1", "r1", "r2", "r2"], ["A", "A", "B", "B"])
        ]
        nwbfile = AxonIntracellularConverter(data_interfaces=interfaces).create_nwbfile()

        # Two repetitions, each grouping the two sequential recordings that share its (condition, label).
        repetitions = nwbfile.icephys_repetitions
        assert len(repetitions) == 2
        assert all(len(repetitions["sequential_recordings"][i]) == 2 for i in range(2))
        # Two conditions, each holding one repetition.
        conditions = nwbfile.icephys_experimental_conditions
        assert len(conditions) == 2
        assert all(len(conditions["repetitions"][i]) == 1 for i in range(2))


class TestAxonConverterSharedElectrodeAcrossFiles:
    """Use case: several runs of one cell were saved as separate files, so each defaults to its own electrode, but the
    user knows they are the same physical pipette and wants them recorded against a single electrode. Editing the
    metadata to point every response series at one electrode entry collapses them onto that shared electrode and its
    device. Merging the electrodes does not merge the runs: each file remains its own sequential recording, so
    electrode identity and run structure stay independent."""

    # The four back-to-back protocol runs (one cell, ascending ABF v2 start times).
    run_files = [
        ICEPHYS_DATA_PATH / "read_raw_protocol" / "step.abf",
        ICEPHYS_DATA_PATH / "read_raw_protocol" / "ramp.abf",
        ICEPHYS_DATA_PATH / "read_raw_protocol" / "pulse_train.abf",
        ICEPHYS_DATA_PATH / "read_raw_protocol" / "biphasic_train.abf",
    ]

    def test_merge_electrodes_via_edited_links(self):
        interfaces = [
            AxonIntracellularInterface(file_path=path, response_channel_name="IN0", mode="current_clamp")
            for path in self.run_files
        ]
        converter = AxonIntracellularConverter(data_interfaces=interfaces)
        metadata = converter.get_metadata()

        # Default: one electrode entry per file.
        assert len(metadata["Icephys"]["IntracellularElectrodes"]) == len(self.run_files)

        # Collapse to a single shared electrode and point every series at it.
        shared_key = "SharedCell"
        first_electrode = next(iter(metadata["Icephys"]["IntracellularElectrodes"].values()))
        metadata["Icephys"]["IntracellularElectrodes"] = {
            shared_key: {**first_electrode, "name": "IntracellularElectrodeSharedCell"}
        }
        for series_entry in metadata["Icephys"]["PatchClampSeries"].values():
            series_entry["electrode_metadata_key"] = shared_key

        nwbfile = converter.create_nwbfile(metadata=metadata)

        # The link edit took effect: the four per-file electrodes collapsed onto the one shared electrode. (That
        # sharing itself is a metadata-linking behavior owned by the interface's TestAxonIntracellularMetadata; here
        # it is only the premise for the converter-specific invariant below.)
        assert len(nwbfile.icephys_electrodes) == 1
        # The invariant this test owns: merging electrodes does not merge runs. Run grouping follows the `sequence`
        # column, not electrode identity, so each file is still its own sequential recording.
        assert len(nwbfile.icephys_sequential_recordings) == len(self.run_files)
