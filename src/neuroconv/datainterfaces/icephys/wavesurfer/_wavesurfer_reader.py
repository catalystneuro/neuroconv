"""Read WaveSurfer 0.945 HDF5 files: the header, the sweeps, and the commands built from the stimulus library.

WaveSurfer (https://wavesurfer.janelia.org) is a MATLAB program that writes one HDF5 file per run. The ``/header``
group is the program's settings at the start of the run, written by MATLAB, so numbers are float64, text is
space-padded fixed-length strings, and a cell array that is not text is a group of ``element1``, ``element2``, ...
Each ``/sweep_NNNN`` group holds ``analogScans`` (int16 counts, one row per active analog input), ``digitalScans``
and ``timestamp`` (seconds from the run start to the sweep's first sample).

The stimulus formulas follow the WaveSurfer source at tag ``release-0.945``: ``+ws/Stimulus.m``,
``+ws/*StimulusDelegate.m`` and ``+ws/StimulusLibrary.m``.
"""

from datetime import datetime, timedelta
from pathlib import Path, PureWindowsPath

import h5py
import numpy as np

SUPPORTED_VERSION = "0.945"

# WaveSurfer electrode mode -> NeuroConv clamp mode.
_MODE_FROM_WAVESURFER_MODE = {"vc": "voltage_clamp", "cc": "current_clamp", "i_equals_zero": "izero"}

# Units WaveSurfer uses for each clamp mode's monitored and commanded quantity.
_VOLTAGE_UNITS = ("V", "mV", "uV")
_CURRENT_UNITS = ("A", "mA", "uA", "nA", "pA")
_MONITOR_UNITS = {"voltage_clamp": _CURRENT_UNITS, "current_clamp": _VOLTAGE_UNITS, "izero": _VOLTAGE_UNITS}
_COMMAND_UNITS = {"voltage_clamp": _VOLTAGE_UNITS, "current_clamp": _CURRENT_UNITS}

# The largest magnitude of an int16 count, where the nonlinear calibration terms are largest.
_LARGEST_COUNT = 32768.0


def _read_strings(dataset: h5py.Dataset) -> list[str]:
    """Decode a MATLAB character array or cell array of strings as a list of strings."""
    return [
        value.decode().rstrip() if isinstance(value, bytes) else str(value).rstrip()
        for value in np.asarray(dataset).ravel().tolist()
    ]


def _read_string(dataset: h5py.Dataset) -> str:
    return _read_strings(dataset)[0]


def _read_number(dataset: h5py.Dataset) -> float:
    return float(np.asarray(dataset).ravel()[0])


def _evaluate_sweep_expression(expression: str, episode_index: int) -> float:
    """Evaluate a WaveSurfer parameter string, a MATLAB expression in ``i``, the 1-based episode index in the run.

    WaveSurfer builds ``@(i)(expression)`` and calls it, so a parameter such as ``'20*(i-1)'`` changes from sweep to
    sweep. Python evaluates the common arithmetic subset after translating MATLAB's power operator.
    """
    try:
        value = eval(expression.replace("^", "**"), {"__builtins__": {}}, {"i": episode_index})
    except Exception as exception:
        raise ValueError(
            f"Could not evaluate the WaveSurfer stimulus parameter '{expression}' for i={episode_index}. "
            "Only arithmetic in `i` is supported."
        ) from exception
    return float(value)


def _calculate_core_signal(stimulus: h5py.Group, times: np.ndarray, episode_index: int) -> np.ndarray:
    """The unscaled shape of a stimulus, by type, on times measured from the end of its delay."""
    type_string = _read_string(stimulus["TypeString"])
    delegate = stimulus["Delegate"]

    def parameter(name: str) -> float:
        return _evaluate_sweep_expression(_read_string(delegate[name]), episode_index)

    if type_string == "SquarePulse":
        return np.ones_like(times)
    if type_string == "SquarePulseTrain":
        period = parameter("Period")
        pulse_duration = parameter("PulseDuration")
        if not (np.isfinite(period) and period > 0 and np.isfinite(pulse_duration) and pulse_duration > 0):
            return np.zeros_like(times)
        return (np.mod(times, period) < pulse_duration).astype("float64")
    if type_string == "TwoSquarePulses":
        first_amplitude = parameter("FirstPulseAmplitude")
        first_duration = parameter("FirstPulseDuration")
        delay_between_pulses = parameter("DelayBetweenPulses")
        second_amplitude = parameter("SecondPulseAmplitude")
        second_duration = parameter("SecondPulseDuration")
        values = (first_amplitude, first_duration, delay_between_pulses, second_amplitude, second_duration)
        if not (all(np.isfinite(values)) and first_duration >= 0 and second_duration >= 0):
            return np.zeros_like(times)
        second_start = first_duration + delay_between_pulses
        second_end = second_start + second_duration
        return first_amplitude * (times < first_duration) + second_amplitude * (
            (second_start <= times) & (times < second_end)
        )
    if type_string == "Ramp":
        duration = _evaluate_sweep_expression(_read_string(stimulus["Duration"]), episode_index)
        if not np.isfinite(duration) or duration <= 0:
            return np.zeros_like(times)
        return times / duration
    if type_string == "Sine":
        frequency = parameter("Frequency")
        if not (np.isfinite(frequency) and frequency > 0):
            return np.zeros_like(times)
        return np.sin(2 * np.pi * frequency * times)
    if type_string == "Chirp":
        duration = _evaluate_sweep_expression(_read_string(stimulus["Duration"]), episode_index)
        initial_frequency = parameter("InitialFrequency")
        final_frequency = parameter("FinalFrequency")
        values = (duration, initial_frequency, final_frequency)
        if not (all(np.isfinite(values)) and duration >= 0 and initial_frequency >= 0 and final_frequency >= 0):
            return np.zeros_like(times)
        frequency_slope = (final_frequency - initial_frequency) / duration
        return np.sin(2 * np.pi * times * (initial_frequency + frequency_slope / 2 * times))
    raise NotImplementedError(
        f"WaveSurfer stimulus type '{type_string}' is not supported. 'Expression' stimuli are arbitrary MATLAB code "
        "and 'File' stimuli read an external audio file, so neither can be rebuilt from the header."
    )


def _calculate_stimulus_signal(stimulus: h5py.Group, times: np.ndarray, episode_index: int) -> np.ndarray:
    """One stimulus on the map's time grid, as ``ws.Stimulus.calculateSignal`` computes it."""
    delay = _evaluate_sweep_expression(_read_string(stimulus["Delay"]), episode_index)
    if not np.isfinite(delay) or delay < 0:
        return np.zeros_like(times)
    times_after_delay = times - delay
    data = _calculate_core_signal(stimulus=stimulus, times=times_after_delay, episode_index=episode_index)
    amplitude = _evaluate_sweep_expression(_read_string(stimulus["Amplitude"]), episode_index)
    dc_offset = _evaluate_sweep_expression(_read_string(stimulus["DCOffset"]), episode_index)
    duration = _evaluate_sweep_expression(_read_string(stimulus["Duration"]), episode_index)
    if not (np.isfinite(amplitude) and np.isfinite(dc_offset) and np.isfinite(duration)) or duration < 0:
        return np.zeros_like(times)
    data = amplitude * data + dc_offset
    # The DC offset is zeroed outside the support too, and the last sample is zeroed so the output ends at 0.
    data[~((0 <= times_after_delay) & (times_after_delay < duration))] = 0.0
    if data.size > 0:
        data[-1] = 0.0
    return data


class WaveSurferFile:
    """The header and sweeps of one WaveSurfer 0.945 run, for one electrode."""

    def __init__(self, file_path: Path, electrode_name: str | None):
        self.file_path = Path(file_path)
        with h5py.File(self.file_path, "r") as file:
            header = file["header"]
            version = _read_string(header["VersionString"])
            if version != SUPPORTED_VERSION:
                raise ValueError(
                    f"'{self.file_path}' was written by WaveSurfer {version}, and only WaveSurfer {SUPPORTED_VERSION} "
                    "files are supported. Please open an issue at https://github.com/catalystneuro/neuroconv/issues "
                    "to request support for this version."
                )

            self.electrode = self._read_electrode(header=header, electrode_name=electrode_name)
            self.mode = _MODE_FROM_WAVESURFER_MODE[self.electrode["Mode"]]

            clock_at_run_start = np.asarray(header["ClockAtRunStart"]).ravel()
            year, month, day, hour, minute = (int(value) for value in clock_at_run_start[:5])
            self.run_start_time = datetime(year, month, day, hour, minute) + timedelta(
                seconds=float(clock_at_run_start[5])
            )
            self.protocol_name = PureWindowsPath(_read_string(header["AbsoluteProtocolFileName"])).stem or None

            acquisition = header["Acquisition"]
            self.sampling_rate = _read_number(acquisition["SampleRate"])
            is_active = np.asarray(acquisition["IsAnalogChannelActive"]).ravel().astype(bool)
            self.input_channel_names = [
                name for name, active in zip(_read_strings(acquisition["AnalogChannelNames"]), is_active) if active
            ]
            self.input_channel_units = [
                unit for unit, active in zip(_read_strings(acquisition["AnalogChannelUnits"]), is_active) if active
            ]
            self.input_channel_scales = np.asarray(acquisition["AnalogChannelScales"]).ravel()[is_active]
            # One row of calibration coefficients per active channel, lowest order first.
            self.input_scaling_coefficients = np.asarray(acquisition["AnalogScalingCoefficients"]).reshape(
                len(self.input_channel_names), -1
            )

            self.sweep_names = sorted(name for name in file if name.startswith("sweep_"))
            self.sweep_start_times = [_read_number(file[name]["timestamp"]) for name in self.sweep_names]
            self.sweep_sample_counts = [int(file[name]["analogScans"].shape[1]) for name in self.sweep_names]

            stimulation = header["Stimulation"]
            self.is_stimulation_enabled = bool(_read_number(stimulation["IsEnabled"]))
            self.stimulation_sampling_rate = _read_number(stimulation["SampleRate"])
            self.output_channel_names = _read_strings(stimulation["AnalogChannelNames"])
            self.output_channel_units = _read_strings(stimulation["AnalogChannelUnits"])
            self.does_repeat_sequence = bool(_read_number(stimulation["DoRepeatSequence"]))
            self.are_sweeps_finite = bool(_read_number(header["AreSweepsFiniteDuration"]))
            self.does_stimulation_use_acquisition_trigger = bool(
                _read_number(header["StimulationUsesAcquisitionTrigger"])
            )
            self.sweep_duration = _read_number(header["SweepDuration"])

        self.response_channel_index = self.get_input_channel_index(self.electrode["MonitorChannelName"])
        response_unit = self.input_channel_units[self.response_channel_index]
        if response_unit not in _MONITOR_UNITS[self.mode]:
            raise ValueError(
                f"The monitor channel '{self.electrode['MonitorChannelName']}' of electrode '{self.electrode['Name']}' "
                f"is in '{response_unit}', which is not a unit of the quantity monitored in {self.mode} mode."
            )
        for channel_index in range(len(self.input_channel_names)):
            self._check_calibration_is_linear(channel_index)

    @staticmethod
    def _read_electrode(header: h5py.Group, electrode_name: str | None) -> dict:
        electrodes = header["Ephys/ElectrodeManager/Electrodes"]
        fields = ("Name", "Type", "Mode", "MonitorChannelName", "CommandChannelName")
        electrode_list = [
            {field: _read_string(electrodes[element][field]) for field in fields} for element in electrodes
        ]
        names = [electrode["Name"] for electrode in electrode_list]
        if len(electrode_list) == 0:
            raise ValueError(
                "The file has no WaveSurfer electrodes, so no channel is known to be a patch-clamp signal."
            )
        if electrode_name is None:
            if len(electrode_list) > 1:
                raise ValueError(f"The file has several electrodes, so pass one of {names} as 'electrode_name'.")
            return electrode_list[0]
        if electrode_name not in names:
            raise ValueError(f"Electrode '{electrode_name}' is not in the file. The electrodes are {names}.")
        return electrode_list[names.index(electrode_name)]

    def _check_calibration_is_linear(self, channel_index: int) -> None:
        """Raise if the nonlinear terms of a channel's ADC calibration move a value by more than one count."""
        coefficients = self.input_scaling_coefficients[channel_index]
        nonlinear_terms = sum(
            abs(coefficient) * _LARGEST_COUNT**power for power, coefficient in enumerate(coefficients) if power >= 2
        )
        deviation_in_counts = nonlinear_terms / abs(coefficients[1])
        if deviation_in_counts > 1.0:
            raise ValueError(
                f"The ADC calibration of channel '{self.input_channel_names[channel_index]}' has quadratic and cubic "
                f"terms that change values by up to {deviation_in_counts:.2f} counts, so they contribute significantly "
                "to the volt values and the linear conversion NWB stores would be inaccurate."
            )

    def get_input_channel_index(self, channel_name: str) -> int:
        """Row of an active analog input in each sweep's ``analogScans``."""
        if channel_name not in self.input_channel_names:
            raise ValueError(
                f"'{channel_name}' is not an active analog input. The active inputs are {self.input_channel_names}."
            )
        return self.input_channel_names.index(channel_name)

    def get_stimulus_channel_index(self, channel_name: str) -> int:
        """Row of the analog input that recorded the delivered command, checked against the clamp mode."""
        channel_index = self.get_input_channel_index(channel_name)
        unit = self.input_channel_units[channel_index]
        if unit not in _COMMAND_UNITS[self.mode]:
            raise ValueError(
                f"The stimulus channel '{channel_name}' is in '{unit}', which is not a unit of the quantity commanded "
                f"in {self.mode} mode."
            )
        return channel_index

    def get_input_channel_conversion(self, channel_index: int) -> tuple[float, float, str]:
        """``(conversion, offset, unit)`` from counts to the channel's unit, using the linear calibration terms."""
        coefficients = self.input_scaling_coefficients[channel_index]
        scale = float(self.input_channel_scales[channel_index])
        return (
            float(coefficients[1]) / scale,
            float(coefficients[0]) / scale,
            self.input_channel_units[channel_index],
        )

    def read_input_channel(self, channel_index: int) -> np.ndarray:
        """All sweeps of one analog input, end to end, as int16 counts."""
        data = np.empty(sum(self.sweep_sample_counts), dtype="int16")
        cursor = 0
        with h5py.File(self.file_path, "r") as file:
            for sweep_name, count in zip(self.sweep_names, self.sweep_sample_counts):
                data[cursor : cursor + count] = file[sweep_name]["analogScans"][channel_index]
                cursor += count
        return data

    def get_sweep_sample_ranges(self, sample_counts: list[int]) -> list[tuple[int, int]]:
        starts = np.concatenate([[0], np.cumsum(sample_counts)[:-1]])
        return [(int(start), int(count)) for start, count in zip(starts, sample_counts)]

    def get_times(self, sample_counts: list[int], sampling_rate: float) -> np.ndarray:
        """Sample times from the run start, each sweep starting at its recorded timestamp."""
        return np.concatenate(
            [
                start_time + np.arange(count) / sampling_rate
                for start_time, count in zip(self.sweep_start_times, sample_counts)
            ]
        )

    def get_command_unit(self) -> str:
        channel_name = self.electrode["CommandChannelName"]
        if channel_name not in self.output_channel_names:
            raise ValueError(
                f"The command channel '{channel_name}' of electrode '{self.electrode['Name']}' is not an analog "
                f"output. The outputs are {self.output_channel_names}."
            )
        command_unit = self.output_channel_units[self.output_channel_names.index(channel_name)]
        if command_unit not in _COMMAND_UNITS[self.mode]:
            raise ValueError(
                f"The command channel '{channel_name}' is in '{command_unit}', which is not a unit of the quantity "
                f"commanded in {self.mode} mode."
            )
        return command_unit

    def check_command_can_be_rebuilt(self) -> None:
        """Raise if the run's command cannot be rebuilt from the stimulus library sweep by sweep."""
        if not self.is_stimulation_enabled:
            raise ValueError("Stimulation was disabled for this run, so no command was delivered.")
        if not (self.are_sweeps_finite and self.does_stimulation_use_acquisition_trigger):
            raise ValueError(
                "The stimulus can only be rebuilt for runs with finite sweeps whose stimulation uses the acquisition "
                "trigger, where every sweep is one stimulus episode."
            )
        self.get_command_unit()

    def calculate_command(self) -> tuple[np.ndarray, list[int]]:
        """The command the stimulus library specified for the electrode, for every sweep, end to end.

        Returns the samples, in the command channel's unit at the stimulation rate, and the sample count of each
        sweep. Episode ``i`` of the run is sweep ``i`` of the file.
        """
        self.check_command_can_be_rebuilt()
        # With finite sweeps on the acquisition trigger, WaveSurfer overrides every map's duration with the sweep's.
        sample_count = round(self.sweep_duration * self.stimulation_sampling_rate)
        sample_period = 1.0 / self.stimulation_sampling_rate
        times = sample_period / 2 + sample_period * np.arange(sample_count)

        channel_name = self.electrode["CommandChannelName"]
        sweeps = []
        with h5py.File(self.file_path, "r") as file:
            library = file["header/Stimulation/StimulusLibrary"]
            for episode_index in range(1, len(self.sweep_names) + 1):
                command = np.zeros(sample_count)
                map_index = self._get_map_index(library=library, episode_index=episode_index)
                if map_index is not None:
                    stimulus_map = library[f"Maps/element{map_index}"]
                    bound_channel_names = _read_strings(stimulus_map["ChannelName"])
                    if channel_name in bound_channel_names:
                        # WaveSurfer uses the first binding to a channel and ignores any later one.
                        binding_index = bound_channel_names.index(channel_name)
                        stimulus_index = int(
                            _read_number(stimulus_map[f"IndexOfEachStimulusInLibrary/element{binding_index + 1}"])
                        )
                        # An empty binding is stored as 0.
                        if stimulus_index > 0:
                            multiplier = float(np.asarray(stimulus_map["Multiplier"]).ravel()[binding_index])
                            stimulus = library[f"Stimuli/element{stimulus_index}"]
                            command = multiplier * _calculate_stimulus_signal(
                                stimulus=stimulus, times=times, episode_index=episode_index
                            )
                sweeps.append(command)
        return np.concatenate(sweeps), [sample_count] * len(sweeps)

    def _get_map_index(self, library: h5py.Group, episode_index: int) -> int | None:
        """The library index of the map played in an episode, following ``getCurrentStimulusMapIndex``."""
        class_name = _read_string(library["SelectedOutputableClassName"])
        if class_name == "":
            return None
        selected_index = int(_read_number(library["SelectedOutputableIndex"]))
        if class_name == "ws.StimulusMap":
            if episode_index > 1 and not self.does_repeat_sequence:
                return None
            return selected_index
        sequence = library[f"Sequences/element{selected_index}"]
        map_count = int(_read_number(sequence["NBindings"]))
        if episode_index <= map_count:
            binding_index = episode_index
        elif self.does_repeat_sequence and map_count > 0:
            binding_index = (episode_index - 1) % map_count + 1
        else:
            return None
        return int(_read_number(sequence[f"IndexOfEachMapInLibrary/element{binding_index}"]))
