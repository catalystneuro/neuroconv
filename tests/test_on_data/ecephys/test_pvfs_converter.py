"""End-to-end tests for :class:`~neuroconv.converters.PvfsConverter`.

These tests require a real Pinnacle ``.pvfs`` file on disk.  Download the
public sleep sample from https://www.pinnaclet.com/data_sets/sleep_data.zip
and point the tests at it using any of:

* ``PVFS_TEST_FILE=/path/to/recording.pvfs`` (environment variable), or
* ``<repo>/pvfs/example.pvfs`` (local scratch; not committed), or
* ``ECEPHY_DATA_PATH/pvfs/`` (GIN layout; see ``gin_test_config.json``).

Tests are skipped automatically when no file is found.
"""

from datetime import datetime

import pytest
from pynwb import read_nwb

from neuroconv.converters import PvfsConverter
from neuroconv.datainterfaces.ecephys.pvfs.pvfsannotationsinterface import (
    PvfsAnnotationsInterface,
)
from neuroconv.datainterfaces.ecephys.pvfs.pvfsdatainterface import PvfsRecordingInterface
from neuroconv.datainterfaces.ecephys.pvfs.pvfssleepscoringinterface import (
    PvfsSleepScoringInterface,
)
from neuroconv.datainterfaces.ecephys.pvfs.pvfsvideointerface import PvfsVideoInterface

from ..setup_paths import PVFS_TEST_FILE_PATH, PVFS_TEST_FILE_SKIP_REASON

pytestmark = pytest.mark.skipif(
    PVFS_TEST_FILE_PATH is None,
    reason=PVFS_TEST_FILE_SKIP_REASON,
)


class TestPvfsConverterOnSleepData:
    """Drive ``PvfsConverter`` against a user-provided Pinnacle PVFS sample."""

    file_path = PVFS_TEST_FILE_PATH

    def test_interface_discovery(self):
        converter = PvfsConverter(file_path=self.file_path, include_video=False)
        interfaces = converter.data_interface_objects

        # At least one Recording interface (one per sampling-rate group) must be present.
        recording_names = [name for name in interfaces if name.startswith("Recording")]
        assert recording_names, (
            f"PvfsConverter created no recording interfaces (got {list(interfaces)})."
        )
        for name in recording_names:
            assert isinstance(interfaces[name], PvfsRecordingInterface)

        # The Annotations interface is created if and only if the PVFS file's
        # experiment_annotation_table is non-empty. The Pinnacle public sample
        # ships without populated annotations, so we only assert the type when it
        # is present.
        if "Annotations" in interfaces:
            assert isinstance(interfaces["Annotations"], PvfsAnnotationsInterface)

    def test_metadata_extracted_from_experiment_db(self):
        converter = PvfsConverter(file_path=self.file_path, include_video=False)
        metadata = converter.get_metadata()

        session_start_time = metadata["NWBFile"]["session_start_time"]
        assert isinstance(session_start_time, datetime)
        assert session_start_time.tzinfo is not None

        # PVFS-specific Device / ElectrodeGroup defaults set by the interface.
        devices = metadata["Ecephys"]["Device"]
        assert any(device["name"] == "DevicePVFS" for device in devices)

        electrode_groups = metadata["Ecephys"]["ElectrodeGroup"]
        assert any(group["name"] == "PVFSGroup" for group in electrode_groups)

    def test_round_trip_writes_electrical_series_and_epochs(self, tmp_path):
        converter = PvfsConverter(file_path=self.file_path, include_video=False)

        metadata = converter.get_metadata()
        metadata["Subject"]["subject_id"] = "pvfs_test_subject"

        nwbfile_path = tmp_path / "pvfs_converter_round_trip.nwb"
        converter.run_conversion(
            nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True
        )
        assert nwbfile_path.exists() and nwbfile_path.stat().st_size > 0

        nwbfile = read_nwb(path=nwbfile_path)

        # Every sampling-rate group must land as its own ElectricalSeries in /acquisition.
        electrical_series = [
            obj
            for obj in nwbfile.acquisition.values()
            if obj.neurodata_type == "ElectricalSeries"
        ]
        assert electrical_series, "No ElectricalSeries was written by PvfsConverter."
        # ElectricalSeries names must be unique and follow the PVFS naming scheme.
        es_names = [es.name for es in electrical_series]
        assert len(set(es_names)) == len(es_names), f"Duplicate ES names: {es_names}"
        for name in es_names:
            assert name.startswith("ElectricalSeriesPVFS"), name
            assert "PVFSPVFS" not in name, f"Double-PVFS suffix in ES name: {name}"

        # If the source file ships annotations they must round-trip into the epochs
        # table with the PVFS-specific columns; if it does not, epochs is allowed
        # to be absent.
        if "Annotations" in converter.data_interface_objects:
            assert nwbfile.epochs is not None
            epoch_columns = {col.name for col in nwbfile.epochs.columns}
            assert {"label", "channel"}.issubset(epoch_columns)
            epoch_df = nwbfile.epochs.to_dataframe()
            assert (epoch_df["stop_time"] > epoch_df["start_time"]).all()

        # Subject overrides are honored.
        assert nwbfile.subject is not None
        assert nwbfile.subject.subject_id == "pvfs_test_subject"

    def test_video_interface_attached_only_when_video_present(self):
        # The sleep_data sample is audio/EEG/EMG only -- no embedded video. Even with
        # include_video=True the converter should only attach a PvfsVideoInterface
        # when ``has_video()`` returns True.
        converter = PvfsConverter(file_path=self.file_path, include_video=True)
        interfaces = converter.data_interface_objects
        video_interfaces = [
            iface for iface in interfaces.values() if isinstance(iface, PvfsVideoInterface)
        ]
        # We don't assert on the exact count -- if Pinnacle ever ships a video stream
        # in this file we want this test to keep passing, but a video interface should
        # only ever appear when there is something to write.
        for iface in video_interfaces:
            assert iface.has_video()

    def test_sleep_scoring_interface_attached_when_scoring_present(self):
        # The sleep_data public sample is fully scored, so the converter must
        # auto-attach a PvfsSleepScoringInterface.
        converter = PvfsConverter(file_path=self.file_path, include_video=False)
        interfaces = converter.data_interface_objects
        assert "SleepScoring" in interfaces, (
            f"PvfsConverter did not attach SleepScoring (got {list(interfaces)})."
        )
        assert isinstance(interfaces["SleepScoring"], PvfsSleepScoringInterface)
        assert interfaces["SleepScoring"].has_scoring()

    def test_sleep_scoring_skipped_when_flag_off(self):
        converter = PvfsConverter(
            file_path=self.file_path,
            include_video=False,
            include_sleep_scoring=False,
        )
        assert "SleepScoring" not in converter.data_interface_objects

    def test_round_trip_writes_sleep_stages_intervals(self, tmp_path):
        converter = PvfsConverter(file_path=self.file_path, include_video=False)
        assert "SleepScoring" in converter.data_interface_objects

        # Read the scoring sessions directly so the test asserts against the
        # exact row counts present in the source file, not a hard-coded number.
        sessions = converter.data_interface_objects["SleepScoring"]._get_sessions()
        populated = {n: s for n, s in sessions.items() if s.epochs}
        assert populated, "expected at least one populated scoring session"

        metadata = converter.get_metadata()
        metadata["Subject"]["subject_id"] = "pvfs_scoring_test_subject"

        nwbfile_path = tmp_path / "pvfs_converter_scoring_round_trip.nwb"
        converter.run_conversion(
            nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True
        )
        assert nwbfile_path.exists() and nwbfile_path.stat().st_size > 0

        nwbfile = read_nwb(path=nwbfile_path)
        expected_columns = {
            "start_time",
            "stop_time",
            "stage_label",
            "stage_value",
            "flags",
            "epoch_uid",
        }

        for session_number, session in populated.items():
            table_name = f"sleep_stages_session_{session_number}"
            assert table_name in nwbfile.intervals, (
                f"Missing TimeIntervals table for session {session_number}; "
                f"got {list(nwbfile.intervals)}."
            )
            table = nwbfile.intervals[table_name]
            actual_columns = {col.name for col in table.columns}
            assert expected_columns.issubset(actual_columns), (
                f"Missing scoring columns: {expected_columns - actual_columns}"
            )

            df = table.to_dataframe()
            assert len(df) == len(session.epochs)
            assert (df["stop_time"] > df["start_time"]).all()
            # Round-trip of the legend mapping: every raw integer score must
            # have produced a non-empty stage_label.
            assert df["stage_label"].astype(str).str.len().gt(0).all()
            # GUIDs must round-trip verbatim so external tools can re-key edits.
            assert list(df["epoch_uid"]) == [e.uid for e in session.epochs]
            # Pinnacle scores fixed-length epochs; verify they are uniform
            # within the file (allowing for fractional sub-second jitter).
            if session.epoch_length_seconds is not None:
                expected = float(session.epoch_length_seconds)
                # Allow a 1 ms slop because PVFS stores sub-seconds as VARCHAR
                # and may round-trip with very small floating-point noise.
                deviation = (df["stop_time"] - df["start_time"] - expected).abs().max()
                assert deviation <= 1e-3, f"epoch durations drifted by {deviation}s"
