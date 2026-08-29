"""Tests of how the MedPC events interfaces decode a value into a time and an event type.

MedPC writes whatever the MSN program computed and records neither the unit it divided by, the resolution of the
box's clock, nor whether the program stored absolute times or intervals. Every one of those decodes without
error, so these tests state each encoding against a file written here rather than against a recording.
"""

from datetime import datetime

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import MedPCArrayEventsInterface, MedPCCodedEventsInterface

SESSION_HEADER = {"Start Date": "04/10/19", "Start Time": "12:36:13"}


def write_medpc_file(file_path, arrays: dict[str, list[float]], columns: int = 5) -> None:
    """Write a MED-PC IV annotated file holding one session and the given arrays."""
    lines = [
        r"File: C:\MED-PC IV\DATA\!2019-04-10_12h36m.Subject TEST-01",
        "",
        "",
        "Start Date: 04/10/19",
        "End Date: 04/10/19",
        "Subject: TEST-01",
        "Experiment: ",
        "Group: 1",
        "Box: 1",
        "Start Time: 12:36:13",
        "End Time: 13:38:19",
        "MSN: TEST_PROGRAM",
    ]
    for name, values in sorted(arrays.items()):
        lines.append(f"{name}:")
        for start in range(0, len(values), columns):
            row = "".join(f"{value:13.3f}" for value in values[start : start + columns])
            lines.append(f"{start:6d}:{row}")
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestTimeUnit:
    """A value is a time only once the unit the program divided by is applied."""

    def test_seconds_is_the_default(self, tmp_path):
        path = tmp_path / "seconds.txt"
        write_medpc_file(path, {"A": [1.5, 2.25, 3.0]})

        interface = MedPCArrayEventsInterface(
            file_path=path, session_header=SESSION_HEADER, event_configuration={"A": {"name": "poke"}}
        )

        assert np.allclose(interface.get_event_times("A"), [1.5, 2.25, 3.0])

    @pytest.mark.parametrize(
        "time_unit, expected",
        [
            ("centiseconds", [1.5, 2.25, 3.0]),
            ("deciseconds", [15.0, 22.5, 30.0]),
            ("milliseconds", [0.15, 0.225, 0.3]),
        ],
    )
    def test_a_scaled_unit(self, tmp_path, time_unit, expected):
        path = tmp_path / "scaled.txt"
        write_medpc_file(path, {"A": [150.0, 225.0, 300.0]})

        interface = MedPCArrayEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            event_configuration={"A": {"name": "poke"}},
            time_unit=time_unit,
        )

        assert np.allclose(interface.get_event_times("A"), expected)

    def test_clock_ticks_take_the_rate(self, tmp_path):
        # An array of raw BTIME counts, which is what a program storing `Set L(K) = BTIME-U` writes. The rate is
        # fixed when MED-PC is installed and appears in no file, so it is stated here.
        path = tmp_path / "ticks.txt"
        write_medpc_file(path, {"A": [500.0, 1000.0, 2750.0]})

        interface = MedPCArrayEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            event_configuration={"A": {"name": "lick"}},
            time_unit="clock_ticks",
            clock_ticks_per_second=500,
        )

        assert np.allclose(interface.get_event_times("A"), [1.0, 2.0, 5.5])

    def test_clock_ticks_without_a_rate_raises(self, tmp_path):
        path = tmp_path / "ticks.txt"
        write_medpc_file(path, {"A": [500.0]})

        with pytest.raises(ValueError, match="`clock_ticks_per_second` is required"):
            MedPCArrayEventsInterface(
                file_path=path,
                session_header=SESSION_HEADER,
                event_configuration={"A": {"name": "lick"}},
                time_unit="clock_ticks",
            )

    def test_a_rate_without_clock_ticks_raises(self, tmp_path):
        # Stating a rate that nothing would use hides a misunderstanding rather than a typo, so it is refused
        # instead of ignored.
        path = tmp_path / "seconds.txt"
        write_medpc_file(path, {"A": [1.0]})

        with pytest.raises(ValueError, match="would not be used"):
            MedPCArrayEventsInterface(
                file_path=path,
                session_header=SESSION_HEADER,
                event_configuration={"A": {"name": "lick"}},
                clock_ticks_per_second=500,
            )

    def test_durations_take_the_same_unit_as_the_onsets(self, tmp_path):
        path = tmp_path / "durative.txt"
        write_medpc_file(path, {"G": [100.0, 300.0], "E": [50.0, 25.0]})

        interface = MedPCArrayEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            event_configuration={"G": {"name": "port_entries", "duration": "E"}},
            time_unit="centiseconds",
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        port_entries = nwbfile.get_events_table("PortEntries")
        assert np.allclose(port_entries["timestamp"][:], [1.0, 3.0])
        assert np.allclose(port_entries["duration"][:], [0.5, 0.25])


class TestRelativeTimes:
    """Med Associates' own example procedures store the interval since the previous event, not the elapsed time."""

    def test_intervals_are_accumulated(self, tmp_path):
        # `SET C(I) = T + 0.10, T = 0` with T in centiseconds, which is what the shipped FR5 procedure writes.
        path = tmp_path / "relative.txt"
        write_medpc_file(path, {"C": [150.10, 62.10, 88.10, 31.20]})

        interface = MedPCCodedEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            timestamps_variable="C",
            code_scale=100,
            time_unit="centiseconds",
            times_are_intervals=True,
            event_configuration={"10": {"name": "left_lever"}, "20": {"name": "reinforcement"}},
        )

        assert np.allclose(interface.get_event_times("10"), [1.5, 2.12, 3.0])
        assert np.allclose(interface.get_event_times("20"), [3.31])

    def test_reading_intervals_as_absolute_times_raises(self, tmp_path):
        # The whole point of the check: this file decodes without error and only the ordering betrays it.
        path = tmp_path / "relative.txt"
        write_medpc_file(path, {"C": [150.10, 62.10, 88.10]})

        interface = MedPCCodedEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            timestamps_variable="C",
            code_scale=100,
            time_unit="centiseconds",
        )

        with pytest.raises(ValueError, match="run backwards"):
            interface.get_event_times("10")


class TestCodePosition:
    """A program packs the event's code into the value from either end."""

    def test_the_code_in_the_fraction(self, tmp_path):
        path = tmp_path / "fraction.txt"
        write_medpc_file(path, {"A": [10602.001, 10602.011, 10852.021]})

        interface = MedPCCodedEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            timestamps_variable="A",
            time_unit="clock_ticks",
            clock_ticks_per_second=500,
        )

        assert set(interface.get_event_type_source_ids()) == {"001", "011", "021"}
        assert np.allclose(interface.get_event_times("001"), [21.204])

    def test_the_code_in_the_leading_digits(self, tmp_path):
        # `^PeckLeft=10000` with `set x(y)=^PeckLeft+Btime/1"`, documented as `aabbbb.bbb` where `aa` is the code
        # and the rest is the time in seconds.
        path = tmp_path / "leading.txt"
        write_medpc_file(path, {"A": [10064.540, 20101.250, 10182.000]})

        interface = MedPCCodedEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            timestamps_variable="A",
            code_scale=10000,
            code_position="leading",
            event_configuration={"1": {"name": "peck_left"}, "2": {"name": "peck_right"}},
        )

        assert np.allclose(interface.get_event_times("1"), [64.54, 182.0])
        assert np.allclose(interface.get_event_times("2"), [101.25])

    def test_the_identifier_is_padded_to_the_divisor(self, tmp_path):
        # A divisor of 100 leaves two digits, so the identifiers read as the program writes them.
        path = tmp_path / "two_digits.txt"
        write_medpc_file(path, {"A": [1.10, 2.20]})

        interface = MedPCCodedEventsInterface(
            file_path=path, session_header=SESSION_HEADER, timestamps_variable="A", code_scale=100
        )

        assert set(interface.get_event_type_source_ids()) == {"10", "20"}

    @pytest.mark.parametrize("legend_key", [11, "11", "011"], ids=["int", "unpadded", "padded"])
    def test_a_legend_key_reaches_the_padded_identifier(self, tmp_path, legend_key):
        # The identifiers are zero-padded to the scale's width, but a legend is written the way the program
        # numbers its codes. Keying the legend literally used to leave the real type named `code_011` and add a
        # phantom empty table carrying the user's name beside it.
        path = tmp_path / "legend.txt"
        write_medpc_file(path, {"A": [100.011, 200.011]})

        interface = MedPCCodedEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            timestamps_variable="A",
            event_configuration={legend_key: {"name": "pump_a_on"}},
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert set(interface.get_event_type_source_ids()) == {"011"}
        assert set(nwbfile.events) == {"PumpAOn"}
        assert len(nwbfile.get_events_table("PumpAOn")) == 2

    def test_a_scale_leaving_no_digits_raises(self, tmp_path):
        path = tmp_path / "a.txt"
        write_medpc_file(path, {"A": [1.0]})

        with pytest.raises(ValueError, match="leaves no digits for a code"):
            MedPCCodedEventsInterface(
                file_path=path, session_header=SESSION_HEADER, timestamps_variable="A", code_scale=1
            )


class TestCompanionCodeArray:
    """Some programs write the codes into their own array instead of packing them into the times."""

    def test_codes_from_a_second_array(self, tmp_path):
        # `SET B(L) = X(1), C(L) = 1`, one array of times beside one array of identities.
        path = tmp_path / "parallel.txt"
        write_medpc_file(path, {"B": [1.9, 7.51, 7.87, 17.2], "C": [3.0, 1.0, 1.0, 3.0]})

        interface = MedPCCodedEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            timestamps_variable="B",
            event_type_variable="C",
            event_configuration={"1": {"name": "lever_press"}, "3": {"name": "magazine_entry"}},
        )

        assert np.allclose(interface.get_event_times("1"), [7.51, 7.87])
        assert np.allclose(interface.get_event_times("3"), [1.9, 17.2])

    def test_a_fractional_code_keeps_its_fraction(self, tmp_path):
        # Codes such as 3.1 and 3.2 appear in the wild, so the identifier is left as the program wrote it.
        path = tmp_path / "fractional.txt"
        write_medpc_file(path, {"B": [1.0, 2.0], "C": [3.1, 3.2]})

        interface = MedPCCodedEventsInterface(
            file_path=path, session_header=SESSION_HEADER, timestamps_variable="B", event_type_variable="C"
        )

        assert set(interface.get_event_type_source_ids()) == {"3.1", "3.2"}

    def test_packing_arguments_beside_a_code_array_raise(self, tmp_path):
        # Both say where the code is, so passing both means one of them is a misunderstanding.
        path = tmp_path / "both.txt"
        write_medpc_file(path, {"B": [1.0], "C": [1.0]})

        with pytest.raises(ValueError, match="not both"):
            MedPCCodedEventsInterface(
                file_path=path,
                session_header=SESSION_HEADER,
                timestamps_variable="B",
                event_type_variable="C",
                code_scale=1000,
            )

    def test_a_mismatched_code_array_raises(self, tmp_path):
        path = tmp_path / "mismatch.txt"
        write_medpc_file(path, {"B": [1.0, 2.0, 3.0], "C": [1.0, 2.0]})

        interface = MedPCCodedEventsInterface(
            file_path=path, session_header=SESSION_HEADER, timestamps_variable="B", event_type_variable="C"
        )

        with pytest.raises(ValueError, match="not one code per event"):
            interface.get_event_type_source_ids()


class TestSealedArray:
    """`-987.987` seals an array at its last real element; it is a marker, not an event."""

    def test_the_seal_and_what_follows_it_are_dropped(self, tmp_path):
        path = tmp_path / "sealed.txt"
        write_medpc_file(path, {"A": [1.0, 2.0, 3.0, -987.987, 0.0, 0.0]})

        interface = MedPCArrayEventsInterface(
            file_path=path, session_header=SESSION_HEADER, event_configuration={"A": {"name": "poke"}}
        )

        assert np.allclose(interface.get_event_times("A"), [1.0, 2.0, 3.0])


def test_a_space_padded_header_value_still_matches(tmp_path):
    # MED-PC pads a single-digit hour with a space ("Start Time:  9:47:07"), which a caller writing the time out
    # would not reproduce. Matching the whole line made 272 of 936 files of one published corpus unreadable.
    path = tmp_path / "padded.txt"
    write_medpc_file(path, {"A": [1.0]})
    text = path.read_text(encoding="utf-8").replace("Start Time: 12:36:13", "Start Time:  9:47:07")
    path.write_text(text, encoding="utf-8")

    interface = MedPCArrayEventsInterface(
        file_path=path,
        session_header={"Start Date": "04/10/19", "Start Time": "9:47:07"},
        event_configuration={"A": {"name": "poke"}},
    )

    assert np.allclose(interface.get_event_times("A"), [1.0])


def test_events_grouped_by_type_are_not_read_as_backwards(tmp_path):
    # A program may write every event of one type before the next, so the pooled array is not sorted even though
    # each type's own onsets climb. The order check is per type for exactly this reason.
    path = tmp_path / "grouped.txt"
    write_medpc_file(path, {"B": [1.0, 2.0, 3.0, 1.5, 2.5], "C": [1.0, 1.0, 1.0, 2.0, 2.0]})

    interface = MedPCCodedEventsInterface(
        file_path=path, session_header=SESSION_HEADER, timestamps_variable="B", event_type_variable="C"
    )

    assert np.allclose(interface.get_event_times("1"), [1.0, 2.0, 3.0])
    assert np.allclose(interface.get_event_times("2"), [1.5, 2.5])


def test_interleaved_events_out_of_order_are_caught(tmp_path):
    # The counterpart of the grouped case. Here the types alternate, so the program was writing events as they
    # happened and the pooled order is a time order. One published corpus stores two types in different units
    # inside one array, which shows up exactly like this and is caught only by the pooled check.
    path = tmp_path / "interleaved.txt"
    write_medpc_file(path, {"B": [1.9, 75.1, 78.7, 17.2], "C": [3.0, 1.0, 1.0, 3.0]})

    interface = MedPCCodedEventsInterface(
        file_path=path, session_header=SESSION_HEADER, timestamps_variable="B", event_type_variable="C"
    )

    with pytest.raises(ValueError, match="run backwards"):
        interface.get_event_type_source_ids()


def test_the_order_check_can_be_refused(tmp_path):
    # The check is a heuristic about the program, and a published file usually does not ship with its program.
    # Someone who has it and knows the order is not evidence of a misreading reads the file as stated.
    path = tmp_path / "unordered.txt"
    write_medpc_file(path, {"A": [3.0, 1.0, 2.0]})

    interface = MedPCArrayEventsInterface(
        file_path=path,
        session_header=SESSION_HEADER,
        event_configuration={"A": {"name": "poke"}},
        check_event_order=False,
    )

    assert np.allclose(interface.get_event_times("A"), [3.0, 1.0, 2.0])


def test_a_clock_rate_of_zero_raises(tmp_path):
    path = tmp_path / "zero_rate.txt"
    write_medpc_file(path, {"A": [1.0]})

    with pytest.raises(ValueError, match="is not a rate"):
        MedPCArrayEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            event_configuration={"A": {"name": "poke"}},
            time_unit="clock_ticks",
            clock_ticks_per_second=0,
        )


def test_a_code_wider_than_the_scale_raises(tmp_path):
    # A value carrying more decimals than the scale accounts for folds part of the time into the code.
    path = tmp_path / "wide.txt"
    write_medpc_file(path, {"A": [5.999, 6.999]})

    interface = MedPCCodedEventsInterface(
        file_path=path, session_header=SESSION_HEADER, timestamps_variable="A", code_scale=100
    )

    with pytest.raises(ValueError, match="has no room for"):
        interface.get_event_type_source_ids()


def test_a_legend_key_that_is_not_a_code_raises(tmp_path):
    path = tmp_path / "bad_legend.txt"
    write_medpc_file(path, {"A": [1.011]})

    interface = MedPCCodedEventsInterface(
        file_path=path,
        session_header=SESSION_HEADER,
        timestamps_variable="A",
        event_configuration={"lick": {"name": "lick"}},
    )

    with pytest.raises(ValueError, match="is not an event code"):
        interface.get_event_type_source_ids()


def test_the_session_header_still_selects(tmp_path):
    # The encodings above all use a single-session file; this checks the header reading survives them.
    path = tmp_path / "header.txt"
    write_medpc_file(path, {"A": [1.0]})

    interface = MedPCArrayEventsInterface(
        file_path=path, session_header=SESSION_HEADER, event_configuration={"A": {"name": "poke"}}
    )
    metadata = interface.get_metadata()

    assert metadata["NWBFile"]["session_start_time"] == datetime(2019, 4, 10, 12, 36, 13)
    assert metadata["Subject"]["subject_id"] == "TEST-01"
    assert metadata["NWBFile"]["protocol"] == "TEST_PROGRAM"
