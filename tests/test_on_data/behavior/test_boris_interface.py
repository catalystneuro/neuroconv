"""Tests for BORISInterface, one class per project file."""

import math
from datetime import datetime

import pytest
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

        # A behavior that declares no slot writes an empty cell in a modifier column it does not own,
        # never a NaN, which could not share the column with the answers.
        for events_table in nwbfile.events.values():
            modifier_columns = [name for name in events_table.colnames if name.startswith("modifier_")]
            for column_name in modifier_columns:
                answers = events_table[column_name].data
                are_all_answers_strings = all(isinstance(answer, str) for answer in answers)
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
        # 1.6 has no categories at all, which has to read as absent rather than as unassigned.
        # The block sits under the observation's own key, so several observations do not collide.
        event_types = metadata["Events"]["boris_media_observation"]["event_types"]
        assert set(event_types) == {"forage", "rest", "groom", "call"}
        # BORIS is one of the few sources carrying its own prose, so the description is reported.
        assert event_types["forage"]["event_description"] == "moves over the substrate collecting food"


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
            "modifier_groom_1",
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
            "modifier_a_x",
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
        assert table.loc["many modifiers", "modifier_many_modifiers_set_1"] == "3"
        assert table.loc["numeric", "modifier_numeric_numeric_modif"] == "789"
        # A multiple selection is several answers to *one* slot, so the comma stays inside one column.
        assert table.loc["multiple modif", "modifier_multiple_modif_set_1"] == "1,2"
        # Two slots are two answers, which is what the split is for: the "|" does not survive.
        assert table.loc["2 sets", "modifier_2_sets_set_1"] == "2"
        assert table.loc["2 sets", "modifier_2_sets_set_2"] == "3"
        # A column is keyed on the behavior as well as the slot, so `2 sets` and `multiple modif` both
        # declaring a slot called `set 1` get a column each rather than sharing two vocabularies. A
        # behavior writes an empty cell in a column it does not own, never a NaN, which could not share
        # a text column with the answers.
        assert table.loc["numeric", "modifier_2_sets_set_1"] == ""
        assert table.loc["2 sets", "modifier_multiple_modif_set_1"] == ""

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
            "modifier_q_modif_1",
            "modifier_r_modif_1",
            "modifier_m_modif_1",
            "modifier_m_modif_2",
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
        assert list(table["modifier_p_test_1"]) == ["a   ", "a   ", "", ""]
        assert list(table["modifier_p_test_2"]) == ["c ", "", "111", "c "]
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
            "modifier_foraging_caching_substrate",
            "stop_comment",
            "modifier_foraging_1",
            "duration",
        )
        # The whole coding scheme reaches the catalogue, including behaviors nothing was scored against.
        assert len(behavior_module["Ethogram"].to_dataframe()) == 5
        assert len(behavior_module["PositiveOffsetBouts"].to_dataframe()) == 1

    def check_extracted_metadata(self, metadata: dict):
        # The code is free text and stays verbatim as the identifier, accent and slash included.
        event_types = metadata["Events"]["boris_positive_offset"]["event_types"]
        assert "Foraging/Caching" in event_types
        assert "Exploraci\u00f3n" in event_types
        # The editable display name is what an object name gets derived from, so the characters an NWB
        # name cannot hold are replaced there rather than in the identifier.
        assert event_types["Foraging/Caching"]["event_name"] == "Foraging_Caching"
        assert event_types["Exploraci\u00f3n"]["event_name"] == "Exploraci\u00f3n"


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


def test_undeclared_behavior_code_warns():
    """The loss has to announce itself, since nothing in the written file records that it happened.

    A code the ethogram no longer declares has no point-or-state kind, so its rows cannot be paired and
    are written without durations. Read as a state behavior that would be every bout it ever had.
    """
    with pytest.warns(UserWarning, match="ethogram does not declare"):
        BORISInterface(file_path=TestBORISTimeOffsetAndUndeclaredCodes.file_path, observation_name="removed behaviors")

    # One warning per code, naming the code and how many rows carry it.
    with pytest.warns(UserWarning) as records:
        BORISInterface(file_path=TestBORISTimeOffsetAndUndeclaredCodes.file_path, observation_name="positive offset")
    messages = " ".join(str(record.message) for record in records)
    assert "'Foraging'" in messages and "4 events" in messages


def test_undeclared_behavior_code_keeps_the_row():
    """A code the ethogram no longer declares still reaches the file, typed as a point event.

    Real projects produce this two ways, both in this fixture: a behavior renamed after the session was
    scored, whose old code stays on every row, and behaviors removed from the scheme outright. Neither
    can be typed, so the extent is not claimed, which does lose a renamed state behavior's durations.
    """
    interface = BORISInterface(
        file_path=TestBORISTimeOffsetAndUndeclaredCodes.file_path, observation_name="removed behaviors"
    )
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)

    table = nwbfile.get_events_table("RemovedBehaviors").to_dataframe()
    assert {"Rearing", "Scent-marking"} <= set(table["event_type"])
    # They are absent from the catalogue, which holds only what the ethogram declares.
    catalogue = BORISInterface(
        file_path=TestBORISTimeOffsetAndUndeclaredCodes.file_path, observation_name="removed behaviors"
    )._project.behaviors
    assert "Rearing" not in catalogue


def test_event_comments_survive():
    """The comment column carries what the coder typed, which almost no fixture exercises."""
    interface = BORISInterface(
        file_path=TestBORISTimeOffsetAndUndeclaredCodes.file_path, observation_name="negative offset"
    )
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)

    comments = set(nwbfile.get_events_table("NegativeOffset").to_dataframe()["comment"])
    assert "digging when the clip opens" in comments


def test_a_behavior_code_with_a_slash_can_take_its_own_table():
    """A code carrying a character an NWB object name cannot hold must not raise.

    `Foraging/Caching` is an ordinary way to name one behavior covering two things, and hdmf rejects a
    slash in an object name outright. The default layout puts every behavior in one table named after the
    observation, so the code never reaches an object name there; routing one behavior to a table of its
    own is what exposes it.
    """
    interface = BORISInterface(
        file_path=TestBORISTimeOffsetAndUndeclaredCodes.file_path, observation_name="positive offset"
    )
    metadata = interface.get_metadata()
    # Give the slashed behavior a table to itself, which the metadata permits.
    metadata["Events"]["boris_positive_offset"]["event_types"]["Foraging/Caching"]["table_metadata_key"] = "solo"

    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
    # The table name is CamelCased from the event_name, which eats the underscore. The separator still
    # earns its place in the default layout, where the event_name is the value in the event_type column.
    assert "ForagingCaching" in nwbfile.events


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


def test_pairing_ignores_the_modifier_string():
    """A bout can open with one modifier and close with another, and must still close.

    Matching on the modifier would leave every such bout open. The only observations in the whole fixture
    set that exercise this are in the Android demo project: ``id2`` opens ``walk`` with ``quadrupedal``
    and closes it with ``None``. The recorded modifier of the opening row is what survives, since that is
    what the coder said was true when the bout began.
    """
    from neuroconv.datainterfaces.behavior.boris._boris_reader import _read_boris_observation

    observation = _read_boris_observation(file_path=TestBORISCategorizedEthogram.file_path, observation_name="id2")
    walk_bouts = [occurrence for occurrence in observation.occurrences if occurrence.code == "walk"]
    assert walk_bouts, "the observation exists to exercise closing a bout across a modifier change"
    for bout in walk_bouts:
        assert bout.duration is not None and not math.isnan(bout.duration)
        assert bout.modifiers == "quadrupedal"


def test_unnamed_modifier_slot_falls_back_to_its_position():
    """A scheme need not name its slots, and an unnamed one still gets a column.

    The BORIS demo project leaves the slot name blank on both the behaviors that carry one, so the name
    cannot be what the column is called there. The position is what is left, and the catalogue is what
    says which behavior's slot it is.
    """
    interface = BORISInterface(file_path=TestBORISCategorizedEthogram.file_path, observation_name="id2")
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)

    table = nwbfile.get_events_table("Id2").to_dataframe().set_index("event_type")
    assert list(table.loc["walk", "modifier_walk_1"]) == ["quadrupedal", "quadrupedal"]
    # `run` declares no slot at all, so it writes an empty cell in the column `walk` owns.
    assert table.loc["run", "modifier_walk_1"] == ""

    # This observation is also the one where a bout closes on a different answer than it opened with, so
    # the closing row earns columns of its own. `walk` opens on `quadrupedal` and closes on the `None`
    # token, which reads as the slot being cleared rather than as the string.
    assert list(table.loc["walk", "stop_modifier_walk_1"]) == ["", ""]
    # The interval view carries the same columns, so a bout is described one way and not two.
    bouts = nwbfile.processing["behavior"]["Id2Bouts"].to_dataframe().set_index("label")
    assert list(bouts.loc["walk", "modifier_walk_1"]) == ["quadrupedal", "quadrupedal"]


def test_observation_without_events_writes_the_scheme():
    """An observation holding nothing still carries the vocabulary it was going to be scored with."""
    interface = BORISInterface(file_path=TestBORISMultiSubject.file_path, observation_name="observation without events")
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)

    assert len(nwbfile.get_events_table("ObservationWithoutEvents").id) == 0
    assert len(nwbfile.processing["behavior"]["Ethogram"].to_dataframe()) == 5
    # Nothing durative was scored, so there is no interval table to write.
    assert "ObservationWithoutEventsBouts" not in nwbfile.processing["behavior"].data_interfaces


def test_project_with_no_observations():
    """A full coding scheme and nothing to convert is a legal file, not an error.

    ``_get_observation_names`` reports the empty list, and asking for an observation by name says which
    ones exist rather than failing obscurely.
    """
    assert (
        BORISInterface._get_observation_names(
            file_path=BORIS_PROJECTS_PATH
            / "version_7_0"
            / "no_observations"
            / "twenty_six_subjects_and_three_converters.boris"
        )
        == []
    )

    with pytest.raises(KeyError, match="No observation"):
        BORISInterface(
            file_path=BORIS_PROJECTS_PATH
            / "version_7_0"
            / "no_observations"
            / "twenty_six_subjects_and_three_converters.boris",
            observation_name="anything",
        )


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


def test_several_observations_of_one_project_share_the_catalogue():
    """One interface reads one observation, so writing several to a file is a converter's job.

    They come from one project and so from one coding scheme, and the catalogue is that scheme, not any
    observation's. The second interface therefore meets its own catalogue and reuses it, while each
    observation keeps its own events table and its own bouts table.
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


def test_a_second_project_cannot_share_the_catalogue():
    """A catalogue is one project's coding scheme, so two projects in one file have to be refused.

    The object name is fixed, so a second project would either find the name taken and skip writing its
    own behaviors, leaving a bouts table whose labels are in no catalogue, or extend the first project's
    and make one catalogue claim to be the scheme of two.
    """
    nwbfile = mock_NWBFile()
    BORISInterface(file_path=TestBORISMultiSubject.file_path, observation_name="observation #1").add_to_nwbfile(
        nwbfile=nwbfile
    )

    with pytest.raises(ValueError, match="cannot share one NWB file"):
        BORISInterface(file_path=TestBORISCategorizedEthogram.file_path, observation_name="test1").add_to_nwbfile(
            nwbfile=nwbfile
        )
