"""Tests for :class:`~neuroconv.datainterfaces.icephys.axon.axonintracellularinterface.AxonIntracellularInterface`.

TODO: this is a prototype test set that points at full, un-stubbed example files under ``~/data``.
Before merging, stub these recordings, upload them to the gin ``ephy_testing_data`` repo, and switch the
paths to ``ECEPHY_DATA_PATH``. Until then the module skips itself when the local example files are absent.

The interface is single-electrode: one instance writes one electrode's response (and an optional paired
stimulus) plus one intracellular-recordings row per sweep, each row tagged with the run's ``sequence`` and
``stimulus_type`` (the run information in denormalized form). Each ``DataInterfaceTestMixin`` subclass below
targets a distinct code path (timing model, clamp-mode series type, the two stimulus sources). The interface
deliberately stops at the per-sweep rows; the upper icephys hierarchy (simultaneous / sequential recordings)
is built once the full set of channels and files is known, not by a single interface. Discovery and the
construction-time validation errors are grouped in ``TestAxonInterfaceConstruction``.
"""

import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from pynwb import NWBHDF5IO
from pynwb.icephys import (
    CurrentClampSeries,
    CurrentClampStimulusSeries,
    IZeroClampSeries,
    VoltageClampSeries,
    VoltageClampStimulusSeries,
)
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import AxonIntracellularInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

from ..setup_paths import OUTPUT_PATH

# TODO: replace these full files with stubbed gin fixtures under ECEPHY_DATA_PATH (see module docstring). Each
# test class names its file directly and skips itself when that file is absent (via SKIP_REASON).
DATA_ROOT = Path.home() / "data"
SKIP_REASON = "Prototype ABF example files under ~/data are not available (TODO: replace with gin fixtures)."


class TestAxonMultiSweepCurrentClampCommand(DataInterfaceTestMixin):
    """Multi-sweep (episodic-mode) current clamp (IN0 recorded in mV) with a reconstructed command stimulus: the core single-series + table path."""

    data_interface_cls = AxonIntracellularInterface
    file_path = (
        DATA_ROOT
        / "khaliq_data"
        / "Electrophysiology recordings"
        / "Cells with AIS component"
        / "10 June 2021"
        / "C1"
        / "ADP"
        / "21610017.abf"
    )
    pytestmark = pytest.mark.skipif(not file_path.exists(), reason=SKIP_REASON)
    response_channel_name = "IN0"
    interface_kwargs = dict(
        file_path=file_path,
        response_channel_name=response_channel_name,
        mode="current_clamp",
        stimulus_command="Cmd 0",
    )
    save_directory = OUTPUT_PATH

    def test_get_channel_names(self):
        # The recorded channels; the reconstructed stimulus comes from the "Cmd 0" command, not one of these.
        names = AxonIntracellularInterface.get_channel_names(file_path=self.file_path)
        assert names == ["IN0", "IN1"]

    def check_extracted_metadata(self, metadata: dict):
        # session_start_time is read from the ABF header (a real date for version 2).
        assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 6, 10, 17, 14, 1, 315000)

        # Default identity: the device key is the plain file stem and the electrode key is the plain stem plus
        # response channel. NWB object names are the CamelCase form of the electrode key (so dual patch still
        # yields distinct electrodes).
        device_metadata_key = "21610017"
        electrode_metadata_key = "21610017_IN0"
        electrode_name_suffix = "21610017IN0"

        expected_device_metadata = {
            device_metadata_key: {
                "name": "MultiClamp 700",
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
                "name": f"CurrentClampSeries{electrode_name_suffix}",
                "description": "Intracellular response (current_clamp).",
                "electrode_metadata_key": electrode_metadata_key,
            },
        }
        # The paired stimulus lives in the parallel PatchClampStimulusSeries registry at the SAME key, with no
        # `_stimulus` suffix and no electrode link (it reuses the response's electrode).
        expected_stimulus_metadata = {
            electrode_metadata_key: {
                "name": f"CurrentClampStimulusSeries{electrode_name_suffix}",
                "description": "Intracellular stimulus (current_clamp).",
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
            response = nwbfile.acquisition["CurrentClampSeries21610017IN0"]
            stimulus = nwbfile.stimulus["CurrentClampStimulusSeries21610017IN0"]
            assert isinstance(response, CurrentClampSeries)
            assert isinstance(stimulus, CurrentClampStimulusSeries)

            # Multi-sweep timing: one continuous series sampled at 20 us, gaps carried as timestamps (not a rate).
            assert response.timestamps[:5].tolist() == [0.0, 2e-05, 4e-05, 6e-05, 8e-05]
            assert response.electrode.device.name == "MultiClamp 700"

            # The sweep structure is preserved on the intracellular table: one row per sweep, each addressing its
            # slice of the concatenated series by (start, count) in samples. Define the expected layout, then assert.
            number_of_sweeps = 9
            sweep_start_sample_indices = [0, 250000, 500000, 750000, 1000000, 1250000, 1500000, 1750000, 2000000]
            samples_per_sweep = [250000] * number_of_sweeps

            intracellular_recordings = nwbfile.intracellular_recordings
            assert len(intracellular_recordings) == number_of_sweeps  # one row per sweep
            responses = intracellular_recordings["responses"]["response"]
            assert sweep_start_sample_indices == [responses[i].idx_start for i in range(len(intracellular_recordings))]
            assert samples_per_sweep == [responses[i].count for i in range(len(intracellular_recordings))]

            # Stimulus is referenced over the identical per-sweep ranges.
            stimuli = intracellular_recordings["stimuli"]["stimulus"]
            assert sweep_start_sample_indices == [stimuli[i].idx_start for i in range(len(intracellular_recordings))]
            assert samples_per_sweep == [stimuli[i].count for i in range(len(intracellular_recordings))]

            # Every row carries the run's `sequence` (the file stem; one run per file, so all 9 rows share it) and
            # `stimulus_type` (here the protocol name from the header) -- the run information in denormalized form.
            sequences = [intracellular_recordings["sequence"][i] for i in range(len(intracellular_recordings))]
            assert set(sequences) == {"21610017"}
            stimulus_types = [
                intracellular_recordings["stimulus_type"][i] for i in range(len(intracellular_recordings))
            ]
            assert set(stimulus_types) == {"CC_ADP"}


class TestAxonSingleSweepABFv1(DataInterfaceTestMixin):
    """Single-sweep (gap-free-mode) ABF version-1 recording: rate timing, no stimulus, unknown amplifier device."""

    data_interface_cls = AxonIntracellularInterface
    file_path = DATA_ROOT / "axon_abf_examples" / "hennestad" / "RL220408_right1_0000.abf"
    pytestmark = pytest.mark.skipif(not file_path.exists(), reason=SKIP_REASON)
    response_channel_name = "Adc0"
    interface_kwargs = dict(
        file_path=file_path,
        response_channel_name=response_channel_name,
        mode="current_clamp",
    )
    save_directory = OUTPUT_PATH

    def test_get_channel_names(self):
        names = AxonIntracellularInterface.get_channel_names(file_path=self.file_path)
        assert names == ["Adc0", "Adc1", "Adc5", "Adc6"]

    def check_extracted_metadata(self, metadata: dict):
        # session_start_time is a version-1 placeholder (no real date: 1900-01-01 plus a time-of-day).
        assert metadata["NWBFile"]["session_start_time"] == datetime(1900, 1, 1, 16, 10, 0, 250000)

        device_metadata_key = "RL220408_right1_0000"
        electrode_metadata_key = "RL220408_right1_0000_Adc0"
        electrode_name_suffix = "RL220408Right10000Adc0"

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
            response = nwbfile.acquisition["CurrentClampSeriesRL220408Right10000Adc0"]
            assert response.rate == 20000.0  # single segment -> uniform rate in Hz, not timestamps
            assert response.timestamps is None
            assert len(nwbfile.stimulus) == 0
            # No telegraph model -> the device name comes from the write-time placeholder.
            assert "Amplifier" in nwbfile.devices
            intracellular_recordings = nwbfile.intracellular_recordings
            assert len(intracellular_recordings) == 1
            # Gap-free acquisition (operation mode 3) -> the `stimulus_type` column is the "gap-free" label.
            assert intracellular_recordings["stimulus_type"][0] == "gap-free"


class TestAxonVoltageClampCommand(DataInterfaceTestMixin):
    """Genuine voltage clamp (IN0 recorded in pA) with a reconstructed command: VoltageClampSeries + VoltageClampStimulusSeries."""

    data_interface_cls = AxonIntracellularInterface
    file_path = DATA_ROOT / "axon_abf_examples" / "combista_gfp" / "GFP_Oligodendrocytes" / "2025_06_09_0000.abf"
    pytestmark = pytest.mark.skipif(not file_path.exists(), reason=SKIP_REASON)
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
        assert names == ["IN0"]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2025, 6, 9, 17, 55, 13, 25000)

        device_metadata_key = "2025_06_09_0000"
        electrode_metadata_key = "2025_06_09_0000_IN0"
        electrode_name_suffix = "202506090000IN0"
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
            response = nwbfile.acquisition["VoltageClampSeries202506090000IN0"]
            stimulus = nwbfile.stimulus["VoltageClampStimulusSeries202506090000IN0"]
            assert isinstance(response, VoltageClampSeries)
            assert isinstance(stimulus, VoltageClampStimulusSeries)
            assert response.electrode.device.name == "MultiClamp 700"
            # The sweeps are contiguous (no inter-sweep gaps), so neo's per-segment start times are regular and
            # the series is written as a uniform 10 kHz rate from the file's 21 ms pre-sweep offset, not timestamps.
            assert response.timestamps is None
            assert response.rate == pytest.approx(10000.0, rel=1e-6)
            assert response.starting_time == pytest.approx(0.021)

            number_of_sweeps = 10
            sweep_start_sample_indices = [0, 7250, 14500, 21750, 29000, 36250, 43500, 50750, 58000, 65250]
            samples_per_sweep = [7250] * number_of_sweeps
            intracellular_recordings = nwbfile.intracellular_recordings
            assert len(intracellular_recordings) == number_of_sweeps
            responses = intracellular_recordings["responses"]["response"]
            assert sweep_start_sample_indices == [responses[i].idx_start for i in range(len(intracellular_recordings))]
            assert samples_per_sweep == [responses[i].count for i in range(len(intracellular_recordings))]
            sequences = [intracellular_recordings["sequence"][i] for i in range(len(intracellular_recordings))]
            assert set(sequences) == {"2025_06_09_0000"}
            stimulus_types = [
                intracellular_recordings["stimulus_type"][i] for i in range(len(intracellular_recordings))
            ]
            assert set(stimulus_types) == {"Simple Voltage Clamp Protocol"}


class TestAxonIZero(DataInterfaceTestMixin):
    """I=0 mode: IZeroClampSeries and no stimulus."""

    data_interface_cls = AxonIntracellularInterface
    file_path = DATA_ROOT / "axon_abf_examples" / "combista_gfp" / "GFP_Oligodendrocytes" / "2025_06_12_0022.abf"
    pytestmark = pytest.mark.skipif(not file_path.exists(), reason=SKIP_REASON)
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
        assert metadata["NWBFile"]["session_start_time"] == datetime(2025, 6, 12, 19, 47, 8, 461999)

        device_metadata_key = "2025_06_12_0022"
        electrode_metadata_key = "2025_06_12_0022_IN0"
        electrode_name_suffix = "202506120022IN0"
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
            response = nwbfile.acquisition["IZeroClampSeries202506120022IN0"]
            assert isinstance(response, IZeroClampSeries)
            assert response.electrode.device.name == "MultiClamp 700"
            # The sweeps are contiguous (no inter-sweep gaps), so neo's per-segment start times are regular and
            # the series is written as a uniform 10 kHz rate from the file's 21 ms pre-sweep offset, not timestamps.
            assert response.timestamps is None
            assert response.rate == pytest.approx(10000.0, rel=1e-6)
            assert response.starting_time == pytest.approx(0.021)

            number_of_sweeps = 4
            sweep_start_sample_indices = [0, 7250, 14500, 21750]
            samples_per_sweep = [7250] * number_of_sweeps
            intracellular_recordings = nwbfile.intracellular_recordings
            assert len(intracellular_recordings) == number_of_sweeps
            responses = intracellular_recordings["responses"]["response"]
            assert sweep_start_sample_indices == [responses[i].idx_start for i in range(len(intracellular_recordings))]
            assert samples_per_sweep == [responses[i].count for i in range(len(intracellular_recordings))]
            sequences = [intracellular_recordings["sequence"][i] for i in range(len(intracellular_recordings))]
            assert set(sequences) == {"2025_06_12_0022"}
            stimulus_types = [
                intracellular_recordings["stimulus_type"][i] for i in range(len(intracellular_recordings))
            ]
            assert set(stimulus_types) == {"Simple Voltage Clamp Protocol"}


class TestAxonRecordedMonitorStimulus(DataInterfaceTestMixin):
    """Stimulus sourced from a recorded monitor channel (not a reconstructed command)."""

    data_interface_cls = AxonIntracellularInterface
    file_path = (
        DATA_ROOT
        / "khaliq_data"
        / "Electrophysiology recordings"
        / "Cells with AIS component"
        / "10 June 2021"
        / "C1"
        / "ADP"
        / "21610017.abf"
    )
    pytestmark = pytest.mark.skipif(not file_path.exists(), reason=SKIP_REASON)
    response_channel_name = "IN0"
    interface_kwargs = dict(
        file_path=file_path,
        response_channel_name=response_channel_name,
        mode="current_clamp",
        stimulus_channel_name="IN1",  # the recorded current monitor
    )
    save_directory = OUTPUT_PATH

    def test_get_channel_names(self):
        names = AxonIntracellularInterface.get_channel_names(file_path=self.file_path)
        assert names == ["IN0", "IN1"]

    def check_extracted_metadata(self, metadata: dict):
        # session_start_time is read from the ABF header (same file as the episodic test).
        assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 6, 10, 17, 14, 1, 315000)

        # A recorded-monitor stimulus produces a paired entry in the parallel PatchClampStimulusSeries registry,
        # at the same key as the response.
        electrode_metadata_key = "21610017_IN0"
        electrode_name_suffix = "21610017IN0"
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
            response = nwbfile.acquisition["CurrentClampSeries21610017IN0"]
            stimulus = nwbfile.stimulus["CurrentClampStimulusSeries21610017IN0"]
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

    file_path = (
        DATA_ROOT
        / "khaliq_data"
        / "Electrophysiology recordings"
        / "Cells with AIS component"
        / "10 June 2021"
        / "C1"
        / "ADP"
        / "21610017.abf"
    )
    pytestmark = pytest.mark.skipif(not file_path.exists(), reason=SKIP_REASON)

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

    episodic_file = (
        DATA_ROOT
        / "khaliq_data"
        / "Electrophysiology recordings"
        / "Cells with AIS component"
        / "10 June 2021"
        / "C1"
        / "ADP"
        / "21610017.abf"
    )
    gapfree_v1_file = DATA_ROOT / "axon_abf_examples" / "hennestad" / "RL220408_right1_0000.abf"
    pytestmark = pytest.mark.skipif(not (episodic_file.exists() and gapfree_v1_file.exists()), reason=SKIP_REASON)

    def test_get_command_names_present_for_v2_empty_for_v1(self):
        # stimulus_command options: present for ABF version 2, empty for version 1 (no reconstructable protocol).
        expected_commands = ["Cmd 0", "Cmd 1", "Cmd 2", "Cmd 3"]
        assert AxonIntracellularInterface.get_command_names(file_path=self.episodic_file) == expected_commands
        assert AxonIntracellularInterface.get_command_names(file_path=self.gapfree_v1_file) == []


class TestAxonInterfaceConstructionErrors:
    """The construction-time validation errors (no conversion is run)."""

    episodic_file = (
        DATA_ROOT
        / "khaliq_data"
        / "Electrophysiology recordings"
        / "Cells with AIS component"
        / "10 June 2021"
        / "C1"
        / "ADP"
        / "21610017.abf"
    )
    gapfree_v1_file = DATA_ROOT / "axon_abf_examples" / "hennestad" / "RL220408_right1_0000.abf"
    izero_file = DATA_ROOT / "axon_abf_examples" / "combista_gfp" / "GFP_Oligodendrocytes" / "2025_06_12_0022.abf"
    pytestmark = pytest.mark.skipif(
        not (episodic_file.exists() and gapfree_v1_file.exists() and izero_file.exists()), reason=SKIP_REASON
    )

    def test_missing_required_arguments_raises(self):
        # pydantic reports each missing keyword-only argument by name, so the user sees what to add.
        with pytest.raises(ValidationError) as exception_info:
            AxonIntracellularInterface(file_path=self.episodic_file)
        message = str(exception_info.value)
        assert "Missing required keyword only argument" in message
        assert "response_channel_name" in message
        assert "mode" in message

    def test_unknown_response_channel_raises(self):
        expected_message = (
            "Recorded channel 'does_not_exist' not found in '21610017.abf'. "
            "Available recorded channels: ['IN0', 'IN1']."
        )
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            AxonIntracellularInterface(
                file_path=self.episodic_file, response_channel_name="does_not_exist", mode="current_clamp"
            )

    def test_stimulus_sources_are_mutually_exclusive(self):
        expected_message = (
            "Provide at most one of 'stimulus_channel_name' (a recorded monitor) or 'stimulus_command' "
            "(a reconstructed command), not both."
        )
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            AxonIntracellularInterface(
                file_path=self.episodic_file,
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
                file_path=self.gapfree_v1_file,
                response_channel_name="Adc0",
                mode="current_clamp",
                stimulus_command="Cmd 0",
            )
