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


def _make_epoched_eeg_struct(traces_3d, urevent_latencies, xmin) -> dict:
    """Build an epoched EEG struct (with ``urevent``) so real per-epoch onsets are recoverable.

    ``traces_3d`` is ``(n_channels, n_points, n_trials)``; ``urevent_latencies`` are the 1-based
    original-recording sample latencies of each epoch's time-locking event.
    """
    number_of_channels, number_of_points, number_of_trials = traces_3d.shape
    chanlocs = dict(
        labels=CHANNEL_LABELS,
        X=np.arange(number_of_channels, dtype="float64"),
        Y=np.arange(number_of_channels, dtype="float64") + 10.0,
        Z=np.arange(number_of_channels, dtype="float64") + 20.0,
    )
    lock_within_sample = 1.0 - xmin * SAMPLING_FREQUENCY  # 1-based within-epoch sample at t_rel == 0
    # One time-locking event per epoch; its concatenated latency is (epoch)*pnts + within-epoch sample.
    event = dict(
        type=["stim"] * number_of_trials,
        latency=np.array([epoch * number_of_points + lock_within_sample for epoch in range(number_of_trials)]),
        epoch=np.arange(1, number_of_trials + 1),
        urevent=np.arange(1, number_of_trials + 1),
    )
    urevent = dict(type=["stim"] * number_of_trials, latency=np.asarray(urevent_latencies, dtype="float64"))
    return dict(
        setname="synthetic-epoched",
        srate=SAMPLING_FREQUENCY,
        nbchan=number_of_channels,
        pnts=number_of_points,
        trials=number_of_trials,
        xmin=xmin,
        data=traces_3d,
        chanlocs=chanlocs,
        event=event,
        urevent=urevent,
    )


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

    def test_epoched_writes_one_series_per_epoch_in_one_file(self, tmp_path):
        """Epoched data → one ElectricalSeries per epoch in a single file, on the shared real timeline."""
        number_of_trials = 3
        xmin = -1.0
        rng = np.random.default_rng(seed=1)
        traces = (rng.standard_normal((NUMBER_OF_CHANNELS, NUMBER_OF_POINTS, number_of_trials)) * 20.0).astype("float32")
        # Real (original-recording) latencies of each epoch's time-locking event — distinct and ordered.
        urevent_latencies = [129.0, 2000.0, 5000.0]
        set_path = tmp_path / "epoched.set"
        savemat(str(set_path), {"EEG": _make_epoched_eeg_struct(traces, urevent_latencies, xmin)}, do_compression=True)

        interface = EEGLABRecordingInterface(file_path=set_path)
        assert interface.is_epoched

        nwbfile_path = tmp_path / "epoched.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=_session_metadata(interface), overwrite=True)

        expected_onsets = [(latency - 1.0) / SAMPLING_FREQUENCY + xmin for latency in urevent_latencies]
        with NWBHDF5IO(path=str(nwbfile_path), mode="r") as io:
            nwbfile = io.read()
            # One ElectricalSeries per epoch (marked with "Epoch"), all in the same file.
            names = sorted(nwbfile.acquisition.keys())
            assert names == ["ElectricalSeriesEpoch0", "ElectricalSeriesEpoch1", "ElectricalSeriesEpoch2"]
            # A single shared electrodes table.
            assert len(nwbfile.electrodes) == NUMBER_OF_CHANNELS
            for index, name in enumerate(names):
                electrical_series = nwbfile.acquisition[name]
                assert electrical_series.data.shape == (NUMBER_OF_POINTS, NUMBER_OF_CHANNELS)
                # Real per-epoch start time on the shared session timeline (starting_time + rate).
                assert electrical_series.starting_time == pytest.approx(expected_onsets[index], abs=1e-6)
                assert electrical_series.rate == pytest.approx(SAMPLING_FREQUENCY)
                written_microvolts = electrical_series.data[:] * electrical_series.conversion * 1e6
                np.testing.assert_allclose(written_microvolts, traces[:, :, index].T, atol=1e-2)

            # Per-epoch boundaries in the epochs table (real times + locking-event label).
            epochs = nwbfile.epochs.to_dataframe()
            assert len(epochs) == number_of_trials
            np.testing.assert_allclose(epochs["start_time"], expected_onsets, atol=1e-6)
            assert list(epochs["epoch_index"]) == [0, 1, 2]
            assert list(epochs["label"]) == ["stim", "stim", "stim"]

            # Events come from urevent (unique) at real times.
            events = nwbfile.intervals["events"]
            assert len(events) == number_of_trials
            np.testing.assert_allclose(
                events["start_time"][:], [(latency - 1.0) / SAMPLING_FREQUENCY for latency in urevent_latencies], atol=1e-6
            )

    def test_epoched_write_epochs_false(self, tmp_path):
        rng = np.random.default_rng(seed=2)
        traces = (rng.standard_normal((NUMBER_OF_CHANNELS, NUMBER_OF_POINTS, 2)) * 20.0).astype("float32")
        set_path = tmp_path / "epoched.set"
        savemat(str(set_path), {"EEG": _make_epoched_eeg_struct(traces, [129.0, 2000.0], -1.0)}, do_compression=True)

        interface = EEGLABRecordingInterface(file_path=set_path)
        nwbfile = interface.create_nwbfile(metadata=_session_metadata(interface), write_epochs=False)
        assert nwbfile.epochs is None
        assert len(nwbfile.acquisition) == 2

    def test_continuous_has_no_epochs_table(self, inline_set_path):
        interface = EEGLABRecordingInterface(file_path=inline_set_path)
        nwbfile = interface.create_nwbfile(metadata=_session_metadata(interface))
        assert list(nwbfile.acquisition.keys()) == ["ElectricalSeries"]
        assert nwbfile.epochs is None

    def test_subject_id_from_eeg_subject_by_default(self, tmp_path, microvolt_traces):
        """By default subject_id comes from EEG.subject and BIDS.pInfo demographics are NOT imported."""
        eeg = _make_eeg_struct(microvolt_traces)
        eeg["subject"] = "S07"
        eeg["BIDS"] = dict(pInfo=[["participant_id", "Gender", "Age"], ["S07", "F", 34]])
        set_path = tmp_path / "with_subject.set"
        savemat(str(set_path), {"EEG": eeg}, do_compression=True)

        subject = EEGLABRecordingInterface(file_path=set_path).get_metadata()["Subject"]
        assert subject["subject_id"] == "S07"
        # pInfo demographics are opt-in, so sex/age are NOT read from BIDS (only the default sex).
        assert subject["sex"] == "U"
        assert "age" not in subject

    def test_bids_demographics_imported_when_opted_in(self, tmp_path, microvolt_traces):
        eeg = _make_eeg_struct(microvolt_traces)
        eeg["subject"] = "S07"
        eeg["BIDS"] = dict(pInfo=[["participant_id", "Gender", "Age"], ["S07", "F", 34]])
        set_path = tmp_path / "with_subject.set"
        savemat(str(set_path), {"EEG": eeg}, do_compression=True)

        interface = EEGLABRecordingInterface(file_path=set_path, import_bids_subject_metadata=True)
        subject = interface.get_metadata()["Subject"]
        assert subject["subject_id"] == "S07"
        assert subject["sex"] == "F"
        assert subject["age"] == "P34Y"

    def test_opted_in_but_bids_empty_yields_only_subject_id(self, tmp_path, microvolt_traces):
        """Opting in but with an empty pInfo (ds004588-style) still yields only subject_id + defaults."""
        eeg = _make_eeg_struct(microvolt_traces)
        eeg["subject"] = "S01"
        eeg["BIDS"] = dict(pInfo=[["participant_id", "Gender", "Age"], ["S1", np.array([]), np.array([])]])
        set_path = tmp_path / "partial_subject.set"
        savemat(str(set_path), {"EEG": eeg}, do_compression=True)

        subject = EEGLABRecordingInterface(
            file_path=set_path, import_bids_subject_metadata=True
        ).get_metadata()["Subject"]
        assert subject["subject_id"] == "S01"  # from EEG.subject
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
