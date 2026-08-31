"""Tests for BORISEventsInterface, one class per project file."""

import math
from datetime import datetime

import numpy as np
import pytest
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import BORISEventsInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH

BORIS_PROJECTS_PATH = BEHAVIOR_DATA_PATH / "boris" / "json_project"

VERSION_1_6 = (
    BORIS_PROJECTS_PATH / "version_1_6" / "string_modifiers_no_categories" / "media_and_live_two_subjects.boris"
)
VERSION_4_0 = (
    BORIS_PROJECTS_PATH / "version_4_0" / "string_modifiers_seconds_time_format" / "categorized_media_and_live.boris"
)
VERSION_7_0 = BORIS_PROJECTS_PATH / "version_7_0"
CATEGORIZED = VERSION_7_0 / "categorized_ethogram" / "mutually_exclusive_behaviors_and_unpaired_starts.boris"
MODIFIER_SLOTS = VERSION_7_0 / "modifier_slot_types" / "single_multiple_numeric_and_point_exclusion.boris"
MULTI_SUBJECT = VERSION_7_0 / "media_and_live_observations" / "two_players_multi_subject_and_an_unclosed_bout.boris"
NO_OBSERVATIONS = VERSION_7_0 / "no_observations" / "twenty_six_subjects_and_three_converters.boris"
UNTIDY_MODIFIERS = VERSION_7_0 / "untidy_modifier_values" / "whitespace_and_the_none_token.boris"
TIME_OFFSET = VERSION_7_0 / "nonzero_time_offset" / "undeclared_codes_and_event_comments.boris"

pytestmark = pytest.mark.skipif(
    not BORIS_PROJECTS_PATH.exists(), reason="The BORIS files are not in the local behavior testing data."
)


class BORISEventsRoundTrip(DataInterfaceTestMixin):
    """What every observation shares: one merged events table, a catalogue, and a bouts table.

    Each subclass states what its own project is there to exercise; the shared assertions are the ones
    true of every BORIS conversion. The whole coding scheme reaches the catalogue, including behaviors
    nothing was ever scored against, and the bouts table holds exactly the state bouts that closed.
    """

    data_interface_cls = BORISEventsInterface
    conversion_options = dict()  # what is written is set at construction, not at write
    save_directory = OUTPUT_PATH

    #: The name of the events table, derived from the observation name.
    expected_table_name: str
    #: One row per occurrence: every point event, plus one per state bout including an unclosed one.
    expected_event_count: int
    #: One row per state bout that closed. A bout with no stop has no stop time to write.
    expected_bout_count: int
    #: Every behavior the project declares, scored or not.
    expected_catalogue_size: int

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)

        events_table = nwbfile.get_events_table(self.expected_table_name)
        assert len(events_table.id) == self.expected_event_count
        # Every behavior lands in one table, so the merge carries the discriminator plus the three
        # per-occurrence columns BORIS records and no other events format does.
        for column_name in ("event_type", "subject", "modifiers", "comment"):
            assert column_name in events_table.colnames

        behavior_module = nwbfile.processing["behavior"]
        catalogue = behavior_module["Ethogram"].to_dataframe()
        assert len(catalogue) == self.expected_catalogue_size
        assert set(catalogue["behavior_type"]) <= {"point", "state"}

        bouts_name = f"{self.expected_table_name}Bouts"
        if self.expected_bout_count == 0:
            # An observation with nothing durative in it gets no interval table at all.
            assert bouts_name not in behavior_module.data_interfaces
            return
        bouts = behavior_module[bouts_name].to_dataframe()
        assert len(bouts) == self.expected_bout_count
        # A bout is a closed interval by construction, so none of these may be reversed or unfinished.
        assert (bouts["stop_time"] >= bouts["start_time"]).all()
        # Only state behaviors reach the bouts table, and every label there is in the catalogue.
        state_behaviors = set(catalogue.loc[catalogue["behavior_type"] == "state", "behavior"])
        assert set(bouts["label"]) <= state_behaviors


class TestBORISVersion1_6(BORISEventsRoundTrip):
    """Format 1.6: no `category` field on a behavior, and `modifiers` a flat comma-separated string."""

    interface_kwargs = dict(file_path=VERSION_1_6, observation_name="media observation")

    expected_table_name = "MediaObservation"
    expected_event_count = 4
    expected_bout_count = 2
    expected_catalogue_size = 4

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2016, 1, 2, 9, 0, 0)
        # 1.6 has no categories at all, which has to read as absent rather than as unassigned.
        event_types = metadata["Events"]["boris"]["event_types"]
        assert set(event_types) == {"forage", "rest", "groom", "call"}
        # BORIS is one of the few sources carrying its own prose, so the description is reported.
        assert event_types["forage"]["event_description"] == "moves over the substrate collecting food"


class TestBORISVersion4_0(BORISEventsRoundTrip):
    """Format 4.0: categories exist, modifiers are still a flat string, and times are in seconds."""

    interface_kwargs = dict(file_path=VERSION_4_0, observation_name="media observation")

    expected_table_name = "MediaObservation"
    expected_event_count = 5
    expected_bout_count = 3
    expected_catalogue_size = 5

    def run_custom_checks(self):
        interface = BORISEventsInterface(file_path=VERSION_4_0, observation_name="media observation")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        catalogue = nwbfile.processing["behavior"]["Ethogram"].to_dataframe()
        assert set(catalogue["category"]) == {"Locomotion", "Maintenance", "Social"}


class TestBORISCategorizedEthogram(BORISEventsRoundTrip):
    """The BORIS Android demo project: eleven behaviors, of which this observation scores a few."""

    interface_kwargs = dict(file_path=CATEGORIZED, observation_name="test1")

    expected_table_name = "Test1"
    expected_event_count = 6
    expected_bout_count = 3
    expected_catalogue_size = 11


class TestBORISModifierSlots(BORISEventsRoundTrip):
    """All three modifier slot types. Every behavior scored here is a point behavior, so no bouts."""

    interface_kwargs = dict(file_path=MODIFIER_SLOTS, observation_name="1")

    expected_table_name = "Observation1"
    expected_event_count = 4
    expected_bout_count = 0
    expected_catalogue_size = 9

    def run_custom_checks(self):
        """The recorded forms of the three slot types, kept as the strings BORIS wrote."""
        interface = BORISEventsInterface(file_path=MODIFIER_SLOTS, observation_name="1")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        table = nwbfile.get_events_table("Observation1").to_dataframe()
        # A single selection, a multiple selection joined with ",", a free numeric, and two slots
        # joined with "|".
        assert set(table["modifiers"]) == {"3", "1,2", "789", "2|3"}


class TestBORISMultiSubject(BORISEventsRoundTrip):
    """One observation carrying events from two named subjects, which is why subject is a column."""

    interface_kwargs = dict(file_path=MULTI_SUBJECT, observation_name="observation #1")

    expected_table_name = "Observation1"
    expected_event_count = 4
    expected_bout_count = 4
    expected_catalogue_size = 5

    def run_custom_checks(self):
        interface = BORISEventsInterface(file_path=MULTI_SUBJECT, observation_name="observation #1")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        table = nwbfile.get_events_table("Observation1").to_dataframe()
        # Two animals scored in one session. NWB has one Subject per file, so this cannot be that.
        assert set(table["subject"]) == {"subject1", "subject2"}


class TestBORISUntidyModifiers(BORISEventsRoundTrip):
    """Untidy declared values and the literal `None` token for a slot nobody answered."""

    interface_kwargs = dict(file_path=UNTIDY_MODIFIERS, observation_name="test1 live")

    expected_table_name = "Test1Live"
    expected_event_count = 4
    expected_bout_count = 0
    expected_catalogue_size = 2

    def run_custom_checks(self):
        interface = BORISEventsInterface(file_path=UNTIDY_MODIFIERS, observation_name="test1 live")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        table = nwbfile.get_events_table("Test1Live").to_dataframe()
        # Whitespace is preserved and an unanswered slot writes the literal token, both verbatim: the
        # values are free text somebody typed and normalizing them here would invent data.
        assert set(table["modifiers"]) == {"a   |c ", "a   |None", "None|111", "None|c "}
        # Both behaviors are point behaviors, so nothing in this observation has an extent.
        assert "duration" not in table.columns


class TestBORISTimeOffsetAndUndeclaredCodes(BORISEventsRoundTrip):
    """The generated fixture: a non-zero time offset, event comments, and codes the ethogram dropped.

    Its three cases come from real files that carry no licence, so the layouts are copied and the
    content invented. The ethogram also declares `Foraging/Caching`, whose slash cannot appear in an
    NWB object name, and `Exploracion` carrying a Spanish accent.
    """

    interface_kwargs = dict(file_path=TIME_OFFSET, observation_name="positive offset")

    expected_table_name = "PositiveOffset"
    #: Four `Foraging` rows the reader cannot type, one `Wake - Alert` bout, one `Freeze`.
    expected_event_count = 6
    expected_bout_count = 1
    expected_catalogue_size = 5

    def check_extracted_metadata(self, metadata: dict):
        # The code is free text and stays verbatim as the identifier, accent and slash included.
        event_types = metadata["Events"]["boris"]["event_types"]
        assert "Foraging/Caching" in event_types
        assert "Exploraci\u00f3n" in event_types
        # The editable display name is what an object name gets derived from, so the characters an NWB
        # name cannot hold are replaced there rather than in the identifier.
        assert event_types["Foraging/Caching"]["event_name"] == "Foraging_Caching"
        assert event_types["Exploraci\u00f3n"]["event_name"] == "Exploraci\u00f3n"


def test_nonzero_time_offset_is_applied():
    """The observation's declared shift reaches the written times through the alignment surface."""
    forward = BORISEventsInterface(file_path=TIME_OFFSET, observation_name="positive offset")
    assert forward.alignment.offset == pytest.approx(12.5)
    backward = BORISEventsInterface(file_path=TIME_OFFSET, observation_name="negative offset")
    assert backward.alignment.offset == pytest.approx(-4.0)

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
        BORISEventsInterface(file_path=TIME_OFFSET, observation_name="removed behaviors")

    # One warning per code, naming the code and how many rows carry it.
    with pytest.warns(UserWarning) as records:
        BORISEventsInterface(file_path=TIME_OFFSET, observation_name="positive offset")
    messages = " ".join(str(record.message) for record in records)
    assert "'Foraging'" in messages and "4 events" in messages


def test_undeclared_behavior_code_keeps_the_row():
    """A code the ethogram no longer declares still reaches the file, typed as a point event.

    Real projects produce this two ways, both in this fixture: a behavior renamed after the session was
    scored, whose old code stays on every row, and behaviors removed from the scheme outright. Neither
    can be typed, so the extent is not claimed, which does lose a renamed state behavior's durations.
    """
    interface = BORISEventsInterface(file_path=TIME_OFFSET, observation_name="removed behaviors")
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)

    table = nwbfile.get_events_table("RemovedBehaviors").to_dataframe()
    assert {"Rearing", "Scent-marking"} <= set(table["event_type"])
    # They are absent from the catalogue, which holds only what the ethogram declares.
    catalogue = BORISEventsInterface(file_path=TIME_OFFSET, observation_name="removed behaviors")._project.behaviors
    assert "Rearing" not in catalogue


def test_event_comments_survive():
    """The comment column carries what the coder typed, which almost no fixture exercises."""
    interface = BORISEventsInterface(file_path=TIME_OFFSET, observation_name="negative offset")
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
    interface = BORISEventsInterface(file_path=TIME_OFFSET, observation_name="positive offset")
    metadata = interface.get_metadata()
    # Give the slashed behavior a table to itself, which the metadata permits.
    metadata["Events"]["boris"]["event_types"]["Foraging/Caching"]["table_metadata_key"] = "solo"

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
    interface = BORISEventsInterface(file_path=MULTI_SUBJECT, observation_name="live not paired")
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
    from neuroconv.datainterfaces.events.boris.boris_reader import read_boris_observation

    observation = read_boris_observation(file_path=CATEGORIZED, observation_name="id2")
    walk_bouts = [occurrence for occurrence in observation.occurrences if occurrence.code == "walk"]
    assert walk_bouts, "the observation exists to exercise closing a bout across a modifier change"
    for bout in walk_bouts:
        assert bout.duration is not None and not math.isnan(bout.duration)
        assert bout.modifiers == "quadrupedal"


def test_observation_without_events_writes_the_scheme():
    """An observation holding nothing still carries the vocabulary it was going to be scored with."""
    interface = BORISEventsInterface(file_path=MULTI_SUBJECT, observation_name="observation without events")
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)

    assert len(nwbfile.get_events_table("ObservationWithoutEvents").id) == 0
    assert len(nwbfile.processing["behavior"]["Ethogram"].to_dataframe()) == 5
    # Nothing durative was scored, so there is no interval table to write.
    assert "ObservationWithoutEventsBouts" not in nwbfile.processing["behavior"].data_interfaces


def test_project_with_no_observations():
    """A full coding scheme and nothing to convert is a legal file, not an error.

    ``get_observation_names`` reports the empty list, and asking for an observation by name says which
    ones exist rather than failing obscurely.
    """
    assert BORISEventsInterface.get_observation_names(file_path=NO_OBSERVATIONS) == []

    with pytest.raises(KeyError, match="No observation"):
        BORISEventsInterface(file_path=NO_OBSERVATIONS, observation_name="anything")


def test_live_observation_has_no_frame_rate():
    """A LIVE observation has no media and so no resolution to claim; a MEDIA one has the frame period."""
    live = BORISEventsInterface(file_path=VERSION_1_6, observation_name="live observation")
    nwbfile = mock_NWBFile()
    live.add_to_nwbfile(nwbfile=nwbfile)
    assert nwbfile.get_events_table("LiveObservation")["timestamp"].resolution is None

    media = BORISEventsInterface(file_path=VERSION_1_6, observation_name="media observation")
    nwbfile = mock_NWBFile()
    media.add_to_nwbfile(nwbfile=nwbfile)
    # The project's media runs at 25 fps, so a coder could only ever mark a 40 ms boundary.
    assert nwbfile.get_events_table("MediaObservation")["timestamp"].resolution == pytest.approx(0.04)


def test_time_offset_goes_through_alignment():
    """The observation's declared shift is an alignment offset, not something folded into the times.

    No fixture declares a non-zero ``time offset``, so the shift itself is unexercised by real data: the
    +20 and -20 in ``offset positif`` and ``offset neg`` are per-player *media* offsets in ``media_info``,
    which align two simultaneous players against each other rather than shifting the observation. What is
    checked here is that the times are the file's own and that the alignment surface moves them.
    """
    interface = BORISEventsInterface(file_path=MULTI_SUBJECT, observation_name="offset positif")
    assert interface.alignment.offset == 0.0

    first_code = interface.get_event_type_source_ids()[0]
    native = interface.get_event_times(event_type_source_id=first_code)
    interface.alignment.shift_times(20.0)
    assert np.allclose(interface.get_event_times(event_type_source_id=first_code), native + 20.0)
