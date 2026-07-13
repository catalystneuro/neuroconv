"""Tests for :class:`~neuroconv.datainterfaces.icephys.axon.axonintracellularconverter.AxonIntracellularConverter`.

The converter is the piece that builds the NWB icephys *hierarchy*. Each ``AxonIntracellularInterface`` writes
only the per-sweep rows of the intracellular-recordings table (one channel, one file), tagging each row with the
run-level grouping columns (``sequence``, ``stimulus_type``, and the optional ``repetition`` / ``condition``). The
converter reads those rows back and aggregates them: rows sharing a timing range within a run become one
``SimultaneousRecordings`` entry, rows sharing a ``sequence`` become one ``SequentialRecordings`` entry,
``repetition`` groups sequentials into ``Repetitions``, and ``condition`` groups repetitions into
``ExperimentalConditions``. When the interfaces come from several files, the converter also places them on one
timeline from each file's header start time (``rec_datetime``).

Each class below is one dataset / configuration and checks only the ``add_to_nwbfile`` result (the in-memory
NWBFile from ``create_nwbfile``), mirroring the one-class-per-scenario shape of the interface tests.

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
    """One interface: the single-cell path that adds the simultaneous / sequential chain."""

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
    """Two electrodes from one dual-patch file: each sweep groups both electrodes into one simultaneous recording."""

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
    """Several files from one cell: each run is its own sequential recording, placed on a shared timeline."""

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


class TestAxonConverterSameStemFiles:
    """Two different recordings that share the Clampex filename ``0000.abf`` (one per cell folder) get distinct,
    disambiguated run identities, distinct ``sequence`` and series names and two separate runs, never the silent
    cross-cell merge or the duplicate-name error that the bare-stem identity would have produced."""

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
        """Repetition labels group the runs' sequential recordings; with no condition, no conditions table."""
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
        """`condition` with no `repetition` defaults each run to its own repetition (identity), then groups them."""
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
        """A repetition label reused in two conditions stays distinct: repetitions are keyed by ``(condition, label)``,
        not by label alone."""
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
        """A repetition label shared by two runs within a condition groups them into one repetition; conditions then
        group those repetitions."""
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
    """Cross-referencing: the editable electrode links can merge several runs of one cell onto one electrode.

    By default each file is its own electrode (distinct, file-derived keys). Repointing every response series at
    a single electrode entry collapses them, exercising the electrode-reuse branch of ``_get_or_create_electrode``
    (an electrode found by name and shared, rather than created once per interface).
    """

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

        # All four runs now share one electrode (and its single amplifier device); every response references it.
        assert len(nwbfile.icephys_electrodes) == 1
        assert len(nwbfile.devices) == 1
        electrode = next(iter(nwbfile.icephys_electrodes.values()))
        assert all(series.electrode is electrode for series in nwbfile.acquisition.values())
        # Merging electrodes does not merge runs: each file is still its own sequential recording.
        assert len(nwbfile.icephys_sequential_recordings) == len(self.run_files)


class TestAxonConverterDistinctDevicesViaLink:
    """Cross-referencing: pointing two electrodes at differently-named device entries yields two devices.

    Devices dedup by ``name``, so the dual-patch file (one amplifier) normally writes one device. Adding a second,
    differently-named device entry and repointing one electrode at it splits them, confirming device identity
    follows the device ``name`` link rather than the metadata key.
    """

    # Genuine dual patch: IN0 (current clamp) and IN1 (voltage clamp) recorded together on one amplifier.
    file_path = ICEPHYS_DATA_PATH / "dual_patch_pairs" / "current_clamp.abf"

    def test_distinct_devices(self):
        interfaces = [
            AxonIntracellularInterface(file_path=self.file_path, response_channel_name="IN0", mode="current_clamp"),
            AxonIntracellularInterface(file_path=self.file_path, response_channel_name="IN1", mode="voltage_clamp"),
        ]
        converter = AxonIntracellularConverter(data_interfaces=interfaces)
        metadata = converter.get_metadata()

        # Both electrodes start on the one shared device (same file).
        assert len(metadata["Devices"]) == 1

        # Add a second, differently-named device and repoint the second electrode at it.
        electrode_keys = list(metadata["Icephys"]["IntracellularElectrodes"])
        metadata["Devices"]["SecondAmplifier"] = {"name": "Second amplifier"}
        metadata["Icephys"]["IntracellularElectrodes"][electrode_keys[1]]["device_metadata_key"] = "SecondAmplifier"

        nwbfile = converter.create_nwbfile(metadata=metadata)

        # Two distinct device names -> two devices, and the second amplifier is present.
        assert len(nwbfile.devices) == 2
        assert "Second amplifier" in {device.name for device in nwbfile.devices.values()}
