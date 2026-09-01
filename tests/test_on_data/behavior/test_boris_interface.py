"""Tests for BORISInterface, one class per project file."""

import json
import re
from datetime import datetime
from pathlib import Path

import pytest
from hdmf.common import VectorIndex
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import BORISInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH

BORIS_PROJECTS_PATH = BEHAVIOR_DATA_PATH / "boris" / "json_project"


class BORISTestMixin(DataInterfaceTestMixin):
    """The assertions true of every BORIS conversion, whatever the project holds.

    Nothing here is parameterised and nothing here is configuration. Each test class states its own
    interface, its own file and its own expectations; this only adds the checks that hold for all of
    them, and a subclass runs them by calling ``super().check_read_nwb`` before its own.
    """

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]

        # A modifier cell is the values ticked in one slot, so it is a list: several where the slot takes
        # several, one where it takes one, and empty where the behavior does not own that column, which
        # is the only fill a ragged column can take.
        for events_table in nwbfile.events.values():
            frame = events_table.to_dataframe()
            modifier_columns = [name for name in events_table.colnames if name.startswith("modifier_")]
            for column_name in modifier_columns:
                cells = [list(cell) for cell in frame[column_name]]
                are_all_answers_strings = all(isinstance(answer, str) for cell in cells for answer in cell)
                assert are_all_answers_strings

        bouts_tables = [
            container for name, container in behavior_module.data_interfaces.items() if name.endswith("Bouts")
        ]
        behaviors_with_a_bout = set()
        for bouts_table in bouts_tables:
            behaviors_with_a_bout.update(bouts_table.to_dataframe()["label"])

        # The bouts table holds exactly the bouts that closed: a behavior appears there if and only if
        # the events table gave it a duration. A point behavior has none, and a bout whose stop was
        # never scored has NaN, so neither reaches the interval view.
        behaviors_with_a_duration = set()
        for events_table in nwbfile.events.values():
            frame = events_table.to_dataframe()
            if "duration" not in frame.columns:
                continue
            behaviors_with_a_duration.update(frame.loc[frame["duration"].notna(), "event_type"])
        assert behaviors_with_a_bout == behaviors_with_a_duration

        # Every label in a bouts table is a state behavior the catalogue declares, which two BORIS
        # projects written into one file would break.
        catalogue = behavior_module["Ethogram"].to_dataframe()
        declared_state_behaviors = set(catalogue.loc[catalogue["behavior_type"] == "state", "behavior"])
        undeclared_labels = behaviors_with_a_bout - declared_state_behaviors
        assert undeclared_labels == set()

        # A bouts table's `label` holds the same vocabulary as the events table's `event_type`, so it
        # carries the same meanings, taken from the catalogue's `definition`. Only a state behavior can
        # be a bout, so this is the state subset, and an ethogram that describes nothing gets no table.
        expected_meanings = {
            row.behavior: row.definition
            for row in catalogue.itertuples()
            if row.behavior_type == "state" and row.definition
        }
        for bouts_table in bouts_tables:
            meanings_tables = bouts_table.meanings_tables or {}
            if not expected_meanings:
                assert "label_meanings" not in meanings_tables
                continue
            meanings = meanings_tables["label_meanings"]
            written = dict(zip(list(meanings["value"][:]), list(meanings["meaning"][:])))
            assert written == expected_meanings

        # The interval view describes a bout the same way the events table does, so its modifier columns
        # come from there. A subset rather than the same set, because a column no closed bout filled is
        # dropped: its values dataset would carry nothing for hdmf to take a dtype from.
        for bouts_table in bouts_tables:
            events_table = nwbfile.events.get(bouts_table.name.removesuffix("Bouts"))
            if events_table is None:
                continue
            bouts_modifiers = {name for name in bouts_table.colnames if name.startswith("modifier_")}
            events_modifiers = {name for name in events_table.colnames if name.startswith("modifier_")}
            assert bouts_modifiers <= events_modifiers


class TestBORISVersion1_6(BORISTestMixin):
    """Format 1.6: no `category` field on a behavior, and `modifiers` a flat comma-separated string."""

    data_interface_cls = BORISInterface
    conversion_options = dict()  # what is written is set at construction, not at write
    save_directory = OUTPUT_PATH

    file_path = (
        BORIS_PROJECTS_PATH / "version_1_6" / "string_modifiers_no_categories" / "media_and_live_two_subjects.boris"
    )

    interface_kwargs = dict(file_path=file_path, observation_name="media observation")

    def check_read_nwb(self, nwbfile_path: str):
        super().check_read_nwb(nwbfile_path=nwbfile_path)
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]

        events_table = nwbfile.get_events_table("MediaObservation")
        assert len(events_table.id) == 4
        assert tuple(events_table.colnames) == (
            "timestamp",
            "event_type",
            "subject",
            "comment",
            "modifier_forage_1",
            "modifier_groom_1",
            "duration",
        )
        # The whole coding scheme reaches the catalogue, including behaviors nothing was scored against.
        assert len(behavior_module["Ethogram"].to_dataframe()) == 4
        assert len(behavior_module["MediaObservationBouts"].to_dataframe()) == 2

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2016, 1, 2, 9, 0, 0)
        # The observation's block sits under its own key, so several of them do not collide.
        assert metadata["Events"]["EventTables"]["boris_media_observation"] == {
            "table_name": "MediaObservation",
            "description": "Behaviors scored in BORIS observation 'media observation' (media).",
        }

        event_types = metadata["Events"]["boris_media_observation"]["event_types"]
        assert set(event_types) == {"forage", "rest", "groom", "call"}
        # BORIS is one of the few sources carrying its own prose, so every description is reported.
        assert {code: entry["event_description"] for code, entry in event_types.items()} == {
            "forage": "moves over the substrate collecting food",
            "rest": "stationary with the body lowered",
            "groom": "a single grooming bout",
            "call": "a single vocalisation",
        }
        # 1.6 declares its modifiers as one flat string with no slot name, so the column falls back to
        # the slot's position and the vocabulary is the menu plus whatever was recorded.
        assert event_types["forage"]["columns"]["modifier_forage_1"]["column_categories"]["labels"] == {
            "far": "far",
            "near": "near",
            "near (N)": "near (N)",
        }
        assert event_types["rest"]["columns"].keys() == {"subject", "comment"}


class TestBORISVersion4_0(BORISTestMixin):
    """Format 4.0: categories exist, modifiers are still a flat string, and times are in seconds."""

    data_interface_cls = BORISInterface
    conversion_options = dict()  # what is written is set at construction, not at write
    save_directory = OUTPUT_PATH

    file_path = (
        BORIS_PROJECTS_PATH
        / "version_4_0"
        / "string_modifiers_seconds_time_format"
        / "categorized_media_and_live.boris"
    )

    interface_kwargs = dict(file_path=file_path, observation_name="media observation")

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2017, 1, 2, 8, 30, 0)
        assert metadata["Events"]["EventTables"]["boris_media_observation"] == {
            "table_name": "MediaObservation",
            "description": "Behaviors scored in BORIS observation 'media observation' (media).",
        }

        event_types = metadata["Events"]["boris_media_observation"]["event_types"]
        assert set(event_types) == {"walk", "stand", "drink", "peck", "vigilance"}
        # This scheme writes no prose, and the key is omitted rather than filled with an empty string.
        assert all("event_description" not in entry for entry in event_types.values())
        # Every behavior routes into the one table by default.
        assert {entry["table_metadata_key"] for entry in event_types.values()} == {"boris_media_observation"}
        # The menu stripped of its shortcuts, plus what was actually recorded. This observation scores
        # only `slow (S)`, and the generated 4.0 fixture records the shortcut that real BORIS strips.
        assert event_types["walk"]["columns"]["modifier_walk_1"]["column_categories"]["labels"] == {
            "fast": "fast",
            "slow": "slow",
            "slow (S)": "slow (S)",
        }

    def check_read_nwb(self, nwbfile_path: str):
        super().check_read_nwb(nwbfile_path=nwbfile_path)
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]

        events_table = nwbfile.get_events_table("MediaObservation")
        assert len(events_table.id) == 5
        assert tuple(events_table.colnames) == (
            "timestamp",
            "event_type",
            "subject",
            "comment",
            "modifier_walk_1",
            "modifier_peck_1",
            "duration",
        )
        # The whole coding scheme reaches the catalogue, including behaviors nothing was scored against.
        assert len(behavior_module["Ethogram"].to_dataframe()) == 5
        assert len(behavior_module["MediaObservationBouts"].to_dataframe()) == 3

    def run_custom_checks(self):
        interface = BORISInterface(file_path=TestBORISVersion4_0.file_path, observation_name="media observation")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        catalogue = nwbfile.processing["behavior"]["Ethogram"].to_dataframe()
        assert set(catalogue["category"]) == {"Locomotion", "Maintenance", "Social"}


class TestBORISCategorizedEthogram(BORISTestMixin):
    """The BORIS Android demo project: eleven behaviors, of which this observation scores a few."""

    data_interface_cls = BORISInterface
    conversion_options = dict()  # what is written is set at construction, not at write
    save_directory = OUTPUT_PATH

    file_path = (
        BORIS_PROJECTS_PATH
        / "version_7_0"
        / "categorized_ethogram"
        / "mutually_exclusive_behaviors_and_unpaired_starts.boris"
    )

    interface_kwargs = dict(file_path=file_path, observation_name="test1")

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2018, 5, 10, 15, 19, 0)
        assert metadata["Events"]["EventTables"]["boris_test1"] == {
            "table_name": "Test1",
            "description": "Behaviors scored in BORIS observation 'test1' (live).",
        }

        event_types = metadata["Events"]["boris_test1"]["event_types"]
        # Every behavior the scheme declares is an event type, including those nothing was scored
        # against in this observation.
        assert set(event_types) == {
            "groom",
            "run",
            "walk",
            "attack",
            "play",
            "jump",
            "approach",
            "drink",
            "eat",
            "defecate",
            "urinate",
        }
        # This project names neither of its two slots, so both columns fall back to their position.
        assert event_types["walk"]["columns"].keys() == {"subject", "comment", "modifier_walk_1"}
        assert event_types["walk"]["columns"]["modifier_walk_1"]["column_categories"]["labels"] == {
            "bipedal": "bipedal",
            "quadrupedal": "quadrupedal",
        }

    def check_read_nwb(self, nwbfile_path: str):
        super().check_read_nwb(nwbfile_path=nwbfile_path)
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]

        events_table = nwbfile.get_events_table("Test1")
        assert len(events_table.id) == 6
        assert tuple(events_table.colnames) == (
            "timestamp",
            "event_type",
            "subject",
            "comment",
            "modifier_walk_1",
            "duration",
        )
        # The whole coding scheme reaches the catalogue, including behaviors nothing was scored against.
        assert len(behavior_module["Ethogram"].to_dataframe()) == 11
        assert len(behavior_module["Test1Bouts"].to_dataframe()) == 3


class TestBORISModifierSlots(BORISTestMixin):
    """All three modifier slot types. Every behavior scored here is a point behavior, so no bouts."""

    data_interface_cls = BORISInterface
    conversion_options = dict()  # what is written is set at construction, not at write
    save_directory = OUTPUT_PATH

    file_path = (
        BORIS_PROJECTS_PATH
        / "version_7_0"
        / "modifier_slot_types"
        / "single_multiple_numeric_and_point_exclusion.boris"
    )

    interface_kwargs = dict(file_path=file_path, observation_name="1")

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2024, 9, 18, 23, 53, 47)
        assert metadata["Events"]["EventTables"]["boris_1"] == {
            "table_name": "Observation1",
            "description": "Behaviors scored in BORIS observation '1' (live).",
        }

        event_types = metadata["Events"]["boris_1"]["event_types"]
        assert set(event_types) == {"p", "a", "b", "z", "x", "many modifiers", "2 sets", "multiple modif", "numeric"}
        # A behavior declaring two slots gets two columns, each keyed on the behavior so the `set 1`
        # that `multiple modif` also declares does not land on top of this one.
        assert event_types["2 sets"]["columns"].keys() == {
            "subject",
            "comment",
            "modifier_2_sets_set_1",
            "modifier_2_sets_set_2",
        }
        assert event_types["2 sets"]["columns"]["modifier_2_sets_set_2"]["column_categories"]["labels"] == {
            "3": "3",
            "4": "4",
            "5": "5",
        }
        # A free numeric slot offers no menu, so its vocabulary is only what was recorded.
        assert event_types["numeric"]["columns"]["modifier_numeric_numeric_modif"]["column_categories"]["labels"] == {
            "789": "789",
        }

    def check_read_nwb(self, nwbfile_path: str):
        super().check_read_nwb(nwbfile_path=nwbfile_path)
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]

        events_table = nwbfile.get_events_table("Observation1")
        assert len(events_table.id) == 4
        assert tuple(events_table.colnames) == (
            "timestamp",
            "event_type",
            "subject",
            "comment",
            "modifier_many_modifiers_set_1",
            "modifier_2_sets_set_1",
            "modifier_2_sets_set_2",
            "modifier_multiple_modif_set_1",
            "modifier_numeric_numeric_modif",
            "duration",
        )
        # The whole coding scheme reaches the catalogue, including behaviors nothing was scored against.
        assert len(behavior_module["Ethogram"].to_dataframe()) == 9
        # Nothing durative was scored, so there is no interval table to write.
        assert "Observation1Bouts" not in behavior_module.data_interfaces

    def run_custom_checks(self):
        """The recorded forms of the three slot types, each answer in the column of its own slot."""
        interface = BORISInterface(file_path=TestBORISModifierSlots.file_path, observation_name="1")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        table = nwbfile.get_events_table("Observation1").to_dataframe().set_index("event_type")

        # A single selection and a free numeric each answer one slot.
        assert list(table.loc["many modifiers", "modifier_many_modifiers_set_1"]) == ["3"]
        assert list(table.loc["numeric", "modifier_numeric_numeric_modif"]) == ["789"]
        # A multiple selection is several values ticked in *one* slot, and both survive as values rather
        # than as a comma somebody has to know to split.
        assert list(table.loc["multiple modif", "modifier_multiple_modif_set_1"]) == ["1", "2"]
        # Two slots are two columns, which is what the outer split is for: the "|" does not survive.
        assert list(table.loc["2 sets", "modifier_2_sets_set_1"]) == ["2"]
        assert list(table.loc["2 sets", "modifier_2_sets_set_2"]) == ["3"]
        # A column is keyed on the behavior as well as the slot, so `2 sets` and `multiple modif` both
        # declaring a slot called `set 1` get a column each rather than sharing two vocabularies. A
        # behavior writes an empty cell in a column it does not own, never a NaN, which could not share
        # a text column with the answers.
        assert list(table.loc["numeric", "modifier_2_sets_set_1"]) == []
        assert list(table.loc["2 sets", "modifier_multiple_modif_set_1"]) == []

        # The catalogue carries the scheme half: which columns a behavior uses and what they may hold.
        catalogue = nwbfile.processing["behavior"]["Ethogram"].to_dataframe().set_index("behavior")
        # The catalogue names the slots as the scheme names them, not as the columns are named.
        assert list(catalogue.loc["2 sets", "modifiers"]) == ["set 1", "set 2"]
        assert [list(values) for values in catalogue.loc["2 sets", "modifier_values"]] == [
            ["1", "2", "3"],
            ["3", "4", "5"],
        ]
        # A free numeric slot has no menu at all, which is not the same as declaring no slot.
        assert list(catalogue.loc["numeric", "modifiers"]) == ["numeric modif"]
        assert [list(values) for values in catalogue.loc["numeric", "modifier_values"]] == [[]]
        assert list(catalogue.loc["p", "modifiers"]) == []

        # BORIS lets the author write about a modifier set beside its name and its menu, describing the
        # question the set asks rather than the answers it offers. It rides on the catalogue with the
        # names it parallels, and empty where the author wrote nothing.
        assert list(catalogue.loc["2 sets", "modifier_descriptions"]) == ["description set 1", "description set 2"]
        assert list(catalogue.loc["numeric", "modifier_descriptions"]) == ["description numeric modif"]
        assert list(catalogue.loc["p", "modifier_descriptions"]) == []

        # And the events column carries a copy, since a bare EventsTable has no link back to the
        # catalogue, so a reader of the column has no route to the description otherwise. The full stop
        # is put in because the author's note mostly ends without one.
        events_table = nwbfile.get_events_table("Observation1")
        columns = {
            name: (column.target if isinstance(column, VectorIndex) else column).description
            for name, column in ((name, events_table[name]) for name in events_table.colnames)
            if name.startswith("modifier_")
        }
        assert columns["modifier_2_sets_set_1"] == "description set 1. Answered when the behavior was scored."
        assert columns["modifier_numeric_numeric_modif"] == (
            "description numeric modif. Answered when the behavior was scored."
        )


class TestBORISMultiSubject(BORISTestMixin):
    """One observation carrying events from two named subjects, which is why subject is a column."""

    data_interface_cls = BORISInterface
    conversion_options = dict()  # what is written is set at construction, not at write
    save_directory = OUTPUT_PATH

    file_path = (
        BORIS_PROJECTS_PATH
        / "version_7_0"
        / "media_and_live_observations"
        / "two_players_multi_subject_and_an_unclosed_bout.boris"
    )

    interface_kwargs = dict(file_path=file_path, observation_name="observation #1")

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2016, 11, 27, 1, 57, 26)
        assert metadata["Events"]["EventTables"]["boris_observation_1"] == {
            "table_name": "Observation1",
            "description": "Behaviors scored in BORIS observation 'observation #1' (media).",
        }

        event_types = metadata["Events"]["boris_observation_1"]["event_types"]
        assert set(event_types) == {"p", "s", "q", "r", "m"}
        assert {code: entry["event_description"] for code, entry in event_types.items()} == {
            "p": "Test point event",
            "s": "Test state event",
            "q": "point event with 1 set of modifiers",
            "r": "state event with 1 set of modifiers",
            "m": "state event with 2 set of modifiers",
        }
        # `m` declares two slots and this observation scores none of its events, so neither column is
        # written: a ragged column nobody fills has no values for hdmf to take a dtype from. The
        # catalogue still records that the behavior declares them.
        assert event_types["m"]["columns"].keys() == {"subject", "comment"}

    def check_read_nwb(self, nwbfile_path: str):
        super().check_read_nwb(nwbfile_path=nwbfile_path)
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]

        events_table = nwbfile.get_events_table("Observation1")
        assert len(events_table.id) == 4
        assert tuple(events_table.colnames) == (
            "timestamp",
            "event_type",
            "subject",
            "comment",
            "duration",
        )
        # The whole coding scheme reaches the catalogue, including behaviors nothing was scored against.
        assert len(behavior_module["Ethogram"].to_dataframe()) == 5
        assert len(behavior_module["Observation1Bouts"].to_dataframe()) == 4

    def run_custom_checks(self):
        interface = BORISInterface(file_path=TestBORISMultiSubject.file_path, observation_name="observation #1")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        table = nwbfile.get_events_table("Observation1").to_dataframe()
        # Two animals scored in one session. NWB has one Subject per file, so this cannot be that.
        assert set(table["subject"]) == {"subject1", "subject2"}


class TestBORISUntidyModifiers(BORISTestMixin):
    """Untidy declared values and the literal `None` token for a slot nobody answered."""

    data_interface_cls = BORISInterface
    conversion_options = dict()  # what is written is set at construction, not at write
    save_directory = OUTPUT_PATH

    file_path = BORIS_PROJECTS_PATH / "version_7_0" / "untidy_modifier_values" / "whitespace_and_the_none_token.boris"

    interface_kwargs = dict(file_path=file_path, observation_name="test1 live")

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2019, 2, 26, 10, 30, 23)
        assert metadata["Events"]["EventTables"]["boris_test1_live"] == {
            "table_name": "Test1Live",
            "description": "Behaviors scored in BORIS observation 'test1 live' (live).",
        }

        event_types = metadata["Events"]["boris_test1_live"]["event_types"]
        assert set(event_types) == {"p", "r"}
        # The menu reaches the vocabulary with the keyboard shortcut stripped, as BORIS strips it when
        # recording, and the coder's whitespace is preserved on both sides.
        assert event_types["p"]["columns"]["modifier_p_test_1"]["column_categories"]["labels"] == {
            "a   ": "a   ",
            "c  ": "c  ",
            "d": "d",
        }
        # Meanings stay empty because BORIS describes a slot and never its values, and the writer skips
        # the MeaningsTable when nothing is described.
        assert event_types["p"]["columns"]["modifier_p_test_1"]["column_categories"]["meanings"] == {}

    def check_read_nwb(self, nwbfile_path: str):
        super().check_read_nwb(nwbfile_path=nwbfile_path)
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]

        events_table = nwbfile.get_events_table("Test1Live")
        assert len(events_table.id) == 4
        assert tuple(events_table.colnames) == (
            "timestamp",
            "event_type",
            "subject",
            "comment",
            "modifier_p_test_1",
            "modifier_p_test_2",
        )
        # The whole coding scheme reaches the catalogue, including behaviors nothing was scored against.
        assert len(behavior_module["Ethogram"].to_dataframe()) == 2
        # Nothing durative was scored, so there is no interval table to write.
        assert "Test1LiveBouts" not in behavior_module.data_interfaces

    def run_custom_checks(self):
        interface = BORISInterface(file_path=TestBORISUntidyModifiers.file_path, observation_name="test1 live")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        table = nwbfile.get_events_table("Test1Live").to_dataframe()
        # The coder's whitespace is preserved, since the values are free text somebody typed and
        # normalizing them here would invent data. The `None` token is not a value, though: it is what
        # BORIS writes for a slot nobody answered, so it reads as unanswered rather than as the string.
        assert [list(cell) for cell in table["modifier_p_test_1"]] == [["a   "], ["a   "], [], []]
        assert [list(cell) for cell in table["modifier_p_test_2"]] == [["c "], [], ["111"], ["c "]]
        # The declared menu reaches the catalogue with the keyboard shortcut stripped, as BORIS strips it
        # when recording, so "a    (a)" is declared and "a   " is what both the menu and the cell hold.
        catalogue = nwbfile.processing["behavior"]["Ethogram"].to_dataframe().set_index("behavior")
        assert list(catalogue.loc["p", "modifier_values"][0]) == ["a   ", "c  ", "d"]
        # Both behaviors are point behaviors, so nothing in this observation has an extent.
        assert "duration" not in table.columns


class TestBORISTimeOffsetAndUndeclaredCodes(BORISTestMixin):
    """The generated fixture: a non-zero time offset, event comments, and codes the ethogram dropped.

    Its three cases come from real files that carry no licence, so the layouts are copied and the
    content invented. The ethogram also declares `Foraging/Caching`, whose slash cannot appear in an
    NWB object name, and `Exploracion` carrying a Spanish accent.
    """

    data_interface_cls = BORISInterface
    conversion_options = dict()  # what is written is set at construction, not at write
    save_directory = OUTPUT_PATH

    file_path = (
        BORIS_PROJECTS_PATH / "version_7_0" / "nonzero_time_offset" / "undeclared_codes_and_event_comments.boris"
    )

    interface_kwargs = dict(file_path=file_path, observation_name="positive offset")

    def check_read_nwb(self, nwbfile_path: str):
        super().check_read_nwb(nwbfile_path=nwbfile_path)
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]

        events_table = nwbfile.get_events_table("PositiveOffset")
        assert len(events_table.id) == 6
        assert tuple(events_table.colnames) == (
            "timestamp",
            "event_type",
            "subject",
            "comment",
            "stop_comment",
            "modifier_foraging_1",
            "duration",
        )
        # The whole coding scheme reaches the catalogue, including behaviors nothing was scored against.
        assert len(behavior_module["Ethogram"].to_dataframe()) == 5
        assert len(behavior_module["PositiveOffsetBouts"].to_dataframe()) == 1

        # This is the only fixture whose coder wrote comments, so it is the only place the column can be
        # shown to carry what they typed rather than merely to exist.
        comments = list(events_table.to_dataframe()["comment"])
        assert comments == [
            "already at the tray when the clip opens",
            "",
            "head up, orienting to the door",
            "something off camera",
            "second visit, nothing left in the tray",
            "",
        ]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2026, 1, 2, 10, 0, 0)
        # The only observation in the set whose coder wrote a description.
        assert metadata["NWBFile"]["session_description"] == "media starts 12.5 s after the observation clock"
        assert metadata["Events"]["EventTables"]["boris_positive_offset"] == {
            "table_name": "PositiveOffset",
            "description": "Behaviors scored in BORIS observation 'positive offset' (media).",
        }

        event_types = metadata["Events"]["boris_positive_offset"]["event_types"]
        # The five the scheme declares plus `Foraging`, which the events name and the scheme dropped.
        assert set(event_types) == {
            "Foraging/Caching",
            "Exploraci\u00f3n",
            "Burrowing",
            "Freeze",
            "Allogroom",
            "Foraging",
        }
        # The code is free text and stays verbatim as the identifier, accent and slash included.
        assert event_types["Foraging/Caching"]["event_description"] == (
            "nose down in the substrate, or carrying a seed to a cache"
        )
        # The display name is the code as well, so one string identifies the behavior in `event_type`,
        # in the catalogue and in the bouts table. The two characters an NWB object name cannot hold are
        # repaired by the writer where that constraint applies, in a table name derived from this.
        assert event_types["Foraging/Caching"]["event_name"] == "Foraging/Caching"
        assert event_types["Exploraci\u00f3n"]["event_name"] == "Exploraci\u00f3n"
        # A code the scheme dropped has no slots to name its column after, so it falls back to position,
        # and it carries no description because there is no behavior to take one from.
        assert "event_description" not in event_types["Foraging"]
        assert event_types["Foraging"]["columns"].keys() == {
            "subject",
            "comment",
            "stop_comment",
            "modifier_foraging_1",
        }


def test_time_offset_is_read_and_applied():
    """The observation's declared shift reaches the written times, and nothing else is mistaken for it.

    BORIS has two unrelated offsets. An observation's ``time offset`` shifts the whole observation, which
    is what an alignment offset is. The per-player offsets in ``media_info`` align two simultaneous
    players against each other and shift nothing, so ``offset positif``, which declares a +20 there and
    no ``time offset``, must come out at zero despite its name.
    """
    forward = BORISInterface(
        file_path=TestBORISTimeOffsetAndUndeclaredCodes.file_path, observation_name="positive offset"
    )
    assert forward.alignment.offset == pytest.approx(12.5)
    backward = BORISInterface(
        file_path=TestBORISTimeOffsetAndUndeclaredCodes.file_path, observation_name="negative offset"
    )
    assert backward.alignment.offset == pytest.approx(-4.0)
    media_offsets_only = BORISInterface(file_path=TestBORISMultiSubject.file_path, observation_name="offset positif")
    assert media_offsets_only.alignment.offset == 0.0

    # The reader keeps the file's own times; the offset is added at write.
    nwbfile = mock_NWBFile()
    forward.add_to_nwbfile(nwbfile=nwbfile)
    table = nwbfile.get_events_table("PositiveOffset").to_dataframe()
    assert table["timestamp"].min() == pytest.approx(1.0 + 12.5)  # the first Foraging row


def test_unpaired_state_start_becomes_nan():
    """A bout that opens and never closes keeps the event and marks the missing offset.

    In a live session a missed stop cannot be repaired afterwards, so a dangling start is a normal
    outcome. It stays in the events table with a NaN duration and is absent from the bouts table, which
    cannot hold a row with no stop time.
    """
    interface = BORISInterface(file_path=TestBORISMultiSubject.file_path, observation_name="live not paired")
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)

    table = nwbfile.get_events_table("LiveNotPaired").to_dataframe()
    state_rows = table[table["event_type"] == "s"]
    assert len(state_rows) == 4  # three bouts that closed, one that did not
    assert state_rows["duration"].isna().sum() == 1

    bouts = nwbfile.processing["behavior"]["LiveNotPairedBouts"].to_dataframe()
    assert len(bouts) == 3


def test_modifier_name_absent():
    """A modifier set the scheme leaves unnamed still gets a column, named for its position.

    BORIS calls one of these a modifier set and lets it be saved without a name; the demo project leaves
    it blank on both the behaviors that carry one, so the name cannot be what the column is called there.
    The position is what is left, and the catalogue's `modifiers` is what says which set it is.
    """
    interface = BORISInterface(file_path=TestBORISCategorizedEthogram.file_path, observation_name="id2")
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)

    table = nwbfile.get_events_table("Id2").to_dataframe().set_index("event_type")
    assert [list(cell) for cell in table.loc["walk", "modifier_walk_1"]] == [["quadrupedal"], ["quadrupedal"]]
    bouts = nwbfile.processing["behavior"]["Id2Bouts"].to_dataframe().set_index("label")
    assert [list(cell) for cell in bouts.loc["walk", "modifier_walk_1"]] == [["quadrupedal"], ["quadrupedal"]]


def test_a_bout_closing_on_the_none_token_writes_no_stop_column():
    """A closing answer that clears the set is not a second answer, so it earns no column.

    `id2` is where a bout closes on a different answer than it opened with: `walk` opens on
    `quadrupedal` and closes on the `None` token. That token reads as the set being cleared rather than
    as a value, so every closing cell would be empty, and a ragged column nothing fills is dropped rather
    than written with no values for hdmf to take a dtype from.
    """
    interface = BORISInterface(file_path=TestBORISCategorizedEthogram.file_path, observation_name="id2")
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)

    assert "stop_modifier_walk_1" not in nwbfile.get_events_table("Id2").colnames


def test_observation_without_events_writes_the_scheme():
    """An observation holding nothing still carries the vocabulary it was going to be scored with."""
    interface = BORISInterface(file_path=TestBORISMultiSubject.file_path, observation_name="observation without events")
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)

    assert len(nwbfile.get_events_table("ObservationWithoutEvents").id) == 0
    assert len(nwbfile.processing["behavior"]["Ethogram"].to_dataframe()) == 5
    # Nothing durative was scored, so there is no interval table to write.
    assert "ObservationWithoutEventsBouts" not in nwbfile.processing["behavior"].data_interfaces


def test_behaviors_can_be_routed_into_separate_tables():
    """The merged layout is a default stated in the metadata, not a decision fixed in the writer.

    Every behavior routes into one table because a modifier slot is rare enough that a table each would
    buy little and cost an NWB object per declared behavior. Somebody who wants the other layout edits
    the routing, and what they get has to be a real per-behavior table: each carrying only the slots its
    own behavior declares, not the union with the rest left empty.
    """
    interface = BORISInterface(file_path=TestBORISModifierSlots.file_path, observation_name="1")
    metadata = interface.get_metadata()
    metadata["Events"]["EventTables"] = {}
    for code, entry in metadata["Events"]["boris_1"]["event_types"].items():
        entry["table_metadata_key"] = code
        table_name = "".join(word.capitalize() for word in code.split())
        metadata["Events"]["EventTables"][code] = {
            "table_name": f"Observation1{table_name}",
            "description": f"'{code}' scored in observation 1.",
        }

    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    assert len(nwbfile.events) == 9  # one per declared behavior, scored or not
    two_sets = nwbfile.get_events_table("Observation12Sets")
    numeric = nwbfile.get_events_table("Observation1Numeric")
    # A behavior's own table carries its own slots and no others.
    assert {name for name in two_sets.colnames if name.startswith("modifier_")} == {
        "modifier_2_sets_set_1",
        "modifier_2_sets_set_2",
    }
    assert {name for name in numeric.colnames if name.startswith("modifier_")} == {"modifier_numeric_numeric_modif"}


class TestBORISErrorsAndWarnings:
    """Every way this interface refuses or complains, and what it says when it does.

    A plain grouping class rather than a ``BORISTestMixin`` subclass: none of these is a conversion, and
    two of them happen before an NWB file exists at all. The two guards that fire when several interfaces
    meet stay in :class:`TestBORISInConverterWorkflows` beside the case where they correctly do not.
    """

    def test_nonexistent_observation_error(self):
        """Naming an observation the project does not hold says which ones it does.

        Read against a project that holds twelve of them rather than against the empty one, so the
        message is pinned in the shape a user actually meets.
        """
        file_path = TestBORISMultiSubject.file_path
        expected = (
            "The observation 'anything' is not available.\n"
            f"The file path {Path(file_path).resolve()} contains the following observations:\n"
            "['offset positif', 'offset neg', 'observation #1', 'observation #2', 'live not paired', 'live', 'modifiers', '2 video', '2 video avi', 'live export behavioral sequences', 'observation #2 (copy)', 'observation without events']"
        )
        with pytest.raises(ValueError, match=re.escape(expected)):
            BORISInterface(file_path=file_path, observation_name="anything")

    def test_a_code_the_ethogram_no_longer_declares(self):
        """Somebody edited the ethogram after scoring, and the already-scored rows still name the old code.

        BORIS does not rewrite rows when a behavior is renamed or deleted, so this is an ordinary state for a
        project to be in rather than a corrupt file. Both shapes are in this fixture: `Rearing` and
        `Scent-marking` were scored and never declared at all.

        What the conversion promises in that situation is three things at once. Nothing the coder recorded is
        dropped, so every one of those events reaches the file. Nothing is invented on their behalf: the code
        has no point-or-state kind, because only the ethogram carries that, so no extent is claimed for it and
        the catalogue does not pretend it was ever part of the scheme. And the loss is announced, once per
        code, with what went missing and how to get it back, because nothing in the written file would
        otherwise say it happened.
        """
        file_path = TestBORISTimeOffsetAndUndeclaredCodes.file_path
        expected = (
            "Observation 'removed behaviors' has 1 events naming 'Rearing', which this project's ethogram "
            "does not declare. BORIS does not rewrite existing rows when a behavior is renamed or removed, "
            "so these are usually the old name of a behavior that is still in the scheme under a new one. "
            "They are read without durations, since only the ethogram says whether a behavior is durative. "
            "If 'Rearing' was a state behavior, its bouts are not in this file. Declare it in the project in "
            "BORIS and re-save to recover them."
        )
        with pytest.warns(UserWarning, match=re.escape(expected)) as records:
            interface = BORISInterface(file_path=file_path, observation_name="removed behaviors")
        # One warning per code, so somebody with three renamed behaviors gets three lines naming three codes.
        messages = [str(record.message) for record in records]
        assert len(messages) == 2
        assert sorted(message.split("naming ")[1].split(",")[0] for message in messages) == [
            "'Rearing'",
            "'Scent-marking'",
        ]

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        events_table = nwbfile.get_events_table("RemovedBehaviors").to_dataframe()

        # Nothing is dropped: every scored event reaches the file, undeclared or not.
        assert list(events_table["event_type"]) == ["Freeze", "Rearing", "Burrowing", "Scent-marking"]
        # Nothing is invented: an undeclared code has no kind, so no extent is claimed for it.
        assert list(events_table["duration"].isna()) == [True, True, False, True]
        # The catalogue is the ethogram and nothing more, so it does not grow to cover a deleted code.
        catalogue = nwbfile.processing["behavior"]["Ethogram"].to_dataframe()
        assert list(catalogue["behavior"]) == [
            "Foraging/Caching",
            "Exploraci\u00f3n",
            "Burrowing",
            "Freeze",
            "Allogroom",
        ]

    def test_two_behaviors_cannot_resolve_to_one_modifier_column(self, tmp_path):
        """A column is named for the behavior and the slot, and the pair has to stay distinguishable.

        Both halves are normalized and joined with underscores, so two different splits can flatten to the
        same name. Nothing downstream would notice: the two behaviors would agree on the description and on
        the vocabulary, so the writer would accept them and their answers would merge into one column
        holding two vocabularies, which is the aggregation naming per behavior exists to prevent.
        """
        scheme = {
            "0": {
                "type": "State event",
                "code": "Traffic",
                "description": "",
                "excluded": "",
                "modifiers": {"0": {"name": "lights state", "type": 0, "values": ["Red", "Green"]}},
            },
            "1": {
                "type": "State event",
                "code": "Traffic lights",
                "description": "",
                "excluded": "",
                "modifiers": {"0": {"name": "State", "type": 0, "values": ["On", "Off"]}},
            },
        }
        events = [
            [1.0, "", "Traffic", "Red", ""],
            [2.0, "", "Traffic", "Red", ""],
            [3.0, "", "Traffic lights", "On", ""],
            [4.0, "", "Traffic lights", "On", ""],
        ]
        project = {
            "project_format_version": "7.0",
            "project_name": "collision",
            "time_format": "s",
            "behaviors_conf": scheme,
            "behavioral_categories": [],
            "subjects_conf": {},
            "independent_variables": {},
            "coding_map": {},
            "converters": {},
            "observations": {
                "obs": {
                    "type": "LIVE",
                    "date": "2026-01-01T10:00:00",
                    "description": "",
                    "time offset": 0.0,
                    "file": [],
                    "independent_variables": {},
                    "events": events,
                }
            },
        }
        file_path = tmp_path / "collision.boris"
        file_path.write_text(json.dumps(project), encoding="utf-8")

        interface = BORISInterface(file_path=file_path, observation_name="obs")
        # The check runs at write, so the metadata naming the column still comes back. That is the recourse:
        # checking at read would raise inside the call that produces the dict the user has to edit.
        metadata = interface.get_metadata()

        expected = (
            "Behaviors 'Traffic' and 'Traffic lights' both write the column "
            "'modifier_traffic_lights_state' into one events table, so their answers would merge into one "
            "column holding two vocabularies. A column is named for the behavior and the slot together, and "
            "these two flatten to the same name. Give one of them a column of its own before writing:\n"
            "    metadata['Events']['boris_obs']['event_types']['Traffic lights']['columns']"
            "['modifier_traffic_lights_state']['column_name'] = 'modifier_traffic_lights_state_2'\n"
            "Or rename the slot on either behavior in BORIS and re-save."
        )
        with pytest.raises(ValueError, match=re.escape(expected)):
            interface.add_to_nwbfile(nwbfile=mock_NWBFile())

        # Renaming either column resolves it, which is what the message tells the user to do.
        columns = metadata["Events"]["boris_obs"]["event_types"]["Traffic lights"]["columns"]
        columns["modifier_traffic_lights_state"]["column_name"] = "modifier_traffic_lights_state_2"
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        assert {"modifier_traffic_lights_state", "modifier_traffic_lights_state_2"} <= set(
            nwbfile.get_events_table("Obs").colnames
        )


class TestBORISInConverterWorkflows:
    """The rules for several ``BORISInterface`` objects writing into one NWB file.

    A plain grouping class rather than a ``BORISTestMixin`` subclass: nothing here runs a conversion from
    ``interface_kwargs``, and what is under test is what a second interface does when it meets what a
    first one already wrote. One interface reads one observation, so anyone converting several assembles
    them into a converter themselves, and these are the rules that assembly has to respect.
    """

    def test_several_observations_of_one_project_share_the_catalogue(self):
        """Two observations of one project meet one catalogue, because the catalogue is the project's.

        They come from one coding scheme, so the second interface finds its own catalogue and reuses it,
        while each observation keeps its own events table and its own bouts table.
        """
        nwbfile = mock_NWBFile()
        for observation_name in ("observation #1", "live not paired"):
            BORISInterface(file_path=TestBORISMultiSubject.file_path, observation_name=observation_name).add_to_nwbfile(
                nwbfile=nwbfile
            )

        behavior_module = nwbfile.processing["behavior"]
        assert set(nwbfile.events) == {"Observation1", "LiveNotPaired"}
        assert {"Observation1Bouts", "LiveNotPairedBouts"} <= set(behavior_module.data_interfaces)
        catalogue = behavior_module["Ethogram"].to_dataframe()
        assert list(catalogue["behavior"]) == ["p", "s", "q", "r", "m"]

    def test_a_second_project_cannot_share_the_catalogue(self):
        """A catalogue is one project's coding scheme, so two projects in one file have to be refused.

        The object name is fixed, so a second project would either find the name taken and skip writing
        its own behaviors, leaving a bouts table whose labels are in no catalogue, or extend the first
        project's and make one catalogue claim to be the scheme of two.
        """
        nwbfile = mock_NWBFile()
        BORISInterface(file_path=TestBORISMultiSubject.file_path, observation_name="observation #1").add_to_nwbfile(
            nwbfile=nwbfile
        )

        expected = (
            "The behavior processing module already holds an 'Ethogram' catalogue declaring "
            "['p', 's', 'q', 'r', 'm'], and this project declares ['groom', 'run', 'walk', 'attack', "
            "'play', 'jump', 'approach', 'drink', 'eat', 'defecate', 'urinate']. A catalogue is one "
            "project's coding scheme, so two BORIS projects cannot share one NWB file. Write them to "
            "separate files."
        )
        with pytest.raises(ValueError, match=re.escape(expected)):
            BORISInterface(file_path=TestBORISCategorizedEthogram.file_path, observation_name="test1").add_to_nwbfile(
                nwbfile=nwbfile
            )

    def test_two_observations_deriving_one_table_name_are_refused(self, tmp_path):
        """Two observation names that differ only in punctuation derive the same events table name.

        `Boccia 223 2` and `Boccia 223_2`, two trials a real study recorded an hour apart against
        different videos, both come out as `Boccia2232`. The events writer is append-capable, which is
        right for several interfaces sharing a table on purpose and wrong here, since the second
        observation's rows would join the first's with nothing to say which trial they came from.
        """
        scheme = {"0": {"type": "Point event", "code": "peck", "description": "", "excluded": "", "modifiers": ""}}

        def observation(events):
            return {
                "type": "LIVE",
                "date": "2026-01-01T10:00:00",
                "description": "",
                "time offset": 0.0,
                "file": [],
                "independent_variables": {},
                "events": events,
            }

        project = {
            "project_format_version": "7.0",
            "project_name": "boccia",
            "time_format": "s",
            "behaviors_conf": scheme,
            "behavioral_categories": [],
            "subjects_conf": {},
            "independent_variables": {},
            "coding_map": {},
            "converters": {},
            "observations": {
                "Boccia 223 2": observation([[1.0, "", "peck", "", ""]]),
                "Boccia 223_2": observation([[2.0, "", "peck", "", ""]]),
            },
        }
        file_path = tmp_path / "boccia.boris"
        file_path.write_text(json.dumps(project), encoding="utf-8")

        nwbfile = mock_NWBFile()
        BORISInterface(file_path=file_path, observation_name="Boccia 223 2").add_to_nwbfile(nwbfile=nwbfile)

        second = BORISInterface(file_path=file_path, observation_name="Boccia 223_2")
        expected = (
            "An events table named 'Boccia2232' already exists and holds a different observation: "
            "Behaviors scored in BORIS observation 'Boccia 223 2' (live). Two observation names that "
            "differ only in punctuation derive the same object name, and 'Boccia 223_2' is one of them. "
            "Give this one a name of its own with "
            "metadata['Events']['EventTables']['boris_boccia_223_2']['table_name'], or write the two "
            "observations to separate files."
        )
        with pytest.raises(ValueError, match=re.escape(expected)):
            second.add_to_nwbfile(nwbfile=nwbfile)

        # Naming the second table is the recourse the message offers, and it has to actually work.
        metadata = second.get_metadata()
        metadata["Events"]["EventTables"][second.metadata_key]["table_name"] = "Boccia2232Underscore"
        second.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        assert set(nwbfile.events) == {"Boccia2232", "Boccia2232Underscore"}
