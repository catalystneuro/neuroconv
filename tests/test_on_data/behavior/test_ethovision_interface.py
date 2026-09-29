"""Tests for EthoVisionDataInterface."""

import re
from datetime import datetime, timezone

import numpy as np
import pytest
from pynwb import NWBFile, read_nwb

from neuroconv.datainterfaces.behavior.ethovision.ethovisiondatainterface import EthoVisionDataInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH

ETHOVISION_FOLDER_PATH = BEHAVIOR_DATA_PATH / "ethovision"


class TestEthoVisionTrackAndManualScoring(DataInterfaceTestMixin):
    """The `two_c57` stub: one subject, one arena, a Manual Scoring sheet with point and state events."""

    FILE_PATH = ETHOVISION_FOLDER_PATH / "excel/single_arena_single_subject/track_and_manual_scoring/two_c57.xlsx"
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
        assert np.isclose(position.timestamps[0], 12.134)
        assert np.isclose(position.timestamps[1] - position.timestamps[0], 0.066)

        events = nwbfile.events["EthoVisionManualScoringArena1"].to_dataframe()
        first_sniff = events[events["event_type"] == "Sniff"].iloc[0]
        assert np.isclose(first_sniff["timestamp"], 112.6)
        assert np.isclose(first_sniff["duration"], 6.134)

        bouts = nwbfile.processing["behavior"]["EthoVisionEthogramBoutsArena1"].to_dataframe()
        first_sniff_bout = bouts[bouts["label"] == "Sniff"].iloc[0]
        assert np.isclose(first_sniff_bout["start_time"], 112.6)
        assert np.isclose(first_sniff_bout["stop_time"], 118.734)


class TestEthoVisionMissingSamples(DataInterfaceTestMixin):
    """A public CC0 file with the real 'subject not found' `-` sentinel and no Manual Scoring sheet.

    Two subjects share the workbook (`Track-Rat Arena 1a-Subject 1/2`); this interface selects
    one of them. The arena label contains spaces and does not start with the word "Arena", which
    the sheet-name pattern has to accept.
    """

    FILE_PATH = (
        ETHOVISION_FOLDER_PATH
        / "excel/single_arena_multiple_subjects/hardware_and_trial_control/two_subjects_missing_samples.xlsx"
    )
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


class TestEthoVisionCommaDelimitedTxt(DataInterfaceTestMixin):
    FILE_PATH = ETHOVISION_FOLDER_PATH / "txt/single_arena_single_subject/comma_delimited/morris_water_maze.txt"
    data_interface_cls = EthoVisionDataInterface
    interface_kwargs = dict(file_path=FILE_PATH)
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2016, 2, 8, 11, 3, 52, 355000)

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]

        position = behavior_module["EthoVisionPositionArena1Subject1"]
        assert position.data.shape == (3001, 2)
        assert position.unit == "cm"
        assert np.isnan(position.data[:, 0]).sum() == 13
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
        expected_tracks = [{"arena_name": "Arena 1", "subject_name": "Subject 1"}]
        assert EthoVisionDataInterface.get_available_tracks(self.FILE_PATH) == expected_tracks


class TestEthoVisionUtf16Txt(DataInterfaceTestMixin):
    """A text export in UTF-16LE with a byte order mark, EthoVision's default "Unicode text" export."""

    FILE_PATH = ETHOVISION_FOLDER_PATH / "txt/single_arena_single_subject/utf16_encoded/track.txt"
    data_interface_cls = EthoVisionDataInterface
    interface_kwargs = dict(file_path=FILE_PATH)
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2017, 4, 11, 16, 22, 36, 333000)

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        position = behavior_module["EthoVisionPositionArena1Subject1"]
        assert position.data.shape == (2000, 2)
        assert position.unit == "cm"
        assert position.timestamps[0] == 1.599
        assert np.isnan(position.data[:, 0]).sum() == 63
        assert behavior_module["EthoVisionVelocityArena1Subject1"].unit == "cm/s"

    def test_available_tracks(self):
        expected_tracks = [{"arena_name": "Arena 1", "subject_name": "Subject 1"}]
        assert EthoVisionDataInterface.get_available_tracks(self.FILE_PATH) == expected_tracks


class TestEthoVisionDecimalCommaHeaderTxt(DataInterfaceTestMixin):
    """A complete CP1252 text export whose header follows a decimal-comma locale while its data uses periods.

    The header writes `17/03/2015 18:52:43,2` (day first) and `Subject not found: 16,5 %`, and every line ends
    with a trailing `;`.
    """

    FILE_PATH = ETHOVISION_FOLDER_PATH / "txt/single_arena_single_subject/track_only/termites.txt"
    data_interface_cls = EthoVisionDataInterface
    interface_kwargs = dict(file_path=FILE_PATH)
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2015, 3, 17, 18, 52, 43, 200000)

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        position = behavior_module["EthoVisionPositionArena2Subject1"]
        assert position.data.shape == (2000, 2)
        assert position.unit == "mm"
        assert position.timestamps[0] == 1.501
        assert np.isnan(position.data[:, 0]).sum() == 1
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
        expected_tracks = [{"arena_name": "Arena 2", "subject_name": "Subject 1"}]
        assert EthoVisionDataInterface.get_available_tracks(self.FILE_PATH) == expected_tracks


class TestEthoVisionCustomMissingValueMarker(DataInterfaceTestMixin):
    """A public CC0 export written with `NA` as its missing-value marker, whose zone labels clash.

    `Zone1(Zone 1 / Center-point)` and `Zone1(Zone-1 / Center-point)` are two zones whose labels differ only by
    punctuation, so they convert to the same name; the second is numbered, and likewise for `Zone2`.
    """

    FILE_PATH = (
        ETHOVISION_FOLDER_PATH
        / "excel/single_arena_single_subject/custom_missing_value_marker/missing_values_as_na.xlsx"
    )
    data_interface_cls = EthoVisionDataInterface
    interface_kwargs = dict(file_path=FILE_PATH, missing_value_representation="NA")
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2022, 9, 3, 16, 30, 44, 40000)

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]

        position = behavior_module["EthoVisionPositionArena1Subject1"]
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
        assert np.nansum(zone_1.data[:]) == 36
        assert np.nansum(zone_1_hyphenated.data[:]) == 0
        assert "EthoVisionZone2Zone2CenterPoint2Arena1Subject1" in behavior_module.data_interfaces

    def test_clashing_channel_names_warn(self):
        expected_warning = (
            "EthoVision channels ['Zone1(Zone 1 / Center-point)', 'Zone1(Zone-1 / Center-point)'] all convert to the "
            "name 'zone1_zone_1_center_point', so they are numbered in column order: "
            "'Zone1(Zone 1 / Center-point)' -> 'zone1_zone_1_center_point', "
            "'Zone1(Zone-1 / Center-point)' -> 'zone1_zone_1_center_point_2'."
        )
        with pytest.warns(UserWarning, match=re.escape(expected_warning)):
            EthoVisionDataInterface(**self.interface_kwargs)


class TestEthoVisionUndetectedSubject(DataInterfaceTestMixin):
    """A subject EthoVision never located: its Track is `-` in every row of every measured channel.

    The header still reports `Subject not found: 96.1 %`, which the description keeps as written.
    """

    FILE_PATH = (
        ETHOVISION_FOLDER_PATH
        / "excel/single_arena_multiple_subjects/undetected_subject/one_subject_never_detected.xlsx"
    )
    data_interface_cls = EthoVisionDataInterface
    interface_kwargs = dict(file_path=FILE_PATH, arena_name="Arena 1", subject_name="Subject 2")
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2020, 2, 18, 13, 58, 19, 640000)

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        position = behavior_module["EthoVisionPositionArena1Subject2"]
        assert position.data.shape == (2138, 2)
        assert np.isnan(position.data[:]).all()
        assert position.description == (
            "Center position for Subject 2 in Arena 1, from EthoVision. EthoVision header: Missed samples 0.0 %, "
            "Subject not found 96.1 %, Interpolated samples 0.0 %."
        )
        for name, series in behavior_module.data_interfaces.items():
            if name != "EthoVisionResult1Arena1Subject2":
                assert np.isnan(series.data[:]).all(), name
        assert not np.isnan(behavior_module["EthoVisionResult1Arena1Subject2"].data[:]).any()

    def test_available_tracks(self):
        expected_tracks = [
            {"arena_name": "Arena 1", "subject_name": "Subject 1"},
            {"arena_name": "Arena 1", "subject_name": "Subject 2"},
        ]
        assert EthoVisionDataInterface.get_available_tracks(self.FILE_PATH) == expected_tracks


class TestEthoVisionMultipleArenasOneSubjectEach(DataInterfaceTestMixin):
    FILE_PATH = (
        ETHOVISION_FOLDER_PATH / "excel/multiple_arenas_one_subject_each/track_only/two_arenas_one_subject_each.xlsx"
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
        ETHOVISION_FOLDER_PATH / "excel/multiple_arenas_multiple_subjects/track_only/two_arenas_four_subjects_each.xlsx"
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


def test_hardware_export_is_not_a_track():
    """A Hardware export carries the time columns but no tracked positions."""
    file_path = ETHOVISION_FOLDER_PATH / "txt/single_arena_single_subject/hardware_only/hardware_events.txt"
    expected_error = (
        "'hardware_events.txt' is not a Track export; missing columns: ['X center', 'Y center']. "
        "Hardware and Trial Control exports share the time columns but hold no tracked positions."
    )
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        EthoVisionDataInterface.get_available_tracks(file_path)


def _write_behavior_series(interface) -> dict[str, np.ndarray]:
    """Write one interface to an in-memory NWB file and return its behavior series data by name."""
    nwbfile = NWBFile(
        session_description="ethovision test",
        identifier="ethovision test",
        session_start_time=datetime.now(timezone.utc),
    )
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
    return {name: np.asarray(series.data) for name, series in nwbfile.processing["behavior"].data_interfaces.items()}


def test_missing_value_representation_names_an_unparsed_marker():
    """A marker other than the one passed raises an error that names the argument to set."""
    file_path = TestEthoVisionCustomMissingValueMarker.FILE_PATH
    expected_error = (
        "Could not parse the Track value 'NA' as a number. If the export marks missing values with 'NA', "
        "pass missing_value_representation='NA' (currently '-')."
    )
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        EthoVisionDataInterface(file_path=file_path)


def test_delimiter_reads_an_undetected_delimiter(tmp_path):
    """A delimiter outside the detected candidates raises without ``delimiter`` and reads with it."""
    source_path = ETHOVISION_FOLDER_PATH / "txt/single_arena_single_subject/comma_delimited/morris_water_maze.txt"
    file_path = tmp_path / "morris_water_maze_pipe_delimited.txt"
    file_path.write_text(source_path.read_text(encoding="utf-8-sig").replace(",", "|"), encoding="utf-8-sig")

    expected_error = (
        f"Could not determine the delimiter used by '{file_path}'. Pass the character the export "
        "separates columns with as delimiter."
    )
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        EthoVisionDataInterface(file_path=file_path)

    assert EthoVisionDataInterface.get_available_tracks(file_path, delimiter="|") == (
        EthoVisionDataInterface.get_available_tracks(source_path)
    )
    comma_series = _write_behavior_series(EthoVisionDataInterface(file_path=source_path))
    pipe_series = _write_behavior_series(EthoVisionDataInterface(file_path=file_path, delimiter="|"))
    assert set(pipe_series) == set(comma_series)
    for name, data in comma_series.items():
        np.testing.assert_array_equal(pipe_series[name], data)


def test_track_without_samples_is_listed_but_raises():
    """A Track whose acquisition never started is declared in the export, so it is listed but cannot be converted."""
    file_path = ETHOVISION_FOLDER_PATH / "excel/single_arena_multiple_subjects/no_data/two_subjects_no_data.xlsx"
    expected_tracks = [
        {"arena_name": "Rat Arena 1a", "subject_name": "Subject 1"},
        {"arena_name": "Rat Arena 1a", "subject_name": "Subject 2"},
    ]
    assert EthoVisionDataInterface.get_available_tracks(file_path) == expected_tracks

    expected_error = (
        "Track 'Rat Arena 1a' / 'Subject 1' in 'Track-Rat Arena 1a-Subject 1' logged no samples "
        "('No samples logged for this track!'). The trial was recorded but acquisition never started, so there is "
        "nothing to convert."
    )
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        EthoVisionDataInterface(file_path=file_path, arena_name="Rat Arena 1a", subject_name="Subject 1")


def test_manual_scoring_reads_the_documented_spellings(tmp_path):
    """The Noldus manuals spell the sheet `Manual scoring - <arena>` and capitalize `State start`; both read the same."""
    import openpyxl

    source_path = ETHOVISION_FOLDER_PATH / "excel/single_arena_single_subject/track_and_manual_scoring/two_c57.xlsx"
    workbook = openpyxl.load_workbook(source_path)
    scoring_sheet = workbook["Manual Scoring-Arena 1"]
    scoring_sheet.title = "Manual scoring - Arena 1"
    for (cell,) in scoring_sheet.iter_rows(min_col=5, max_col=5):
        if cell.value in ("state start", "state stop", "point event"):
            cell.value = cell.value.capitalize()
    file_path = tmp_path / "two_c57_documented_spellings.xlsx"
    workbook.save(file_path)

    def write_events(interface):
        nwbfile = NWBFile(
            session_description="ethovision test",
            identifier="ethovision test",
            session_start_time=datetime.now(timezone.utc),
        )
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
        return nwbfile.events["EthoVisionManualScoringArena1"].to_dataframe()

    source_events = write_events(EthoVisionDataInterface(file_path=source_path))
    documented_events = write_events(EthoVisionDataInterface(file_path=file_path))
    assert len(source_events) == 35
    assert documented_events.equals(source_events)
