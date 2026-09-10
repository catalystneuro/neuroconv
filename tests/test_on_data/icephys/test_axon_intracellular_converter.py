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
from ``create_nwbfile``). Every scenario here needs real ABF files for something the format alone provides: the
protocol-derived stimulus type, channels that genuinely share sweeps, header start times to align on, or filenames
that collide. The parts of the aggregator that need no file (the ``repetition`` / ``condition`` grouping branches
and metadata-driven electrode sharing) are tested generically through ``MockIcephysInterface`` in
``tests/test_minimal/test_tools/test_icephys.py``, so every icephys interface benefits from that coverage.

Fixtures live in the gin ``ephy_testing_data`` repo under ``axon/intracellular_data`` (the same purpose-built set
the interface tests use). The ``read_raw_protocol`` files are several runs recorded back-to-back on one rig
(ascending header start times, all ABF v2, recorded on ``IN0``), which is what the multi-file alignment needs;
``dual_patch_pairs/current_clamp.abf`` is a genuine dual patch (``IN0`` current clamp, ``IN1`` voltage clamp).
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
        # The sweeps are also written as intervals: one row per sweep, in time order, inside the series span.
        sweeps = nwbfile.intervals["sweeps"]
        assert len(sweeps) == n_sweeps
        response_series = next(iter(nwbfile.acquisition.values()))
        series_start = response_series.starting_time or float(response_series.timestamps[0])
        assert sweeps.start_time[0] == series_start
        assert list(sweeps.start_time[:]) == sorted(sweeps.start_time[:])


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
        # The two rows of a sweep describe one interval, so the sweeps table has a row per sweep, not per row.
        assert len(nwbfile.intervals["sweeps"]) == n_sweeps
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
        # Point at the resolved real file: the gin source is itself a git-annex symlink, and pydantic's FilePath
        # validator does not follow a symlink-to-a-symlink chain (it reports the staged path as not-a-file).
        cell_a.symlink_to(self.source_files[0].resolve())
        cell_b.symlink_to(self.source_files[1].resolve())

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
