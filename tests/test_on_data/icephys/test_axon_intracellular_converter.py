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

TODO: like the interface tests, this points at full example files under ``~/data``; stub them onto the gin
``ephy_testing_data`` repo and switch to ``ECEPHY_DATA_PATH`` before merging.
"""

import glob
from pathlib import Path

import pytest

from neuroconv.converters import AxonIntracellularConverter
from neuroconv.datainterfaces import AxonIntracellularInterface

# TODO: replace these full files with stubbed gin fixtures under ECEPHY_DATA_PATH (see module docstring).
DATA_ROOT = Path.home() / "data"
_khaliq = glob.glob(str(DATA_ROOT / "khaliq_data" / "**" / "21610017.abf"), recursive=True)
SINGLE_CELL_FILE = Path(_khaliq[0]) if _khaliq else DATA_ROOT / "missing.abf"
# Genuine dual patch: IN0 recorded in mV (current clamp), IN1 in pA (voltage clamp), 20 sweeps.
DUAL_PATCH_FILE = DATA_ROOT / "axon" / "pyabf_samples" / "abfs" / "2018_05_08_0028-IC-VC-pair.abf"

# Several runs of one cell (Khaliq C39), recorded back-to-back: distinct protocols, ascending header start times,
# all ABF v2. Exercises multi-file alignment and the repetition / condition levels.
_C39 = (
    DATA_ROOT / "khaliq_data" / "Electrophysiology recordings" / "Cells without AIS component" / "29 Sep 2021" / "C39"
)
MULTI_FILE_RUNS = [
    _C39 / "SF" / "2021_09_29_0024.abf",
    _C39 / "CS" / "2021_09_29_0025.abf",
    _C39 / "CS" / "2021_09_29_0026.abf",
    _C39 / "ADP" / "2021_09_29_0027.abf",
]

pytestmark = pytest.mark.skipif(
    not all(path.exists() for path in [SINGLE_CELL_FILE, DUAL_PATCH_FILE, *MULTI_FILE_RUNS]),
    reason="Prototype ABF example files under ~/data are not available (TODO: replace with gin fixtures).",
)


class TestAxonConverterSingleCell:
    """One interface: the single-cell path that adds the simultaneous / sequential chain."""

    def test_add_to_nwbfile(self):
        interface = AxonIntracellularInterface(
            file_path=str(SINGLE_CELL_FILE), response_channel_name="IN0", mode="current_clamp", stimulus_command="Cmd 0"
        )
        nwbfile = AxonIntracellularConverter(data_interfaces=[interface]).create_nwbfile()

        assert len(nwbfile.intracellular_recordings) == 9
        # One electrode: one simultaneous recording per sweep, one sequential run with a real stimulus type.
        assert len(nwbfile.icephys_simultaneous_recordings) == 9
        assert len(nwbfile.icephys_sequential_recordings) == 1
        stimulus_type = nwbfile.icephys_sequential_recordings["stimulus_type"][0]
        assert stimulus_type and stimulus_type != "not described"


class TestAxonConverterDualPatch:
    """Two electrodes from one dual-patch file: each sweep groups both electrodes into one simultaneous recording."""

    def test_add_to_nwbfile(self):
        interfaces = [
            AxonIntracellularInterface(
                file_path=str(DUAL_PATCH_FILE), response_channel_name="IN0", mode="current_clamp"
            ),
            AxonIntracellularInterface(
                file_path=str(DUAL_PATCH_FILE), response_channel_name="IN1", mode="voltage_clamp"
            ),
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

    def test_add_to_nwbfile(self):
        interfaces = [
            AxonIntracellularInterface(file_path=str(path), response_channel_name="IN0", mode="current_clamp")
            for path in MULTI_FILE_RUNS
        ]
        nwbfile = AxonIntracellularConverter(data_interfaces=interfaces).create_nwbfile()

        # One run per file: each distinct file is its own sequence, hence its own sequential recording.
        assert len(nwbfile.icephys_sequential_recordings) == len(MULTI_FILE_RUNS)
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


class TestAxonConverterRepetitions:
    """Repetition labels group the runs' sequential recordings into repetitions (no conditions)."""

    def test_add_to_nwbfile(self):
        interfaces = [
            AxonIntracellularInterface(
                file_path=str(path), response_channel_name="IN0", mode="current_clamp", repetition=repetition
            )
            for path, repetition in zip(MULTI_FILE_RUNS, ["r1", "r1", "r2", "r2"])
        ]
        nwbfile = AxonIntracellularConverter(data_interfaces=interfaces).create_nwbfile()

        assert len(nwbfile.icephys_sequential_recordings) == 4
        # Two repetitions, each grouping two of the four sequential recordings.
        repetitions = nwbfile.icephys_repetitions
        assert len(repetitions) == 2
        assert all(len(repetitions["sequential_recordings"][i]) == 2 for i in range(2))
        # No condition column -> the experimental-conditions table is not built.
        assert nwbfile.icephys_experimental_conditions is None


class TestAxonConverterConditions:
    """Condition labels group repetitions into experimental conditions (the full chain)."""

    def test_add_to_nwbfile(self):
        interfaces = [
            AxonIntracellularInterface(
                file_path=str(path),
                response_channel_name="IN0",
                mode="current_clamp",
                repetition=repetition,
                condition=condition,
            )
            for path, repetition, condition in zip(MULTI_FILE_RUNS, ["r1", "r2", "r3", "r4"], ["A", "A", "B", "B"])
        ]
        nwbfile = AxonIntracellularConverter(data_interfaces=interfaces).create_nwbfile()

        # Four distinct repetitions, grouped into two conditions of two repetitions each.
        assert len(nwbfile.icephys_repetitions) == 4
        conditions = nwbfile.icephys_experimental_conditions
        assert len(conditions) == 2
        assert all(len(conditions["repetitions"][i]) == 2 for i in range(2))


class TestAxonConverterConditionWithoutRepetition:
    """`condition` with no `repetition` defaults each run to its own repetition (identity), then groups by condition."""

    def test_add_to_nwbfile(self):
        interfaces = [
            AxonIntracellularInterface(
                file_path=str(path), response_channel_name="IN0", mode="current_clamp", condition=condition
            )
            for path, condition in zip(MULTI_FILE_RUNS, ["A", "A", "B", "B"])
        ]
        nwbfile = AxonIntracellularConverter(data_interfaces=interfaces).create_nwbfile()

        # Identity repetitions: one per run, each holding a single sequential recording.
        repetitions = nwbfile.icephys_repetitions
        assert len(repetitions) == len(MULTI_FILE_RUNS)
        assert all(len(repetitions["sequential_recordings"][i]) == 1 for i in range(len(MULTI_FILE_RUNS)))
        # Conditions group those identity repetitions: two conditions of two repetitions each.
        conditions = nwbfile.icephys_experimental_conditions
        assert len(conditions) == 2
        assert all(len(conditions["repetitions"][i]) == 2 for i in range(2))


class TestAxonConverterSharedElectrodeAcrossFiles:
    """Cross-referencing: the editable electrode links can merge several runs of one cell onto one electrode.

    By default each file is its own electrode (distinct, file-derived keys). Repointing every response series at
    a single electrode entry collapses them, exercising the electrode-reuse branch of ``_get_or_create_electrode``
    (an electrode found by name and shared, rather than created once per interface).
    """

    def test_merge_electrodes_via_edited_links(self):
        interfaces = [
            AxonIntracellularInterface(file_path=str(path), response_channel_name="IN0", mode="current_clamp")
            for path in MULTI_FILE_RUNS
        ]
        converter = AxonIntracellularConverter(data_interfaces=interfaces)
        metadata = converter.get_metadata()

        # Default: one electrode entry per file.
        assert len(metadata["Icephys"]["IntracellularElectrodes"]) == len(MULTI_FILE_RUNS)

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
        assert len(nwbfile.icephys_sequential_recordings) == len(MULTI_FILE_RUNS)


class TestAxonConverterDistinctDevicesViaLink:
    """Cross-referencing: pointing two electrodes at differently-named device entries yields two devices.

    Devices dedup by ``name``, so the dual-patch file (one amplifier) normally writes one device. Adding a second,
    differently-named device entry and repointing one electrode at it splits them, confirming device identity
    follows the device ``name`` link rather than the metadata key.
    """

    def test_distinct_devices(self):
        interfaces = [
            AxonIntracellularInterface(
                file_path=str(DUAL_PATCH_FILE), response_channel_name="IN0", mode="current_clamp"
            ),
            AxonIntracellularInterface(
                file_path=str(DUAL_PATCH_FILE), response_channel_name="IN1", mode="voltage_clamp"
            ),
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
