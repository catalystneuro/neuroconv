"""Tests of how the MedPC events interfaces decode a value into a time and an event type.

MedPC writes whatever the MSN program computed and records neither the unit it divided by, the resolution of the
box's clock, nor whether the program stored absolute times or intervals. Every one of those decodes without
error, so these tests state each encoding against a file written here rather than against a recording.
"""

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import MedPCArrayEventsInterface, MedPCPackedEventsInterface

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


def test_a_file_printing_no_decimals_cannot_hold_a_packed_code(tmp_path):
    # `DISKFORMAT = 13` prints no decimals at all, which is the commonest setting of the 361 programs
    # surveyed, and is why those programs pack into the leading digits instead.
    path = tmp_path / "no_decimals.txt"
    write_medpc_file(path, {"A": [10602.0, 10900.0]}, decimals=0)

    interface = MedPCPackedEventsInterface(file_path=path, session_header=SESSION_HEADER, events_variable="A")

    with pytest.raises(ValueError, match="print no digits after the decimal point"):
        interface.get_event_type_source_ids()


def test_events_grouped_by_type_are_not_read_as_backwards(tmp_path):
    # A program may write every event of one type before the next, so the pooled array is not sorted even though
    # each type's own onsets climb. The order check is per type for exactly this reason.
    path = tmp_path / "grouped.txt"
    write_medpc_file(path, {"B": [1.1, 2.1, 3.1, 1.2, 2.2]})

    interface = MedPCPackedEventsInterface(file_path=path, session_header=SESSION_HEADER, events_variable="B")

    assert np.allclose(interface.get_event_times("100"), [1.0, 2.0, 3.0])
    assert np.allclose(interface.get_event_times("200"), [1.0, 2.0])


def test_interleaved_events_out_of_order_are_caught(tmp_path):
    # The counterpart of the grouped case. Here the types alternate, so the program was writing events as they
    # happened and the pooled order is a time order. A program that times two of its event types differently
    # and stores them in one array shows up exactly like this, and only the pooled check catches it.
    path = tmp_path / "interleaved.txt"
    write_medpc_file(path, {"B": [1.003, 75.001, 78.001, 17.003]})

    interface = MedPCPackedEventsInterface(file_path=path, session_header=SESSION_HEADER, events_variable="B")

    with pytest.raises(ValueError, match="run backwards"):
        interface.get_event_type_source_ids()


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
