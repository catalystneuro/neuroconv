"""Tests for :class:`~neuroconv.datainterfaces.icephys.brukervoltagerecording.BrukerVoltageRecordingInterface`.

The fixtures live in the gin ``ephy_testing_data`` repo under ``bruker/voltage_recording``: nine stubbed
sessions from DANDI 001538 (Zhai et al.), each the ``VoltageRecording`` XML plus its CSV truncated to 100
samples. Between them they carry the format variation that reaches the writer: both clamp modes (``mV`` and
``pA`` on ``Primary``), the three ``Divisor`` values, and the two spellings of the amplifier name. See that
folder's README.

Each folder holds a single cycle, so the fixtures cannot exercise sweep assembly. The cycles of one run, and
the cases that need more than one recorded signal, are covered here on pairs derived from a real fixture (its
XML edited, its samples reused) rather than invented wholesale; a gin fixture with several cycles and several
enabled signals would be the better home for them. The format-independent machinery those rows feed lives in
``tests/test_minimal/test_tools/test_icephys.py``.
"""

import re
from datetime import datetime, timedelta, timezone

import pytest
from pynwb import NWBHDF5IO
from pynwb.icephys import CurrentClampSeries, IZeroClampSeries, VoltageClampSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.converters import BrukerVoltageRecordingConverter
from neuroconv.datainterfaces import BrukerVoltageRecordingInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

from ..setup_paths import ECEPHY_DATA_PATH, OUTPUT_PATH

BRUKER_DATA_PATH = ECEPHY_DATA_PATH / "bruker" / "voltage_recording"


def cycle_csv_path(folder_name: str):
    """The single cycle CSV of one fixture folder."""
    return next((BRUKER_DATA_PATH / folder_name).glob("*_VoltageRecording_*.csv"))


def write_derived_cycle(
    tmp_path,
    source_folder: str,
    cycle_number: int,
    start_datetime: str | None = None,
    divisor: str | None = None,
    extra_signal_name: str | None = None,
):
    """Write one cycle pair into ``tmp_path``, derived from a real fixture with targeted edits.

    The XML is a real ``VRecSessionEntry`` throughout; only the fields a test varies are substituted, so the
    parsing under test still runs against PrairieView's own structure. ``extra_signal_name`` enables a second
    signal, which means adding both its ``SignalList`` entry's ``Enabled`` flag and a duplicate CSV column,
    since no fixture on gin records more than one signal.
    """
    source_csv = cycle_csv_path(source_folder)
    stem = f"cell1-001_Cycle{cycle_number:05d}_VoltageRecording_001"
    csv_path = tmp_path / f"{stem}.csv"
    xml_path = tmp_path / f"{stem}.xml"

    xml_text = source_csv.with_suffix(".xml").read_text()
    xml_text = re.sub(r"<DataFile>[^<]+</DataFile>", f"<DataFile>{stem}</DataFile>", xml_text)
    if start_datetime is not None:
        xml_text = re.sub(r"<DateTime>[^<]+</DateTime>", f"<DateTime>{start_datetime}</DateTime>", xml_text)
    if divisor is not None:
        # Only the first Divisor, which belongs to `Primary`, the signal these tests write.
        xml_text = re.sub(r"<Divisor>[^<]+</Divisor>", f"<Divisor>{divisor}</Divisor>", xml_text, count=1)
    if extra_signal_name is not None:
        pattern = rf"(<Name>{extra_signal_name}</Name>.*?)<Enabled>false</Enabled>"
        xml_text = re.sub(pattern, r"\1<Enabled>true</Enabled>", xml_text, count=1, flags=re.DOTALL)
    xml_path.write_text(xml_text)

    lines = source_csv.read_text().splitlines()
    if extra_signal_name is not None:
        header, *rows = lines
        lines = [f"{header}, {extra_signal_name}"] + [f"{row},{row.split(',')[1]}" for row in rows]
    csv_path.write_text("\n".join(lines) + "\n")
    return csv_path


class TestBrukerCurrentClamp(DataInterfaceTestMixin):
    """A current-clamp cycle (``Primary`` in mV, ``Divisor`` 0.01): the core single-series path, the mode read
    off the unit, and the ``Multiclamp700B Ch1`` spelling of the amplifier name."""

    data_interface_cls = BrukerVoltageRecordingInterface
    file_path = cycle_csv_path("cc_01_cell1-001")
    interface_kwargs = dict(file_paths=[file_path])
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        # The cycle's own DateTime, which carries the rig's UTC offset, so no timezone is guessed.
        expected_start_time = datetime(2017, 2, 2, 15, 39, 33, 108257, tzinfo=timezone(timedelta(hours=-6)))
        assert metadata["NWBFile"]["session_start_time"] == expected_start_time

        # Default identity: the electrode key is the acquisition stem the cycles share (PrairieView writes it
        # into `DataFile`), and the device key is the amplifier, which runs share. The electrode is per run
        # rather than per signal, since `Primary` and `Secondary` are two outputs of one headstage.
        assert metadata["Devices"] == {
            "multiclamp700b_ch1": {
                "name": "Multiclamp700B Ch1",
                "description": "Patch-clamp amplifier (model as named by PrairieView).",
            }
        }
        assert metadata["Icephys"]["IntracellularElectrodes"] == {
            "cell1-001": {
                "name": "IntracellularElectrodeCell1001",
                "description": "Patch-clamp electrode.",
                "device_metadata_key": "multiclamp700b_ch1",
            }
        }
        assert metadata["Icephys"]["PatchClampSeries"] == {
            "cell1-001_Primary": {
                "name": "CurrentClampSeriesCell1001Primary",
                "description": "Intracellular response (current_clamp).",
                "electrode_metadata_key": "cell1-001",
            }
        }

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            assert len(nwbfile.acquisition) == 1
            response = nwbfile.acquisition["CurrentClampSeriesCell1001Primary"]
            assert isinstance(response, CurrentClampSeries)
            assert response.electrode.device.name == "Multiclamp700B Ch1"

            # A single cycle is regularly sampled, so it is written with a rate rather than timestamps.
            assert response.rate == 10_000.0
            assert response.starting_time == 0.0

            # The samples are stored exactly as the CSV holds them; the whole scale chain lives in
            # `conversion`, which takes raw * Multiplier / Divisor into volts.
            assert response.data[0] == pytest.approx(-0.81695556640625)
            assert response.conversion == pytest.approx(0.1)
            assert response.data[0] * response.conversion == pytest.approx(-0.081695556640625)

            # One row per cycle, addressing the whole series, with no stimulus half and no placeholder column.
            recordings = nwbfile.intracellular_recordings
            assert len(recordings) == 1
            assert recordings.colnames == ("sequence",)
            assert recordings["sequence"][0] == "cell1-001"

    def test_signal_names_lists_the_recorded_columns(self):
        assert BrukerVoltageRecordingInterface.get_signal_names(file_path=self.file_path) == ["Primary"]


class TestBrukerVoltageClamp(DataInterfaceTestMixin):
    """A voltage-clamp cycle (``Primary`` in pA, ``Divisor`` 0.005): the other series class, the other unit
    factor, and the ``Multiclamp700B`` spelling with no channel suffix."""

    data_interface_cls = BrukerVoltageRecordingInterface
    file_path = cycle_csv_path("vc_01_cell1_LED12-018")
    interface_kwargs = dict(file_paths=[file_path])
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["Devices"]["multiclamp700b"]["name"] == "Multiclamp700B"

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            response = nwbfile.acquisition["VoltageClampSeriesCell1LED12018Primary"]
            assert isinstance(response, VoltageClampSeries)
            # 20 kHz here against 10 kHz in the current-clamp files, so the rate is read and not assumed.
            assert response.rate == 20_000.0
            # pA through a 0.005 divisor: (1 / 0.005) * 1e-12 amperes per stored unit.
            assert response.conversion == pytest.approx(2e-10)


@pytest.mark.parametrize(
    "folder_name, expected_mode, expected_conversion",
    [
        # mV, so current clamp; the three divisors the fixture set carries.
        ("cc_01_cell1-001", "current_clamp", 1e-3 / 0.01),
        ("cc_02_cell1-003", "current_clamp", 1e-3 / 0.1),
        ("cc_03_cell2-020", "current_clamp", 1e-3 / 0.1),
        ("cc_05_cell1-001_2016", "current_clamp", 1e-3 / 0.1),
        # pA, so voltage clamp.
        ("vc_01_cell1_LED12-018", "voltage_clamp", 1e-12 / 0.005),
        ("vc_02_cell2_LED12-013", "voltage_clamp", 1e-12 / 0.005),
        ("vc_03_cell1_LED16-012", "voltage_clamp", 1e-12 / 0.005),
        ("vc_04_cell1_LED20-004", "voltage_clamp", 1e-12 / 0.005),
        ("vc_05_cell2_LED100-018", "voltage_clamp", 1e-12 / 0.005),
    ],
)
def test_mode_and_scaling_across_the_fixture_set(folder_name, expected_mode, expected_conversion):
    """``Primary``'s unit decides the clamp mode and, with the divisor, the whole conversion factor. Every
    fixture is checked because the set exists to carry those variants: three divisors and two units."""
    interface = BrukerVoltageRecordingInterface(file_paths=[cycle_csv_path(folder_name)])
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)

    response = next(iter(nwbfile.acquisition.values()))
    expected_class = {"current_clamp": CurrentClampSeries, "voltage_clamp": VoltageClampSeries}[expected_mode]
    assert isinstance(response, expected_class)
    assert response.conversion == pytest.approx(expected_conversion)


def test_explicit_mode_overrides_the_derived_one():
    """``izero`` reads ``mV`` exactly like ordinary current clamp, so it is the one mode the file cannot state
    and the argument is the only way to reach ``IZeroClampSeries``."""
    interface = BrukerVoltageRecordingInterface(file_paths=[cycle_csv_path("cc_01_cell1-001")], mode="izero")
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)

    assert isinstance(nwbfile.acquisition["IZeroClampSeriesCell1001Primary"], IZeroClampSeries)


class TestCycleAssembly:
    """Several cycles of one run become one continuous series. No gin fixture has more than one cycle, so
    these run on pairs derived from ``cc_01`` with only the timestamp (or the divisor) changed."""

    def test_cycles_are_concatenated_onto_one_timeline(self, tmp_path):
        """Each cycle is placed at its own ``DateTime``, the earliest being the origin, so the dead time
        between them survives as a gap. That makes the samples irregular, which is the branch that writes
        explicit timestamps instead of a rate, and each cycle keeps its own row."""
        cycles = [
            write_derived_cycle(tmp_path, "cc_01_cell1-001", 1, start_datetime="2017-02-02T15:39:33.1082577-06:00"),
            write_derived_cycle(tmp_path, "cc_01_cell1-001", 2, start_datetime="2017-02-02T15:40:20.4082577-06:00"),
            write_derived_cycle(tmp_path, "cc_01_cell1-001", 3, start_datetime="2017-02-02T15:41:08.9082577-06:00"),
        ]
        interface = BrukerVoltageRecordingInterface(file_paths=cycles)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        response = nwbfile.acquisition["CurrentClampSeriesCell1001Primary"]
        assert response.data.shape == (300,)
        assert response.rate is None
        assert response.timestamps[0] == pytest.approx(0.0)
        assert response.timestamps[100] == pytest.approx(47.3)
        assert response.timestamps[200] == pytest.approx(95.8)

        # One row per cycle, each addressing its own slice of the concatenated series.
        recordings = nwbfile.intracellular_recordings
        assert len(recordings) == 3
        responses = recordings["responses"]["response"]
        assert [(reference.idx_start, reference.count) for reference in responses] == [(0, 100), (100, 100), (200, 100)]
        # One run, so every row carries the same sequence and they aggregate into a single sequential recording.
        assert set(recordings["sequence"][:]) == {"cell1-001"}

    def test_cycles_that_disagree_are_rejected(self, tmp_path):
        """A change of scaling partway through cannot be represented by one series with one ``conversion``,
        so it fails at construction rather than being silently applied to only part of the data."""
        cycles = [
            write_derived_cycle(tmp_path, "cc_01_cell1-001", 1),
            write_derived_cycle(tmp_path, "cc_01_cell1-001", 2, divisor="0.1"),
        ]
        with pytest.raises(ValueError, match="disagrees with .* on the divisor"):
            BrukerVoltageRecordingInterface(file_paths=cycles)


class TestSignalResolution:
    """Which recorded signal becomes the response, and what happens when the file cannot answer that or the
    mode question on its own. Needs a second recorded signal, which no gin fixture has."""

    def test_several_recorded_signals_need_naming(self, tmp_path):
        cycle = write_derived_cycle(tmp_path, "cc_01_cell1-001", 1, extra_signal_name="Secondary")
        with pytest.raises(ValueError, match="Pass response_signal_name"):
            BrukerVoltageRecordingInterface(file_paths=[cycle])

    def test_mode_cannot_be_derived_from_a_signal_other_than_primary(self, tmp_path):
        """``Secondary`` carries whichever complementary signal the amplifier was configured to emit (``pA``
        here, ``mV`` on other fixtures), so its unit does not identify the mode."""
        cycle = write_derived_cycle(tmp_path, "cc_01_cell1-001", 1, extra_signal_name="Secondary")
        with pytest.raises(ValueError, match="only the amplifier's 'Primary' output identifies the mode"):
            BrukerVoltageRecordingInterface(file_paths=[cycle], response_signal_name="Secondary")

    def test_an_explicit_mode_makes_a_secondary_response_writable(self, tmp_path):
        cycle = write_derived_cycle(tmp_path, "cc_01_cell1-001", 1, extra_signal_name="Secondary")
        interface = BrukerVoltageRecordingInterface(
            file_paths=[cycle], response_signal_name="Secondary", mode="voltage_clamp"
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        # Secondary is the other output of the same headstage, so it shares the electrode key with Primary
        # and only the series key distinguishes it.
        assert isinstance(nwbfile.acquisition["VoltageClampSeriesCell1001Secondary"], VoltageClampSeries)

    def test_a_signal_that_was_not_recorded_says_so(self):
        with pytest.raises(ValueError, match="Enabled=false"):
            BrukerVoltageRecordingInterface(
                file_paths=[cycle_csv_path("cc_01_cell1-001")], response_signal_name="Secondary"
            )

    def test_a_non_patch_signal_is_refused(self, tmp_path):
        """PrairieView's sync, photodiode and wavelength channels carry no ``PatchclampDevice``. They are
        volts, not intracellular data, and belong in a TimeSeries rather than here."""
        cycle = write_derived_cycle(tmp_path, "cc_01_cell1-001", 1, extra_signal_name="WF")
        with pytest.raises(ValueError, match="carries no PatchclampDevice"):
            BrukerVoltageRecordingInterface(file_paths=[cycle], response_signal_name="WF")


def test_the_xml_must_be_beside_the_csv(tmp_path):
    """The XML holds the units, scaling and acquisition time, so a lone CSV is not convertible."""
    lonely_csv = tmp_path / "cell1-001_Cycle00001_VoltageRecording_001.csv"
    lonely_csv.write_text(cycle_csv_path("cc_01_cell1-001").read_text())

    with pytest.raises(FileNotFoundError, match="No VoltageRecording XML beside"):
        BrukerVoltageRecordingInterface(file_paths=[lonely_csv])


class TestBrukerVoltageRecordingConverter:
    """The converter's own jobs: the session origin, the shifts that put the electrodes on it, the run labels
    that keep them distinct, and the hierarchy and sweep tables no interface builds."""

    def test_electrodes_are_placed_on_one_timeline_and_finalized(self):
        first = BrukerVoltageRecordingInterface(file_paths=[cycle_csv_path("cc_03_cell2-020")])
        second = BrukerVoltageRecordingInterface(file_paths=[cycle_csv_path("cc_05_cell1-001_2016")])
        converter = BrukerVoltageRecordingConverter(data_interfaces=dict(CellA=first, CellB=second))

        metadata = converter.get_metadata()
        # The earliest cycle of the set is the origin, not whichever interface the metadata merge saw last.
        earliest = min(first._recording_start_datetime, second._recording_start_datetime)
        assert metadata["NWBFile"]["session_start_time"] == earliest

        metadata["NWBFile"]["session_description"] = "test"
        metadata["NWBFile"]["identifier"] = "test"
        nwbfile = converter.create_nwbfile(metadata=metadata)

        # Each electrode sits at its own offset from that origin, so the later one does not start at zero.
        offsets = sorted(series.starting_time for series in nwbfile.acquisition.values())
        assert offsets[0] == pytest.approx(0.0)
        assert offsets[1] == pytest.approx(
            (max(first._recording_start_datetime, second._recording_start_datetime) - earliest).total_seconds()
        )

        # Distinct runs keep distinct identities, so nothing is merged across cells.
        assert len(nwbfile.icephys_electrodes) == 2
        assert set(nwbfile.intracellular_recordings["sequence"][:]) == {"cell2-020", "cell1-001"}

        # The tables the interfaces deliberately leave unbuilt.
        assert len(nwbfile.icephys_sequential_recordings) == 2
        assert list(nwbfile.icephys_sequential_recordings["stimulus_type"][:]) == ["not described"] * 2
        assert len(nwbfile.intervals["sweeps"]) == 2

    def test_stimulus_type_is_written_when_given(self):
        """PrairieView records no protocol, so the column exists only when the caller supplies one; then it is
        carried up to the sequential recording in place of the placeholder."""
        interface = BrukerVoltageRecordingInterface(
            file_paths=[cycle_csv_path("cc_01_cell1-001")], stimulus_type="somatic excitability"
        )
        converter = BrukerVoltageRecordingConverter(data_interfaces=dict(CellA=interface))
        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_description"] = "test"
        metadata["NWBFile"]["identifier"] = "test"

        nwbfile = converter.create_nwbfile(metadata=metadata)

        assert list(nwbfile.intracellular_recordings["stimulus_type"][:]) == ["somatic excitability"]
        assert list(nwbfile.icephys_sequential_recordings["stimulus_type"][:]) == ["somatic excitability"]

    def test_runs_sharing_a_stem_are_disambiguated(self, tmp_path):
        """The acquisition stem is the experimenter's own naming and collides across session folders, so the
        converter falls back to the folder to keep the two runs (and their electrodes) apart."""
        first_folder = tmp_path / "session_a"
        second_folder = tmp_path / "session_b"
        first_folder.mkdir()
        second_folder.mkdir()
        first = BrukerVoltageRecordingInterface(file_paths=[write_derived_cycle(first_folder, "cc_01_cell1-001", 1)])
        second = BrukerVoltageRecordingInterface(
            file_paths=[
                write_derived_cycle(
                    second_folder, "cc_01_cell1-001", 1, start_datetime="2017-02-02T16:00:00.0000000-06:00"
                )
            ]
        )
        converter = BrukerVoltageRecordingConverter(data_interfaces=dict(CellA=first, CellB=second))

        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_description"] = "test"
        metadata["NWBFile"]["identifier"] = "test"
        nwbfile = converter.create_nwbfile(metadata=metadata)

        assert set(nwbfile.intracellular_recordings["sequence"][:]) == {"session_a_cell1-001", "session_b_cell1-001"}
        assert len(nwbfile.icephys_electrodes) == 2
