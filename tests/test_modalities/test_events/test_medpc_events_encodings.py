"""Tests of how the MedPC events interfaces decode a value into a time and an event type.

MedPC writes whatever the MSN program computed and records neither the unit it divided by, the resolution of the
box's clock, nor whether the program stored absolute times or intervals. Every one of those decodes without
error, so these tests state each encoding against a file written here rather than against a recording.
"""

import numpy as np
import pytest
from pydantic import ValidationError
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import MedPCArrayEventsInterface, MedPCCodedEventsInterface

SESSION_HEADER = {"Start Date": "04/10/19", "Start Time": "12:36:13"}


def write_medpc_file(file_path, arrays: dict[str, list[float]], columns: int = 5, decimals: int = 3) -> None:
    """Write a MED-PC IV annotated file holding one session and the given arrays.

    ``decimals`` is `DISKFORMAT`'s second half, the digits printed after the decimal point. It is what fixes how
    many digits a fraction-packed event code occupies, so a test that wants two-digit codes writes two.
    """
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
            row = "".join(f"{value:13.{decimals}f}" for value in values[start : start + columns])
            lines.append(f"{start:6d}:{row}")
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestTimeUnit:
    """A value is a time only once the unit the program divided by is applied."""

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
            event_configuration={"A": None},
            time_unit=time_unit,
        )

        assert np.allclose(interface.get_event_times("A"), expected)

    def test_a_resolution_given_as_a_number(self, tmp_path):
        # An array of raw BTIME counts, which is what a program storing `Set L(K) = BTIME-U` writes. A tick has
        # no name because its worth is the resolution MED-PC was installed at, which appears in no file, so it
        # is stated as a number of seconds: 0.002 on a 2 ms system.
        path = tmp_path / "ticks.txt"
        write_medpc_file(path, {"A": [500.0, 1000.0, 2750.0]})

        interface = MedPCArrayEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            event_configuration={"A": None},
            time_unit=0.002,
        )

        assert np.allclose(interface.get_event_times("A"), [1.0, 2.0, 5.5])

    def test_durations_take_the_same_unit_as_the_onsets(self, tmp_path):
        path = tmp_path / "durative.txt"
        write_medpc_file(path, {"G": [100.0, 300.0], "E": [50.0, 25.0]})

        interface = MedPCArrayEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            event_configuration={"G": {"duration": "E"}},
            time_unit="centiseconds",
        )
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        metadata["Events"]["medpc"]["event_types"]["G"]["event_name"] = "port_entries"
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        port_entries = nwbfile.get_events_table("PortEntries")
        assert np.allclose(port_entries["timestamp"][:], [1.0, 3.0])
        assert np.allclose(port_entries["duration"][:], [0.5, 0.25])


class TestRelativeTimes:
    """Med Associates' own example procedures store the interval since the previous event, not the elapsed time."""

    def test_intervals_are_accumulated(self, tmp_path):
        # `SET C(I) = T + 0.10, T = 0` with T in centiseconds, which is what the shipped FR5 procedure writes.
        path = tmp_path / "relative.txt"
        write_medpc_file(path, {"C": [150.10, 62.10, 88.10, 31.20]}, decimals=2)

        interface = MedPCCodedEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            events_variable="C",
            time_unit="centiseconds",
            relative_mode=True,
        )

        assert np.allclose(interface.get_event_times("10"), [1.5, 2.12, 3.0])
        assert np.allclose(interface.get_event_times("20"), [3.31])

    def test_reading_intervals_as_absolute_times_raises(self, tmp_path):
        # The whole point of the check: this file decodes without error and only the ordering betrays it.
        path = tmp_path / "relative.txt"
        write_medpc_file(path, {"C": [150.10, 62.10, 88.10]}, decimals=2)

        interface = MedPCCodedEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            events_variable="C",
            time_unit="centiseconds",
        )

        with pytest.raises(ValueError, match="run backwards"):
            interface.get_event_times("10")


class TestCodePosition:
    """A program packs the event's code into the value from either end."""

    def test_the_code_in_the_leading_digits(self, tmp_path):
        # `^PeckLeft=10000` with `set x(y)=^PeckLeft+Btime/1"`, documented as `aabbbb.bbb` where `aa` is the code
        # and the rest is the time in seconds.
        path = tmp_path / "leading.txt"
        write_medpc_file(path, {"A": [10064.540, 20101.250, 10182.000]})

        interface = MedPCCodedEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            events_variable="A",
            event_code_factor=10000,
            event_code_position="leading",
        )

        assert np.allclose(interface.get_event_times("1"), [64.54, 182.0])
        assert np.allclose(interface.get_event_times("2"), [101.25])

    def test_the_printed_width_fixes_the_code_width(self, tmp_path):
        # `DISKFORMAT` decides how many digits print after the point, and those digits are the code. A file
        # printing two gives two-digit identifiers without anything being stated.
        path = tmp_path / "two_digits.txt"
        write_medpc_file(path, {"A": [1.10, 2.20]}, decimals=2)

        interface = MedPCCodedEventsInterface(file_path=path, session_header=SESSION_HEADER, events_variable="A")

        assert set(interface.get_event_type_source_ids()) == {"10", "20"}

    def test_a_file_printing_no_decimals_cannot_hold_a_packed_code(self, tmp_path):
        # `DISKFORMAT = 13` prints no decimals at all, which is the commonest setting of the 361 programs
        # surveyed, and is why those programs pack into the leading digits instead.
        path = tmp_path / "no_decimals.txt"
        write_medpc_file(path, {"A": [10602.0, 10900.0]}, decimals=0)

        interface = MedPCCodedEventsInterface(file_path=path, session_header=SESSION_HEADER, events_variable="A")

        with pytest.raises(ValueError, match="print no digits after the decimal point"):
            interface.get_event_type_source_ids()

    def test_a_factor_in_fraction_position_is_refused(self, tmp_path):
        # The file states it, so stating it again is a misunderstanding rather than a harmless extra.
        path = tmp_path / "a.txt"
        write_medpc_file(path, {"A": [1.011]})

        with pytest.raises(ValueError, match="not needed in fraction position"):
            MedPCCodedEventsInterface(
                file_path=path, session_header=SESSION_HEADER, events_variable="A", event_code_factor=1000
            )

    def test_leading_position_without_a_factor_raises(self, tmp_path):
        path = tmp_path / "a.txt"
        write_medpc_file(path, {"A": [10064.540]})

        with pytest.raises(ValueError, match="`event_code_factor` is required"):
            MedPCCodedEventsInterface(
                file_path=path,
                session_header=SESSION_HEADER,
                events_variable="A",
                event_code_position="leading",
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
            events_variable="B",
            event_type_variable="C",
        )

        assert np.allclose(interface.get_event_times("1"), [7.51, 7.87])
        assert np.allclose(interface.get_event_times("3"), [1.9, 17.2])

    def test_a_fractional_code_keeps_its_fraction(self, tmp_path):
        # Codes such as 3.1 and 3.2 appear in the wild, so the identifier is left as the program wrote it.
        path = tmp_path / "fractional.txt"
        write_medpc_file(path, {"B": [1.0, 2.0], "C": [3.1, 3.2]})

        interface = MedPCCodedEventsInterface(
            file_path=path, session_header=SESSION_HEADER, events_variable="B", event_type_variable="C"
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
                events_variable="B",
                event_type_variable="C",
                event_code_factor=1000,
            )

    def test_a_unit_per_event_type(self, tmp_path):
        # A program can time two event types differently and store them in one array. Nothing in the file says
        # so; the sign of it is that the pooled times run backwards while each type on its own climbs.
        path = tmp_path / "two_bases.txt"
        write_medpc_file(path, {"B": [19.8, 2.62, 27.0, 2.94, 30.1], "C": [1.0, 3.0, 1.0, 3.0, 1.0]})

        interface = MedPCCodedEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            events_variable="B",
            event_type_variable="C",
            time_unit={"1": "seconds", "3": "decaseconds"},
        )

        assert np.allclose(interface.get_event_times("1"), [19.8, 27.0, 30.1])
        assert np.allclose(interface.get_event_times("3"), [26.2, 29.4])

    def test_one_unit_for_a_two_base_file_is_still_refused(self, tmp_path):
        # The same file read with a single unit: the guard has to keep firing, or the mapping would be the only
        # thing standing between a user and a silently mis-scaled conversion.
        path = tmp_path / "two_bases.txt"
        write_medpc_file(path, {"B": [19.8, 2.62, 27.0, 2.94, 30.1], "C": [1.0, 3.0, 1.0, 3.0, 1.0]})

        interface = MedPCCodedEventsInterface(
            file_path=path, session_header=SESSION_HEADER, events_variable="B", event_type_variable="C"
        )

        with pytest.raises(ValueError, match="run backwards"):
            interface.get_event_type_source_ids()

    def test_a_unit_mapping_missing_a_type_raises(self, tmp_path):
        path = tmp_path / "two_bases.txt"
        write_medpc_file(path, {"B": [1.0, 2.0], "C": [1.0, 3.0]})

        interface = MedPCCodedEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            events_variable="B",
            event_type_variable="C",
            time_unit={"1": "seconds"},
        )

        with pytest.raises(ValueError, match="has to give a unit for every type"):
            interface.get_event_type_source_ids()

    def test_a_mismatched_code_array_raises(self, tmp_path):
        path = tmp_path / "mismatch.txt"
        write_medpc_file(path, {"B": [1.0, 2.0, 3.0], "C": [1.0, 2.0]})

        interface = MedPCCodedEventsInterface(
            file_path=path, session_header=SESSION_HEADER, events_variable="B", event_type_variable="C"
        )

        with pytest.raises(ValueError, match="not one code per event"):
            interface.get_event_type_source_ids()


class TestSealedArray:
    """`-987.987` seals an array at its last real element; it is a marker, not an event."""

    def test_the_seal_and_what_follows_it_are_dropped(self, tmp_path):
        path = tmp_path / "sealed.txt"
        write_medpc_file(path, {"A": [1.0, 2.0, 3.0, -987.987, 0.0, 0.0]})

        interface = MedPCArrayEventsInterface(
            file_path=path, session_header=SESSION_HEADER, event_configuration={"A": None}
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
        event_configuration={"A": None},
    )

    assert np.allclose(interface.get_event_times("A"), [1.0])


def test_events_grouped_by_type_are_not_read_as_backwards(tmp_path):
    # A program may write every event of one type before the next, so the pooled array is not sorted even though
    # each type's own onsets climb. The order check is per type for exactly this reason.
    path = tmp_path / "grouped.txt"
    write_medpc_file(path, {"B": [1.0, 2.0, 3.0, 1.5, 2.5], "C": [1.0, 1.0, 1.0, 2.0, 2.0]})

    interface = MedPCCodedEventsInterface(
        file_path=path, session_header=SESSION_HEADER, events_variable="B", event_type_variable="C"
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
        file_path=path, session_header=SESSION_HEADER, events_variable="B", event_type_variable="C"
    )

    with pytest.raises(ValueError, match="run backwards"):
        interface.get_event_type_source_ids()


def test_a_unit_mapping_is_refused_by_the_array_interface(tmp_path):
    # One array per event type means each already has its own unit slot; a mapping there says nothing.
    path = tmp_path / "array.txt"
    write_medpc_file(path, {"A": [1.0, 2.0]})

    with pytest.raises(ValidationError):
        MedPCArrayEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            event_configuration={"A": None},
            time_unit={"A": "seconds"},
        )


def test_a_time_after_the_session_ended_is_caught(tmp_path):
    # The header states both ends of the session, so the file itself says how long it ran and no event can fall
    # outside that. This is the only bound MedPC gives on the size of a time, and it is what catches an
    # over-scaled file: accumulating intervals always yields a rising series, so ordering alone cannot.
    path = tmp_path / "too_long.txt"
    write_medpc_file(path, {"A": [100.0, 200.0, 9000.0]})  # the header says 12:36:13 to 13:38:19, 3726 s

    interface = MedPCArrayEventsInterface(
        file_path=path, session_header=SESSION_HEADER, event_configuration={"A": None}
    )

    with pytest.raises(ValueError, match="says the session ran"):
        interface.get_event_times("A")


def test_accumulating_times_that_were_not_intervals_is_caught(tmp_path):
    # The trap the ordering error's own first suggestion can lead into: `relative_mode=True` always produces a
    # rising series, so it silences the ordering check whether or not the program used Relative Mode.
    path = tmp_path / "not_intervals.txt"
    write_medpc_file(path, {"A": [600.0, 1200.0, 1800.0, 2400.0]})  # already elapsed times, well inside 3726 s

    interface = MedPCArrayEventsInterface(
        file_path=path,
        session_header=SESSION_HEADER,
        event_configuration={"A": None},
        relative_mode=True,
    )

    with pytest.raises(ValueError, match="says the session ran"):
        interface.get_event_times("A")


def test_a_resolution_of_zero_raises(tmp_path):
    path = tmp_path / "zero_rate.txt"
    write_medpc_file(path, {"A": [1.0]})

    with pytest.raises(ValueError, match="is not a length of time"):
        MedPCArrayEventsInterface(
            file_path=path,
            session_header=SESSION_HEADER,
            event_configuration={"A": None},
            time_unit=0.0,
        )
