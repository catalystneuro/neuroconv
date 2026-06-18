"""Tests for the EEGLABRecordingInterface.

These tests build small synthetic EEGLAB datasets (both the self-contained ``.set`` layout and the
``.set`` + ``.fdt`` pair layout) so they run without any external data or network access.
"""

from datetime import datetime, timezone

import numpy as np
import pytest
from pynwb import NWBHDF5IO
from scipy.io import savemat

from neuroconv.datainterfaces import EEGLABRecordingInterface

SAMPLING_FREQUENCY = 128.0
NUMBER_OF_CHANNELS = 4
NUMBER_OF_POINTS = 500
CHANNEL_LABELS = ["Fz", "Cz", "Pz", "Oz"]


def _make_eeg_struct(data_field, *, with_events: bool = True, trials: int = 1) -> dict:
    """Build a MATLAB-style EEG struct dict. ``data_field`` is either an array (inline) or a filename."""
    chanlocs = dict(
        labels=CHANNEL_LABELS,
        X=np.arange(NUMBER_OF_CHANNELS, dtype="float64"),
        Y=np.arange(NUMBER_OF_CHANNELS, dtype="float64") + 10.0,
        Z=np.arange(NUMBER_OF_CHANNELS, dtype="float64") + 20.0,
    )
    eeg = dict(
        setname="synthetic",
        srate=SAMPLING_FREQUENCY,
        nbchan=NUMBER_OF_CHANNELS,
        pnts=NUMBER_OF_POINTS,
        trials=trials,
        xmin=0.0,
        data=data_field,
        chanlocs=chanlocs,
    )
    if with_events:
        eeg["event"] = dict(
            type=["stim", "resp", "stim"],
            latency=np.array([1.0, 129.0, 257.0]),  # 1-based sample indices
        )
    return eeg


@pytest.fixture
def microvolt_traces() -> np.ndarray:
    """Deterministic (n_channels, n_points) traces in microvolts."""
    rng = np.random.default_rng(seed=0)
    return (rng.standard_normal((NUMBER_OF_CHANNELS, NUMBER_OF_POINTS)) * 20.0).astype("float32")


@pytest.fixture
def pair_set_path(tmp_path, microvolt_traces):
    """A .set file referencing an external .fdt file."""
    fdt_path = tmp_path / "pair.fdt"
    # EEGLAB .fdt is float32 in column-major (n_channels, n_points) order.
    microvolt_traces.T.astype("<f4").tofile(fdt_path)
    set_path = tmp_path / "pair.set"
    savemat(str(set_path), {"EEG": _make_eeg_struct("pair.fdt")}, do_compression=True)
    return set_path


@pytest.fixture
def inline_set_path(tmp_path, microvolt_traces):
    """A self-contained .set file with inline data."""
    set_path = tmp_path / "inline.set"
    savemat(str(set_path), {"EEG": _make_eeg_struct(microvolt_traces)}, do_compression=True)
    return set_path


def _session_metadata(interface):
    metadata = interface.get_metadata()
    metadata["NWBFile"]["session_start_time"] = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return metadata


class TestEEGLABRecordingInterface:
    def test_inline_layout_traces_and_events(self, inline_set_path, microvolt_traces, tmp_path):
        interface = EEGLABRecordingInterface(file_path=inline_set_path)
        nwbfile_path = tmp_path / "inline.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=_session_metadata(interface), overwrite=True)

        with NWBHDF5IO(path=str(nwbfile_path), mode="r") as io:
            nwbfile = io.read()
            electrical_series = nwbfile.acquisition["ElectricalSeries"]
            # Data is written in volts; the source is in microvolts.
            written_microvolts = electrical_series.data[:] * electrical_series.conversion * 1e6
            np.testing.assert_allclose(written_microvolts, microvolt_traces.T, atol=1e-2)

            # Channel names and locations land in the electrodes table.
            electrodes = nwbfile.electrodes.to_dataframe()
            assert list(electrodes["channel_name"]) == CHANNEL_LABELS
            assert {"rel_x", "rel_y", "rel_z"}.issubset(electrodes.columns)

            # Events are written to a TimeIntervals table.
            events = nwbfile.intervals["events"]
            assert list(events["label"][:]) == ["stim", "resp", "stim"]
            np.testing.assert_allclose(
                events["start_time"][:], [0.0, 128.0 / SAMPLING_FREQUENCY, 256.0 / SAMPLING_FREQUENCY]
            )

    def test_pair_and_inline_layouts_match(self, pair_set_path, inline_set_path):
        """Both EEGLAB layouts must produce equivalent recordings."""
        pair_interface = EEGLABRecordingInterface(file_path=pair_set_path)
        inline_interface = EEGLABRecordingInterface(file_path=inline_set_path)

        np.testing.assert_allclose(
            pair_interface.recording_extractor.get_traces(),
            inline_interface.recording_extractor.get_traces(),
            atol=1e-3,
        )
        assert list(pair_interface.recording_extractor.get_channel_ids()) == CHANNEL_LABELS
        assert list(inline_interface.recording_extractor.get_channel_ids()) == CHANNEL_LABELS
        assert len(pair_interface._eeglab_events) == len(inline_interface._eeglab_events) == 3

    def test_write_events_false(self, inline_set_path):
        interface = EEGLABRecordingInterface(file_path=inline_set_path)
        nwbfile = interface.create_nwbfile(metadata=_session_metadata(interface), write_events=False)
        assert nwbfile.intervals is None or "events" not in nwbfile.intervals

    def test_epoched_data_splits_into_one_file_per_epoch(self, tmp_path):
        number_of_trials = 6
        epoch_start_time = -1.0
        rng = np.random.default_rng(seed=1)
        # Epoched EEGLAB data is a (n_channels, n_points, n_trials) tensor.
        epoched_traces = (rng.standard_normal((NUMBER_OF_CHANNELS, NUMBER_OF_POINTS, number_of_trials)) * 20.0).astype(
            "float32"
        )
        eeg = _make_eeg_struct(epoched_traces, trials=number_of_trials, with_events=False)
        eeg["xmin"] = epoch_start_time
        set_path = tmp_path / "epoched.set"
        savemat(str(set_path), {"EEG": eeg}, do_compression=True)

        interface = EEGLABRecordingInterface(file_path=set_path)
        assert interface.is_epoched

        written_paths = interface.run_conversion_split_by_epoch(
            nwbfile_path=tmp_path / "epoched.nwb", metadata=_session_metadata(interface), overwrite=True
        )
        expected_paths = [tmp_path / f"epoched_epoch{index}.nwb" for index in range(number_of_trials)]
        assert written_paths == expected_paths

        for epoch_index, path in enumerate(expected_paths):
            assert path.exists()
            with NWBHDF5IO(path=str(path), mode="r") as io:
                nwbfile = io.read()
                electrical_series = nwbfile.acquisition["ElectricalSeries"]
                # Each file holds exactly one epoch.
                assert electrical_series.data.shape == (NUMBER_OF_POINTS, NUMBER_OF_CHANNELS)
                written_microvolts = electrical_series.data[:] * electrical_series.conversion * 1e6
                np.testing.assert_allclose(written_microvolts, epoched_traces[:, :, epoch_index].T, atol=1e-2)
                # Epoch-relative time axis: the series starts at EEG.xmin.
                assert electrical_series.starting_time == pytest.approx(epoch_start_time)

    def test_epoched_conversion_without_split_raises(self, tmp_path):
        rng = np.random.default_rng(seed=3)
        epoched_traces = (rng.standard_normal((NUMBER_OF_CHANNELS, NUMBER_OF_POINTS, 4)) * 20.0).astype("float32")
        set_path = tmp_path / "epoched.set"
        savemat(str(set_path), {"EEG": _make_eeg_struct(epoched_traces, trials=4)}, do_compression=True)

        interface = EEGLABRecordingInterface(file_path=set_path)
        with pytest.raises(ValueError, match="epoched"):
            interface.create_nwbfile(metadata=_session_metadata(interface))

    def test_epoched_events_assigned_to_correct_epoch(self, tmp_path):
        """Events are partitioned to their epoch with epoch-relative onsets."""
        number_of_trials = 3
        epoch_start_time = -1.0
        rng = np.random.default_rng(seed=4)
        epoched_traces = (rng.standard_normal((NUMBER_OF_CHANNELS, NUMBER_OF_POINTS, number_of_trials)) * 20.0).astype(
            "float32"
        )
        eeg = _make_eeg_struct(epoched_traces, trials=number_of_trials, with_events=False)
        eeg["xmin"] = epoch_start_time
        # Two events: one time-locking event in epoch 1 and one in epoch 2 (1-based EEGLAB indices).
        locking_sample = 1 - epoch_start_time * SAMPLING_FREQUENCY  # within-epoch sample for t_rel == 0
        eeg["event"] = dict(
            type=["stim", "stim"],
            latency=np.array([locking_sample, NUMBER_OF_POINTS + locking_sample]),
            epoch=np.array([1, 2]),
        )
        set_path = tmp_path / "epoched_events.set"
        savemat(str(set_path), {"EEG": eeg}, do_compression=True)

        sub_interfaces = EEGLABRecordingInterface(file_path=set_path).split_by_epoch()
        assert len(sub_interfaces) == number_of_trials
        # Epochs 0 and 1 each get one event at the time-locking time (t == 0); epoch 2 gets none.
        assert len(sub_interfaces[0]._eeglab_events) == 1
        assert sub_interfaces[0]._eeglab_events[0]["start_time"] == pytest.approx(0.0)
        assert len(sub_interfaces[1]._eeglab_events) == 1
        assert sub_interfaces[1]._eeglab_events[0]["start_time"] == pytest.approx(0.0)
        assert len(sub_interfaces[2]._eeglab_events) == 0

    def test_subject_metadata_from_struct_and_bids(self, tmp_path, microvolt_traces):
        eeg = _make_eeg_struct(microvolt_traces)
        eeg["subject"] = "S07"
        eeg["BIDS"] = dict(pInfo=[["participant_id", "Gender", "Age"], ["S07", "F", 34]])
        set_path = tmp_path / "with_subject.set"
        savemat(str(set_path), {"EEG": eeg}, do_compression=True)

        metadata = EEGLABRecordingInterface(file_path=set_path).get_metadata()
        assert metadata["Subject"]["subject_id"] == "S07"
        assert metadata["Subject"]["sex"] == "F"
        assert metadata["Subject"]["age"] == "P34Y"

    def test_subject_metadata_partial_when_bids_empty(self, tmp_path, microvolt_traces):
        """Only subject_id is set when Gender/Age are empty (as in real LSL-sourced files)."""
        eeg = _make_eeg_struct(microvolt_traces)
        eeg["subject"] = "S01"
        eeg["BIDS"] = dict(pInfo=[["participant_id", "Gender", "Age"], ["S1", np.array([]), np.array([])]])
        set_path = tmp_path / "partial_subject.set"
        savemat(str(set_path), {"EEG": eeg}, do_compression=True)

        subject = EEGLABRecordingInterface(file_path=set_path).get_metadata()["Subject"]
        # The real subject_id flows through; required fields are filled with defaults, and no fake age.
        assert subject["subject_id"] == "S01"
        assert subject["sex"] == "U"
        assert subject["species"] == "Unknown species"
        assert "age" not in subject

    def test_no_subject_metadata_when_absent(self, inline_set_path):
        """No Subject block is fabricated when the .set has no subject info."""
        metadata = EEGLABRecordingInterface(file_path=inline_set_path).get_metadata()
        assert "subject_id" not in metadata.get("Subject", {})

    def test_missing_channel_locations(self, tmp_path, microvolt_traces):
        """Channels lacking a location (e.g. EOG) are handled without error."""
        eeg = _make_eeg_struct(microvolt_traces)
        # Emulate EEGLAB storing an empty coordinate for a channel without a location.
        eeg["chanlocs"]["X"] = [0.0, np.array([]), 2.0, 3.0]
        eeg["chanlocs"]["Y"] = [10.0, np.array([]), 12.0, 13.0]
        eeg["chanlocs"]["Z"] = [20.0, np.array([]), 22.0, 23.0]
        set_path = tmp_path / "missing_loc.set"
        savemat(str(set_path), {"EEG": eeg}, do_compression=True)

        interface = EEGLABRecordingInterface(file_path=set_path)
        nwbfile = interface.create_nwbfile(metadata=_session_metadata(interface))
        electrodes = nwbfile.electrodes.to_dataframe()
        assert np.isnan(electrodes["rel_x"].iloc[1])
        assert not np.isnan(electrodes["rel_x"].iloc[0])

    def test_missing_fdt_raises(self, tmp_path):
        set_path = tmp_path / "broken.set"
        savemat(str(set_path), {"EEG": _make_eeg_struct("does_not_exist.fdt")}, do_compression=True)
        with pytest.raises(FileNotFoundError, match="does_not_exist.fdt"):
            EEGLABRecordingInterface(file_path=set_path)
