"""Tests for EthoVisionTrackInterface."""

import re
from datetime import datetime

import numpy as np
import pytest
from pynwb import read_nwb

from neuroconv.datainterfaces.behavior.ethovision.ethovisiontrackinterface import EthoVisionTrackInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH

ETHOVISION_FOLDER_PATH = BEHAVIOR_DATA_PATH / "ethovision"


class TestEthoVisionTrackAndManualScoring(DataInterfaceTestMixin):
    """The `two_c57` stub: one subject, one arena, and a Manual Scoring sheet the Track interface does not read."""

    file_path = ETHOVISION_FOLDER_PATH / "excel/single_arena_single_subject/track_and_manual_scoring/two_c57.xlsx"
    interface_kwargs = dict(file_path=file_path)
    data_interface_cls = EthoVisionTrackInterface
    save_directory = OUTPUT_PATH

    expected_session_start_time = datetime(2022, 1, 25, 19, 38, 10)
    # Timestamps come from `Trial time`, the clock every Track of the run shares. It starts at the header's
    # `Recording after` delay, where `Recording time` would start at 0, so a nonzero value tells the clocks apart.
    expected_first_timestamp = 1.067
    expected_number_of_samples = 9080
    expected_number_of_missing_positions = 0
    expected_position_unit = "cm"
    expected_available_tracks = [{"arena_name": "Arena 1", "subject_name": "Subject 1"}]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == self.expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        position = behavior_module["EthoVisionPositionArena1Subject1"]
        assert position.data.shape == (self.expected_number_of_samples, 2)
        assert np.isnan(position.data[:]).any(axis=1).sum() == self.expected_number_of_missing_positions
        assert position.unit == self.expected_position_unit
        assert position.get_starting_time() == self.expected_first_timestamp

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
            *expected_channel_names,
        }
        assert not nwbfile.events

    def test_available_tracks(self):
        assert EthoVisionTrackInterface.get_available_tracks(self.file_path) == self.expected_available_tracks


class TestEthoVisionMissingSamples(DataInterfaceTestMixin):
    """A public CC0 file with the real 'subject not found' `-` sentinel and no Manual Scoring sheet.

    Two subjects share the workbook (`Track-Rat Arena 1a-Subject 1/2`); this interface selects
    one of them. The arena label contains spaces and does not start with the word "Arena", which
    the sheet-name pattern has to accept.
    """

    file_path = (
        ETHOVISION_FOLDER_PATH
        / "excel/single_arena_multiple_subjects/hardware_and_trial_control/two_subjects_missing_samples.xlsx"
    )
    interface_kwargs = dict(
        file_path=file_path,
        arena_name="Rat Arena 1a",
        subject_name="Subject 1",
    )
    data_interface_cls = EthoVisionTrackInterface
    save_directory = OUTPUT_PATH

    expected_session_start_time = datetime(2023, 3, 22, 14, 30, 22, 300000)
    expected_first_timestamp = 6.92
    expected_number_of_samples = 552
    expected_number_of_missing_positions = 63
    expected_position_unit = "cm"
    expected_available_tracks = [
        {"arena_name": "Rat Arena 1a", "subject_name": "Subject 1"},
        {"arena_name": "Rat Arena 1a", "subject_name": "Subject 2"},
    ]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == self.expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        position = behavior_module["EthoVisionPositionRatArena1aSubject1"]
        assert position.data.shape == (self.expected_number_of_samples, 2)
        assert np.isnan(position.data[:]).any(axis=1).sum() == self.expected_number_of_missing_positions
        assert position.unit == self.expected_position_unit
        assert position.get_starting_time() == self.expected_first_timestamp

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
        # 'Control' is never populated anywhere in this sheet: the source spreadsheet stores no
        # cell at all for it on any row, rather than a stored 0 or a '-' sentinel, so every row
        # comes back shorter than the declared column count for this channel specifically.
        control = behavior_module["EthoVisionControlRatArena1aSubject1"].data[:]
        assert np.isnan(control).all()

    def test_available_tracks(self):
        assert EthoVisionTrackInterface.get_available_tracks(self.file_path) == self.expected_available_tracks


class TestEthoVisionCommaDelimitedTxt(DataInterfaceTestMixin):
    file_path = ETHOVISION_FOLDER_PATH / "txt/single_arena_single_subject/comma_delimited/morris_water_maze.txt"
    interface_kwargs = dict(file_path=file_path)
    data_interface_cls = EthoVisionTrackInterface
    save_directory = OUTPUT_PATH

    expected_session_start_time = datetime(2016, 2, 8, 11, 3, 52, 355000)
    expected_first_timestamp = 9.92
    expected_number_of_samples = 3001
    # `-` where EthoVision lost the subject, in three short gaps (the header's "Subject not found 0.4 %").
    expected_number_of_missing_positions = 13
    expected_position_unit = "cm"
    expected_available_tracks = [{"arena_name": "Arena 1", "subject_name": "Subject 1"}]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == self.expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        position = behavior_module["EthoVisionPositionArena1Subject1"]
        assert position.data.shape == (self.expected_number_of_samples, 2)
        assert np.isnan(position.data[:]).any(axis=1).sum() == self.expected_number_of_missing_positions
        assert position.unit == self.expected_position_unit
        assert position.get_starting_time() == self.expected_first_timestamp

        expected_names = {
            "EthoVisionPositionArena1Subject1",
            "EthoVisionAreaArena1Subject1",
            "EthoVisionAreachangeArena1Subject1",
            "EthoVisionElongationArena1Subject1",
            "EthoVisionDistanceMovedArena1Subject1",
            "EthoVisionVelocityArena1Subject1",
            "EthoVisionInZoneArenaCenterPointArena1Subject1",
            "EthoVisionInZonePeripheryCenterPointArena1Subject1",
            "EthoVisionInZoneTarget1CenterPointArena1Subject1",
            "EthoVisionInZoneTargetQCenterPointArena1Subject1",
            "EthoVisionInZoneA1CenterPointArena1Subject1",
            "EthoVisionInZoneOpqCenterPointArena1Subject1",
            "EthoVisionInZoneA2CenterPointArena1Subject1",
            "EthoVisionMovementMovingCenterPointArena1Subject1",
            "EthoVisionMovementNotMovingCenterPointArena1Subject1",
            "EthoVisionDistanceToPointArena1Subject1",
            "EthoVisionResult1Arena1Subject1",
        }
        assert set(behavior_module.data_interfaces) == expected_names

    def test_available_tracks(self):
        assert EthoVisionTrackInterface.get_available_tracks(self.file_path) == self.expected_available_tracks


class TestEthoVisionUtf16Txt(DataInterfaceTestMixin):
    """A text export in UTF-16LE with a byte order mark, EthoVision's default "Unicode text" export."""

    file_path = ETHOVISION_FOLDER_PATH / "txt/single_arena_single_subject/utf16_encoded/track.txt"
    interface_kwargs = dict(file_path=file_path)
    data_interface_cls = EthoVisionTrackInterface
    save_directory = OUTPUT_PATH

    expected_session_start_time = datetime(2017, 4, 11, 16, 22, 36, 333000)
    expected_first_timestamp = 1.599
    expected_number_of_samples = 2000
    expected_number_of_missing_positions = 63
    expected_position_unit = "cm"
    expected_available_tracks = [{"arena_name": "Arena 1", "subject_name": "Subject 1"}]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == self.expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        position = behavior_module["EthoVisionPositionArena1Subject1"]
        assert position.data.shape == (self.expected_number_of_samples, 2)
        assert np.isnan(position.data[:]).any(axis=1).sum() == self.expected_number_of_missing_positions
        assert position.unit == self.expected_position_unit
        assert position.get_starting_time() == self.expected_first_timestamp
        assert behavior_module["EthoVisionVelocityArena1Subject1"].unit == "cm/s"

    def test_available_tracks(self):
        assert EthoVisionTrackInterface.get_available_tracks(self.file_path) == self.expected_available_tracks


class TestEthoVisionDecimalCommaHeaderTxt(DataInterfaceTestMixin):
    """A complete CP1252 text export whose header follows a decimal-comma locale while its data uses periods.

    The header writes `17/03/2015 18:52:43,2` (day first) and `Subject not found: 16,5 %`, and every line ends
    with a trailing `;`.
    """

    file_path = ETHOVISION_FOLDER_PATH / "txt/single_arena_single_subject/track_only/termites.txt"
    interface_kwargs = dict(file_path=file_path)
    data_interface_cls = EthoVisionTrackInterface
    save_directory = OUTPUT_PATH

    expected_session_start_time = datetime(2015, 3, 17, 18, 52, 43, 200000)
    expected_first_timestamp = 1.501
    expected_number_of_samples = 2000
    expected_number_of_missing_positions = 1
    expected_position_unit = "mm"
    expected_available_tracks = [{"arena_name": "Arena 2", "subject_name": "Subject 1"}]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == self.expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        position = behavior_module["EthoVisionPositionArena2Subject1"]
        assert position.data.shape == (self.expected_number_of_samples, 2)
        assert np.isnan(position.data[:]).any(axis=1).sum() == self.expected_number_of_missing_positions
        assert position.unit == self.expected_position_unit
        assert position.get_starting_time() == self.expected_first_timestamp
        assert position.description == (
            "Center position for Subject 1 in Arena 2, from EthoVision. EthoVision header: Missed samples 0,0 %, "
            "Subject not found 16,5 %."
        )
        assert set(behavior_module.data_interfaces) == {
            "EthoVisionPositionArena2Subject1",
            "EthoVisionAreaArena2Subject1",
            "EthoVisionAreachangeArena2Subject1",
            "EthoVisionElongationArena2Subject1",
            "EthoVisionDistanceMovedArena2Subject1",
            "EthoVisionVelocityArena2Subject1",
            "EthoVisionResult1Arena2Subject1",
        }

    def test_available_tracks(self):
        assert EthoVisionTrackInterface.get_available_tracks(self.file_path) == self.expected_available_tracks


class TestEthoVisionCustomMissingValueMarker(DataInterfaceTestMixin):
    """A public CC0 export written with `NA` as its missing-value marker, whose zone labels clash.

    `Zone1(Zone 1 / Center-point)` and `Zone1(Zone-1 / Center-point)` are two zones whose labels differ only by
    punctuation, so they convert to the same name; the second is numbered, and likewise for `Zone2`.
    """

    file_path = (
        ETHOVISION_FOLDER_PATH
        / "excel/single_arena_single_subject/custom_missing_value_marker/missing_values_as_na.xlsx"
    )
    interface_kwargs = dict(file_path=file_path, missing_value_representation="NA")
    data_interface_cls = EthoVisionTrackInterface
    save_directory = OUTPUT_PATH

    expected_session_start_time = datetime(2022, 9, 3, 16, 30, 44, 40000)
    expected_first_timestamp = 0.0
    expected_number_of_samples = 3011
    expected_number_of_missing_positions = 48
    expected_position_unit = "cm"
    expected_available_tracks = [{"arena_name": "Arena 1", "subject_name": "Subject 1"}]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == self.expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]

        position = behavior_module["EthoVisionPositionArena1Subject1"]
        assert position.data.shape == (self.expected_number_of_samples, 2)
        assert np.isnan(position.data[:]).any(axis=1).sum() == self.expected_number_of_missing_positions
        assert position.unit == self.expected_position_unit
        assert position.get_starting_time() == self.expected_first_timestamp
        assert position.description == (
            "Center position for Subject 1 in Arena 1, from EthoVision. EthoVision header: Missed samples 0.0 %, "
            "Subject not found 87.9 %, Interpolated samples 0.0 %."
        )

        missing_value_count = sum(
            int(np.isnan(series.data[:]).sum()) for series in behavior_module.data_interfaces.values()
        )
        assert missing_value_count == 9279

        zone_1 = behavior_module["EthoVisionZone1Zone1CenterPointArena1Subject1"]
        zone_1_hyphenated = behavior_module["EthoVisionZone1Zone1CenterPoint2Arena1Subject1"]
        assert zone_1.description == "'Zone1(Zone 1 / Center-point)' channel from an EthoVision Track sheet."
        assert zone_1_hyphenated.description == "'Zone1(Zone-1 / Center-point)' channel from an EthoVision Track sheet."
        # Each zone channel flags, per sample, whether the fish was in that zone (1) or not (0). The fish entered
        # the first Zone 1 in 36 samples and the hyphenated one never, so the numbered channel holds its own
        # column's data rather than a copy of the first.
        samples_in_zone_1 = np.nansum(zone_1.data[:])
        samples_in_zone_1_hyphenated = np.nansum(zone_1_hyphenated.data[:])
        assert samples_in_zone_1 == 36
        assert samples_in_zone_1_hyphenated == 0
        assert "EthoVisionZone2Zone2CenterPoint2Arena1Subject1" in behavior_module.data_interfaces

    def test_available_tracks(self):
        assert EthoVisionTrackInterface.get_available_tracks(self.file_path) == self.expected_available_tracks


class TestEthoVisionUndetectedSubject(DataInterfaceTestMixin):
    """A subject EthoVision never located: its Track is `-` in every row of every measured channel.

    The header still reports `Subject not found: 96.1 %`, which the description keeps as written.
    """

    file_path = (
        ETHOVISION_FOLDER_PATH
        / "excel/single_arena_multiple_subjects/undetected_subject/one_subject_never_detected.xlsx"
    )
    interface_kwargs = dict(file_path=file_path, arena_name="Arena 1", subject_name="Subject 2")
    data_interface_cls = EthoVisionTrackInterface
    save_directory = OUTPUT_PATH

    expected_session_start_time = datetime(2020, 2, 18, 13, 58, 19, 640000)
    expected_first_timestamp = 0.0
    expected_number_of_samples = 2138
    expected_number_of_missing_positions = 2138
    expected_position_unit = "cm"
    expected_available_tracks = [
        {"arena_name": "Arena 1", "subject_name": "Subject 1"},
        {"arena_name": "Arena 1", "subject_name": "Subject 2"},
    ]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == self.expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        position = behavior_module["EthoVisionPositionArena1Subject2"]
        assert position.data.shape == (self.expected_number_of_samples, 2)
        assert np.isnan(position.data[:]).any(axis=1).sum() == self.expected_number_of_missing_positions
        assert position.unit == self.expected_position_unit
        assert position.get_starting_time() == self.expected_first_timestamp
        assert position.description == (
            "Center position for Subject 2 in Arena 1, from EthoVision. EthoVision header: Missed samples 0.0 %, "
            "Subject not found 96.1 %, Interpolated samples 0.0 %."
        )
        for name, series in behavior_module.data_interfaces.items():
            if name != "EthoVisionResult1Arena1Subject2":
                assert np.isnan(series.data[:]).all(), name
        assert not np.isnan(behavior_module["EthoVisionResult1Arena1Subject2"].data[:]).any()

    def test_available_tracks(self):
        assert EthoVisionTrackInterface.get_available_tracks(self.file_path) == self.expected_available_tracks


class TestEthoVisionMultipleArenasOneSubjectEach(DataInterfaceTestMixin):
    file_path = (
        ETHOVISION_FOLDER_PATH / "excel/multiple_arenas_one_subject_each/track_only/two_arenas_one_subject_each.xlsx"
    )
    interface_kwargs = dict(file_path=file_path, arena_name="Arena 2", subject_name="Subject 1")
    data_interface_cls = EthoVisionTrackInterface
    save_directory = OUTPUT_PATH

    expected_session_start_time = datetime(2017, 10, 19, 13, 35, 57, 494000)
    expected_first_timestamp = 0.0
    expected_number_of_samples = 120
    expected_number_of_missing_positions = 0
    expected_position_unit = "cm"
    expected_available_tracks = [
        {"arena_name": "Arena 1", "subject_name": "Subject 1"},
        {"arena_name": "Arena 2", "subject_name": "Subject 1"},
    ]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == self.expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        position = nwbfile.processing["behavior"]["EthoVisionPositionArena2Subject1"]
        assert position.data.shape == (self.expected_number_of_samples, 2)
        assert np.isnan(position.data[:]).any(axis=1).sum() == self.expected_number_of_missing_positions
        assert position.unit == self.expected_position_unit
        assert position.get_starting_time() == self.expected_first_timestamp

    def test_available_tracks(self):
        assert EthoVisionTrackInterface.get_available_tracks(self.file_path) == self.expected_available_tracks


class TestEthoVisionMultipleArenasMultipleSubjects(DataInterfaceTestMixin):
    file_path = (
        ETHOVISION_FOLDER_PATH / "excel/multiple_arenas_multiple_subjects/track_only/two_arenas_four_subjects_each.xlsx"
    )
    interface_kwargs = dict(file_path=file_path, arena_name="Arena 2", subject_name="Subject 4")
    data_interface_cls = EthoVisionTrackInterface
    save_directory = OUTPUT_PATH

    expected_session_start_time = datetime(2017, 9, 14, 10, 36, 33)
    expected_first_timestamp = 1.066
    expected_number_of_samples = 120
    expected_number_of_missing_positions = 8
    expected_position_unit = "cm"
    expected_available_tracks = [
        {"arena_name": "Arena 1", "subject_name": "Subject 1"},
        {"arena_name": "Arena 1", "subject_name": "Subject 2"},
        {"arena_name": "Arena 1", "subject_name": "Subject 3"},
        {"arena_name": "Arena 1", "subject_name": "Subject 4"},
        {"arena_name": "Arena 2", "subject_name": "Subject 1"},
        {"arena_name": "Arena 2", "subject_name": "Subject 2"},
        {"arena_name": "Arena 2", "subject_name": "Subject 3"},
        {"arena_name": "Arena 2", "subject_name": "Subject 4"},
    ]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == self.expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        position = nwbfile.processing["behavior"]["EthoVisionPositionArena2Subject4"]
        assert position.data.shape == (self.expected_number_of_samples, 2)
        assert np.isnan(position.data[:]).any(axis=1).sum() == self.expected_number_of_missing_positions
        assert position.unit == self.expected_position_unit
        assert position.get_starting_time() == self.expected_first_timestamp

    def test_available_tracks(self):
        assert EthoVisionTrackInterface.get_available_tracks(self.file_path) == self.expected_available_tracks


class TestEthoVisionEdgeCases:
    """Errors, warnings and options that the round trips above do not exercise.

    A plain grouping class: each case reads a published fixture, or a copy rewritten here, to reach one error
    path, warning or argument rather than to convert a new layout.
    """

    def test_remap_times_moves_the_track(self):
        interface = EthoVisionTrackInterface(file_path=TestEthoVisionTrackAndManualScoring.file_path)
        interface.alignment.remap_times(
            local_sync_times=np.array([0.0, 200.0]),
            reference_sync_times=np.array([10.0, 410.0]),
        )

        nwbfile = interface.create_nwbfile()

        position = nwbfile.processing["behavior"]["EthoVisionPositionArena1Subject1"]
        assert np.isclose(position.timestamps[0], 12.134)
        assert np.isclose(position.timestamps[1] - position.timestamps[0], 0.066)

    def test_metadata_propagation(self):
        file_path = TestEthoVisionMissingSamples.file_path
        interface = EthoVisionTrackInterface(
            file_path=file_path,
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

        nwbfile = interface.create_nwbfile(metadata=metadata)

        behavior_module = nwbfile.processing["behavior"]
        assert "MouseOneCenter" in behavior_module.data_interfaces
        assert "MouseOneControl" in behavior_module.data_interfaces

    def test_interface_requires_one_track(self):
        file_path = TestEthoVisionMissingSamples.file_path
        expected_error = (
            f"arena_name=None, subject_name=None does not identify one Track in '{file_path}'. "
            "Matching tracks: [('Rat Arena 1a', 'Subject 1'), ('Rat Arena 1a', 'Subject 2')]."
        )
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            EthoVisionTrackInterface(file_path=file_path)

    def test_interface_rejects_a_nonexistent_track_identity(self):
        file_path = TestEthoVisionMissingSamples.file_path
        expected_error = (
            "No EthoVision Track matches arena_name='Rat Arena 1a', subject_name='Subject 3' "
            f"in '{file_path}'. Available tracks: "
            "[('Rat Arena 1a', 'Subject 1'), ('Rat Arena 1a', 'Subject 2')]."
        )
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            EthoVisionTrackInterface(
                file_path=file_path,
                arena_name="Rat Arena 1a",
                subject_name="Subject 3",
            )

    def test_clashing_channel_names_warn(self):
        expected_warning = (
            "EthoVision channels ['Zone1(Zone 1 / Center-point)', 'Zone1(Zone-1 / Center-point)'] all convert to the "
            "name 'zone1_zone_1_center_point', so they are numbered in column order: "
            "'Zone1(Zone 1 / Center-point)' -> 'zone1_zone_1_center_point', "
            "'Zone1(Zone-1 / Center-point)' -> 'zone1_zone_1_center_point_2'."
        )
        with pytest.warns(UserWarning, match=re.escape(expected_warning)):
            EthoVisionTrackInterface(**TestEthoVisionCustomMissingValueMarker.interface_kwargs)

    def test_hardware_export_is_not_a_track(self):
        """A Hardware export carries the time columns but no tracked positions."""
        file_path = ETHOVISION_FOLDER_PATH / "txt/single_arena_single_subject/hardware_only/hardware_events.txt"
        expected_error = (
            "'hardware_events.txt' is not a Track export; missing columns: ['X center', 'Y center']. "
            "Hardware and Trial Control exports share the time columns but hold no tracked positions."
        )
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            EthoVisionTrackInterface.get_available_tracks(file_path)

    def test_incorrect_missing_value_representation(self):
        """A marker other than the one passed raises an error that names the argument to set."""
        file_path = TestEthoVisionCustomMissingValueMarker.file_path
        expected_error = (
            "Could not parse the Track value 'NA' as a number. If the export marks missing values with 'NA', "
            "pass missing_value_representation='NA' (currently '-')."
        )
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            EthoVisionTrackInterface(file_path=file_path)

    def test_uncommon_delimiter_must_be_passed(self, tmp_path):
        """A delimiter outside the detected candidates raises without ``delimiter`` and reads with it."""
        source_path = ETHOVISION_FOLDER_PATH / "txt/single_arena_single_subject/comma_delimited/morris_water_maze.txt"
        file_path = tmp_path / "morris_water_maze_pipe_delimited.txt"
        file_path.write_text(source_path.read_text(encoding="utf-8-sig").replace(",", "|"), encoding="utf-8-sig")

        expected_error = (
            f"Could not determine the delimiter used by '{file_path}'. Pass the character the export "
            "separates columns with as delimiter."
        )
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            EthoVisionTrackInterface(file_path=file_path)

        assert EthoVisionTrackInterface.get_available_tracks(file_path, delimiter="|") == (
            EthoVisionTrackInterface.get_available_tracks(source_path)
        )

        comma_nwbfile = EthoVisionTrackInterface(file_path=source_path).create_nwbfile()
        pipe_nwbfile = EthoVisionTrackInterface(file_path=file_path, delimiter="|").create_nwbfile()
        comma_series = comma_nwbfile.processing["behavior"].data_interfaces
        pipe_series = pipe_nwbfile.processing["behavior"].data_interfaces
        assert set(pipe_series) == set(comma_series)
        for name, series in comma_series.items():
            np.testing.assert_array_equal(pipe_series[name].data, series.data)

    def test_track_without_samples_is_listed_but_raises(self):
        """A Track whose acquisition never started is declared in the export, so it is listed but cannot be converted."""
        file_path = ETHOVISION_FOLDER_PATH / "excel/single_arena_multiple_subjects/no_data/two_subjects_no_data.xlsx"
        expected_tracks = [
            {"arena_name": "Rat Arena 1a", "subject_name": "Subject 1"},
            {"arena_name": "Rat Arena 1a", "subject_name": "Subject 2"},
        ]
        assert EthoVisionTrackInterface.get_available_tracks(file_path) == expected_tracks

        expected_error = (
            "Track 'Rat Arena 1a' / 'Subject 1' in 'Track-Rat Arena 1a-Subject 1' logged no samples "
            "('No samples logged for this track!'). The trial was recorded but acquisition never started, so there is "
            "nothing to convert."
        )
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            EthoVisionTrackInterface(file_path=file_path, arena_name="Rat Arena 1a", subject_name="Subject 1")
