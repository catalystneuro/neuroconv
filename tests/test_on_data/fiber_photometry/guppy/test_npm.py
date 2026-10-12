"""Tests for the NPM seam of ``GuppyConverter``.

Only what is specific to ``acquisition_format="npm"``. Everything format-independent -- role grouping,
fiber-region linking, event merging, the registries -- is asserted once in ``test_reference_session``.

NPM has the hardest seam of the four, because its store names are *synthetic*: GuPPy invents
``signals_470nm_G2`` while demultiplexing an interleaved recording, and no such column exists on disk.
Decoding one means resolving its parts back to the file, the excitation and the region column they
name, so the expected data here is read straight from the acquisition file using GuPPy's own channel
rule (the excitation bit test) rather than taken from any interface.

The assertions stop at the constructed interface rather than running a conversion, since the decode is
settled at construction.

Both raw paths point at one staged folder, mirroring a real GuPPy session: the acquisition CSV and its
event CSV live together, and a store names its source file by stem.
"""

import json
import shutil

import numpy as np
import pandas
import pytest
from pydantic import ValidationError

from neuroconv.converters import GuppyConverter
from neuroconv.datainterfaces.events.csv_events.csveventsdatainterface import (
    CSVEventsInterface,
)
from neuroconv.datainterfaces.fiber_photometry.csv.csvfiberphotometrydatainterface import (
    CSVFiberPhotometryInterface,
)
from neuroconv.datainterfaces.fiber_photometry.guppy._legacy_store_names import (
    decode_legacy_store_name,
    npm_source_files,
)
from neuroconv.datainterfaces.fiber_photometry.guppy.npm_utils import (
    build_npm_acquisition_interface,
    npm_run_parameters,
    npm_store_provenance,
    npm_store_to_demux,
)
from neuroconv.tools.testing import generate_mock_guppy_output_folder

from ...setup_paths import OPHYS_DATA_PATH

NPM_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "NPM"
NPM_EVENTS_FOLDER = OPHYS_DATA_PATH / "events_datasets" / "NPM"


EXCITATION_BITS = 0b111
WAVELENGTH_TO_EXCITATION_CODE = {415: 1, 470: 2, 560: 4}


def guppy_channel_rows(file_path, *, state_column, wavelength):
    """Return the row indices GuPPy's demultiplexer assigns to one excitation wavelength.

    Reproduces the bit test: a frame belongs to a wavelength when its state word has that
    wavelength's excitation bit set, whatever else is set alongside it, so one channel can span
    several state words and one word can reach several channels. A leading frame with every
    excitation bit set is an initialization frame and belongs to none of them.
    """
    code = WAVELENGTH_TO_EXCITATION_CODE[wavelength]
    state = pandas.read_csv(file_path)[state_column].to_numpy().astype(int)
    startup_row_count = 1 if state[0] & EXCITATION_BITS == EXCITATION_BITS else 0
    rows = np.zeros(len(state), dtype=bool)
    rows[startup_row_count:] = (state[startup_row_count:] & code) == code
    return np.flatnonzero(rows)


class NPMConverterTestMixin:
    """Shared assertions; each subclass supplies one NPM layout's fixtures and expectations.

    Subclasses define the two source files, the storesList topology, the `.npm_params.json` the GuPPy
    run would have written, and a ``read_expected_store_data`` staticmethod reading a store's samples
    straight from the acquisition file.
    """

    ACQUISITION_FILE_NAME = "signals.csv"
    EVENT_FILE_NAME = "ttls.csv"

    @pytest.fixture(scope="class")
    @classmethod
    def session_folder(cls, tmp_path_factory):
        folder_path = tmp_path_factory.mktemp("npm_session") / "session"
        folder_path.mkdir()
        shutil.copy(cls.ACQUISITION_SOURCE, folder_path / cls.ACQUISITION_FILE_NAME)
        shutil.copy(cls.EVENT_SOURCE, folder_path / cls.EVENT_FILE_NAME)
        return folder_path

    @pytest.fixture(scope="class")
    @classmethod
    def guppy_output_folder(cls, tmp_path_factory):
        folder_path = generate_mock_guppy_output_folder(
            tmp_path_factory.mktemp("npm_output") / "session_output_1",
            recording_site_to_stores=cls.RECORDING_SITE_TO_STORES,
            event_store_to_name=cls.EVENT_STORE_TO_NAME,
            cross_correlation_pairs=(),
        )
        # Which clock and unit a session was read on is a choice made when GuPPy ran; it records them
        # here beside storesList.csv, one unit and one column for the whole session.
        (folder_path / ".npm_params.json").write_text(json.dumps(cls.NPM_PARAMETERS), encoding="utf-8")
        return folder_path

    @pytest.fixture
    def converter(self, session_folder, guppy_output_folder):
        return GuppyConverter(
            fiber_photometry_folder_path=session_folder,
            events_folder_path=session_folder,
            guppy_folder_path=guppy_output_folder,
            acquisition_format="npm",
        )

    def test_synthetic_store_names_decode_to_the_right_rows_and_columns(self, converter, session_folder):
        """Each store name resolves to the samples GuPPy's demultiplexer picks out of the file."""
        source_path = session_folder / self.ACQUISITION_FILE_NAME
        for role in ("signal", "control"):
            interface = converter.data_interface_objects[f"FiberPhotometry_{role}"]
            store_ids = [stores[role] for stores in self.RECORDING_SITE_TO_STORES.values()]
            (stream_name,) = interface.source_data["stream_names"]

            demultiplexed = np.asarray(interface._get_stream_data(stream_name=stream_name))
            if demultiplexed.ndim == 1:  # a single recording site is squeezed to one dimension
                demultiplexed = demultiplexed[:, np.newaxis]
            assert demultiplexed.shape[1] == len(store_ids)
            for column, store_id in enumerate(store_ids):
                expected = self.read_expected_store_data(source_path, store_id)
                np.testing.assert_array_equal(demultiplexed[:, column], expected)

    def test_event_store_ids_map_to_the_names_guppy_gave_them(self, converter):
        """GuPPy's ``event<N>`` store ids are synthetic too, and must round-trip back to the source file."""
        (events_spec,) = converter._events_specs
        for store_id in self.EVENT_STORE_TO_NAME:
            assert store_id in events_spec["source_id_to_store_id"].values()


class TestGuppyConverterNPMInterleaved(NPMConverterTestMixin):
    """The common layout: one file, two LED states interleaved frame by frame, three regions.

    This fixture's ``Flags`` also change mid-recording (17/18 become 273/274 when a digital input goes
    high), which is the case that proves the channel split must not match raw state words.
    """

    ACQUISITION_SOURCE = NPM_FOLDER / "multi_led_state_per_wavelength" / "digital_input_transition.csv"
    EVENT_SOURCE = NPM_EVENTS_FOLDER / "event_type_as_bool" / "PagCeAVgatFear_1442_ts0.csv"
    # 415 nm is the isosbestic control and 470 nm the signal; each is crossed with the three regions.
    RECORDING_SITE_TO_STORES = {
        f"roi0{index}": {
            "signal": f"signals_470nm_Region{index}G",
            "control": f"signals_415nm_Region{index}G",
        }
        for index in (0, 1, 2)
    }
    EVENT_STORE_TO_NAME = {"eventTrue": "cue_on", "eventFalse": "cue_off"}
    NPM_PARAMETERS = {
        "npm_split_events": {"ttls.csv": True},
        "npm_time_unit": "seconds",
        "npm_timestamp_column_name": None,
        "stores": {
            f"signals_{wavelength}nm_Region{index}G": {
                "file": "signals.csv",
                "excitation_wavelength_in_nm": wavelength,
                "interleave_position": None,
                "data_column": f"Region{index}G",
                "timestamp_column": "Timestamp",
            }
            for wavelength in (415, 470)
            for index in (0, 1, 2)
        },
    }

    @staticmethod
    def read_expected_store_data(file_path, store_id):
        _, wavelength, region = store_id.rsplit("_", 2)
        rows = guppy_channel_rows(file_path, state_column="Flags", wavelength=int(wavelength.removesuffix("nm")))
        return pandas.read_csv(file_path)[region].to_numpy()[rows]

    def test_store_wavelength_reaches_the_interface_as_its_state_words(self, converter):
        """The LED state's low three bits name the wavelength, and the interface selects on those bits.

        415 nm keeps both `17` and `273`: the digital input going high mid-recording sets a bit above the
        excitation ones without changing which LED fired.
        """
        signal = converter.data_interface_objects["FiberPhotometry_signal"]
        control = converter.data_interface_objects["FiberPhotometry_control"]
        assert signal._demux_configuration.values == [18, 274]  # Flags 18 -> bits 010 -> 470 nm
        assert control._demux_configuration.values == [17, 273]  # Flags 17 -> bits 001 -> 415 nm


class TestGuppyConverterNPMTwoClocks(NPMConverterTestMixin):
    """Four regions and two timestamp columns, so the clock must come from ``.npm_params.json``."""

    ACQUISITION_SOURCE = NPM_FOLDER / "multi_timestamp" / "signals.csv"
    EVENT_SOURCE = NPM_EVENTS_FOLDER / "event_type_as_number" / "ttls.csv"
    RECORDING_SITE_TO_STORES = {
        f"roi0{index}": {"signal": f"signals_470nm_G{index}", "control": f"signals_415nm_G{index}"}
        for index in (0, 1, 2, 3)
    }
    EVENT_STORE_TO_NAME = {"event1": "trial_start", "event3": "trial_end"}
    NPM_PARAMETERS = {
        "npm_split_events": {"ttls.csv": True},
        "npm_time_unit": "milliseconds",
        "npm_timestamp_column_name": "ComputerTimestamp",
        "stores": {
            f"signals_{wavelength}nm_G{index}": {
                "file": "signals.csv",
                "excitation_wavelength_in_nm": wavelength,
                "interleave_position": None,
                "data_column": f"G{index}",
                "timestamp_column": "ComputerTimestamp",
            }
            for wavelength in (415, 470)
            for index in (0, 1, 2, 3)
        },
    }

    @staticmethod
    def read_expected_store_data(file_path, store_id):
        _, wavelength, region = store_id.rsplit("_", 2)
        rows = guppy_channel_rows(file_path, state_column="LedState", wavelength=int(wavelength.removesuffix("nm")))
        return pandas.read_csv(file_path)[region].to_numpy()[rows]

    def test_timestamps_come_from_the_recorded_clock(self, converter):
        """`.npm_params.json` names ComputerTimestamp, so that column is read rather than SystemTimestamp."""
        signal = converter.data_interface_objects["FiberPhotometry_signal"]
        assert signal.source_data["timestamps_column"] == "ComputerTimestamp"

        rows = guppy_channel_rows(
            TestGuppyConverterNPMTwoClocks.ACQUISITION_SOURCE, state_column="LedState", wavelength=470
        )
        expected = pandas.read_csv(TestGuppyConverterNPMTwoClocks.ACQUISITION_SOURCE)["ComputerTimestamp"].to_numpy()
        np.testing.assert_allclose(signal.get_original_timestamps(), expected[rows] / 1e3)


class TestGuppyConverterNPMHeaderless(NPMConverterTestMixin):
    """The legacy layout, which has no state column, paired with GuPPy's unsplit ``event0`` store.

    Both fall back to the generic CSV interfaces: channels cycle by row parity alone (so the count comes
    from ``noChannels``), and ``event0`` means the whole event file as one type, which
    ``NPMEventsInterface`` cannot express because it always splits by label.

    Both files come from GuPPy's ``sampleData_NPM_5``, whose real storesList names the file's stem
    followed by the cycle position. Their timestamps share the millisecond clock, but the GIN
    acquisition stub is truncated to 40 rows, so the event onsets fall past its end.
    """

    ACQUISITION_SOURCE = NPM_FOLDER / "no_header_no_state_column" / "three_regions_milliseconds.csv"
    EVENT_SOURCE = NPM_EVENTS_FOLDER / "single_event_type" / "PagCeAVgatFear_1512_ts0.csv"
    RECORDING_SITE_TO_STORES = {
        f"roi0{index}": {"signal": f"signals_chod{index}", "control": f"signals_chev{index}"} for index in (1, 2, 3)
    }
    EVENT_STORE_TO_NAME = {"event0": "ttl"}
    NPM_PARAMETERS = {
        "npm_split_events": {"ttls.csv": False},
        "npm_time_unit": "milliseconds",
        "npm_timestamp_column_name": None,
        "stores": {
            f"signals_{slot}{column}": {
                "file": "signals.csv",
                "excitation_wavelength_in_nm": None,
                "interleave_position": position,
                "data_column": column,
                "timestamp_column": 0,
            }
            for slot, position in (("chev", 0), ("chod", 1))
            for column in (1, 2, 3)
        },
    }

    @staticmethod
    def read_expected_store_data(file_path, store_id):
        # No state column: the slot is the phase directly, and the stride is noChannels (2 in the mock).
        slot_ordinal = {"chev": 0, "chod": 1}[store_id.rsplit("_", 1)[1][:4]]
        column_position = int(store_id[-1])
        frame = pandas.read_csv(file_path, header=None)
        return frame[column_position].to_numpy()[np.arange(slot_ordinal, len(frame), 2)]

    def test_falls_back_to_the_generic_interfaces(self, converter):
        """Neither NPM interface can read this session, so both sides use the CSV ones."""
        assert isinstance(converter.data_interface_objects["FiberPhotometry_signal"], CSVFiberPhotometryInterface)
        assert isinstance(converter.data_interface_objects["Events"], CSVEventsInterface)

    def test_event0_is_translated_back_to_its_store_id(self, converter):
        """The CSV events interface keys its lone type by file stem, so the seam maps it to `event0`."""
        (events_spec,) = converter._events_specs
        assert events_spec["source_id_to_store_id"] == {"ttls": "event0"}
        assert converter._store_id_for(events_spec, "ttls") == "event0"


class TestGuppyConverterNPMLegacyStoreNames(NPMConverterTestMixin):
    """A run folder written before GuPPy recorded what it demultiplexed.

    Its ``.npm_params.json`` carries no ``stores`` mapping and its stores are named positionally,
    so every part has to be decoded.

    Same source file as ``TestGuppyConverterNPMInterleaved``, so the two paths are asserted
    against identical data and any divergence between them shows up here.
    """

    ACQUISITION_SOURCE = NPM_FOLDER / "multi_led_state_per_wavelength" / "digital_input_transition.csv"
    EVENT_SOURCE = NPM_EVENTS_FOLDER / "event_type_as_bool" / "PagCeAVgatFear_1442_ts0.csv"
    # chev is the lower state (17, the isosbestic) and chod the higher (18); the column counts from
    # 1 past the timestamps, so Region0G/1G/2G are 1/2/3.
    RECORDING_SITE_TO_STORES = {
        f"roi0{index}": {"signal": f"file0_chod{index}", "control": f"file0_chev{index}"} for index in (1, 2, 3)
    }
    EVENT_STORE_TO_NAME = {"eventTrue": "cue_on", "eventFalse": "cue_off"}
    NPM_PARAMETERS = {
        "npm_split_events": [False, True],
        "npm_time_unit": "seconds",
        "npm_timestamp_column_name": None,
    }

    @staticmethod
    def read_expected_store_data(file_path, store_id):
        wavelength = {"chev": 415, "chod": 470}[store_id.split("_")[1][:4]]
        column_position = int(store_id[-1])
        rows = guppy_channel_rows(file_path, state_column="Flags", wavelength=wavelength)
        return pandas.read_csv(file_path)[f"Region{column_position - 1}G"].to_numpy()[rows]

    def test_the_legacy_names_reach_the_same_wavelengths(self, converter):
        """The slot ordinal stands for an excitation, and the interface still selects on its bits."""
        signal = converter.data_interface_objects["FiberPhotometry_signal"]
        control = converter.data_interface_objects["FiberPhotometry_control"]
        assert signal._demux_configuration.values == [18, 274]  # chod -> Flags 18 -> 470 nm
        assert control._demux_configuration.values == [17, 273]  # chev -> Flags 17 -> 415 nm


class TestNPMRunParameters:
    """Reading the session-wide settings GuPPy recorded beside ``storesList.csv``."""

    @pytest.fixture
    def guppy_output_folder(self, tmp_path):
        return generate_mock_guppy_output_folder(
            tmp_path / "session_output_1",
            recording_site_to_stores={"roi01": {"signal": "signals_470nm_G0", "control": "signals_415nm_G0"}},
            event_store_to_name={"event0": "ttl"},
            cross_correlation_pairs=(),
        )

    def test_reads_the_session_wide_unit_and_column(self, guppy_output_folder):
        (guppy_output_folder / ".npm_params.json").write_text(
            json.dumps(
                {
                    "npm_split_events": {"ttls.csv": False},
                    "npm_time_unit": "microseconds",
                    "npm_timestamp_column_name": "SystemTimestamp",
                }
            ),
            encoding="utf-8",
        )
        run_parameters = npm_run_parameters(guppy_output_folder)
        assert run_parameters["time_unit"] == "microseconds"
        assert run_parameters["timestamp_column_name"] == "SystemTimestamp"
        assert run_parameters["number_of_channels"] == 2

    def test_the_channel_count_is_read_from_the_npm_parameters(self, guppy_output_folder):
        """Newer GuPPy runs record the count beside the other NPM settings, not in the snapshot."""
        (guppy_output_folder / ".npm_params.json").write_text(
            json.dumps(
                {
                    "npm_split_events": {"ttls.csv": False},
                    "npm_time_unit": "seconds",
                    "npm_timestamp_column_name": "SystemTimestamp",
                    "noChannels": 3,
                }
            ),
            encoding="utf-8",
        )
        (guppy_output_folder / "GuPPyParamtersUsed.json").unlink()
        assert npm_run_parameters(guppy_output_folder)["number_of_channels"] == 3

    def test_a_file_predating_the_session_wide_unit_is_refused(self, guppy_output_folder):
        """The per-file unit could disagree with the one GuPPy applied, so such a file is unusable."""
        (guppy_output_folder / ".npm_params.json").write_text(
            json.dumps(
                {
                    "npm_split_events": [False, True],
                    "npm_time_units": ["milliseconds", "seconds"],
                    "npm_timestamp_column_names": ["ComputerTimestamp", None],
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(AssertionError, match="records no 'npm_time_unit'"):
            npm_run_parameters(guppy_output_folder)


@pytest.fixture
def session_folder(tmp_path):
    folder_path = tmp_path / "session"
    folder_path.mkdir()
    return folder_path


def write_npm_parameters(guppy_output_folder, **npm_parameters):
    """Write the ``.npm_params.json`` a GuPPy NPM run leaves beside ``storesList.csv``."""
    defaults = dict(npm_split_events={"ttls.csv": False}, npm_time_unit="milliseconds", npm_timestamp_column_name=None)
    (guppy_output_folder / ".npm_params.json").write_text(json.dumps({**defaults, **npm_parameters}), encoding="utf-8")


class TestNPMStoreProvenance:
    """Reading what each store was demultiplexed from, on both paths."""

    @pytest.fixture
    def guppy_output_folder(self, tmp_path):
        return generate_mock_guppy_output_folder(
            tmp_path / "session_output_1",
            recording_site_to_stores={"roi01": {"signal": "signals_470nm_G0", "control": "signals_415nm_G0"}},
            event_store_to_name={"event0": "ttl"},
            cross_correlation_pairs=(),
        )

    def test_recorded_stores_are_read_as_given(self, session_folder, guppy_output_folder):
        """A run that records its demultiplexing is believed, so nothing is derived."""
        record = {
            "file": "signals.csv",
            "excitation_wavelength_in_nm": 470,
            "interleave_position": None,
            "data_column": "G0",
            "timestamp_column": "ComputerTimestamp",
        }
        write_npm_parameters(guppy_output_folder, stores={"anything_at_all": record})

        provenance = npm_store_provenance(
            folder_path=session_folder,
            guppy_folder_path=guppy_output_folder,
            store_ids=["anything_at_all"],
        )

        assert provenance == {"anything_at_all": record}

    def test_a_store_missing_from_the_record_raises(self, session_folder, guppy_output_folder):
        """A run folder that records its stores records all of them, so an absence is a mismatch.

        The name would decode on the older path, which is what makes falling through to it wrong:
        it resolves against arithmetic the run that wrote this folder no longer used.
        """
        shutil.copy(NPM_FOLDER / "multi_timestamp" / "signals.csv", session_folder / "signals.csv")
        write_npm_parameters(
            guppy_output_folder,
            stores={"some_other_store": {"file": "signals.csv", "excitation_wavelength_in_nm": 415}},
        )

        with pytest.raises(AssertionError, match=r"says nothing about \['file0_chev1'\]"):
            npm_store_provenance(
                folder_path=session_folder,
                guppy_folder_path=guppy_output_folder,
                store_ids=["file0_chev1"],
            )

    def test_a_run_recording_no_stores_falls_back_to_decoding_the_names(self, session_folder, guppy_output_folder):
        """With no record to read, the positional names are decoded into the same shape."""
        shutil.copy(NPM_FOLDER / "multi_timestamp" / "signals.csv", session_folder / "signals.csv")
        # A run from before the stores were recorded also recorded split events by file position.
        write_npm_parameters(guppy_output_folder, npm_split_events=[False, False])

        provenance = npm_store_provenance(
            folder_path=session_folder,
            guppy_folder_path=guppy_output_folder,
            store_ids=["file0_chev1"],
        )

        assert provenance == {
            "file0_chev1": {
                "file": "signals.csv",
                "excitation_wavelength_in_nm": 415,
                "interleave_position": None,
                "data_column": "G0",
                "timestamp_column": "SystemTimestamp",
            }
        }


class TestNPMStoreResolution:
    """Turning one store's record into the file, channel and column it is read from."""

    def test_an_excitation_record_resolves_to_its_wavelength(self, session_folder):
        """The record names the file, excitation, column and clock, so nothing is derived."""
        shutil.copy(NPM_FOLDER / "multi_timestamp" / "signals.csv", session_folder / "signals.csv")
        record = {
            "file": "signals.csv",
            "excitation_wavelength_in_nm": 470,
            "interleave_position": None,
            "data_column": "G0",
            "timestamp_column": "ComputerTimestamp",
        }

        demux = npm_store_to_demux(session_folder, "anything_at_all", record, number_of_channels=2)

        assert demux["demultiplex_by"] == "excitation"
        assert demux["file_path"].name == "signals.csv"
        assert demux["excitation_wavelength_in_nm"] == 470
        assert demux["data_column"] == "G0"
        # The file's first timestamp column is SystemTimestamp; the record names the other one, and
        # the record is what GuPPy actually read.
        assert demux["timestamps_column"] == "ComputerTimestamp"

    def test_a_cycle_position_record_resolves_to_a_stride(self, session_folder):
        shutil.copy(
            NPM_FOLDER / "no_header_no_state_column" / "three_regions_milliseconds.csv",
            session_folder / "signals.csv",
        )
        record = {
            "file": "signals.csv",
            "excitation_wavelength_in_nm": None,
            "interleave_position": 1,
            "data_column": 2,
            "timestamp_column": 0,
        }

        demux = npm_store_to_demux(session_folder, "signals_chod2", record, number_of_channels=2)

        assert demux["demultiplex_by"] == "stride"
        assert demux["slot_index"] == 1
        assert demux["data_column"] == 2
        assert demux["timestamps_column"] == 0

    def test_a_record_naming_an_absent_file_raises(self, session_folder):
        """The raw folder and the GuPPy output folder have to be the pair they were written as."""
        shutil.copy(NPM_FOLDER / "multi_timestamp" / "signals.csv", session_folder / "signals.csv")
        record = {
            "file": "elsewhere.csv",
            "excitation_wavelength_in_nm": 470,
            "interleave_position": None,
            "data_column": "G0",
            "timestamp_column": "SystemTimestamp",
        }

        with pytest.raises(AssertionError, match="which is not in"):
            npm_store_to_demux(session_folder, "elsewhere_470nm_G0", record, number_of_channels=2)

    def test_a_stride_record_without_a_channel_count_raises(self, session_folder):
        """The header-less interleave has no on-disk signature, so it cannot be guessed."""
        shutil.copy(
            NPM_FOLDER / "no_header_no_state_column" / "three_regions_milliseconds.csv",
            session_folder / "signals.csv",
        )
        record = {
            "file": "signals.csv",
            "excitation_wavelength_in_nm": None,
            "interleave_position": 0,
            "data_column": 1,
            "timestamp_column": 0,
        }

        with pytest.raises(AssertionError, match="recorded no 'noChannels'"):
            npm_store_to_demux(session_folder, "signals_chev1", record, number_of_channels=None)

    def test_a_cycle_position_the_interleave_has_no_room_for_is_refused(self, session_folder):
        """Position 2 of a two-channel cycle would otherwise be read as position 0's rows."""
        shutil.copy(
            NPM_FOLDER / "no_header_no_state_column" / "three_regions_milliseconds.csv",
            session_folder / "signals.csv",
        )
        guppy_output_folder = generate_mock_guppy_output_folder(
            session_folder.parent / "session_output_1",
            recording_site_to_stores={"roi01": {"signal": "signals_chpr2", "control": "signals_chpr2"}},
            event_store_to_name={"event0": "ttl"},
            cross_correlation_pairs=(),
        )
        write_npm_parameters(
            guppy_output_folder,
            noChannels=2,
            stores={
                "signals_chpr2": {
                    "file": "signals.csv",
                    "excitation_wavelength_in_nm": None,
                    "interleave_position": 2,
                    "data_column": 2,
                    "timestamp_column": 0,
                }
            },
        )

        with pytest.raises(ValidationError, match="must be < channels"):
            build_npm_acquisition_interface(
                folder_path=session_folder,
                guppy_folder_path=guppy_output_folder,
                store_ids=["signals_chpr2"],
                metadata_key="FiberPhotometry_signal",
                verbose=False,
            )


class TestLegacyStoreNames:
    """Decoding the positional names a run wrote before GuPPy recorded what it demultiplexed."""

    def test_a_state_column_file_decodes_the_slot_to_a_wavelength(self, session_folder):
        """`chev` is the lowest of the sorted LED states, whose excitation bits name the wavelength."""
        shutil.copy(NPM_FOLDER / "multi_timestamp" / "signals.csv", session_folder / "signals.csv")

        record = decode_legacy_store_name(session_folder, "file0_chev1", None)

        assert record == {
            "file": "signals.csv",
            "excitation_wavelength_in_nm": 415,
            "interleave_position": None,
            "data_column": "G0",
            "timestamp_column": "SystemTimestamp",
        }

    def test_a_headerless_file_decodes_the_slot_to_a_cycle_position(self, session_folder):
        """With no LED named, the slot is the position itself and the timestamps are the first column."""
        shutil.copy(
            NPM_FOLDER / "no_header_no_state_column" / "three_regions_milliseconds.csv",
            session_folder / "signals.csv",
        )

        record = decode_legacy_store_name(session_folder, "file0_chod2", None)

        assert record == {
            "file": "signals.csv",
            "excitation_wavelength_in_nm": None,
            "interleave_position": 1,
            "data_column": 2,
            "timestamp_column": 0,
        }

    def test_the_session_wide_clock_beats_the_file_s_first(self, session_folder):
        """With no record to name one, the run's own choice stands, else the file's first."""
        shutil.copy(NPM_FOLDER / "multi_timestamp" / "signals.csv", session_folder / "signals.csv")

        named = decode_legacy_store_name(session_folder, "file0_chev1", "ComputerTimestamp")
        unnamed = decode_legacy_store_name(session_folder, "file0_chev1", None)

        assert named["timestamp_column"] == "ComputerTimestamp"
        assert unnamed["timestamp_column"] == "SystemTimestamp"

    def test_event_file_occupies_a_file_index(self, session_folder):
        """A legacy name indexes every surviving CSV, so an event file sorting first shifts them."""
        shutil.copy(NPM_EVENTS_FOLDER / "event_type_as_number" / "ttls.csv", session_folder / "a_events.csv")
        shutil.copy(NPM_FOLDER / "multi_timestamp" / "signals.csv", session_folder / "b_signals.csv")

        source_files = npm_source_files(session_folder)

        assert [path.name for path in source_files] == ["a_events.csv", "b_signals.csv"]
        assert decode_legacy_store_name(session_folder, "file1_chev1", None)["file"] == "b_signals.csv"

    def test_derived_files_are_excluded(self, session_folder):
        """GuPPy globs out the per-channel files it wrote itself, so they never take an index."""
        shutil.copy(NPM_FOLDER / "multi_timestamp" / "signals.csv", session_folder / "signals.csv")
        shutil.copy(NPM_FOLDER / "multi_timestamp" / "signals.csv", session_folder / "file0_chev1.csv")

        source_files = npm_source_files(session_folder)

        assert [path.name for path in source_files] == ["signals.csv"]

    def test_an_unrecognized_name_raises(self, session_folder):
        shutil.copy(NPM_FOLDER / "multi_timestamp" / "signals.csv", session_folder / "signals.csv")
        with pytest.raises(AssertionError, match="is not a GuPPy NPM store name"):
            decode_legacy_store_name(session_folder, "signals_470nm_G0", None)

    def test_strobed_state_has_no_single_wavelength(self, session_folder):
        """`LedState 6` is 470+560 in one frame, which no single legacy slot can stand for."""
        shutil.copy(
            NPM_FOLDER / "multi_wavelength_per_led_state" / "simultaneous_470_and_560.csv",
            session_folder / "signals.csv",
        )
        with pytest.raises(AssertionError, match="not a single wavelength"):
            decode_legacy_store_name(session_folder, "file0_chod1", None)

    def test_slot_beyond_the_interleave_raises(self, session_folder):
        """A two-state file has no third channel, so `chpr` cannot be resolved."""
        shutil.copy(NPM_FOLDER / "multi_timestamp" / "signals.csv", session_folder / "signals.csv")
        with pytest.raises(AssertionError, match="interleaves only 2 channel"):
            decode_legacy_store_name(session_folder, "file0_chpr1", None)
