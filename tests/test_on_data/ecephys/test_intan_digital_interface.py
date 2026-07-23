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

    # A file whose digital-input word has a single toggling line (bit 0, one high pulse). The line's
    # native channel name is "DIGITAL-IN-01" while its bit position is 0.
    FILE_PATH = ECEPHY_DATA_PATH / "intan" / "intan_fps_test_231117_052500" / "info.rhd"
    STREAM = "USB board digital input channel"

    def test_get_metadata(self):
        """get_metadata (default event_specs) seeds one event_type per derived line, under the given
        metadata_key. Exact equality covers it all: the metadata_key namespace, the source id, the
        default event_name (the native channel name), and the absence of ``columns`` (a single line has
        no value column) and ``event_description`` (an Intan file has no prose for a digital line)."""
        interface = IntanDigitalInterface(file_path=self.FILE_PATH, stream_name=self.STREAM, metadata_key="my_ttl")
        metadata = interface.get_metadata()

        # The Events block is namespaced under the given metadata_key ("my_ttl"); the fixture's one
        # toggling line is the single event_type, named after its native channel name "DIGITAL-IN-01".
        expected_events = {"my_ttl": {"event_types": {"DIGITAL-IN-01": {"event_name": "DIGITAL-IN-01"}}}}
        assert metadata["Events"] == expected_events

    def test_run_conversion(self, tmp_path):
        """Generic end-to-end default: a conversion writes the enabled toggling line to nwbfile.events as
        an EventsTable named from the header channel, surviving a disk roundtrip. With no event_specs the
        default detect is ``high_period`` (onset at the 0->1 rise, duration to the 1->0 fall, assuming an
        active-high line), so the table is durative; the fixture's single high pulse gives the exact onset
        and span asserted below."""
        interface = IntanDigitalInterface(file_path=self.FILE_PATH, stream_name=self.STREAM)
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now(timezone.utc)  # Intan carries none

        path = tmp_path / "digital.nwb"
        interface.run_conversion(nwbfile_path=path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(path)
        tables = list(nwbfile.events.values())
        assert len(tables) == 1  # the word exposes one enabled line -> one table
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

    def test_each_detect_value_produces_its_event_shape(self):
        """The four detect values, each as one event_specs entry over the same bit (named after the
        detect), produce their distinct shapes. rising and falling are point events (timestamp only) at
        the 0->1 and 1->0 edges; high_period and low_period are durative, onset at their opening edge with
        the span to the closing edge as duration (NaN for low_period here, as the low span never closes).
        In-memory: the events are read off the nwbfile add_to_nwbfile builds, no disk roundtrip (that is
        test_run_conversion's job)."""
        interface = IntanDigitalInterface(
            file_path=self.FILE_PATH,
            stream_name=self.STREAM,
            event_specs={
                "rising": {"bits": [0], "detect": "rising"},
                "falling": {"bits": [0], "detect": "falling"},
                "high_period": {"bits": [0], "detect": "high_period"},
                "low_period": {"bits": [0], "detect": "low_period"},
            },
        )
        nwbfile = mock_NWBFile()  # already carries a session_start_time
        interface.add_to_nwbfile(nwbfile=nwbfile)  # in-memory, no disk IO
        events = nwbfile.events

        # One table per detect entry; the event_name (the detect) CamelCases into the table object name.
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


class TestIntanDigitalMultipleEnabledLines:
    """This is a test for a an intan file with multiple enabled lines.

    A recorded-but-idle line is written as an empty (zero-row) table, faithful to the source (the line
    existed, nothing fired), rather than being dropped. Whether an empty table is undesirable for archival
    is a best-practice question the NWB Inspector owns, not a conversion-time error.
    """

    # RHS with a digital-input word carrying 9 enabled lines, of which only 3 toggle (DIGITAL-IN-13/14/15);
    # the other 6 are enabled but idle. This is the shape the single-toggling fixture cannot exercise.
    FILE_PATH = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
    STREAM = "USB board digital input channel"

    def test_get_metadata(self):
        """get_metadata is header-derived: it lists all 9 enabled lines regardless of which ones fired,
        so the set is decided by the format, not by the samples (and no traces are read to produce it).
        A custom metadata_key namespaces the Events block."""
        interface = IntanDigitalInterface(file_path=self.FILE_PATH, stream_name=self.STREAM, metadata_key="digital_in")
        metadata = interface.get_metadata()

        # get_metadata contributes one Events block under the given metadata_key ("digital_in"), listing
        # every enabled line as an event_type named after its native channel name (the 6 idle lines 01-06
        # next to the 3 active ones 13-15). The NWBFile block it also returns carries a random identifier
        # and the neuroconv version, so it is not part of this equality.
        expected_events = {
            "digital_in": {
                "event_types": {
                    "DIGITAL-IN-01": {"event_name": "DIGITAL-IN-01"},
                    "DIGITAL-IN-02": {"event_name": "DIGITAL-IN-02"},
                    "DIGITAL-IN-03": {"event_name": "DIGITAL-IN-03"},
                    "DIGITAL-IN-04": {"event_name": "DIGITAL-IN-04"},
                    "DIGITAL-IN-05": {"event_name": "DIGITAL-IN-05"},
                    "DIGITAL-IN-06": {"event_name": "DIGITAL-IN-06"},
                    "DIGITAL-IN-13": {"event_name": "DIGITAL-IN-13"},
                    "DIGITAL-IN-14": {"event_name": "DIGITAL-IN-14"},
                    "DIGITAL-IN-15": {"event_name": "DIGITAL-IN-15"},
                }
            }
        }
        assert metadata["Events"] == expected_events
        assert interface._events_data_dict is None  # get_metadata did not trigger a trace read

    def test_add_to_nwbfile(self):
        """Which lines get a table is decided by the Intan header, not by the data: every line flagged
        ``channel_enabled`` is written to nwbfile.events. A line that never fires is an empty (zero-row)
        table, not a dropped one."""
        interface = IntanDigitalInterface(file_path=self.FILE_PATH, stream_name=self.STREAM)
        nwbfile = mock_NWBFile()  # already carries a session_start_time
        interface.add_to_nwbfile(nwbfile=nwbfile)  # in-memory, no disk IO
        events = nwbfile.events

        # nwbfile.events holds one EventsTable per enabled line, each named after that line. Exactly the 9
        # enabled digital channels are written, each as its own table.
        assert set(events.keys()) == {
            "DIGITAL-IN-01",
            "DIGITAL-IN-02",
            "DIGITAL-IN-03",
            "DIGITAL-IN-04",
            "DIGITAL-IN-05",
            "DIGITAL-IN-06",
            "DIGITAL-IN-13",
            "DIGITAL-IN-14",
            "DIGITAL-IN-15",
        }

        # The 3 toggling lines carry their events, one row per high pulse.
        assert len(events["DIGITAL-IN-13"]) == 3
        assert len(events["DIGITAL-IN-14"]) == 10
        assert len(events["DIGITAL-IN-15"]) == 10

        # The 6 enabled-but-idle lines are present but empty (zero-row), not dropped.
        assert len(events["DIGITAL-IN-01"]) == 0
        assert len(events["DIGITAL-IN-02"]) == 0
        assert len(events["DIGITAL-IN-03"]) == 0
        assert len(events["DIGITAL-IN-04"]) == 0
        assert len(events["DIGITAL-IN-05"]) == 0
        assert len(events["DIGITAL-IN-06"]) == 0

    def test_metadata_annotation(self):
        """The events-metadata propagation machinery and the addressability of its keys, through
        add_to_nwbfile. Three toggling lines are named explicitly (so the idle lines are not written),
        addressed by a short source id in event_specs, one detect shape each: an onset (rising, point),
        a high-span duration (high_period), and a low-span duration (low_period). The editable metadata
        then reaches each event type by ``metadata_key`` -> its ``event_type_source_id`` (the join key)
        and sets:

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
            stream_name=self.STREAM,
            metadata_key=metadata_key,  # namespaces this interface's Events block
            event_specs={
                onset_id: {
                    "bits": [12],
                    "detect": "rising",
                },  # DIGITAL-IN-13, point onset
                high_id: {
                    "bits": [13],
                    "detect": "high_period",
                },  # DIGITAL-IN-14, high span
                low_id: {
                    "bits": [14],
                    "detect": "low_period",
                },  # DIGITAL-IN-15, low span
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
            stream_name=self.STREAM,
            event_specs={
                "onset": {
                    "bits": [12],
                    "detect": "rising",
                },  # DIGITAL-IN-13, stays solo
                "high": {
                    "bits": [13],
                    "detect": "high_period",
                },  # DIGITAL-IN-14, pooled
                "low": {"bits": [14], "detect": "low_period"},  # DIGITAL-IN-15, pooled
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


class TestIntanDigitalEventSpecs:
    """How the ``event_specs`` argument is interpreted and validated (selection, bits, detect)."""

    # A file whose digital-input word has a single toggling line at bit 0 (native name "DIGITAL-IN-01").
    FILE_PATH = ECEPHY_DATA_PATH / "intan" / "intan_fps_test_231117_052500" / "info.rhd"
    STREAM = "USB board digital input channel"

    def test_event_name_comes_from_user_field_not_channel(self):
        """Metadata propagation: naming an event_specs field ``trig`` on bit 0 makes ``trig`` both the
        event type and its ``event_name`` in get_metadata, not the channel's native name ``DIGITAL-IN-01``.
        The line is only *addressed* by bit (native_order into the packed word); the user's field supplies
        the identity, and an explicit spec lists only that field (not the enabled-based default)."""
        interface = IntanDigitalInterface(
            file_path=self.FILE_PATH,
            stream_name=self.STREAM,
            event_specs={"trig": {"bits": [0], "detect": "rising"}},
        )
        event_types = interface.get_metadata()["Events"]["intan_digital"]["event_types"]

        assert event_types == {"trig": {"event_name": "trig"}}

    def test_empty_config_raises(self):
        """An empty event_specs is a likely mistake and raises (unlike None, which derives all lines)."""
        expected_error = (
            "event_specs is empty. Pass None (the default) to derive every enabled line, or name at "
            "least one line, e.g. {'sync': {'bits': [0]}}. To skip digital events entirely, do not "
            "construct this interface (or exclude the stream in the converter)."
        )
        with pytest.raises(ValueError) as exception_info:
            IntanDigitalInterface(file_path=self.FILE_PATH, stream_name=self.STREAM, event_specs={})
        assert str(exception_info.value) == expected_error

    def test_coded_multibit_word_raises(self):
        """A coded/multi-bit word (bits length > 1) is deferred and raises with the exact message."""
        expected_error = (
            "event_specs field 'c' declares a coded/multi-bit word (bits=[0, 1, 2]). Coded words need a strobe line "
            "to be read safely and are not supported yet; pass one bit per entry."
        )
        with pytest.raises(ValueError) as exception_info:
            IntanDigitalInterface(
                file_path=self.FILE_PATH,
                stream_name=self.STREAM,
                event_specs={"c": {"bits": [0, 1, 2]}},
            )
        assert str(exception_info.value) == expected_error

    def test_absent_bit_position_raises(self):
        """A bit position not present in the word raises with the exact message (listing available bits)."""
        expected_error = (
            "event_specs field 'c' references bit 99, which is not present in stream 'USB board digital input channel'. "
            "Available bit positions are [0]."
        )
        with pytest.raises(ValueError) as exception_info:
            IntanDigitalInterface(
                file_path=self.FILE_PATH,
                stream_name=self.STREAM,
                event_specs={"c": {"bits": [99]}},
            )
        assert str(exception_info.value) == expected_error

    def test_invalid_detect_raises(self):
        """An unknown detect value raises with the exact message (listing valid values)."""
        expected_error = (
            "event_specs field 'c' has invalid detect 'nope'. Valid values are "
            "['rising', 'falling', 'high_period', 'low_period']."
        )
        with pytest.raises(ValueError) as exception_info:
            IntanDigitalInterface(
                file_path=self.FILE_PATH,
                stream_name=self.STREAM,
                event_specs={"c": {"bits": [0], "detect": "nope"}},
            )
        assert str(exception_info.value) == expected_error

    def test_empty_bits_list_raises(self):
        """An empty bits list raises with the exact message."""
        expected_error = "event_specs field 'c' must set 'bits' to a non-empty list, got []."
        with pytest.raises(ValueError) as exception_info:
            IntanDigitalInterface(
                file_path=self.FILE_PATH,
                stream_name=self.STREAM,
                event_specs={"c": {"bits": []}},
            )
        assert str(exception_info.value) == expected_error
