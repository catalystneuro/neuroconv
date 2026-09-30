"""Tests for EthoVisionManualScoringInterface."""

import re
from datetime import datetime

import numpy as np
import pytest
from pynwb import read_nwb

from neuroconv import ConverterPipe
from neuroconv.datainterfaces.behavior.ethovision.ethovisionmanualscoringinterface import (
    EthoVisionManualScoringInterface,
)
from neuroconv.datainterfaces.behavior.ethovision.ethovisiontrackinterface import EthoVisionTrackInterface
from neuroconv.tools.testing.data_interface_mixins import EventsInterfaceTestMixin

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH

ETHOVISION_FOLDER_PATH = BEHAVIOR_DATA_PATH / "ethovision"


class TestEthoVisionManualScoring(EventsInterfaceTestMixin):
    """The `two_c57` stub: a Manual Scoring sheet beside the Track, with point events and state bouts."""

    file_path = ETHOVISION_FOLDER_PATH / "excel/single_arena_single_subject/track_and_manual_scoring/two_c57.xlsx"
    interface_kwargs = dict(file_path=file_path)
    data_interface_cls = EthoVisionManualScoringInterface
    save_directory = OUTPUT_PATH

    expected_session_start_time = datetime(2022, 1, 25, 19, 38, 10)
    expected_number_of_point_events = 4
    expected_number_of_bouts = 31
    expected_behavior_types = {
        "start": "point",
        "tail rattle": "point",
        "Sniff": "state",
        "aggressive groom": "state",
        "attacking": "state",
        "carry": "state",
        "digging": "state",
        "groom": "state",
    }
    expected_available_scorings = [{"arena_name": "Arena 1", "subject_name": "Subject 1"}]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == self.expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):
        super().check_read_nwb(nwbfile_path=nwbfile_path)
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        assert set(behavior_module.data_interfaces) == {"EthoVisionEthogramArena1", "EthoVisionEthogramBoutsArena1"}

        # Point events carry no duration and every state bout in this file closes, so the rows without a duration
        # are the point events and the rows with one are the bouts.
        events = nwbfile.events["EthoVisionManualScoringArena1"].to_dataframe()
        assert events["duration"].isna().sum() == self.expected_number_of_point_events
        assert events["duration"].notna().sum() == self.expected_number_of_bouts

        ethogram = behavior_module["EthoVisionEthogramArena1"].to_dataframe()
        assert dict(zip(ethogram["behavior"], ethogram["behavior_type"])) == self.expected_behavior_types

        bouts = behavior_module["EthoVisionEthogramBoutsArena1"].to_dataframe()
        assert len(bouts) == self.expected_number_of_bouts
        assert set(bouts["subject"]) == {"Subject 1"}
        assert set(bouts["arena"]) == {"Arena 1"}

    def test_available_scorings(self):
        assert (
            EthoVisionManualScoringInterface.get_available_scorings(self.file_path) == self.expected_available_scorings
        )


class TestEthoVisionManualScoringOnly(EventsInterfaceTestMixin):
    """A Manual Scoring sheet exported without any Track, so the session start comes from the sheet's own header."""

    file_path = ETHOVISION_FOLDER_PATH / "excel/single_arena_single_subject/manual_scoring_only/manual_scoring.xlsx"
    interface_kwargs = dict(file_path=file_path)
    data_interface_cls = EthoVisionManualScoringInterface
    save_directory = OUTPUT_PATH

    expected_session_start_time = datetime(2023, 12, 13, 12, 58, 24, 71000)
    expected_number_of_point_events = 0
    expected_number_of_bouts = 30
    expected_behavior_types = {
        "Rearing": "state",
        "Sniffing": "state",
        "Operant": "state",
        "Free-air whisking": "state",
        "Tone": "state",
    }
    expected_available_scorings = [{"arena_name": "Arena 1", "subject_name": "Subject 1"}]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == self.expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):
        super().check_read_nwb(nwbfile_path=nwbfile_path)
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]

        # Point events carry no duration and every state bout in this file closes, so the rows without a duration
        # are the point events and the rows with one are the bouts.
        events = nwbfile.events["EthoVisionManualScoringArena1"].to_dataframe()
        assert events["duration"].isna().sum() == self.expected_number_of_point_events
        assert events["duration"].notna().sum() == self.expected_number_of_bouts

        ethogram = behavior_module["EthoVisionEthogramArena1"].to_dataframe()
        assert dict(zip(ethogram["behavior"], ethogram["behavior_type"])) == self.expected_behavior_types

        bouts = behavior_module["EthoVisionEthogramBoutsArena1"].to_dataframe()
        assert len(bouts) == self.expected_number_of_bouts
        assert bouts["label"].value_counts().to_dict() == {
            "Sniffing": 12,
            "Rearing": 10,
            "Operant": 4,
            "Free-air whisking": 3,
            "Tone": 1,
        }

    def test_available_scorings(self):
        assert (
            EthoVisionManualScoringInterface.get_available_scorings(self.file_path) == self.expected_available_scorings
        )


class TestEthoVisionManualScoringEdgeCases:
    """Errors, options and combinations that the round trips above do not exercise.

    A plain grouping class: each case reads a published fixture, or a copy rewritten here, to reach one error
    path, argument or combination rather than to convert a new layout.
    """

    def test_remap_times_moves_events_and_bouts(self):
        interface = EthoVisionManualScoringInterface(file_path=TestEthoVisionManualScoring.file_path)
        interface.alignment.remap_times(
            local_sync_times=np.array([0.0, 200.0]),
            reference_sync_times=np.array([10.0, 410.0]),
        )

        nwbfile = interface.create_nwbfile()

        events = nwbfile.events["EthoVisionManualScoringArena1"].to_dataframe()
        first_sniff = events[events["event_type"] == "Sniff"].iloc[0]
        assert np.isclose(first_sniff["timestamp"], 112.6)
        assert np.isclose(first_sniff["duration"], 6.134)

        bouts = nwbfile.processing["behavior"]["EthoVisionEthogramBoutsArena1"].to_dataframe()
        first_sniff_bout = bouts[bouts["label"] == "Sniff"].iloc[0]
        assert np.isclose(first_sniff_bout["start_time"], 112.6)
        assert np.isclose(first_sniff_bout["stop_time"], 118.734)

    def test_documented_spellings_read_the_same(self, tmp_path):
        """The Noldus manuals spell the sheet `Manual scoring - <arena>` and capitalize `State start`."""
        import openpyxl

        source_path = TestEthoVisionManualScoring.file_path
        workbook = openpyxl.load_workbook(source_path)
        scoring_sheet = workbook["Manual Scoring-Arena 1"]
        scoring_sheet.title = "Manual scoring - Arena 1"
        for (cell,) in scoring_sheet.iter_rows(min_col=5, max_col=5):
            if cell.value in ("state start", "state stop", "point event"):
                cell.value = cell.value.capitalize()
        file_path = tmp_path / "two_c57_documented_spellings.xlsx"
        workbook.save(file_path)

        source_nwbfile = EthoVisionManualScoringInterface(file_path=source_path).create_nwbfile()
        documented_nwbfile = EthoVisionManualScoringInterface(file_path=file_path).create_nwbfile()
        source_events = source_nwbfile.events["EthoVisionManualScoringArena1"].to_dataframe()
        documented_events = documented_nwbfile.events["EthoVisionManualScoringArena1"].to_dataframe()
        assert len(source_events) == 35
        assert documented_events.equals(source_events)

    def test_workbook_without_manual_scoring_lists_nothing(self):
        file_path = (
            ETHOVISION_FOLDER_PATH
            / "excel/single_arena_multiple_subjects/hardware_and_trial_control/two_subjects_missing_samples.xlsx"
        )
        assert EthoVisionManualScoringInterface.get_available_scorings(file_path) == []

        expected_error = (
            "No EthoVision Manual Scoring matches arena_name=None, subject_name=None "
            f"in '{file_path}'. Available scorings: []."
        )
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            EthoVisionManualScoringInterface(file_path=file_path)

    def test_text_export_raises(self):
        file_path = ETHOVISION_FOLDER_PATH / "txt/single_arena_single_subject/comma_delimited/morris_water_maze.txt"
        expected_error = (
            "'morris_water_maze.txt' is a text export. EthoVisionManualScoringInterface reads Manual Scoring only "
            "from the Manual Scoring sheet of an Excel workbook; text Manual Scoring logs are not supported yet "
            "because none was available to build or test a reader against. If you have one, please open an issue "
            "at https://github.com/catalystneuro/neuroconv/issues with a sample file."
        )
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            EthoVisionManualScoringInterface(file_path=file_path)
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            EthoVisionManualScoringInterface.get_available_scorings(file_path)

    def test_converter_pipe_writes_track_and_manual_scoring(self):
        file_path = TestEthoVisionManualScoring.file_path
        converter = ConverterPipe(
            data_interfaces=dict(
                Track=EthoVisionTrackInterface(file_path=file_path),
                ManualScoring=EthoVisionManualScoringInterface(file_path=file_path),
            )
        )

        nwbfile = converter.create_nwbfile()

        behavior_module = nwbfile.processing["behavior"]
        assert "EthoVisionPositionArena1Subject1" in behavior_module.data_interfaces
        assert "EthoVisionEthogramArena1" in behavior_module.data_interfaces
        assert "EthoVisionEthogramBoutsArena1" in behavior_module.data_interfaces
        assert len(nwbfile.events["EthoVisionManualScoringArena1"]) == 35
