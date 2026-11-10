"""Tests for :class:`~neuroconv.datainterfaces.icephys.wavesurfer.WaveSurferIntracellularInterface` and its converter.

The real fixtures live in the gin ``ephy_testing_data`` repo under ``wavesurfer/version_0_945``: WaveSurfer 0.945 runs
cut to their first sweeps, with their headers unchanged. See that folder's README.

The other tests run on small WaveSurfer 0.945 files written here with h5py, laid out as WaveSurfer lays out its
header and sweeps. They cover the configurations the real fixtures do not: several electrodes, inactive channels,
every stimulus type the interface rebuilds, sequences, and the errors. The rates are 10 Hz so a 2 s sweep is 20
samples and the expected arrays can be written by hand. The stimulus time grid is WaveSurfer's, ``t = dt/2 + k*dt``,
so at 10 Hz the samples sit at 0.05, 0.15, ..., 1.95 s.
"""

from datetime import datetime

import h5py
import numpy as np
import pytest
from pynwb.icephys import CurrentClampSeries, IZeroClampSeries, VoltageClampSeries

from neuroconv.converters import WaveSurferIntracellularConverter
from neuroconv.datainterfaces import WaveSurferIntracellularInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

from ..setup_paths import ECEPHY_DATA_PATH, OUTPUT_PATH

WAVESURFER_DATA_PATH = ECEPHY_DATA_PATH / "wavesurfer" / "version_0_945"

SAMPLING_RATE = 10.0
SWEEP_DURATION = 2.0
SAMPLES_PER_SWEEP = 20

# Counts -> volts is c0 + c1 * counts, and volts -> mV divides by the 0.01 V/mV scale: 0.1 mV per count, 50 mV offset.
LINEAR_COEFFICIENTS = [0.5, 0.001, 0.0, 0.0]


def square_pulse(name: str, amplitude: str, delay: str = "0.5", duration: str = "1", dc_offset: str = "0") -> dict:
    return dict(
        Name=name,
        TypeString="SquarePulse",
        Amplitude=amplitude,
        Delay=delay,
        Duration=duration,
        DCOffset=dc_offset,
        Delegate={},
    )


def stimulus_map(name: str, bindings: list) -> dict:
    """A map from ``(channel name, 1-based stimulus index or 0 for empty, multiplier)`` bindings."""
    return dict(Name=name, Bindings=bindings)


def electrode(
    name: str = "Electrode 1",
    mode: str = "cc",
    monitor: str = "Electrode 1 Voltage",
    command: str = "Command 1",
    electrode_type: str = "Axon Multiclamp",
) -> dict:
    return dict(Name=name, Type=electrode_type, Mode=mode, MonitorChannelName=monitor, CommandChannelName=command)


@pytest.fixture
def write_wavesurfer_file(tmp_path):
    """Return a function writing a WaveSurfer 0.945 file with the header fields and sweeps the interface reads."""

    def strings(values: list) -> np.ndarray:
        return np.array([value.encode() for value in values])

    def number(value: float) -> np.ndarray:
        return np.array([[float(value)]])

    def write(
        file_name: str = "cell_0001-0002.h5",
        *,
        version: str = "0.945",
        clock_at_run_start: tuple = (2025, 3, 10, 13, 17, 39.5),
        protocol_file: str = r"R:\protocols\FI steps.cfg",
        electrodes: list | None = None,
        input_channels: list | None = None,
        output_channels: list | None = None,
        stimuli: list | None = None,
        maps: list | None = None,
        sequences: list | None = None,
        selected_outputable: tuple = ("ws.StimulusMap", 1),
        stimulation_enabled: bool = True,
        stimulation_rate: float = SAMPLING_RATE,
        do_repeat_sequence: bool = True,
        stimulation_uses_acquisition_trigger: bool = True,
        sweep_timestamps: tuple = (0.0, 5.0),
        first_sweep_number: int = 1,
    ):
        electrodes = electrodes or [electrode()]
        # (name, unit, scale in V per unit, active, calibration coefficients, counts of every sweep end to end)
        input_channels = input_channels or [
            ("Electrode 1 Voltage", "mV", 0.01, True, LINEAR_COEFFICIENTS, np.arange(40)),
            ("Current Injection", "pA", 0.0025, True, LINEAR_COEFFICIENTS, np.arange(100, 140)),
        ]
        output_channels = output_channels or [("Command 1", "pA")]
        stimuli = stimuli or [square_pulse("Step", amplitude="10*i")]
        maps = maps or [stimulus_map("Steps", [("Command 1", 1, 1.0)])]
        sequences = sequences or []

        file_path = tmp_path / file_name
        with h5py.File(file_path, "w") as file:
            header = file.create_group("header")
            header["VersionString"] = strings([version])
            header["ClockAtRunStart"] = np.array(clock_at_run_start, dtype=float).reshape(-1, 1)
            header["AbsoluteProtocolFileName"] = strings([protocol_file])
            header["AreSweepsFiniteDuration"] = number(1)
            header["StimulationUsesAcquisitionTrigger"] = number(stimulation_uses_acquisition_trigger)
            header["SweepDuration"] = number(SWEEP_DURATION)
            for index, electrode_fields in enumerate(electrodes, start=1):
                group = header.create_group(f"Ephys/ElectrodeManager/Electrodes/element{index}")
                for field, value in electrode_fields.items():
                    group[field] = strings([value])

            acquisition = header.create_group("Acquisition")
            acquisition["SampleRate"] = number(SAMPLING_RATE)
            acquisition["AnalogChannelNames"] = strings([channel[0] for channel in input_channels])
            acquisition["AnalogChannelUnits"] = strings([channel[1] for channel in input_channels])
            acquisition["AnalogChannelScales"] = np.array([[channel[2]] for channel in input_channels])
            acquisition["IsAnalogChannelActive"] = np.array([[float(channel[3])] for channel in input_channels])
            active_channels = [channel for channel in input_channels if channel[3]]
            acquisition["AnalogScalingCoefficients"] = np.array([channel[4] for channel in active_channels])

            stimulation = header.create_group("Stimulation")
            stimulation["IsEnabled"] = number(stimulation_enabled)
            stimulation["SampleRate"] = number(stimulation_rate)
            stimulation["AnalogChannelNames"] = strings([channel[0] for channel in output_channels])
            stimulation["AnalogChannelUnits"] = strings([channel[1] for channel in output_channels])
            stimulation["DoRepeatSequence"] = number(do_repeat_sequence)
            library = stimulation.create_group("StimulusLibrary")
            library["SelectedOutputableClassName"] = strings([selected_outputable[0]])
            library["SelectedOutputableIndex"] = number(selected_outputable[1])
            for index, stimulus in enumerate(stimuli, start=1):
                group = library.create_group(f"Stimuli/element{index}")
                for field in ("Name", "TypeString", "Amplitude", "Delay", "Duration", "DCOffset"):
                    group[field] = strings([stimulus[field]])
                delegate = group.create_group("Delegate")
                delegate["TypeString"] = strings([stimulus["TypeString"]])
                for field, value in stimulus["Delegate"].items():
                    delegate[field] = strings([value])
            for index, map_fields in enumerate(maps, start=1):
                group = library.create_group(f"Maps/element{index}")
                group["Name"] = strings([map_fields["Name"]])
                group["Duration"] = number(1.0)
                group["ChannelName"] = strings([binding[0] for binding in map_fields["Bindings"]])
                group["Multiplier"] = np.array([[binding[2]] for binding in map_fields["Bindings"]])
                for binding_index, binding in enumerate(map_fields["Bindings"], start=1):
                    group[f"IndexOfEachStimulusInLibrary/element{binding_index}"] = number(binding[1])
            for index, map_indices in enumerate(sequences, start=1):
                group = library.create_group(f"Sequences/element{index}")
                group["NBindings"] = number(len(map_indices))
                for binding_index, map_index in enumerate(map_indices, start=1):
                    group[f"IndexOfEachMapInLibrary/element{binding_index}"] = number(map_index)

            for sweep_index, timestamp in enumerate(sweep_timestamps):
                sweep = file.create_group(f"sweep_{first_sweep_number + sweep_index:04d}")
                sweep["timestamp"] = number(timestamp)
                window = slice(sweep_index * SAMPLES_PER_SWEEP, (sweep_index + 1) * SAMPLES_PER_SWEEP)
                sweep["analogScans"] = np.array([channel[5][window] for channel in active_channels], dtype="int16")
        return file_path

    return write


class TestWaveSurferIntracellularInterface:
    def test_unsupported_version_raises(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file(version="1.0.2")

        with pytest.raises(ValueError, match="written by WaveSurfer 1.0.2, and only WaveSurfer 0.945"):
            WaveSurferIntracellularInterface(file_path=file_path)

    def test_current_clamp_response(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file()
        interface = WaveSurferIntracellularInterface(file_path=file_path)
        nwbfile = interface.create_nwbfile()

        response = nwbfile.acquisition["CurrentClampSeriesCell00010002Electrode1"]
        assert isinstance(response, CurrentClampSeries)
        np.testing.assert_array_equal(response.data, np.arange(40, dtype="int16"))
        # 0.001 V per count / 0.01 V per mV = 0.1 mV per count, and 0.5 V / 0.01 V per mV = 50 mV.
        assert response.conversion == pytest.approx(1e-4)
        assert response.offset == pytest.approx(0.05)
        # The second sweep starts at its recorded timestamp, 5 s into the run.
        np.testing.assert_allclose(response.get_timestamps()[[0, 19, 20, 39]], [0.0, 1.9, 5.0, 6.9])
        responses = nwbfile.intracellular_recordings["responses"]["response"]
        assert [(responses[row].idx_start, responses[row].count) for row in range(2)] == [(0, 20), (20, 20)]

    def test_voltage_clamp_response(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file(
            electrodes=[electrode(mode="vc", monitor="Electrode 1 Current", command="Command 1")],
            input_channels=[("Electrode 1 Current", "pA", 0.0005, True, LINEAR_COEFFICIENTS, np.arange(40))],
            output_channels=[("Command 1", "mV")],
        )
        interface = WaveSurferIntracellularInterface(file_path=file_path)
        nwbfile = interface.create_nwbfile()

        response = nwbfile.acquisition["VoltageClampSeriesCell00010002Electrode1"]
        assert isinstance(response, VoltageClampSeries)
        # 0.001 V per count / 0.0005 V per pA = 2 pA per count, and 0.5 V / 0.0005 V per pA = 1000 pA.
        assert response.conversion == pytest.approx(2e-12)
        assert response.offset == pytest.approx(1e-9)

    def test_izero_response_and_no_stimulus(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file(electrodes=[electrode(mode="i_equals_zero")])
        interface = WaveSurferIntracellularInterface(file_path=file_path)
        nwbfile = interface.create_nwbfile()

        assert isinstance(nwbfile.acquisition["IZeroClampSeriesCell00010002Electrode1"], IZeroClampSeries)
        with pytest.raises(ValueError, match="I=0 mode, which has no stimulus"):
            WaveSurferIntracellularInterface(file_path=file_path, reconstruct_stimulus=True)

    def test_inactive_channel_is_not_a_row(self, write_wavesurfer_file):
        # The monitor is the third channel, but the second is inactive, so the monitor is the second analogScans row.
        file_path = write_wavesurfer_file(
            input_channels=[
                ("Current Injection", "pA", 0.0025, True, LINEAR_COEFFICIENTS, np.arange(100, 140)),
                ("Unused", "V", 1.0, False, LINEAR_COEFFICIENTS, np.arange(40)),
                ("Electrode 1 Voltage", "mV", 0.01, True, LINEAR_COEFFICIENTS, np.arange(200, 240)),
            ]
        )
        interface = WaveSurferIntracellularInterface(file_path=file_path)
        nwbfile = interface.create_nwbfile()

        response = nwbfile.acquisition["CurrentClampSeriesCell00010002Electrode1"]
        np.testing.assert_array_equal(response.data, np.arange(200, 240, dtype="int16"))

    def test_nonlinear_calibration_raises(self, write_wavesurfer_file):
        # c2 * 32768^2 = 1e-11 * 1.07e9 = 0.0107 V, more than ten 0.001 V counts.
        file_path = write_wavesurfer_file(
            input_channels=[("Electrode 1 Voltage", "mV", 0.01, True, [0.5, 0.001, 1e-11, 0.0], np.arange(40))]
        )

        with pytest.raises(ValueError, match="quadratic and cubic terms that change values by up to 10.74 counts"):
            WaveSurferIntracellularInterface(file_path=file_path)

    def test_monitor_unit_that_does_not_match_the_mode_raises(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file(
            input_channels=[("Electrode 1 Voltage", "pA", 0.01, True, LINEAR_COEFFICIENTS, np.arange(40))]
        )

        with pytest.raises(ValueError, match="is in 'pA', which is not a unit of the quantity monitored"):
            WaveSurferIntracellularInterface(file_path=file_path)

    def test_recorded_stimulus(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file()
        interface = WaveSurferIntracellularInterface(file_path=file_path, stimulus_channel_name="Current Injection")
        nwbfile = interface.create_nwbfile()

        stimulus = nwbfile.stimulus["CurrentClampStimulusSeriesCell00010002Electrode1"]
        np.testing.assert_array_equal(stimulus.data, np.arange(100, 140, dtype="int16"))
        # 0.001 V per count / 0.0025 V per pA = 0.4 pA per count, and 0.5 V / 0.0025 V per pA = 200 pA.
        assert stimulus.conversion == pytest.approx(4e-13)
        assert stimulus.offset == pytest.approx(2e-10)

    def test_stimulus_channel_in_the_wrong_unit_raises(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file()

        with pytest.raises(ValueError, match="'Electrode 1 Voltage' is in 'mV', which is not a unit of the quantity"):
            WaveSurferIntracellularInterface(file_path=file_path, stimulus_channel_name="Electrode 1 Voltage")

    def test_channel_names_and_clamp_mode_before_construction(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file(electrodes=[electrode(mode="i_equals_zero")])

        assert WaveSurferIntracellularInterface.get_channel_names(file_path) == [
            "Electrode 1 Voltage",
            "Current Injection",
        ]
        assert WaveSurferIntracellularInterface.get_clamp_mode(file_path) == "izero"

    def test_stimulus_type_is_the_protocol_file_name(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file(protocol_file=r"R:\Lab\protocols\CC excitability 20 pA steps.cfg")
        interface = WaveSurferIntracellularInterface(file_path=file_path)
        nwbfile = interface.create_nwbfile()

        assert list(nwbfile.intracellular_recordings["stimulus_type"][:]) == ["CC excitability 20 pA steps"] * 2

    def test_session_start_time_is_the_run_start(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file(clock_at_run_start=(2025, 3, 10, 13, 17, 39.5))
        interface = WaveSurferIntracellularInterface(file_path=file_path)

        assert interface.get_metadata()["NWBFile"]["session_start_time"] == datetime(2025, 3, 10, 13, 17, 39, 500000)

    def test_device_from_the_electrode_type(self, write_wavesurfer_file):
        interface = WaveSurferIntracellularInterface(file_path=write_wavesurfer_file())
        manual_interface = WaveSurferIntracellularInterface(
            file_path=write_wavesurfer_file(file_name="manual.h5", electrodes=[electrode(electrode_type="Manual")])
        )

        assert interface.get_metadata()["Devices"] == {
            "axon_multiclamp": {
                "name": "AxonMulticlamp",
                "description": "Axon Multiclamp amplifier, as set for the electrode in WaveSurfer.",
            }
        }
        assert "Devices" not in manual_interface.get_metadata()

    def test_two_electrodes_need_a_name(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file(
            electrodes=[
                electrode(name="Electrode 1", monitor="Electrode 1 Voltage"),
                electrode(name="Electrode 2", monitor="Electrode 2 Voltage"),
            ],
            input_channels=[
                ("Electrode 1 Voltage", "mV", 0.01, True, LINEAR_COEFFICIENTS, np.arange(40)),
                ("Electrode 2 Voltage", "mV", 0.01, True, LINEAR_COEFFICIENTS, np.arange(300, 340)),
            ],
        )

        with pytest.raises(ValueError, match=r"several electrodes, so pass one of \['Electrode 1', 'Electrode 2'\]"):
            WaveSurferIntracellularInterface(file_path=file_path)
        interface = WaveSurferIntracellularInterface(file_path=file_path, electrode_name="Electrode 2")
        nwbfile = interface.create_nwbfile()
        response = nwbfile.acquisition["CurrentClampSeriesCell00010002Electrode2"]
        np.testing.assert_array_equal(response.data, np.arange(300, 340, dtype="int16"))


class TestWaveSurferStimulusReconstruction:
    """The command rebuilt from the stimulus library, written as the stimulus template."""

    @staticmethod
    def get_template(file_path) -> np.ndarray:
        interface = WaveSurferIntracellularInterface(file_path=file_path, reconstruct_stimulus=True)
        nwbfile = interface.create_nwbfile()
        return np.asarray(nwbfile.stimulus_template["CurrentClampStimulusSeriesTemplateCell00010002Electrode1"].data)

    def test_square_pulse_amplitude_follows_the_episode(self, write_wavesurfer_file):
        # Delay 0.5 s and duration 1 s cover the samples at 0.55 ... 1.45 s, indices 5 to 14; amplitude 10*i.
        file_path = write_wavesurfer_file()
        interface = WaveSurferIntracellularInterface(file_path=file_path, reconstruct_stimulus=True)
        nwbfile = interface.create_nwbfile()

        template = nwbfile.stimulus_template["CurrentClampStimulusSeriesTemplateCell00010002Electrode1"]
        first_sweep = [0.0] * 5 + [10.0] * 10 + [0.0] * 5
        second_sweep = [0.0] * 5 + [20.0] * 10 + [0.0] * 5
        np.testing.assert_array_equal(template.data, first_sweep + second_sweep)
        assert template.conversion == 1e-12
        templates = nwbfile.intracellular_recordings["stimuli"]["stimulus_template"]
        assert [(templates[row].idx_start, templates[row].count) for row in range(2)] == [(0, 20), (20, 20)]

    def test_dc_offset_is_zero_outside_the_pulse(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file(stimuli=[square_pulse("Step", amplitude="10", dc_offset="1")])

        template = self.get_template(file_path)

        np.testing.assert_array_equal(template[:20], [0.0] * 5 + [11.0] * 10 + [0.0] * 5)

    def test_square_pulse_train(self, write_wavesurfer_file):
        # Period 0.4 s, pulses 0.2 s long: two samples on, two off. The last sample is always 0.
        stimulus = dict(
            Name="Train",
            TypeString="SquarePulseTrain",
            Amplitude="1",
            Delay="0",
            Duration="2",
            DCOffset="0",
            Delegate=dict(Period="0.4", PulseDuration="0.2"),
        )
        file_path = write_wavesurfer_file(stimuli=[stimulus])

        template = self.get_template(file_path)

        np.testing.assert_array_equal(template[:20], [1.0, 1.0, 0.0, 0.0] * 4 + [1.0, 1.0, 0.0, 0.0])

    def test_two_square_pulses(self, write_wavesurfer_file):
        # After a 0.2 s delay: 3 for 0.3 s (0.25, 0.35, 0.45 s), 0.2 s apart from -2 for 0.3 s (0.75, 0.85, 0.95 s).
        stimulus = dict(
            Name="Pair",
            TypeString="TwoSquarePulses",
            Amplitude="1",
            Delay="0.2",
            Duration="1.5",
            DCOffset="0",
            Delegate=dict(
                FirstPulseAmplitude="3",
                FirstPulseDuration="0.3",
                DelayBetweenPulses="0.2",
                SecondPulseAmplitude="-2",
                SecondPulseDuration="0.3",
            ),
        )
        file_path = write_wavesurfer_file(stimuli=[stimulus])

        template = self.get_template(file_path)

        expected = [0.0, 0.0, 3.0, 3.0, 3.0, 0.0, 0.0, -2.0, -2.0, -2.0] + [0.0] * 10
        np.testing.assert_array_equal(template[:20], expected)

    def test_ramp(self, write_wavesurfer_file):
        # 10 * t / 1 s over the first second: 0.5, 1.5, ..., 9.5.
        stimulus = dict(
            Name="Ramp", TypeString="Ramp", Amplitude="10", Delay="0", Duration="1", DCOffset="0", Delegate={}
        )
        file_path = write_wavesurfer_file(stimuli=[stimulus])

        template = self.get_template(file_path)

        np.testing.assert_allclose(template[:20], [0.5 + index for index in range(10)] + [0.0] * 10, atol=1e-6)

    def test_sine(self, write_wavesurfer_file):
        # sin(2*pi*2.5*t) at t = 0.05 + 0.1*k is sin(pi/4 + k*pi/2).
        stimulus = dict(
            Name="Sine",
            TypeString="Sine",
            Amplitude="1",
            Delay="0",
            Duration="2",
            DCOffset="0",
            Delegate=dict(Frequency="2.5"),
        )
        file_path = write_wavesurfer_file(stimuli=[stimulus])

        template = self.get_template(file_path)

        np.testing.assert_allclose(template[:4], [0.70710678, 0.70710678, -0.70710678, -0.70710678], atol=1e-6)

    def test_chirp(self, write_wavesurfer_file):
        # From 0 to 10 Hz over 1 s, the phase is 2*pi*t*(5*t): sin(0.025*pi), sin(0.625*pi), sin(2.025*pi) at k=0, 2, 4.
        stimulus = dict(
            Name="Chirp",
            TypeString="Chirp",
            Amplitude="1",
            Delay="0",
            Duration="1",
            DCOffset="0",
            Delegate=dict(InitialFrequency="0", FinalFrequency="10"),
        )
        file_path = write_wavesurfer_file(stimuli=[stimulus])

        template = self.get_template(file_path)

        np.testing.assert_allclose(template[[0, 2, 4]], [0.07845910, 0.92387953, 0.07845910], atol=1e-6)

    def test_map_multiplier_and_first_binding(self, write_wavesurfer_file):
        # The command channel is bound twice: WaveSurfer plays only the first binding, scaled by its multiplier.
        file_path = write_wavesurfer_file(
            stimuli=[square_pulse("Step", amplitude="10"), square_pulse("Other", amplitude="1000")],
            maps=[stimulus_map("Steps", [("Command 1", 1, 2.0), ("Command 1", 2, 1.0)])],
        )

        template = self.get_template(file_path)

        np.testing.assert_array_equal(template[:20], [0.0] * 5 + [20.0] * 10 + [0.0] * 5)

    def test_unbound_and_empty_bindings_are_zero(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file(
            output_channels=[("Command 1", "pA"), ("Command 2", "pA")],
            maps=[
                stimulus_map("Other channel", [("Command 2", 1, 1.0)]),
                stimulus_map("Empty", [("Command 1", 0, 1.0)]),
            ],
        )
        empty_file_path = write_wavesurfer_file(
            file_name="cell_0003-0004.h5",
            output_channels=[("Command 1", "pA"), ("Command 2", "pA")],
            maps=[
                stimulus_map("Other channel", [("Command 2", 1, 1.0)]),
                stimulus_map("Empty", [("Command 1", 0, 1.0)]),
            ],
            selected_outputable=("ws.StimulusMap", 2),
        )

        np.testing.assert_array_equal(self.get_template(file_path), np.zeros(40))
        interface = WaveSurferIntracellularInterface(file_path=empty_file_path, reconstruct_stimulus=True)
        nwbfile = interface.create_nwbfile()
        template = nwbfile.stimulus_template["CurrentClampStimulusSeriesTemplateCell00030004Electrode1"]
        np.testing.assert_array_equal(template.data, np.zeros(40))

    def test_sequence_cycles_its_maps(self, write_wavesurfer_file):
        # Three sweeps through a two-map sequence play maps 1, 2, 1; without repeating, the third plays nothing.
        options = dict(
            stimuli=[square_pulse("Small", amplitude="1"), square_pulse("Large", amplitude="5")],
            maps=[stimulus_map("Small", [("Command 1", 1, 1.0)]), stimulus_map("Large", [("Command 1", 2, 1.0)])],
            sequences=[[1, 2]],
            selected_outputable=("ws.StimulusSequence", 1),
            sweep_timestamps=(0.0, 5.0, 10.0),
            input_channels=[("Electrode 1 Voltage", "mV", 0.01, True, LINEAR_COEFFICIENTS, np.arange(60))],
        )
        repeating = self.get_template(write_wavesurfer_file(**options))
        not_repeating = self.get_template(write_wavesurfer_file(do_repeat_sequence=False, **options))

        on_samples = [5, 25, 45]
        np.testing.assert_array_equal(repeating[on_samples], [1.0, 5.0, 1.0])
        np.testing.assert_array_equal(not_repeating[on_samples], [1.0, 5.0, 0.0])

    def test_stimulation_rate_gives_the_template_its_own_sweeps(self, write_wavesurfer_file):
        # At 20 Hz a 2 s sweep is 40 template samples against 20 response samples.
        file_path = write_wavesurfer_file(stimulation_rate=20.0)
        interface = WaveSurferIntracellularInterface(file_path=file_path, reconstruct_stimulus=True)
        nwbfile = interface.create_nwbfile()

        templates = nwbfile.intracellular_recordings["stimuli"]["stimulus_template"]
        assert [(templates[row].idx_start, templates[row].count) for row in range(2)] == [(0, 40), (40, 40)]
        template = nwbfile.stimulus_template["CurrentClampStimulusSeriesTemplateCell00010002Electrode1"]
        np.testing.assert_allclose(template.get_timestamps()[[0, 39, 40]], [0.0, 1.95, 5.0])

    def test_expression_stimulus_raises(self, write_wavesurfer_file):
        stimulus = dict(
            Name="Expression",
            TypeString="Expression",
            Amplitude="1",
            Delay="0",
            Duration="1",
            DCOffset="0",
            Delegate=dict(Expression="sin(t)"),
        )
        file_path = write_wavesurfer_file(stimuli=[stimulus])
        interface = WaveSurferIntracellularInterface(file_path=file_path, reconstruct_stimulus=True)

        with pytest.raises(NotImplementedError, match="WaveSurfer stimulus type 'Expression' is not supported"):
            interface.create_nwbfile()

    def test_disabled_stimulation_raises(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file(stimulation_enabled=False)

        with pytest.raises(ValueError, match="Stimulation was disabled for this run"):
            WaveSurferIntracellularInterface(file_path=file_path, reconstruct_stimulus=True)

    def test_separate_stimulation_trigger_raises(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file(stimulation_uses_acquisition_trigger=False)

        with pytest.raises(ValueError, match="whose stimulation uses the acquisition trigger"):
            WaveSurferIntracellularInterface(file_path=file_path, reconstruct_stimulus=True)


class TestWaveSurferIntracellularConverter:
    def test_runs_on_one_timeline(self, write_wavesurfer_file):
        # The second run starts 60.5 s after the first, which is the session start.
        first_run = write_wavesurfer_file("cell_0001-0002.h5", clock_at_run_start=(2025, 3, 10, 13, 17, 39.5))
        second_run = write_wavesurfer_file(
            "cell_0003-0004.h5",
            clock_at_run_start=(2025, 3, 10, 13, 18, 40.0),
            protocol_file=r"R:\protocols\Spontaneous.cfg",
            first_sweep_number=3,
        )
        converter = WaveSurferIntracellularConverter(
            data_interfaces=[
                WaveSurferIntracellularInterface(file_path=first_run),
                WaveSurferIntracellularInterface(file_path=second_run),
            ]
        )
        metadata = converter.get_metadata()
        nwbfile = converter.create_nwbfile(metadata=metadata)

        assert metadata["NWBFile"]["session_start_time"] == datetime(2025, 3, 10, 13, 17, 39, 500000)
        second_response = nwbfile.acquisition["CurrentClampSeriesCell00030004Electrode1"]
        np.testing.assert_allclose(second_response.get_timestamps()[[0, 20]], [60.5, 65.5])
        sequential = nwbfile.icephys_sequential_recordings
        assert list(sequential["stimulus_type"][:]) == ["FI steps", "Spontaneous"]
        assert len(nwbfile.intervals["sweeps"]) == 4

    def test_repetitions_and_conditions(self, write_wavesurfer_file):
        run_specifications = [
            ("cell_0001-0002.h5", 39.5, "first", "baseline"),
            ("cell_0003-0004.h5", 50.0, "second", "baseline"),
            ("cell_0005-0006.h5", 59.0, "third", "drug"),
        ]
        interfaces = [
            WaveSurferIntracellularInterface(
                file_path=write_wavesurfer_file(file_name, clock_at_run_start=(2025, 3, 10, 13, 17, seconds)),
                repetition=repetition,
                condition=condition,
            )
            for file_name, seconds, repetition, condition in run_specifications
        ]
        converter = WaveSurferIntracellularConverter(data_interfaces=interfaces)
        nwbfile = converter.create_nwbfile()

        assert len(nwbfile.icephys_repetitions) == 3
        assert len(nwbfile.icephys_experimental_conditions) == 2

    def test_two_electrodes_in_one_file_are_simultaneous(self, write_wavesurfer_file):
        file_path = write_wavesurfer_file(
            electrodes=[
                electrode(name="Electrode 1", monitor="Electrode 1 Voltage"),
                electrode(name="Electrode 2", monitor="Electrode 2 Voltage"),
            ],
            input_channels=[
                ("Electrode 1 Voltage", "mV", 0.01, True, LINEAR_COEFFICIENTS, np.arange(40)),
                ("Electrode 2 Voltage", "mV", 0.01, True, LINEAR_COEFFICIENTS, np.arange(300, 340)),
            ],
        )
        converter = WaveSurferIntracellularConverter(
            data_interfaces=[
                WaveSurferIntracellularInterface(file_path=file_path, electrode_name="Electrode 1"),
                WaveSurferIntracellularInterface(file_path=file_path, electrode_name="Electrode 2"),
            ]
        )
        nwbfile = converter.create_nwbfile()

        assert len(nwbfile.intracellular_recordings) == 4
        assert len(nwbfile.icephys_simultaneous_recordings) == 2
        assert len(nwbfile.icephys_sequential_recordings) == 1


class TestWaveSurferCurrentClampSteps(DataInterfaceTestMixin):
    """Current-clamp steps of 20*(i-1) pA from 0.5 s to 1 s, with the delivered command recorded on a second input."""

    data_interface_cls = WaveSurferIntracellularInterface
    file_path = WAVESURFER_DATA_PATH / "current_clamp" / "square_pulse_steps" / "m114_0279-0281.h5"
    interface_kwargs = dict(file_path=file_path, stimulus_channel_name="Current Injection", reconstruct_stimulus=True)
    expected_temporal_alignment_keys = ("m114_0279-0281_Electrode_1",)
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2025, 3, 10, 13, 9, 43, 49000)
        assert metadata["Devices"]["axon_multiclamp"]["name"] == "AxonMulticlamp"

    def test_template_steps(self):
        interface = WaveSurferIntracellularInterface(**self.interface_kwargs)
        nwbfile = interface.create_nwbfile()

        template = np.asarray(
            nwbfile.stimulus_template["CurrentClampStimulusSeriesTemplateM11402790281Electrode1"].data
        )
        # At 10 kHz the samples at 0.50005 ... 0.99995 s, indices 5000 to 9999 of each 20000-sample sweep, are on.
        np.testing.assert_array_equal(template[[4999, 5000, 9999, 10000]], [0.0, 0.0, 0.0, 0.0])
        np.testing.assert_array_equal(template[[24999, 25000, 29999, 30000]], [0.0, 20.0, 20.0, 0.0])
        np.testing.assert_array_equal(template[[44999, 45000, 49999, 50000]], [0.0, 40.0, 40.0, 0.0])
        assert (
            list(nwbfile.intracellular_recordings["stimulus_type"][:])
            == ["PA_Ch1_CC excitability 20 pA steps to 200 pA"] * 3
        )


class TestWaveSurferVoltageClampTestPulse(DataInterfaceTestMixin):
    """A -5 mV test pulse with stimulation at 20 kHz and acquisition at 10 kHz."""

    data_interface_cls = WaveSurferIntracellularInterface
    file_path = WAVESURFER_DATA_PATH / "voltage_clamp" / "stimulation_rate_above_acquisition_rate" / "m114_0275-0277.h5"
    interface_kwargs = dict(file_path=file_path, stimulus_channel_name="Voltage Cmd", reconstruct_stimulus=True)
    expected_temporal_alignment_keys = ("m114_0275-0277_Electrode_1",)
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2025, 3, 10, 13, 8, 52, 489000)

    def test_template_has_its_own_sweeps(self):
        interface = WaveSurferIntracellularInterface(**self.interface_kwargs)
        nwbfile = interface.create_nwbfile()

        # A 0.3 s sweep is 3000 response samples and 6000 template samples; the pulse covers 0.1 s to 0.2 s.
        templates = nwbfile.intracellular_recordings["stimuli"]["stimulus_template"]
        assert [(templates[row].idx_start, templates[row].count) for row in range(3)] == [
            (0, 6000),
            (6000, 6000),
            (12000, 6000),
        ]
        template = np.asarray(
            nwbfile.stimulus_template["VoltageClampStimulusSeriesTemplateM11402750277Electrode1"].data
        )
        np.testing.assert_array_equal(template[[1999, 2000, 3999, 4000]], [0.0, -5.0, -5.0, 0.0])


class TestWaveSurferRealFileConfigurations:
    def test_second_input_in_voltage_units_is_not_a_current_clamp_stimulus(self):
        file_path = (
            WAVESURFER_DATA_PATH
            / "current_clamp"
            / "voltage_clamp_protocol_recorded_in_current_clamp"
            / "m114_0433-0435.h5"
        )

        with pytest.raises(ValueError, match="'Voltage Cmd' is in 'mV', which is not a unit of the quantity commanded"):
            WaveSurferIntracellularInterface(file_path=file_path, stimulus_channel_name="Voltage Cmd")

    def test_only_the_first_stimulus_bound_to_a_channel_plays(self):
        # The map binds a 30 mV / -50 mV pulse pair (from 0.5 s, 1.5 s each) and then a -0.005 mV pulse at 0.1 s to
        # the same channel. WaveSurfer plays only the first binding, so the samples at 0.1 s stay 0.
        file_path = WAVESURFER_DATA_PATH / "voltage_clamp" / "two_stimuli_bound_to_one_channel" / "m114_0435-0436.h5"
        interface = WaveSurferIntracellularInterface(file_path=file_path, reconstruct_stimulus=True)
        nwbfile = interface.create_nwbfile()

        template = np.asarray(
            nwbfile.stimulus_template["VoltageClampStimulusSeriesTemplateM11404350436Electrode1"].data
        )
        np.testing.assert_array_equal(
            template[[1000, 4999, 5000, 19999, 20000, 34999, 35000]], [0, 0, 30, 30, -50, -50, 0]
        )
