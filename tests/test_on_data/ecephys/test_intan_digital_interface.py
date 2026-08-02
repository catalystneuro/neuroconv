from datetime import datetime, timezone

import numpy as np
import pytest
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import IntanDigitalInterface

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


class TestIntanDigitalInterface:
    """
    This test a simple Intan digital file with a single enabled line
    """

    # A file whose digital-input word has a single toggling line, named "DIGITAL-IN-01" in the header
    # (bit 0 of the word: this Intan software version names its lines from one while the bit positions
    # count from zero, which is why the name is the handle and the bit is not).
    FILE_PATH = ECEPHY_DATA_PATH / "intan" / "intan_fps_test_231117_052500" / "info.rhd"

    def test_get_metadata(self):
        """get_metadata (default configuration) seeds one event_type per derived line, under the given
        metadata_key. Exact equality covers it all: the metadata_key namespace, the source id, the
        default event_name (the header's channel name), and the absence of ``columns`` (a single line has
        no value column) and ``event_description`` (an Intan file has no prose for a digital line)."""
        interface = IntanDigitalInterface(file_path=self.FILE_PATH, metadata_key="my_ttl")
        metadata = interface.get_metadata()

        # The Events block is namespaced under the given metadata_key ("my_ttl"); the fixture's one
        # line is the single event_type, named after its header channel name "DIGITAL-IN-01".
        expected_events = {"my_ttl": {"event_types": {"DIGITAL-IN-01": {"event_name": "DIGITAL-IN-01"}}}}
        assert metadata["Events"] == expected_events

    def test_available_signals_descriptor(self):
        """The inventory the validator checks a configuration against: its keys are the names the
        configuration may use, and each says which digital word the line came off."""
        available_signals = IntanDigitalInterface(file_path=self.FILE_PATH)._available_signals

        assert list(available_signals) == ["DIGITAL-IN-01"]
        assert available_signals["DIGITAL-IN-01"]["stream_name"] == "USB board digital input channel"
        # Every Intan digital signal is a line: the word arrives already demultiplexed into 0/1 traces.
        assert available_signals["DIGITAL-IN-01"]["kind"] == "line"

    def test_run_conversion(self, tmp_path):
        """Generic end-to-end default: a conversion writes the line to nwbfile.events as an EventsTable
        named from the header channel, surviving a disk roundtrip. With no configuration the default
        detection is ``high_period`` (onset at the 0->1 rise, duration to the 1->0 fall, assuming an
        active-high line), so the table is durative; the fixture's single high pulse gives the exact onset
        and span asserted below."""
        interface = IntanDigitalInterface(file_path=self.FILE_PATH)
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now(timezone.utc)  # Intan carries none

        path = tmp_path / "digital.nwb"
        interface.run_conversion(nwbfile_path=path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(path)
        tables = list(nwbfile.events.values())
        assert len(tables) == 1  # the word exposes one line -> one table
        table = tables[0]
        assert table.name == "DIGITAL-IN-01"  # named from the header channel
        assert set(table.colnames) == {
            "timestamp",
            "duration",
        }  # the default high_period is durative
        assert len(table) == 1  # one high pulse -> one event
        expected_timestamps = [0.1652]
        expected_durations = [0.5000333333333333]
        np.testing.assert_allclose(table["timestamp"][:], expected_timestamps)
        np.testing.assert_allclose(table["duration"][:], expected_durations)

    def test_each_detection_value_produces_its_event_shape(self):
        """The four readings, each as one spec over the same line (named after the reading), produce their
        distinct shapes. rising and falling are point events (timestamp only) at the 0->1 and 1->0 edges;
        high_period and low_period are durative, onset at their opening edge with the span to the closing
        edge as duration (NaN for low_period here, as the low span never closes). In-memory: the events
        are read off the nwbfile add_to_nwbfile builds, no disk roundtrip (that is test_run_conversion's
        job)."""
        interface = IntanDigitalInterface(
            file_path=self.FILE_PATH,
            detection_configuration={
                "DIGITAL-IN-01": [
                    {"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising", "event_name": "rising"},
                    {"signal_conditioning": {"binarize": "midpoint"}, "detection": "falling", "event_name": "falling"},
                    {
                        "signal_conditioning": {"binarize": "midpoint"},
                        "detection": "high_period",
                        "event_name": "high_period",
                    },
                    {
                        "signal_conditioning": {"binarize": "midpoint"},
                        "detection": "low_period",
                        "event_name": "low_period",
                    },
                ]
            },
        )
        nwbfile = mock_NWBFile()  # already carries a session_start_time
        interface.add_to_nwbfile(nwbfile=nwbfile)  # in-memory, no disk IO
        events = nwbfile.events

        # One table per spec; the event_name (the reading) CamelCases into the table object name.
        assert set(events.keys()) == {"Rising", "Falling", "HighPeriod", "LowPeriod"}

        # rising: a point event at each 0->1 rise. The fixture's single high pulse gives one rise.
        expected_name = "Rising"
        expected_timestamps = [0.1652]
        table = events[expected_name]
        assert table.name == expected_name
        assert table.colnames == ("timestamp",)  # point event: timestamp only, no duration
        np.testing.assert_allclose(table["timestamp"][:], expected_timestamps)

        # falling: a point event at each 1->0 fall. The single high pulse gives one fall.
        expected_name = "Falling"
        expected_timestamps = [0.6652333333333333]
        table = events[expected_name]
        assert table.name == expected_name
        assert table.colnames == ("timestamp",)  # point event: timestamp only, no duration
        np.testing.assert_allclose(table["timestamp"][:], expected_timestamps)

        # high_period: a durative event, onset at the 0->1 rise, duration = the span to the 1->0 fall.
        expected_name = "HighPeriod"
        expected_timestamps = [0.1652]
        expected_durations = [0.5000333333333333]
        table = events[expected_name]
        assert table.name == expected_name
        assert table.colnames == ("timestamp", "duration")  # durative: onset + span
        np.testing.assert_allclose(table["timestamp"][:], expected_timestamps)
        np.testing.assert_allclose(table["duration"][:], expected_durations)

        # low_period: a durative event, onset at the 1->0 fall. The low span never closes within the
        # recording, so its duration is NaN (a missing offset).
        expected_name = "LowPeriod"
        expected_timestamps = [0.6652333333333333]
        expected_durations = [np.nan]
        table = events[expected_name]
        assert table.name == expected_name
        assert table.colnames == ("timestamp", "duration")  # durative: onset + span
        np.testing.assert_allclose(table["timestamp"][:], expected_timestamps)
        np.testing.assert_allclose(table["duration"][:], expected_durations)


class TestIntanDigitalBothWords:
    """This is a test for an Intan file carrying both digital words.

    One interface covers both, because the header names every line individually and the name alone does
    the addressing. A recorded-but-idle line is written as an empty (zero-row) table, faithful to the
    source (the line existed, nothing fired), rather than being dropped. Whether an empty table is
    undesirable for archival is a best-practice question the NWB Inspector owns, not a conversion-time
    error.
    """

    # RHS carrying a digital-input word with 9 lines and a digital-output word with 16, of which only
    # DIGITAL-IN-13/14/15 and DIGITAL-OUT-13/14/15 toggle. This is the shape the single-line fixture
    # cannot exercise.
    FILE_PATH = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"

    def test_both_words_are_covered_without_naming_a_stream(self):
        """The interface is not told which digital word to read: it reads whichever the file carries.

        The two words share the amplifier's sampling rate and timeline, and their header names cannot
        collide (DIGITAL-IN-* against DIGITAL-OUT-*), so one keyspace addresses both.
        """
        available_signals = IntanDigitalInterface(file_path=self.FILE_PATH)._available_signals

        assert len(available_signals) == 25  # 9 input lines + 16 output lines
        streams = {descriptor["stream_name"] for descriptor in available_signals.values()}
        assert streams == {"USB board digital input channel", "USB board digital output channel"}

    def test_get_metadata(self):
        """get_metadata is configuration-derived: it lists every line regardless of which ones fired, so
        the set is decided by the format, not by the samples (and no traces are read to produce it). A
        custom metadata_key namespaces the Events block."""
        interface = IntanDigitalInterface(file_path=self.FILE_PATH, metadata_key="digital")
        metadata = interface.get_metadata()

        event_types = metadata["Events"]["digital"]["event_types"]
        assert len(event_types) == 25
        # Each line is one event_type named after its header channel name, idle lines included.
        assert event_types["DIGITAL-IN-01"] == {"event_name": "DIGITAL-IN-01"}
        assert event_types["DIGITAL-OUT-16"] == {"event_name": "DIGITAL-OUT-16"}
        assert interface._events_data_dict is None  # get_metadata did not trigger a trace read

    def test_add_to_nwbfile(self):
        """Which lines get a table is decided by the Intan header, not by the data: every line the header
        names is written to nwbfile.events. A line that never fires is an empty (zero-row) table, not a
        dropped one."""
        interface = IntanDigitalInterface(file_path=self.FILE_PATH)
        nwbfile = mock_NWBFile()  # already carries a session_start_time
        interface.add_to_nwbfile(nwbfile=nwbfile)  # in-memory, no disk IO
        events = nwbfile.events

        assert len(events) == 25  # one EventsTable per line, each named after that line

        # The toggling lines carry their events, one row per high pulse, on both words.
        non_empty = {name: len(table) for name, table in events.items() if len(table)}
        assert non_empty == {
            "DIGITAL-IN-13": 3,
            "DIGITAL-IN-14": 10,
            "DIGITAL-IN-15": 10,
            "DIGITAL-OUT-13": 3,
            "DIGITAL-OUT-14": 10,
            "DIGITAL-OUT-15": 10,
        }

    def test_lines_from_the_two_words_share_one_timeline(self):
        """The mirrored input and output lines carry identical event times, which is the check that
        reading both words through one interface does not put them on different clocks."""
        interface = IntanDigitalInterface(
            file_path=self.FILE_PATH,
            detection_configuration={
                "DIGITAL-IN-14": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "high_period"}],
                "DIGITAL-OUT-14": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "high_period"}],
            },
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        input_line = nwbfile.get_events_table("DIGITAL-IN-14")
        output_line = nwbfile.get_events_table("DIGITAL-OUT-14")
        np.testing.assert_allclose(input_line["timestamp"][:], output_line["timestamp"][:])
        np.testing.assert_allclose(input_line["duration"][:], output_line["duration"][:])

    def test_metadata_annotation(self):
        """The events-metadata propagation machinery and the addressability of its keys, through
        add_to_nwbfile. Three toggling lines are named explicitly (so the idle lines are not written),
        each pinned to a short identifier by its spec's ``event_name``, one reading shape each: an onset
        (rising, point), a high-span duration (high_period), and a low-span duration (low_period). The
        editable metadata then reaches each event type by ``metadata_key`` -> its ``event_type_source_id``
        (the join key) and sets:

        - a friendly ``event_name``, which the writer CamelCases into the table's NWB object name (so the
          source id "onset" with event_name "trial_onset" lands as the table "TrialOnset"); and
        - an ``event_description``, which becomes that solo table's description.

        Names and descriptions are the whole annotation surface here: these events are timestamps
        (+durations) only, no value column, so ``column_categories`` and a MeaningsTable do not apply."""
        metadata_key = "intan_digital_events"

        # Per event type, defined once and reused both when setting the metadata and when asserting the
        # result (so the set value and the checked value cannot drift): the source id that addresses it,
        # the event_name we set (which CamelCases into the table object name given beside it), and the
        # event_description we set.
        onset_id, onset_name, onset_table = "onset", "trial_onset", "TrialOnset"
        high_id, high_name, high_table = (
            "high",
            "camera_exposure_high",
            "CameraExposureHigh",
        )
        low_id, low_name, low_table = "low", "camera_exposure_low", "CameraExposureLow"
        onset_description = "Rising edge marking a trial onset."
        high_description = "Span the camera line is high."
        low_description = "Span the camera line is low."

        interface = IntanDigitalInterface(
            file_path=self.FILE_PATH,
            metadata_key=metadata_key,  # namespaces this interface's Events block
            detection_configuration={
                "DIGITAL-IN-13": [
                    {"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising", "event_name": onset_id}
                ],  # point onset
                "DIGITAL-IN-14": [
                    {"signal_conditioning": {"binarize": "midpoint"}, "detection": "high_period", "event_name": high_id}
                ],  # high span
                "DIGITAL-IN-15": [
                    {"signal_conditioning": {"binarize": "midpoint"}, "detection": "low_period", "event_name": low_id}
                ],  # low span
            },
        )
        metadata = interface.get_metadata()

        # Reach the event types by metadata_key -> event_type_source_id (the addressing/join keys).
        event_types = metadata["Events"][metadata_key]["event_types"]
        assert set(event_types) == {onset_id, high_id, low_id}

        event_types[onset_id]["event_name"] = onset_name
        event_types[onset_id]["event_description"] = onset_description
        event_types[high_id]["event_name"] = high_name
        event_types[high_id]["event_description"] = high_description
        event_types[low_id]["event_name"] = low_name
        event_types[low_id]["event_description"] = low_description

        nwbfile = mock_NWBFile()  # already carries a session_start_time
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)  # in-memory, no disk IO
        events = nwbfile.events

        # Each event_name CamelCases into its table's NWB object name; the source ids are the addressing
        # keys, not the table names.
        assert set(events.keys()) == {onset_table, high_table, low_table}

        # onset: a point event; its event_name named the table, its event_description describes it.
        trial_onset = events[onset_table]
        assert trial_onset.colnames == ("timestamp",)  # point event, no duration
        assert len(trial_onset) == 3
        assert trial_onset.description == onset_description

        # high: durative, the high-span duration of the line.
        camera_high = events[high_table]
        assert camera_high.colnames == ("timestamp", "duration")
        assert len(camera_high) == 10
        assert camera_high.description == high_description

        # low: durative, the low-span duration of the line.
        camera_low = events[low_table]
        assert camera_low.colnames == ("timestamp", "duration")
        assert len(camera_low) == 10
        assert camera_low.description == low_description

    def test_explicit_table_name_via_event_tables(self):
        """A table can be named explicitly in the metadata instead of from an event_name: declare it under
        the global ``EventTables`` block with a ``table_name`` and point event types at it via their
        ``table_metadata_key``. That is the pooling mechanism, so the named table also gains an
        ``event_type`` discriminator column naming each row's type. Here the two durative camera lines are
        pooled into one explicitly-named ``CameraExposure`` table, while the onset line stays solo and is
        named the default way (its event_name CamelCased)."""
        metadata_key = "intan_digital"  # the default namespace (no metadata_key passed)
        table_key, table_name = "exposure", "CameraExposure"
        table_description = "Camera exposure spans."
        onset_name, onset_table = "trial_onset", "TrialOnset"
        high_name, low_name = "exposure_high", "exposure_low"

        interface = IntanDigitalInterface(
            file_path=self.FILE_PATH,
            detection_configuration={
                "DIGITAL-IN-13": [
                    {"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising", "event_name": "onset"}
                ],  # stays solo
                "DIGITAL-IN-14": [
                    {"signal_conditioning": {"binarize": "midpoint"}, "detection": "high_period", "event_name": "high"}
                ],  # pooled
                "DIGITAL-IN-15": [
                    {"signal_conditioning": {"binarize": "midpoint"}, "detection": "low_period", "event_name": "low"}
                ],  # pooled
            },
        )
        metadata = interface.get_metadata()
        event_types = metadata["Events"][metadata_key]["event_types"]

        # onset keeps the default naming: its event_name CamelCases into the table object name.
        event_types["onset"]["event_name"] = onset_name

        # Declare the pooled table's name explicitly, and route the two durative lines into it. Each
        # pooled type's event_name becomes its label in the table's event_type column.
        metadata["Events"]["EventTables"] = {table_key: {"table_name": table_name, "description": table_description}}
        event_types["high"]["event_name"] = high_name
        event_types["high"]["table_metadata_key"] = table_key
        event_types["low"]["event_name"] = low_name
        event_types["low"]["table_metadata_key"] = table_key

        nwbfile = mock_NWBFile()  # already carries a session_start_time
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)  # in-memory, no disk IO
        events = nwbfile.events

        # The explicitly-named pooled table sits next to the solo onset table.
        assert set(events.keys()) == {table_name, onset_table}

        # onset: solo, named the default way, a plain point table (no event_type discriminator).
        assert events[onset_table].colnames == ("timestamp",)

        # The pooled table takes its name and description from the EventTables entry, carries an
        # event_type column labelling each row, and is durative (both pooled lines have durations).
        exposure = events[table_name]
        assert exposure.description == table_description
        assert set(exposure.colnames) == {"timestamp", "duration", "event_type"}
        assert set(exposure["event_type"][:]) == {high_name, low_name}
        assert len(exposure) == 20  # 10 high spans + 10 low spans


class TestIntanDigitalConfigurationIsCheckedAgainstTheInventory:
    """What Intan's own inventory adds to the shared validator, whose grammar checks are tested in
    ``tests/test_minimal/test_tools/test_events.py`` and are not repeated here."""

    FILE_PATH = ECEPHY_DATA_PATH / "intan" / "intan_fps_test_231117_052500" / "info.rhd"

    def test_a_line_admits_no_cut(self):
        """``bits`` has no place on Intan any more: the word is already demultiplexed, so there is no
        packed integer left to carve and every signal is a line. This is what removed the ``bits`` and
        ``stream_name`` arguments, since a line is addressed by its name rather than by its position."""
        with pytest.raises(ValueError, match="that signal is not a packed word"):
            IntanDigitalInterface(
                file_path=self.FILE_PATH,
                detection_configuration={
                    "DIGITAL-IN-01": [{"signal_conditioning": {"bits": [0]}, "detection": "rising"}]
                },
            )

    def test_a_line_takes_a_cut_but_not_a_bit_carve(self):
        """A line's spelling is a cut; what it refuses is `bits`, since there is no word left to carve.

        Intan's reader demultiplexes the digital word before this interface sees it, so every signal it
        exposes is a line and none of them is a packed integer.
        """
        interface = IntanDigitalInterface(
            file_path=self.FILE_PATH,
            detection_configuration={
                "DIGITAL-IN-01": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising"}]
            },
        )
        assert interface._get_events_data_dict()["DIGITAL-IN-01"].timestamps.size >= 0

        with pytest.raises(ValueError, match="not a packed\\nword|not a packed word"):
            IntanDigitalInterface(
                file_path=self.FILE_PATH,
                detection_configuration={
                    "DIGITAL-IN-01": [{"signal_conditioning": {"bits": [0]}, "detection": "rising"}]
                },
            )

    def test_a_line_the_file_does_not_have_raises_with_the_ones_it_does(self):
        """The old surface addressed lines by bit, so a typo named a number; now it names a string, and the
        message has to show which strings the file offers."""
        with pytest.raises(ValueError, match=r"'DIN-00', which is not one of the file's signals: \['DIGITAL-IN-01'\]"):
            IntanDigitalInterface(
                file_path=self.FILE_PATH,
                detection_configuration={
                    "DIN-00": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising"}]
                },
            )
