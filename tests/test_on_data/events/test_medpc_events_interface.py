"""Tests of the two MedPC events interfaces, over both layouts and both labs whose array output is on gin."""

from datetime import datetime

import numpy as np
import pytest
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import MedPCArrayEventsInterface, MedPCCodedEventsInterface

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH

MEDPC_DATA_PATH = BEHAVIOR_DATA_PATH / "medpc"


class MedPCEventsInterfaceMixin:
    """Builds ``self.interface`` from the ``interface_class`` and ``interface_kwargs`` set on the subclass."""

    event_names: dict = {}
    column_names: dict = {}

    @pytest.fixture
    def interface(self):
        return self.interface_class(**self.interface_kwargs)

    @pytest.fixture
    def metadata(self, interface):
        """The interface's metadata with the event types named, which is the only place naming happens."""
        metadata = interface.get_metadata()
        event_types = metadata["Events"]["medpc"]["event_types"]
        for event_type_source_id, event_name in self.event_names.items():
            event_types[event_type_source_id]["event_name"] = event_name
        for event_type_source_id, columns in self.column_names.items():
            for field_source_id, column_name in columns.items():
                event_types[event_type_source_id]["columns"][field_source_id]["column_name"] = column_name
        return metadata


class TestPerArrayLernerLab(MedPCEventsInterfaceMixin):
    """A per-array file from the Lerner lab: one lettered array per event type, plus an interval type
    pairing the port-entry onsets in G with the durations in E."""

    interface_class = MedPCArrayEventsInterface

    event_names = {
        "A": "left_nose_poke_times",
        "B": "left_reward_times",
        "C": "right_nose_poke_times",
        "D": "right_reward_times",
        "G": "port_entries",
    }
    interface_kwargs = dict(
        file_path=MEDPC_DATA_PATH / "example_medpc_file_06_06_2024.txt",
        session_header={"Start Date": "04/10/19", "Start Time": "12:36:13"},
        event_configuration={
            "A": None,
            "B": None,
            "C": None,
            "D": None,
            "G": {"duration": "E"},
        },
    )

    def test_get_metadata(self, interface):
        expected_metadata = {
            "medpc": {
                "event_types": {
                    # Each event type is keyed by the MedPC variable that holds it, and its editable
                    # event_name starts as that variable, since a MedPC variable is a slot rather than a
                    # label. A MedPC file carries no prose, so no description is reported either.
                    "A": {"event_name": "A"},
                    "B": {"event_name": "B"},
                    "C": {"event_name": "C"},
                    "D": {"event_name": "D"},
                    "G": {"event_name": "G"},
                },
            },
        }
        assert interface.get_metadata()["Events"] == expected_metadata

    def test_get_metadata_reads_the_session_header(self, interface):
        metadata = interface.get_metadata()

        # The header states no timezone, so this is the session's own wall clock, left naive for pynwb to
        # localize at write.
        assert metadata["NWBFile"]["session_start_time"] == datetime(2019, 4, 10, 12, 36, 13)
        assert metadata["Subject"]["subject_id"] == "95.259"
        # The MSN is the program that ran the session, so it is what gives every array its meaning.
        assert metadata["NWBFile"]["protocol"] == "FOOD_FR1 TTL Left"
        # This file's Experiment line is blank, so nothing is reported for it.
        assert "experiment_description" not in metadata["NWBFile"]

    def test_add_to_nwbfile(self, interface, metadata):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert set(nwbfile.events) == {
            "LeftNosePokeTimes",
            "LeftRewardTimes",
            "RightNosePokeTimes",
            "RightRewardTimes",
            "PortEntries",
        }
        left_nose_pokes = nwbfile.get_events_table("LeftNosePokeTimes")
        assert left_nose_pokes.colnames == ("timestamp",)
        assert len(left_nose_pokes) == 114
        assert np.allclose(left_nose_pokes["timestamp"][:3], [12.35, 13.0, 13.85])
        assert len(nwbfile.get_events_table("LeftRewardTimes")) == 49
        assert len(nwbfile.get_events_table("RightNosePokeTimes")) == 27

    def test_event_type_that_never_fired(self, interface, metadata):
        # D is declared by the program and holds nothing in this session, which is a recorded event type that
        # never fired rather than an absent one, so it is written as a zero-row table.
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert len(nwbfile.get_events_table("RightRewardTimes")) == 0

    def test_interval_event_type(self, interface, metadata):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        # The onsets in G and the durations in E become one durative event type, rather than the transition
        # points of an IntervalSeries.
        port_entries = nwbfile.get_events_table("PortEntries")
        assert port_entries.colnames == ("timestamp", "duration")
        assert len(port_entries) == 175
        assert np.allclose(port_entries["timestamp"][:3], [58.05, 105.9, 106.65])
        assert np.allclose(port_entries["duration"][:3], [0.8, 0.7, 0.19])
        # The session stopped while the animal was in the port, so E holds 174 durations for 175 onsets and
        # the last event's offset is missing rather than the onset being dropped.
        assert np.isnan(port_entries["duration"][-1])

    def test_alignment_shifts_the_written_times(self, interface, metadata):
        original_timestamps = interface.get_event_times("A")
        interface.alignment.shift_times(delta=1.23)

        assert np.allclose(interface.get_event_times("A"), original_timestamps + 1.23)

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        written = nwbfile.get_events_table("LeftNosePokeTimes")["timestamp"][:]
        assert np.allclose(written, original_timestamps + 1.23)

    def test_externally_aligned_timestamps(self, interface, metadata):
        # Times recovered from another device, such as the TTL pulse a photometry rig recorded for each event, are
        # not the source's times shifted, so they are substituted per event type rather than offset.
        original_timestamps = interface.get_event_times("A")
        aligned_timestamps = original_timestamps + np.linspace(0.0, 0.5, len(original_timestamps))
        interface.set_aligned_timestamps(aligned_timestamps_dict={"A": aligned_timestamps})

        assert np.allclose(interface.get_event_times("A"), aligned_timestamps)
        # An event type left out keeps the times read from the file.
        assert np.allclose(interface.get_event_times("B")[:3], [12.35, 89.0, 174.45])

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        assert np.allclose(nwbfile.get_events_table("LeftNosePokeTimes")["timestamp"][:], aligned_timestamps)

    def test_externally_aligned_timestamps_of_the_wrong_length_raise(self, interface):
        with pytest.raises(ValueError, match="has 114 events but 3 aligned timestamps were given"):
            interface.set_aligned_timestamps(aligned_timestamps_dict={"A": np.array([1.0, 2.0, 3.0])})

    def test_externally_aligned_timestamps_for_an_unknown_event_type_raise(self, interface):
        with pytest.raises(KeyError, match="No event type 'Z'"):
            interface.set_aligned_timestamps(aligned_timestamps_dict={"Z": np.array([1.0])})

    def test_round_trip(self, interface, metadata, tmp_path):
        metadata["Events"]["medpc"]["event_types"]["G"]["event_description"] = "Time spent in the reward port."
        nwbfile_path = tmp_path / "test_medpc_lerner_lab.nwb"

        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        nwbfile = read_nwb(nwbfile_path)
        port_entries = nwbfile.get_events_table("PortEntries")
        assert port_entries.description == "Time spent in the reward port."
        assert len(port_entries) == 175
        assert np.allclose(port_entries["timestamp"][:3], [58.05, 105.9, 106.65])
        nwbfile.read_io.close()


class TestPerArrayTyeLab(MedPCEventsInterfaceMixin):
    """A per-array file from a second lab, whose program writes one value per index line rather than five,
    and whose `.MPC` source names what each array holds."""

    interface_class = MedPCArrayEventsInterface
    event_names = {
        "P": "lick_start_ethanol",
        "N": "lick_end_ethanol",
        "Q": "lick_start_water",
        "R": "lick_end_water",
        "S": "cs_presentation",
        "H": "ethanol_laser_trigger_off",
    }
    column_names = {"S": {"K": "cs_type"}}

    interface_kwargs = dict(
        file_path=MEDPC_DATA_PATH / "medpc_tye_lab" / "!2022-10-06_14h12m.Subject cohort10-M3.3",
        session_header={"Start Date": "10/06/22", "Subject": "cohort10-M3.3"},
        event_configuration={
            # The lick start/end arrays are onset/offset pairs rather than onset/duration ones, so each is
            # its own point event type.
            "P": None,
            "N": None,
            "Q": None,
            "R": None,
            # K holds the type of each CS presentation in S, one value per event, so it rides along as a column
            # of that event type's table rather than becoming a table of its own.
            "S": {"payload": ["K"]},
            "H": None,
        },
    )

    def test_get_metadata(self, interface):
        metadata = interface.get_metadata()
        event_types = metadata["Events"]["medpc"]["event_types"]

        # 10/06/22 is October 6, as the recording's own filename states.
        assert metadata["NWBFile"]["session_start_time"] == datetime(2022, 10, 6, 14, 12, 35)
        assert metadata["Subject"]["subject_id"] == "cohort10-M3.3"
        assert metadata["NWBFile"]["protocol"] == "HL_CS_lickometer_retract_recording_box 6"
        assert metadata["NWBFile"]["experiment_description"] == "cued2bc-sucrose"

        assert list(event_types) == ["P", "N", "Q", "R", "S", "H"]
        # The column is seeded bare: the program's `.MPC` source says 1 is water, 2 ethanol and 3 both, but the
        # output file carries none of that, so labelling the codes is left to the metadata.
        assert event_types["S"] == {
            "event_name": "S",
            "columns": {"K": {"column_name": "K"}},
        }

    def test_add_to_nwbfile(self, interface, metadata):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        lick_start = nwbfile.get_events_table("LickStartEthanol")
        assert len(lick_start) == 906
        assert np.allclose(lick_start["timestamp"][:3], [259.20, 259.32, 259.42])
        assert len(nwbfile.get_events_table("LickEndEthanol")) == 906
        assert len(nwbfile.get_events_table("LickStartWater")) == 12
        assert len(nwbfile.get_events_table("LickEndWater")) == 12

        cs_presentation = nwbfile.get_events_table("CsPresentation")
        assert len(cs_presentation) == 30
        assert np.allclose(cs_presentation["timestamp"][:3], [245.01, 368.01, 491.01])
        # The value array rides along as a column of the same table, written as the integer codes the program
        # wrote rather than as the decimals every MedPC array is printed as.
        assert cs_presentation.colnames == ("timestamp", "cs_type")
        assert list(cs_presentation["cs_type"][:5]) == [3, 1, 3, 3, 2]

        # The laser was never triggered off in this session, so its array is dimensioned and empty.
        assert len(nwbfile.get_events_table("EthanolLaserTriggerOff")) == 0

    def test_value_column_with_labelled_codes(self, interface, metadata):
        # What the codes mean lives in the `.MPC` program, so it reaches the file through the metadata.
        metadata["Events"]["medpc"]["event_types"]["S"]["columns"]["K"] = {
            "column_name": "cs_type",
            "description": "Which reward the conditioned stimulus signalled.",
            "column_categories": {
                "labels": {1: "water", 2: "ethanol", 3: "both"},
                "meanings": {
                    1: "The water bottle was extended.",
                    2: "The ethanol bottle was extended.",
                    3: "Both bottles were extended.",
                },
            },
        }

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        cs_presentation = nwbfile.get_events_table("CsPresentation")
        assert list(cs_presentation["cs_type"][:5]) == ["both", "water", "both", "both", "ethanol"]
        meanings_table = next(iter(cs_presentation.meanings_tables.values()))
        assert list(meanings_table["value"][:]) == ["water", "ethanol", "both"]

    def test_value_array_of_the_wrong_length_raises(self):
        # N holds the 906 ethanol lick ends, which is not one value per CS presentation.
        interface_kwargs = dict(self.interface_kwargs)
        interface_kwargs["event_configuration"] = {"S": {"payload": ["N"]}}
        interface = MedPCArrayEventsInterface(**interface_kwargs)

        with pytest.raises(ValueError, match="has 30 events but its value array 'N' holds 906 values"):
            interface.get_metadata()

    def test_round_trip(self, interface, metadata, tmp_path):
        nwbfile_path = tmp_path / "test_medpc_tye_lab.nwb"

        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        nwbfile = read_nwb(nwbfile_path)
        assert len(nwbfile.get_events_table("LickStartEthanol")) == 906
        nwbfile.read_io.close()


class TestCodedWithLegend(MedPCEventsInterfaceMixin):
    """A packed-code file whose event codes are known: every event is a TIME.EVENTCODE value in array A,
    and the legend of `ExampleFile2` names each code."""

    interface_class = MedPCCodedEventsInterface
    event_names = {
        "001": "lick",
        "011": "pump_a_on",
        "021": "pump_a_off",
        "012": "pump_b_on",
        "022": "pump_b_off",
        "050": "concentration_low",
        "051": "concentration_high",
        "052": "shift",
    }

    interface_kwargs = dict(
        file_path=MEDPC_DATA_PATH / "event_type_in_column_laubach_lab" / "ExampleFile2",
        session_header={"Start Date": "09/25/15", "Subject": "ML03"},
        timestamps_variable="A",
        # The program clocks at 2 ms, so the integer part of each value is in 500ths of a second.
        time_unit=0.002,
    )

    def test_get_metadata(self, interface):
        metadata = interface.get_metadata()
        event_types = metadata["Events"]["medpc"]["event_types"]

        # One event type per code found in the packed array, keyed by the code's digits as the file writes
        # them, in the order the codes first occur.
        assert metadata["NWBFile"]["session_start_time"] == datetime(2015, 9, 25, 10, 38, 46)
        assert metadata["Subject"]["subject_id"] == "ML03"
        assert metadata["NWBFile"]["protocol"] == "Lick_CShift_FI30_Box123"
        assert metadata["NWBFile"]["experiment_description"] == "value switching"

        assert list(event_types) == ["001", "011", "051", "021", "052", "012", "050", "022"]
        assert event_types["011"] == {"event_name": "011"}

    def test_add_to_nwbfile(self, interface, metadata):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        # 1800 events split over the eight codes, each its own table.
        counts = {name: len(table) for name, table in nwbfile.events.items()}
        assert counts == {
            "Lick": 1127,
            "PumpAOn": 113,
            "PumpAOff": 117,
            "PumpBOn": 208,
            "PumpBOff": 211,
            "ConcentrationLow": 6,
            "ConcentrationHigh": 6,
            "Shift": 12,
        }

        # The first line of the array is 10602.001, which is code 1 at tick 10602, i.e. 21.204 s.
        licks = nwbfile.get_events_table("Lick")
        assert licks.colnames == ("timestamp",)
        assert np.allclose(licks["timestamp"][:3], [21.204, 21.8, 57.526])

    def test_the_wrong_resolution_is_caught_by_the_session_length(self):
        # The file states its times in raw clock ticks and not what a tick is worth, so the number the user
        # passes is what puts the events in seconds. Passing 0.005 where the box ran at 2 ms stretches every
        # time by two and a half, which pushes the last event past the end the header states.
        interface_kwargs = dict(self.interface_kwargs)
        interface_kwargs["time_unit"] = 0.005
        interface = MedPCCodedEventsInterface(**interface_kwargs)

        with pytest.raises(ValueError, match="says the session ran"):
            interface.get_event_times("001")

    def test_round_trip(self, interface, metadata, tmp_path):
        nwbfile_path = tmp_path / "test_medpc_coded.nwb"

        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        nwbfile = read_nwb(nwbfile_path)
        assert np.allclose(nwbfile.get_events_table("Lick")["timestamp"][:3], [21.204, 21.8, 57.526])
        nwbfile.read_io.close()


class TestCodedWithoutLegend(MedPCEventsInterfaceMixin):
    """A packed-code file whose codes are not known: `ExampleFile1` ships no legend, and the MSN template
    beside it is a later version whose numbering disagrees with the file, so the codes cannot be named."""

    interface_class = MedPCCodedEventsInterface
    event_names = {
        code: f"code_{code}" for code in ("036", "034", "004", "029", "041", "001", "030", "032", "002", "012")
    }

    interface_kwargs = dict(
        file_path=MEDPC_DATA_PATH / "event_type_in_column_laubach_lab" / "ExampleFile1",
        session_header={"Start Date": "09/17/15", "Subject": "EX01"},
        timestamps_variable="A",
        time_unit=0.002,
    )

    def test_get_metadata(self, interface):
        metadata = interface.get_metadata()
        event_types = metadata["Events"]["medpc"]["event_types"]

        # A code the legend does not name is still read; it takes its digits as both its identifier and its
        # name, so the file is read completely and the user renames what they recognize.
        assert metadata["NWBFile"]["session_start_time"] == datetime(2015, 9, 17, 14, 23, 8)
        assert metadata["Subject"]["subject_id"] == "EX01"
        assert metadata["NWBFile"]["protocol"] == "Switch30-l(8-2)"
        assert metadata["NWBFile"]["experiment_description"] == "MedParse Ex"

        assert set(event_types) == {"036", "034", "004", "029", "041", "001", "030", "032", "002", "012"}
        assert event_types["029"] == {"event_name": "029"}

    def test_add_to_nwbfile(self, interface, metadata):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert len(nwbfile.get_events_table("Code001")) == 1447
        assert len(nwbfile.get_events_table("Code029")) == 106
        assert sum(len(table) for table in nwbfile.events.values()) == 2036

        # The file opens with 2500.036, i.e. code 36 at tick 2500, which is 5 s in.
        assert np.allclose(nwbfile.get_events_table("Code036")["timestamp"][:2], [5.0, 19.198])


def test_metadata_of_the_deprecated_interface_raises():
    # A script moved over from MedPCInterface brings its metadata["MedPC"] block, which this interface does not
    # read, so the events it describes would go unwritten.
    interface = MedPCArrayEventsInterface(
        file_path=MEDPC_DATA_PATH / "example_medpc_file_06_06_2024.txt",
        session_header={"Start Date": "04/10/19", "Start Time": "12:36:13"},
        event_configuration={"A": None},
    )
    metadata = interface.get_metadata()
    metadata["MedPC"] = {"Events": [{"name": "left_nose_poke_times", "description": "Left nose poke times"}]}

    with pytest.raises(ValueError, match=r"metadata\['MedPC'\] is not read by this interface"):
        interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)


def test_variable_missing_from_the_session_is_named():
    # The dictionary is keyed by the MedPC variable, so keying it by the name to give that variable (which is
    # how the removed metadata block was written) names nothing in the file and is reported as such.
    interface = MedPCArrayEventsInterface(
        file_path=MEDPC_DATA_PATH / "example_medpc_file_06_06_2024.txt",
        session_header={"Start Date": "04/10/19", "Start Time": "12:36:13"},
        event_configuration={"left_nose_poke_times": None},
    )

    with pytest.raises(ValueError, match="The MedPC variable 'left_nose_poke_times' is not in the session"):
        interface.get_metadata()
