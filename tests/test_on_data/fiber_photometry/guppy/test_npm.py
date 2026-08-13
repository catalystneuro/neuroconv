"""Tests for the NPM seam of ``GuppyConverter``.

Only what is specific to ``acquisition_format="npm"``. Everything format-independent -- role grouping,
fiber-region linking, event merging, the registries -- is asserted once in ``test_reference_session``.

NPM has the hardest seam of the four, because its store names are *synthetic*: GuPPy invents
``file0_chod3`` while demultiplexing an interleaved recording, and none of its three parts appear on
disk. Decoding one means reproducing GuPPy's own arithmetic -- which file index, which channel slot,
which region column -- so the expected data here is computed from that arithmetic
(``arange(first_row, num_rows, num_channels)``) rather than taken from any interface.

The assertions stop at the constructed interface rather than running a conversion, since the decode is
settled at construction.

Both raw paths point at one staged folder, mirroring a real GuPPy session: the acquisition CSV and its
event CSV live together, which is also what makes the ``file<N>`` indices line up with GuPPy's.
"""

import json
import shutil

import numpy as np
import pandas
import pytest

from neuroconv.converters import GuppyConverter
from neuroconv.datainterfaces.events.csv_events.csveventsdatainterface import (
    CSVEventsInterface,
)
from neuroconv.datainterfaces.fiber_photometry.csv.csvfiberphotometrydatainterface import (
    CSVFiberPhotometryInterface,
)
from neuroconv.datainterfaces.fiber_photometry.guppy.npm_utils import (
    npm_run_parameters,
    npm_source_files,
    npm_store_to_demux,
)
from neuroconv.tools.testing import generate_mock_guppy_output_folder

from ...setup_paths import OPHYS_DATA_PATH

NPM_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "NPM"
NPM_EVENTS_FOLDER = OPHYS_DATA_PATH / "events_datasets" / "NPM"


def guppy_channel_rows(file_path, *, state_column, slot_ordinal):
    """Return the row indices GuPPy's demultiplexer assigns to one channel slot.

    Reproduces `check_channels` plus the stride: the channel count and slot order come from the distinct
    state values in rows 2-11 sorted ascending, and the slot's phase is that value's first occurrence
    anywhere in the recording.
    """
    state = pandas.read_csv(file_path)[state_column].to_numpy().astype(int)
    unique_states = np.unique(state[2:12])
    first_row = int(np.where(state == unique_states[slot_ordinal])[0][0])
    return np.arange(first_row, len(state), len(unique_states))


class NPMConverterTestMixin:
    """Shared assertions; each subclass supplies one NPM layout's fixtures and expectations.

    Subclasses define the two source files, the storesList topology, the `.npm_params.json` the GuPPy
    run would have written, and a ``read_expected_store_data`` staticmethod reading a store's samples
    straight from the acquisition file.
    """

    ACQUISITION_FILE_NAME = "signals.csv"
    EVENT_FILE_NAME = "ttls.csv"

    @pytest.fixture
    def session_folder(self, tmp_path):
        folder_path = tmp_path / "session"
        folder_path.mkdir()
        shutil.copy(self.ACQUISITION_SOURCE, folder_path / self.ACQUISITION_FILE_NAME)
        shutil.copy(self.EVENT_SOURCE, folder_path / self.EVENT_FILE_NAME)
        return folder_path

    @pytest.fixture
    def guppy_output_folder(self, tmp_path):
        folder_path = generate_mock_guppy_output_folder(
            tmp_path / "session_output_1",
            recording_site_to_stores=self.RECORDING_SITE_TO_STORES,
            event_store_to_name=self.EVENT_STORE_TO_NAME,
            cross_correlation_pairs=(),
        )
        # Which clock and unit a session was read on is a choice made when GuPPy ran; it records them
        # here beside storesList.csv, one unit and one column for the whole session.
        (folder_path / ".npm_params.json").write_text(json.dumps(self.NPM_PARAMETERS), encoding="utf-8")
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
        """Each ``file<N>_ch<slot><column>`` store resolves to the samples GuPPy's demultiplexer picks."""
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
    # chev is the lower state (17, the isosbestic) and chod the higher (18); column J counts from 1 past
    # the timestamps, so Region0G/1G/2G are J=1/2/3.
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
        slot_ordinal = {"chev": 0, "chod": 1}[store_id.split("_")[1][:4]]
        column_position = int(store_id[-1])
        rows = guppy_channel_rows(file_path, state_column="Flags", slot_ordinal=slot_ordinal)
        return pandas.read_csv(file_path)[f"Region{column_position - 1}G"].to_numpy()[rows]

    def test_slot_maps_to_its_excitation_wavelength(self, converter):
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
        f"roi0{index}": {"signal": f"file0_chod{index}", "control": f"file0_chev{index}"} for index in (1, 2, 3, 4)
    }
    EVENT_STORE_TO_NAME = {"event1": "trial_start", "event3": "trial_end"}
    NPM_PARAMETERS = {
        "npm_split_events": [False, True],
        "npm_time_unit": "milliseconds",
        "npm_timestamp_column_name": "ComputerTimestamp",
    }

    @staticmethod
    def read_expected_store_data(file_path, store_id):
        slot_ordinal = {"chev": 0, "chod": 1}[store_id.split("_")[1][:4]]
        column_position = int(store_id[-1])
        rows = guppy_channel_rows(file_path, state_column="LedState", slot_ordinal=slot_ordinal)
        return pandas.read_csv(file_path)[f"G{column_position - 1}"].to_numpy()[rows]

    def test_timestamps_come_from_the_recorded_clock(self, converter):
        """`.npm_params.json` names ComputerTimestamp, so that column is read rather than SystemTimestamp."""
        signal = converter.data_interface_objects["FiberPhotometry_signal"]
        assert signal.source_data["timestamps_column"] == "ComputerTimestamp"

        rows = guppy_channel_rows(
            TestGuppyConverterNPMTwoClocks.ACQUISITION_SOURCE, state_column="LedState", slot_ordinal=1
        )
        expected = pandas.read_csv(TestGuppyConverterNPMTwoClocks.ACQUISITION_SOURCE)["ComputerTimestamp"].to_numpy()
        np.testing.assert_allclose(signal.get_original_timestamps(), expected[rows] / 1e3)


class TestGuppyConverterNPMHeaderless(NPMConverterTestMixin):
    """The legacy layout, which has no state column, paired with GuPPy's unsplit ``event0`` store.

    Both fall back to the generic CSV interfaces: channels cycle by row parity alone (so the count comes
    from ``noChannels``), and ``event0`` means the whole event file as one type, which
    ``NPMEventsInterface`` cannot express because it always splits by label.

    Both files come from GuPPy's ``sampleData_NPM_5``, whose real storesList is literally
    ``file0_chev1,file0_chod1,event0``. Their timestamps share the millisecond clock, but the GIN
    acquisition stub is truncated to 40 rows, so the event onsets fall past its end.
    """

    ACQUISITION_SOURCE = NPM_FOLDER / "no_header_no_state_column" / "three_regions_milliseconds.csv"
    EVENT_SOURCE = NPM_EVENTS_FOLDER / "single_event_type" / "PagCeAVgatFear_1512_ts0.csv"
    RECORDING_SITE_TO_STORES = {
        f"roi0{index}": {"signal": f"file0_chod{index}", "control": f"file0_chev{index}"} for index in (1, 2, 3)
    }
    EVENT_STORE_TO_NAME = {"event0": "ttl"}
    NPM_PARAMETERS = {
        "npm_split_events": [False, False],
        "npm_time_unit": "milliseconds",
        "npm_timestamp_column_name": None,
    }

    @staticmethod
    def read_expected_store_data(file_path, store_id):
        # No state column: the slot is the phase directly, and the stride is noChannels (2 in the mock).
        slot_ordinal = {"chev": 0, "chod": 1}[store_id.split("_")[1][:4]]
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


class TestNPMRunParameters:
    """Reading the session-wide settings GuPPy recorded beside ``storesList.csv``."""

    @pytest.fixture
    def guppy_output_folder(self, tmp_path):
        return generate_mock_guppy_output_folder(
            tmp_path / "session_output_1",
            recording_site_to_stores={"roi01": {"signal": "file0_chod1", "control": "file0_chev1"}},
            event_store_to_name={"event0": "ttl"},
            cross_correlation_pairs=(),
        )

    def test_reads_the_session_wide_unit_and_column(self, guppy_output_folder):
        (guppy_output_folder / ".npm_params.json").write_text(
            json.dumps(
                {
                    "npm_split_events": [False, False],
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


class TestNPMStoreDecoding:
    """Unit tests for decode paths the three end-to-end fixtures do not reach."""

    @pytest.fixture
    def session_folder(self, tmp_path):
        folder_path = tmp_path / "session"
        folder_path.mkdir()
        return folder_path

    def test_event_file_occupies_a_file_index(self, session_folder):
        """GuPPy indexes every surviving CSV, so an event file that sorts first shifts the data files."""
        shutil.copy(NPM_EVENTS_FOLDER / "event_type_as_number" / "ttls.csv", session_folder / "a_events.csv")
        shutil.copy(NPM_FOLDER / "multi_timestamp" / "signals.csv", session_folder / "b_signals.csv")

        source_files = npm_source_files(session_folder)
        assert [path.name for path in source_files] == ["a_events.csv", "b_signals.csv"]
        demux = npm_store_to_demux(session_folder, "file1_chev1", number_of_channels=2)
        assert demux["file_path"].name == "b_signals.csv"

    def test_derived_files_are_excluded(self, session_folder):
        """GuPPy globs out the per-channel files it wrote itself, so they never take an index."""
        shutil.copy(NPM_FOLDER / "multi_timestamp" / "signals.csv", session_folder / "signals.csv")
        shutil.copy(NPM_FOLDER / "multi_timestamp" / "signals.csv", session_folder / "file0_chev1.csv")

        source_files = npm_source_files(session_folder)
        assert [path.name for path in source_files] == ["signals.csv"]

    def test_strobed_state_has_no_single_wavelength(self, session_folder, tmp_path):
        """`LedState 6` is 470+560 in one frame, which no single fiber photometry series can express."""
        shutil.copy(
            NPM_FOLDER / "multi_wavelength_per_led_state" / "simultaneous_470_and_560.csv",
            session_folder / "signals.csv",
        )
        shutil.copy(NPM_EVENTS_FOLDER / "event_type_as_number" / "ttls.csv", session_folder / "ttls.csv")
        guppy_output_folder = generate_mock_guppy_output_folder(
            tmp_path / "session_output_1",
            # chod is LedState 6, the strobed frame.
            recording_site_to_stores={"roi01": {"signal": "file0_chod1", "control": "file0_chev1"}},
            event_store_to_name={"event1": "ttl"},
            cross_correlation_pairs=(),
        )
        (guppy_output_folder / ".npm_params.json").write_text(
            json.dumps(
                {
                    "npm_split_events": [False, True],
                    "npm_time_unit": "seconds",
                    "npm_timestamp_column_name": None,
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(AssertionError, match="not a single wavelength"):
            GuppyConverter(
                fiber_photometry_folder_path=session_folder,
                events_folder_path=session_folder,
                guppy_folder_path=guppy_output_folder,
                acquisition_format="npm",
            )

    def test_slot_beyond_the_interleave_raises(self, session_folder):
        """A two-state file has no third channel, so `chpr` cannot be resolved."""
        shutil.copy(NPM_FOLDER / "multi_timestamp" / "signals.csv", session_folder / "signals.csv")
        with pytest.raises(AssertionError, match="interleaves only 2 channel"):
            npm_store_to_demux(session_folder, "file0_chpr1", number_of_channels=2)

    def test_headerless_without_channel_count_raises(self, session_folder):
        """The legacy layout's interleave has no on-disk signature, so it cannot be guessed."""
        shutil.copy(
            NPM_FOLDER / "no_header_no_state_column" / "three_regions_milliseconds.csv",
            session_folder / "signals.csv",
        )
        with pytest.raises(AssertionError, match="recorded no 'noChannels'"):
            npm_store_to_demux(session_folder, "file0_chev1", number_of_channels=None)
