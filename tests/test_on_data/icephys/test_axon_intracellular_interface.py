"""Tests for :class:`~neuroconv.datainterfaces.icephys.axon.axonintracellularinterface.AxonIntracellularInterface`.

The fixtures live in the gin ``ephy_testing_data`` repo under ``axon/intracellular_data`` (a purpose-built set
of small ABF files, each shrunk by structure-preserving truncation so the header, protocol, and channel metadata
are intact while the samples are cut). See that folder's READMEs for what each file exercises.

The interface is single-electrode: one instance writes one electrode's response (and an optional paired
stimulus) plus one intracellular-recordings row per sweep, each row tagged with the run's ``sequence`` and
``stimulus_type`` (the run information in denormalized form). Each ``DataInterfaceTestMixin`` subclass below
targets a distinct code path (timing model, clamp-mode series type, the two stimulus sources). The interface
deliberately stops at the per-sweep rows; the upper icephys hierarchy (simultaneous / sequential recordings)
is built once the full set of channels and files is known, not by a single interface. Discovery and the
construction-time validation errors are grouped at the end.

Note on the reconstructed-command tests: a ``stimulus_command`` is rebuilt full-length from the protocol epoch
table, so it only matches a response that was not truncated per sweep. Both reconstructed-command fixtures here
(``step.abf``, ``user_list.abf``) are recorded in pA (voltage clamp); the truncated current-clamp protocol files
would have a command longer than their response. Current-clamp stimulus coverage is via the recorded-monitor path.
"""

import re
from copy import deepcopy
from datetime import datetime

import pytest
from pydantic import ValidationError
from pynwb import NWBHDF5IO
from pynwb.icephys import (
    CurrentClampStimulusSeries,
    IZeroClampSeries,
    VoltageClampSeries,
    VoltageClampStimulusSeries,
)
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import AxonIntracellularInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

from ..setup_paths import ECEPHY_DATA_PATH, OUTPUT_PATH

ICEPHYS_DATA_PATH = ECEPHY_DATA_PATH / "axon" / "intracellular_data"


class TestAxonMultiSweepVoltageClampCommand(DataInterfaceTestMixin):
    """Multi-sweep voltage clamp (IN0 recorded in pA) with a reconstructed command, on a gapped (episodic) timeline:
    the core single-series + table path with the irregular-timing (timestamps) branch."""

    data_interface_cls = AxonIntracellularInterface
    file_path = ICEPHYS_DATA_PATH / "read_raw_protocol" / "user_list.abf"
    response_channel_name = "IN0"
    interface_kwargs = dict(
        file_path=file_path,
        response_channel_name=response_channel_name,
        mode="voltage_clamp",
        stimulus_command="Cmd 0",
    )
    save_directory = OUTPUT_PATH

    def test_get_channel_names(self):
        # The recorded channels; the reconstructed stimulus comes from the "Cmd 0" command, not one of these.
        names = AxonIntracellularInterface.get_channel_names(file_path=self.file_path)
        assert names == ["IN0", "AO#0"]

    def check_extracted_metadata(self, metadata: dict):
        # session_start_time is read from the ABF header (a real date for version 2).
        assert metadata["NWBFile"]["session_start_time"] == datetime(2020, 12, 3, 14, 13, 3, 760000)

        # Default identity: the device key is the plain file stem and the electrode key is the plain stem plus
        # response channel. NWB object names are the CamelCase form of the electrode key.
        device_metadata_key = "user_list"
        electrode_metadata_key = "user_list_IN0"
        electrode_name_suffix = "UserListIN0"

        expected_device_metadata = {
            device_metadata_key: {
                "name": "Axopatch 200B",
                "description": "Axon Instruments amplifier (telegraph-reported model).",
            }
        }
        expected_electrode_metadata = {
            electrode_metadata_key: {
                "name": f"IntracellularElectrode{electrode_name_suffix}",
                "description": "Patch-clamp electrode.",
                "device_metadata_key": device_metadata_key,
            }
        }
        expected_series_metadata = {
            electrode_metadata_key: {
                "name": f"VoltageClampSeries{electrode_name_suffix}",
                "description": "Intracellular response (voltage_clamp).",
                "electrode_metadata_key": electrode_metadata_key,
            },
        }
        # The paired stimulus lives in the parallel PatchClampStimulusSeries registry at the SAME key, with no
        # `_stimulus` suffix and no electrode link (it reuses the response's electrode).
        expected_stimulus_metadata = {
            electrode_metadata_key: {
                "name": f"VoltageClampStimulusSeries{electrode_name_suffix}",
                "description": "Intracellular stimulus (voltage_clamp).",
            },
        }

        assert metadata["Devices"] == expected_device_metadata
        assert metadata["Icephys"]["IntracellularElectrodes"] == expected_electrode_metadata
        assert metadata["Icephys"]["PatchClampSeries"] == expected_series_metadata
        assert metadata["Icephys"]["PatchClampStimulusSeries"] == expected_stimulus_metadata

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            # The interface concatenates all sweeps into one continuous series, so there is exactly one response
            # series and one stimulus series, not one per sweep.
            assert len(nwbfile.acquisition) == 1
            assert len(nwbfile.stimulus) == 1
            response = nwbfile.acquisition["VoltageClampSeriesUserListIN0"]
            stimulus = nwbfile.stimulus["VoltageClampStimulusSeriesUserListIN0"]
            assert isinstance(response, VoltageClampSeries)
            assert isinstance(stimulus, VoltageClampStimulusSeries)

            # Multi-sweep timing: one continuous series sampled at 2 kHz, gaps carried as timestamps (not a rate).
            assert response.rate is None
            assert response.timestamps[:5].tolist() == [0.0, 0.0005, 0.001, 0.0015, 0.002]
            assert response.electrode.device.name == "Axopatch 200B"

            # The sweep structure is preserved on the intracellular table: one row per sweep, each addressing its
            # slice of the concatenated series by (start, count) in samples.
            number_of_sweeps = 3
            sweep_start_sample_indices = [0, 51612, 103224]
            samples_per_sweep = [51612] * number_of_sweeps

            intracellular_recordings = nwbfile.intracellular_recordings
            assert len(intracellular_recordings) == number_of_sweeps  # one row per sweep
            responses = intracellular_recordings["responses"]["response"]
            assert sweep_start_sample_indices == [responses[i].idx_start for i in range(len(intracellular_recordings))]
            assert samples_per_sweep == [responses[i].count for i in range(len(intracellular_recordings))]

            # Stimulus is referenced over the identical per-sweep ranges.
            stimuli = intracellular_recordings["stimuli"]["stimulus"]
            assert sweep_start_sample_indices == [stimuli[i].idx_start for i in range(len(intracellular_recordings))]
            assert samples_per_sweep == [stimuli[i].count for i in range(len(intracellular_recordings))]

            # Every row carries the run's `sequence` (the file stem; one run per file, so all rows share it) and
            # `stimulus_type` (here the protocol name from the header) -- the run information in denormalized form.
            sequences = [intracellular_recordings["sequence"][i] for i in range(len(intracellular_recordings))]
            assert set(sequences) == {"user_list"}
            stimulus_types = [
                intracellular_recordings["stimulus_type"][i] for i in range(len(intracellular_recordings))
            ]
            assert set(stimulus_types) == {"WT_act with ramp_reversed_env"}


class TestAxonSingleSweepABFv1(DataInterfaceTestMixin):
    """Single-sweep (gap-free-mode) ABF version-1 recording: rate timing, no stimulus, unknown amplifier device.

    This file's header reports a bogus episode count; the interface trusts ``nOperationMode`` (gap-free) over it,
    so it reads as one sweep.
    """

    data_interface_cls = AxonIntracellularInterface
    file_path = ICEPHYS_DATA_PATH / "abf1_gapfree_bogus_episode_count.abf"
    response_channel_name = "10Vm"
    interface_kwargs = dict(
        file_path=file_path,
        response_channel_name=response_channel_name,
        mode="current_clamp",
    )
    save_directory = OUTPUT_PATH

    def test_get_channel_names(self):
        names = AxonIntracellularInterface.get_channel_names(file_path=self.file_path)
        assert names == ["10Vm"]

    def check_extracted_metadata(self, metadata: dict):
        # session_start_time is a version-1 placeholder (no real date: 1900-01-01 plus a time-of-day).
        assert metadata["NWBFile"]["session_start_time"] == datetime(1900, 1, 1, 14, 15, 0, 711999)

        device_metadata_key = "abf1_gapfree_bogus_episode_count"
        electrode_metadata_key = "abf1_gapfree_bogus_episode_count_10Vm"
        electrode_name_suffix = "Abf1GapfreeBogusEpisodeCount10vm"

        # ABF v1 has no telegraph block, so the amplifier model is unknown: get_metadata does not invent a name
        # (only a generic description); the actual device name is filled at write time from the placeholder.
        expected_device_metadata = {
            device_metadata_key: {
                "description": "Axon Instruments amplifier.",
            }
        }
        # No stimulus configured -> exactly the response entry, no `_stimulus`.
        expected_series_metadata = {
            electrode_metadata_key: {
                "name": f"CurrentClampSeries{electrode_name_suffix}",
                "description": "Intracellular response (current_clamp).",
                "electrode_metadata_key": electrode_metadata_key,
            }
        }

        assert metadata["Devices"] == expected_device_metadata
        assert metadata["Icephys"]["PatchClampSeries"] == expected_series_metadata

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            response = nwbfile.acquisition["CurrentClampSeriesAbf1GapfreeBogusEpisodeCount10vm"]
            assert response.rate == 1000.0  # single segment -> uniform rate in Hz, not timestamps
            assert response.timestamps is None
            assert len(nwbfile.stimulus) == 0
            # No telegraph model -> the device name comes from the write-time placeholder.
            assert "Amplifier" in nwbfile.devices
            intracellular_recordings = nwbfile.intracellular_recordings
            assert len(intracellular_recordings) == 1
            # Gap-free acquisition (operation mode 3) -> the `stimulus_type` column is the "gap-free" label.
            assert intracellular_recordings["stimulus_type"][0] == "gap-free"


class TestAxonVoltageClampCommand(DataInterfaceTestMixin):
    """Genuine voltage clamp (IN0 recorded in pA) with a reconstructed command, on a contiguous timeline:
    VoltageClampSeries + VoltageClampStimulusSeries with the regular-timing (rate) branch."""

    data_interface_cls = AxonIntracellularInterface
    file_path = ICEPHYS_DATA_PATH / "read_raw_protocol" / "step.abf"
    response_channel_name = "IN0"
    interface_kwargs = dict(
        file_path=file_path,
        response_channel_name=response_channel_name,
        mode="voltage_clamp",
        stimulus_command="Cmd 0",
    )
    save_directory = OUTPUT_PATH

    def test_get_channel_names(self):
        names = AxonIntracellularInterface.get_channel_names(file_path=self.file_path)
        assert names == ["IN0", "IN1"]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2018, 7, 2, 9, 29, 4, 849999)

        device_metadata_key = "step"
        electrode_metadata_key = "step_IN0"
        electrode_name_suffix = "StepIN0"
        assert metadata["Devices"] == {
            device_metadata_key: {
                "name": "MultiClamp 700",
                "description": "Axon Instruments amplifier (telegraph-reported model).",
            }
        }
        assert metadata["Icephys"]["PatchClampSeries"] == {
            electrode_metadata_key: {
                "name": f"VoltageClampSeries{electrode_name_suffix}",
                "description": "Intracellular response (voltage_clamp).",
                "electrode_metadata_key": electrode_metadata_key,
            },
        }
        assert metadata["Icephys"]["PatchClampStimulusSeries"] == {
            electrode_metadata_key: {
                "name": f"VoltageClampStimulusSeries{electrode_name_suffix}",
                "description": "Intracellular stimulus (voltage_clamp).",
            },
        }

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            assert len(nwbfile.acquisition) == 1
            assert len(nwbfile.stimulus) == 1
            response = nwbfile.acquisition["VoltageClampSeriesStepIN0"]
            stimulus = nwbfile.stimulus["VoltageClampStimulusSeriesStepIN0"]
            assert isinstance(response, VoltageClampSeries)
            assert isinstance(stimulus, VoltageClampStimulusSeries)
            assert response.electrode.device.name == "MultiClamp 700"
            # The sweeps are contiguous (no inter-sweep gaps), so neo's per-segment start times are regular and
            # the series is written as a uniform 20 kHz rate from the start of the file, not timestamps.
            assert response.timestamps is None
            assert response.rate == pytest.approx(20000.0, rel=1e-6)
            assert response.starting_time == pytest.approx(0.0)

            number_of_sweeps = 3
            sweep_start_sample_indices = [0, 20000, 40000]
            samples_per_sweep = [20000] * number_of_sweeps
            intracellular_recordings = nwbfile.intracellular_recordings
            assert len(intracellular_recordings) == number_of_sweeps
            responses = intracellular_recordings["responses"]["response"]
            assert sweep_start_sample_indices == [responses[i].idx_start for i in range(len(intracellular_recordings))]
            assert samples_per_sweep == [responses[i].count for i in range(len(intracellular_recordings))]
            sequences = [intracellular_recordings["sequence"][i] for i in range(len(intracellular_recordings))]
            assert set(sequences) == {"step"}
            stimulus_types = [
                intracellular_recordings["stimulus_type"][i] for i in range(len(intracellular_recordings))
            ]
            assert set(stimulus_types) == {"0201 memtest"}


class TestAxonIZero(DataInterfaceTestMixin):
    """I=0 mode: IZeroClampSeries and no stimulus."""

    data_interface_cls = AxonIntracellularInterface
    file_path = ICEPHYS_DATA_PATH / "abf2_zero_current_clamp.abf"
    response_channel_name = "IN0"
    interface_kwargs = dict(
        file_path=file_path,
        response_channel_name=response_channel_name,
        mode="izero",
    )
    save_directory = OUTPUT_PATH

    def test_get_channel_names(self):
        names = AxonIntracellularInterface.get_channel_names(file_path=self.file_path)
        assert names == ["IN0"]

    def check_extracted_metadata(self, metadata: dict):
        # session_start_time is read from the ABF header (this file is anonymized, so the date is a cleared default).
        assert metadata["NWBFile"]["session_start_time"] == datetime(2000, 1, 1, 0, 0)

        device_metadata_key = "abf2_zero_current_clamp"
        electrode_metadata_key = "abf2_zero_current_clamp_IN0"
        electrode_name_suffix = "Abf2ZeroCurrentClampIN0"
        assert metadata["Devices"] == {
            device_metadata_key: {
                "name": "MultiClamp 700",
                "description": "Axon Instruments amplifier (telegraph-reported model).",
            }
        }
        # I=0 has no stimulus -> only the response entry.
        assert metadata["Icephys"]["PatchClampSeries"] == {
            electrode_metadata_key: {
                "name": f"IZeroClampSeries{electrode_name_suffix}",
                "description": "Intracellular response (izero).",
                "electrode_metadata_key": electrode_metadata_key,
            }
        }

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            assert len(nwbfile.acquisition) == 1
            assert len(nwbfile.stimulus) == 0
            response = nwbfile.acquisition["IZeroClampSeriesAbf2ZeroCurrentClampIN0"]
            assert isinstance(response, IZeroClampSeries)
            assert response.electrode.device.name == "MultiClamp 700"
            # The sweeps are gapped (episodic), so the series is written with explicit timestamps, not a rate; the
            # first sample sits at the file's 21 ms pre-sweep offset.
            assert response.rate is None
            assert response.timestamps is not None
            assert response.timestamps[0] == pytest.approx(0.021)

            number_of_sweeps = 4
            sweep_start_sample_indices = [0, 1000, 2000, 3000]
            samples_per_sweep = [1000] * number_of_sweeps
            intracellular_recordings = nwbfile.intracellular_recordings
            assert len(intracellular_recordings) == number_of_sweeps
            responses = intracellular_recordings["responses"]["response"]
            assert sweep_start_sample_indices == [responses[i].idx_start for i in range(len(intracellular_recordings))]
            assert samples_per_sweep == [responses[i].count for i in range(len(intracellular_recordings))]
            sequences = [intracellular_recordings["sequence"][i] for i in range(len(intracellular_recordings))]
            assert set(sequences) == {"abf2_zero_current_clamp"}
            stimulus_types = [
                intracellular_recordings["stimulus_type"][i] for i in range(len(intracellular_recordings))
            ]
            assert set(stimulus_types) == {"Simple Voltage Clamp Protocol"}


class TestAxonRecordedMonitorStimulus(DataInterfaceTestMixin):
    """Current clamp (IN0 in mV) with a stimulus sourced from a recorded monitor channel (IN1), not a
    reconstructed command: CurrentClampSeries + CurrentClampStimulusSeries from a recorded channel."""

    data_interface_cls = AxonIntracellularInterface
    file_path = ICEPHYS_DATA_PATH / "dual_patch_pairs" / "current_clamp.abf"
    response_channel_name = "IN0"
    interface_kwargs = dict(
        file_path=file_path,
        response_channel_name=response_channel_name,
        mode="current_clamp",
        stimulus_channel_name="IN1",  # the second recorded electrode, used here as a recorded monitor
    )
    save_directory = OUTPUT_PATH

    def test_get_channel_names(self):
        names = AxonIntracellularInterface.get_channel_names(file_path=self.file_path)
        assert names == ["IN0", "IN1"]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2014, 10, 8, 16, 43, 18, 203000)

        # A recorded-monitor stimulus produces a paired entry in the parallel PatchClampStimulusSeries registry,
        # at the same key as the response.
        electrode_metadata_key = "current_clamp_IN0"
        electrode_name_suffix = "CurrentClampIN0"
        assert metadata["Icephys"]["PatchClampSeries"] == {
            electrode_metadata_key: {
                "name": f"CurrentClampSeries{electrode_name_suffix}",
                "description": "Intracellular response (current_clamp).",
                "electrode_metadata_key": electrode_metadata_key,
            },
        }
        assert metadata["Icephys"]["PatchClampStimulusSeries"] == {
            electrode_metadata_key: {
                "name": f"CurrentClampStimulusSeries{electrode_name_suffix}",
                "description": "Intracellular stimulus (current_clamp).",
            },
        }

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            response = nwbfile.acquisition["CurrentClampSeriesCurrentClampIN0"]
            stimulus = nwbfile.stimulus["CurrentClampStimulusSeriesCurrentClampIN0"]
            assert isinstance(stimulus, CurrentClampStimulusSeries)
            # The recorded monitor (IN1) is read like the response, so the stimulus shares the response's length
            # (unlike a reconstructed command, which is synthesized from the protocol).
            assert stimulus.data.shape[0] == response.data.shape[0]


class TestAxonIntracellularMetadata:
    """How the dict-based icephys metadata's ``*_metadata_key`` link fields drive which devices and electrodes
    are shared, and that writing does not mutate the caller's metadata.

    Mirrors the pose-estimation ``TestPoseEstimationMetadata``: instantiate two interfaces with distinct
    ``metadata_key``s, build the full ``metadata`` dict inline with the link fields pointing where we want, write
    both to one NWBFile, and assert the linking. Electrodes and devices dedup by ``name``, so a shared
    ``device_metadata_key`` yields one device, a shared ``electrode_metadata_key`` yields one electrode, and
    distinct keys yield independent objects.
    """

    file_path = ICEPHYS_DATA_PATH / "dual_patch_pairs" / "current_clamp.abf"

    def test_two_electrodes_share_one_device(self):
        # The two electrodes reference the same `device_metadata_key`, so one device is created and shared.
        interface_in0 = AxonIntracellularInterface(
            file_path=self.file_path, response_channel_name="IN0", mode="current_clamp", metadata_key="patch_a"
        )
        interface_in1 = AxonIntracellularInterface(
            file_path=self.file_path, response_channel_name="IN1", mode="voltage_clamp", metadata_key="patch_b"
        )
        shared_device_key = "rig_amplifier"
        metadata = {
            "Devices": {
                shared_device_key: {"name": "SharedAmplifier", "description": "One amplifier, two headstages."}
            },
            "Icephys": {
                "IntracellularElectrodes": {
                    "patch_a": {
                        "name": "ElectrodeA",
                        "description": "Patch A.",
                        "device_metadata_key": shared_device_key,
                    },
                    "patch_b": {
                        "name": "ElectrodeB",
                        "description": "Patch B.",
                        "device_metadata_key": shared_device_key,
                    },
                },
                "PatchClampSeries": {
                    "patch_a": {"name": "ResponseA", "description": "A.", "electrode_metadata_key": "patch_a"},
                    "patch_b": {"name": "ResponseB", "description": "B.", "electrode_metadata_key": "patch_b"},
                },
            },
        }

        nwbfile = mock_NWBFile()
        interface_in0.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        interface_in1.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        # One shared device; the two named electrodes from the metadata both link to it, and each response
        # series links to its electrode.
        assert list(nwbfile.devices) == ["SharedAmplifier"]
        assert set(nwbfile.icephys_electrodes) == {"ElectrodeA", "ElectrodeB"}
        assert nwbfile.icephys_electrodes["ElectrodeA"].device.name == "SharedAmplifier"
        assert nwbfile.icephys_electrodes["ElectrodeB"].device.name == "SharedAmplifier"
        assert set(nwbfile.acquisition) == {"ResponseA", "ResponseB"}
        assert nwbfile.acquisition["ResponseA"].electrode.name == "ElectrodeA"
        assert nwbfile.acquisition["ResponseB"].electrode.name == "ElectrodeB"

    def test_two_series_share_one_electrode(self):
        # The two series reference the same `electrode_metadata_key`, so one electrode is created and shared.
        interface_a = AxonIntracellularInterface(
            file_path=self.file_path, response_channel_name="IN0", mode="current_clamp", metadata_key="series_a"
        )
        interface_b = AxonIntracellularInterface(
            file_path=self.file_path, response_channel_name="IN0", mode="current_clamp", metadata_key="series_b"
        )
        shared_electrode_key = "the_pipette"
        metadata = {
            "Devices": {"amp": {"name": "Amplifier"}},
            "Icephys": {
                "IntracellularElectrodes": {
                    shared_electrode_key: {
                        "name": "SharedElectrode",
                        "description": "One pipette.",
                        "device_metadata_key": "amp",
                    },
                },
                "PatchClampSeries": {
                    "series_a": {
                        "name": "ResponseA",
                        "description": "A.",
                        "electrode_metadata_key": shared_electrode_key,
                    },
                    "series_b": {
                        "name": "ResponseB",
                        "description": "B.",
                        "electrode_metadata_key": shared_electrode_key,
                    },
                },
            },
        }

        nwbfile = mock_NWBFile()
        interface_a.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        interface_b.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        # One shared electrode (named from the metadata, linked to its device); both response series link to it.
        assert list(nwbfile.devices) == ["Amplifier"]
        assert set(nwbfile.icephys_electrodes) == {"SharedElectrode"}
        assert nwbfile.icephys_electrodes["SharedElectrode"].device.name == "Amplifier"
        assert set(nwbfile.acquisition) == {"ResponseA", "ResponseB"}
        assert nwbfile.acquisition["ResponseA"].electrode.name == "SharedElectrode"
        assert nwbfile.acquisition["ResponseB"].electrode.name == "SharedElectrode"

    def test_independent_devices_and_electrodes(self):
        # Distinct device and electrode keys yield two independent devices and two independent electrodes.
        interface_a = AxonIntracellularInterface(
            file_path=self.file_path, response_channel_name="IN0", mode="current_clamp", metadata_key="cell_a"
        )
        interface_b = AxonIntracellularInterface(
            file_path=self.file_path, response_channel_name="IN1", mode="voltage_clamp", metadata_key="cell_b"
        )
        metadata = {
            "Devices": {"amp_a": {"name": "AmplifierA"}, "amp_b": {"name": "AmplifierB"}},
            "Icephys": {
                "IntracellularElectrodes": {
                    "cell_a": {"name": "ElectrodeA", "description": "A.", "device_metadata_key": "amp_a"},
                    "cell_b": {"name": "ElectrodeB", "description": "B.", "device_metadata_key": "amp_b"},
                },
                "PatchClampSeries": {
                    "cell_a": {"name": "ResponseA", "description": "A.", "electrode_metadata_key": "cell_a"},
                    "cell_b": {"name": "ResponseB", "description": "B.", "electrode_metadata_key": "cell_b"},
                },
            },
        }

        nwbfile = mock_NWBFile()
        interface_a.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        interface_b.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        # Two independent devices and electrodes; each response series links to its own electrode and device.
        assert {device.name for device in nwbfile.devices.values()} == {"AmplifierA", "AmplifierB"}
        assert set(nwbfile.icephys_electrodes) == {"ElectrodeA", "ElectrodeB"}
        assert nwbfile.icephys_electrodes["ElectrodeA"].device.name == "AmplifierA"
        assert nwbfile.icephys_electrodes["ElectrodeB"].device.name == "AmplifierB"
        assert set(nwbfile.acquisition) == {"ResponseA", "ResponseB"}
        assert nwbfile.acquisition["ResponseA"].electrode.name == "ElectrodeA"
        assert nwbfile.acquisition["ResponseB"].electrode.name == "ElectrodeB"

    def test_no_metadata_mutation(self):
        # Writing must not mutate the caller's metadata dict (a non-mixin class, so it needs its own guard).
        interface = AxonIntracellularInterface(
            file_path=self.file_path, response_channel_name="IN0", mode="current_clamp"
        )
        metadata = interface.get_metadata()
        metadata_before = deepcopy(metadata)
        interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)
        assert metadata == metadata_before


class TestAxonCommandFetching:
    """get_command_names lists the DAC command channels for ABF version 2, and is empty for version 1."""

    v2_file = ICEPHYS_DATA_PATH / "dual_patch_pairs" / "current_clamp.abf"
    v1_file = ICEPHYS_DATA_PATH / "abf1_gapfree_bogus_episode_count.abf"

    def test_get_command_names_present_for_v2_empty_for_v1(self):
        # stimulus_command options: present for ABF version 2, empty for version 1 (no reconstructable protocol).
        expected_commands = ["Cmd 0", "Cmd 1", "Cmd 2", "Cmd 3"]
        assert AxonIntracellularInterface.get_command_names(file_path=self.v2_file) == expected_commands
        assert AxonIntracellularInterface.get_command_names(file_path=self.v1_file) == []


class TestAxonInterfaceConstructionErrors:
    """The construction-time validation errors (no conversion is run)."""

    v2_file = ICEPHYS_DATA_PATH / "dual_patch_pairs" / "current_clamp.abf"
    v1_file = ICEPHYS_DATA_PATH / "abf1_gapfree_bogus_episode_count.abf"
    izero_file = ICEPHYS_DATA_PATH / "abf2_zero_current_clamp.abf"

    def test_missing_required_arguments_raises(self):
        # pydantic reports each missing keyword-only argument by name, so the user sees what to add.
        with pytest.raises(ValidationError) as exception_info:
            AxonIntracellularInterface(file_path=self.v2_file)
        message = str(exception_info.value)
        assert "Missing required keyword only argument" in message
        assert "response_channel_name" in message
        assert "mode" in message

    def test_unknown_response_channel_raises(self):
        expected_message = (
            "Recorded channel 'does_not_exist' not found in 'current_clamp.abf'. "
            "Available recorded channels: ['IN0', 'IN1']."
        )
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            AxonIntracellularInterface(
                file_path=self.v2_file, response_channel_name="does_not_exist", mode="current_clamp"
            )

    def test_stimulus_sources_are_mutually_exclusive(self):
        expected_message = (
            "Provide at most one of 'stimulus_channel_name' (a recorded monitor) or 'stimulus_command' "
            "(a reconstructed command), not both."
        )
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            AxonIntracellularInterface(
                file_path=self.v2_file,
                response_channel_name="IN0",
                mode="current_clamp",
                stimulus_channel_name="IN1",
                stimulus_command="Cmd 0",
            )

    def test_izero_with_a_stimulus_raises(self):
        expected_message = "mode='izero' has no stimulus; remove 'stimulus_channel_name' / 'stimulus_command'."
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            AxonIntracellularInterface(
                file_path=self.izero_file, response_channel_name="IN0", mode="izero", stimulus_command="Cmd 0"
            )

    def test_stimulus_command_requires_abf_v2(self):
        expected_message = (
            "stimulus_command (a reconstructed command) requires ABF version 2; this file is version 1, "
            "which has no protocol section. Use stimulus_channel_name (a recorded monitor) instead."
        )
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            AxonIntracellularInterface(
                file_path=self.v1_file,
                response_channel_name="10Vm",
                mode="current_clamp",
                stimulus_command="Cmd 0",
            )
