"""Tests for EthoVisionDataInterface and same-session Track composition.

These fixtures are on the unmerged ``behavior_testing_data`` branch, so their source paths remain
local until that data branch is published and the test-data checkout can provide them.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
from pynwb import NWBFile, read_nwb

from neuroconv import ConverterPipe
from neuroconv.datainterfaces.behavior.ethovision.ethovisiondatainterface import EthoVisionDataInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from ..setup_paths import OUTPUT_PATH
except ImportError:
    from setup_paths import OUTPUT_PATH

ETHOVISION_FOLDER_PATH = Path("/home/heberto/data/ethovision")


class TestEthoVisionTwoC57(DataInterfaceTestMixin):
    """The `two_c57` stub: one subject, one arena, a Manual Scoring sheet with point and state events."""

    FILE_PATH = ETHOVISION_FOLDER_PATH / "stubs/excel/track_and_manual_scoring/two_c57.xlsx"
    data_interface_cls = EthoVisionDataInterface
    interface_kwargs = dict(file_path=FILE_PATH)
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2022, 1, 25, 19, 38, 10)

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]

        position = behavior_module["EthoVisionPositionArena1Subject1"]
        assert position.data.shape == (9080, 2)
        assert position.unit == "cm"

        expected_channel_names = {
            "EthoVisionAreaArena1Subject1",
            "EthoVisionAreachangeArena1Subject1",
            "EthoVisionElongationArena1Subject1",
            "EthoVisionSniffArena1Subject1",
            "EthoVisionAttackArena1Subject1",
            "EthoVisionAggressiveGroomArena1Subject1",
            "EthoVisionGroomArena1Subject1",
            "EthoVisionRetrieveArena1Subject1",
            "EthoVisionRetrieve2Arena1Subject1",
            "EthoVisionNestBuildingArena1Subject1",
            "EthoVisionStartArena1Subject1",
            "EthoVisionDiggingArena1Subject1",
            "EthoVisionInterruptionArena1Subject1",
            "EthoVisionCarryArena1Subject1",
            "EthoVisionAnogenitalArena1Subject1",
            "EthoVisionBackMountArena1Subject1",
            "EthoVisionSideMountArena1Subject1",
            "EthoVisionResult1Arena1Subject1",
        }
        assert set(behavior_module.data_interfaces) == {
            "EthoVisionPositionArena1Subject1",
            "EthoVisionEthogramArena1",
            "EthoVisionEthogramBoutsArena1",
            *expected_channel_names,
        }

        events = nwbfile.events["EthoVisionManualScoringArena1"].to_dataframe()
        assert len(events) == 35

        # Two behaviors the sheet scores as bouts never close within this stub's episode boundary,
        # so a reader relying only on the Track sheet's per-frame indicator columns for these two
        # names would find nothing: 'attacking' has no matching Track column at all ('Attack' does,
        # but under a different string), and 'tail rattle' is scored only as a point event with no
        # Track column whatsoever.
        expected_event_types = {
            "Sniff",
            "aggressive groom",
            "attacking",
            "carry",
            "digging",
            "groom",
            "start",
            "tail rattle",
        }
        assert set(events["event_type"]) == expected_event_types
        assert "EthoVisionAttackingArena1Subject1" not in behavior_module.data_interfaces
        assert "EthoVisionTailRattleArena1Subject1" not in behavior_module.data_interfaces

        # The two 'start' point events bracket the stub's retained episode and carry no duration.
        start_rows = events[events["event_type"] == "start"]
        assert len(start_rows) == 2
        assert start_rows["duration"].isna().all()

        # Every state bout in this stub closes: nothing here exercises the NaN-duration,
        # never-closed-bout path that a messier file would. 'start' and 'tail rattle' are point
        # events (no extent to record), so they are excluded rather than expected to close.
        state_rows = events[~events["event_type"].isin(["start", "tail rattle"])]
        assert not state_rows["duration"].isna().any()

        ethogram = behavior_module["EthoVisionEthogramArena1"].to_dataframe()
        assert set(ethogram["behavior"]) == set(events["event_type"])
        assert set(ethogram["behavior_type"]) == {"point", "state"}

        bouts = behavior_module["EthoVisionEthogramBoutsArena1"].to_dataframe()
        assert len(bouts) == 31
        assert set(bouts["subject"]) == {"Subject 1"}
        assert set(bouts["arena"]) == {"Arena 1"}
        assert set(bouts["label"]).isdisjoint({"start", "tail rattle"})

    def test_available_tracks(self):
        expected_tracks = [{"arena_name": "Arena 1", "subject_name": "Subject 1"}]
        assert EthoVisionDataInterface.get_available_tracks(self.FILE_PATH) == expected_tracks

    def test_nonlinear_alignment_remaps_tracks_events_and_bouts(self):
        interface = EthoVisionDataInterface(file_path=self.FILE_PATH)
        interface.alignment.remap_times(
            local_sync_times=np.array([0.0, 200.0]),
            reference_sync_times=np.array([10.0, 410.0]),
        )

        nwbfile = NWBFile(
            session_description="alignment test",
            identifier="alignment test",
            session_start_time=datetime.now(timezone.utc),
        )
        interface.add_to_nwbfile(nwbfile=nwbfile)

        position = nwbfile.processing["behavior"]["EthoVisionPositionArena1Subject1"]
        assert np.isclose(position.timestamps[0], 10.0)
        assert np.isclose(position.timestamps[1] - position.timestamps[0], 0.068)

        events = nwbfile.events["EthoVisionManualScoringArena1"].to_dataframe()
        first_sniff = events[events["event_type"] == "Sniff"].iloc[0]
        assert np.isclose(first_sniff["timestamp"], 110.466)
        assert np.isclose(first_sniff["duration"], 6.134)

        bouts = nwbfile.processing["behavior"]["EthoVisionEthogramBoutsArena1"].to_dataframe()
        first_sniff_bout = bouts[bouts["label"] == "Sniff"].iloc[0]
        assert np.isclose(first_sniff_bout["start_time"], 110.466)
        assert np.isclose(first_sniff_bout["stop_time"], 116.6)


class TestEthoVisionMissingSamples(DataInterfaceTestMixin):
    """A public CC0 file with the real 'subject not found' `-` sentinel and no Manual Scoring sheet.

    Two subjects share the workbook (`Track-Rat Arena 1a-Subject 1/2`); this interface selects
    one of them. The composition test below combines both. The arena label contains spaces and
    does not start with the word "Arena", which the sheet-name pattern has to accept.
    """

    FILE_PATH = ETHOVISION_FOLDER_PATH / "stubs/excel/hardware_and_trial_control/two_subjects_missing_samples.xlsx"
    data_interface_cls = EthoVisionDataInterface
    interface_kwargs = dict(
        file_path=FILE_PATH,
        arena_name="Rat Arena 1a",
        subject_name="Subject 1",
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 3, 22, 14, 30, 22, 300000)

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]

        # No Manual Scoring sheet in this file: the more common real-world shape, per the format
        # survey, and unexercised by the two_c57 stub.
        assert not nwbfile.events

        expected_channel_stems = {
            "XNose",
            "YNose",
            "XTail",
            "YTail",
            "Area",
            "Areachange",
            "Elongation",
            "Direction",
            "HeadDirectedToObject1",
            "HeadDirectedToObject2",
            "Control",
        }
        assert set(behavior_module.data_interfaces) == {
            "EthoVisionPositionRatArena1aSubject1",
            *(f"EthoVision{stem}RatArena1aSubject1" for stem in expected_channel_stems),
        }
        position = behavior_module["EthoVisionPositionRatArena1aSubject1"]
        assert position.data.shape == (552, 2)

        # 'Subject not found' frames dash X/Y (and every other value column) together. Subject 1
        # exercises 63 such rows in this stub.
        subject_1_position = behavior_module["EthoVisionPositionRatArena1aSubject1"]
        assert np.isnan(subject_1_position.data[:, 0]).sum() == 63
        assert np.isnan(subject_1_position.data[:, 1]).sum() == 63

        # 'Control' is never populated anywhere in this sheet: the source spreadsheet stores no
        # cell at all for it on any row, rather than a stored 0 or a '-' sentinel, so every row
        # comes back shorter than the declared column count for this channel specifically.
        control = behavior_module["EthoVisionControlRatArena1aSubject1"].data[:]
        assert np.isnan(control).all()

    def test_available_tracks(self):
        expected_tracks = [
            {"arena_name": "Rat Arena 1a", "subject_name": "Subject 1"},
            {"arena_name": "Rat Arena 1a", "subject_name": "Subject 2"},
        ]
        assert EthoVisionDataInterface.get_available_tracks(self.FILE_PATH) == expected_tracks

    def test_metadata_keys_control_written_names(self):
        interface = EthoVisionDataInterface(
            file_path=self.FILE_PATH,
            arena_name="Rat Arena 1a",
            subject_name="Subject 1",
        )
        metadata = interface.get_metadata()
        metadata_key = "ethovision_rat_arena_1a_subject_1"
        control_metadata_key = f"{metadata_key}_control"
        assert "EthoVision" not in metadata.get("Behavior", {})
        assert set(metadata["SpatialSeries"]) == {metadata_key}
        assert control_metadata_key in metadata["TimeSeries"]

        metadata["SpatialSeries"][metadata_key]["name"] = "MouseOneCenter"
        metadata["TimeSeries"][control_metadata_key]["name"] = "MouseOneControl"

        nwbfile = NWBFile(
            session_description="metadata naming test",
            identifier="metadata naming test",
            session_start_time=datetime.now(timezone.utc),
        )
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        behavior_module = nwbfile.processing["behavior"]
        assert "MouseOneCenter" in behavior_module.data_interfaces
        assert "MouseOneControl" in behavior_module.data_interfaces

    def test_interface_requires_one_track(self):
        expected_error = (
            f"arena_name=None, subject_name=None does not identify one Track in '{self.FILE_PATH}'. "
            "Matching tracks: [('Rat Arena 1a', 'Subject 1'), ('Rat Arena 1a', 'Subject 2')]."
        )
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            EthoVisionDataInterface(file_path=self.FILE_PATH)

    def test_interface_rejects_a_nonexistent_track_identity(self):
        expected_error = (
            "No EthoVision Track matches arena_name='Rat Arena 1a', subject_name='Subject 3' "
            f"in '{self.FILE_PATH}'. Available tracks: "
            "[('Rat Arena 1a', 'Subject 1'), ('Rat Arena 1a', 'Subject 2')]."
        )
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            EthoVisionDataInterface(
                file_path=self.FILE_PATH,
                arena_name="Rat Arena 1a",
                subject_name="Subject 3",
            )


class TestEthoVisionConverterPipeMultiSubject:
    FILE_PATH = ETHOVISION_FOLDER_PATH / "stubs/excel/hardware_and_trial_control/two_subjects_missing_samples.xlsx"

    def test_converter_pipe_combines_all_subject_tracks_in_one_arena(self):
        arena_name = "Rat Arena 1a"
        available_tracks = EthoVisionDataInterface.get_available_tracks(self.FILE_PATH)
        interfaces = [
            EthoVisionDataInterface(file_path=self.FILE_PATH, **track)
            for track in available_tracks
            if track["arena_name"] == arena_name
        ]
        converter = ConverterPipe(data_interfaces={interface.metadata_key: interface for interface in interfaces})
        assert set(converter.data_interface_objects) == {
            "ethovision_rat_arena_1a_subject_1",
            "ethovision_rat_arena_1a_subject_2",
        }

        nwbfile = NWBFile(
            session_description="converter test",
            identifier="converter test",
            session_start_time=datetime.now(timezone.utc),
        )
        converter.add_to_nwbfile(nwbfile=nwbfile)

        behavior_module = nwbfile.processing["behavior"]
        expected_names = {
            "EthoVisionPositionRatArena1aSubject1",
            "EthoVisionXNoseRatArena1aSubject1",
            "EthoVisionYNoseRatArena1aSubject1",
            "EthoVisionXTailRatArena1aSubject1",
            "EthoVisionYTailRatArena1aSubject1",
            "EthoVisionAreaRatArena1aSubject1",
            "EthoVisionAreachangeRatArena1aSubject1",
            "EthoVisionElongationRatArena1aSubject1",
            "EthoVisionDirectionRatArena1aSubject1",
            "EthoVisionHeadDirectedToObject1RatArena1aSubject1",
            "EthoVisionHeadDirectedToObject2RatArena1aSubject1",
            "EthoVisionControlRatArena1aSubject1",
            "EthoVisionPositionRatArena1aSubject2",
            "EthoVisionXNoseRatArena1aSubject2",
            "EthoVisionYNoseRatArena1aSubject2",
            "EthoVisionXTailRatArena1aSubject2",
            "EthoVisionYTailRatArena1aSubject2",
            "EthoVisionAreaRatArena1aSubject2",
            "EthoVisionAreachangeRatArena1aSubject2",
            "EthoVisionElongationRatArena1aSubject2",
            "EthoVisionDirectionRatArena1aSubject2",
            "EthoVisionHeadDirectedToObject1RatArena1aSubject2",
            "EthoVisionHeadDirectedToObject2RatArena1aSubject2",
            "EthoVisionControlRatArena1aSubject2",
        }
        assert set(behavior_module.data_interfaces) == expected_names


class TestEthoVisionCsv(DataInterfaceTestMixin):
    FILE_PATH = ETHOVISION_FOLDER_PATH / "stubs/csv/track_only/morris_water_maze.csv"
    data_interface_cls = EthoVisionDataInterface
    interface_kwargs = dict(file_path=FILE_PATH)
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2020, 1, 1, 9, 0)

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]

        position = behavior_module["EthoVisionPositionArena1Subject1"]
        assert position.data.shape == (1500, 2)
        assert position.unit == "cm"
        assert np.isnan(position.data[:, 0]).sum() == 33
        expected_names = {
            "EthoVisionPositionArena1Subject1",
            "EthoVisionAreaArena1Subject1",
            "EthoVisionAreachangeArena1Subject1",
            "EthoVisionElongationArena1Subject1",
            "EthoVisionDistanceMovedArena1Subject1",
            "EthoVisionVelocityArena1Subject1",
            "EthoVisionInZoneArenaCenterPointArena1Subject1",
            "EthoVisionInZonePeripheryCenterPointArena1Subject1",
            "EthoVisionInZoneZone1CenterPointArena1Subject1",
            "EthoVisionInZoneZone2CenterPointArena1Subject1",
            "EthoVisionInZoneZone3CenterPointArena1Subject1",
            "EthoVisionMovementMovingCenterPointArena1Subject1",
            "EthoVisionMovementNotMovingCenterPointArena1Subject1",
            "EthoVisionDistanceToPointArena1Subject1",
            "EthoVisionResult1Arena1Subject1",
        }
        assert set(behavior_module.data_interfaces) == expected_names

    def test_available_tracks(self):
        expected_tracks = [{"arena_name": "Arena 1", "subject_name": "Subject 1"}]
        assert EthoVisionDataInterface.get_available_tracks(self.FILE_PATH) == expected_tracks


class TestEthoVisionTxt(DataInterfaceTestMixin):
    FILE_PATH = ETHOVISION_FOLDER_PATH / "stubs/txt/track_only/termites.txt"
    data_interface_cls = EthoVisionDataInterface
    interface_kwargs = dict(file_path=FILE_PATH)
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2014, 2, 9, 18, 4, 58, 400000)

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        position = behavior_module["EthoVisionPositionArena1Subject1"]
        assert position.data.shape == (1877, 2)
        assert position.unit == "mm"
        assert position.timestamps[0] == 0.0

        distance_moved = behavior_module["EthoVisionDistanceMovedArena1Subject1"]
        assert np.isnan(distance_moved.data[0])

    def test_available_tracks(self):
        expected_tracks = [{"arena_name": "Arena 1", "subject_name": "Subject 1"}]
        assert EthoVisionDataInterface.get_available_tracks(self.FILE_PATH) == expected_tracks


class TestEthoVisionMultipleArenasSingleSubject(DataInterfaceTestMixin):
    FILE_PATH = (
        ETHOVISION_FOLDER_PATH / "stubs/excel/multiple_arenas_single_subject/track_only/two_arenas_one_subject.xlsx"
    )
    data_interface_cls = EthoVisionDataInterface
    interface_kwargs = dict(file_path=FILE_PATH, arena_name="Arena 2", subject_name="Subject 1")
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2017, 10, 19, 13, 35, 57, 494000)

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        position = nwbfile.processing["behavior"]["EthoVisionPositionArena2Subject1"]
        assert position.data.shape == (120, 2)
        assert position.unit == "cm"

    def test_available_tracks(self):
        expected_tracks = [
            {"arena_name": "Arena 1", "subject_name": "Subject 1"},
            {"arena_name": "Arena 2", "subject_name": "Subject 1"},
        ]
        assert EthoVisionDataInterface.get_available_tracks(self.FILE_PATH) == expected_tracks


class TestEthoVisionMultipleArenasMultipleSubjects(DataInterfaceTestMixin):
    FILE_PATH = (
        ETHOVISION_FOLDER_PATH
        / "stubs/excel/multiple_arenas_multiple_subjects/track_only/two_arenas_four_subjects.xlsx"
    )
    data_interface_cls = EthoVisionDataInterface
    interface_kwargs = dict(file_path=FILE_PATH, arena_name="Arena 2", subject_name="Subject 4")
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2017, 9, 14, 10, 36, 33)

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        position = nwbfile.processing["behavior"]["EthoVisionPositionArena2Subject4"]
        assert position.data.shape == (120, 2)
        assert position.unit == "cm"

    def test_available_tracks(self):
        expected_tracks = [
            {"arena_name": "Arena 1", "subject_name": "Subject 1"},
            {"arena_name": "Arena 1", "subject_name": "Subject 2"},
            {"arena_name": "Arena 1", "subject_name": "Subject 3"},
            {"arena_name": "Arena 1", "subject_name": "Subject 4"},
            {"arena_name": "Arena 2", "subject_name": "Subject 1"},
            {"arena_name": "Arena 2", "subject_name": "Subject 2"},
            {"arena_name": "Arena 2", "subject_name": "Subject 3"},
            {"arena_name": "Arena 2", "subject_name": "Subject 4"},
        ]
        assert EthoVisionDataInterface.get_available_tracks(self.FILE_PATH) == expected_tracks
