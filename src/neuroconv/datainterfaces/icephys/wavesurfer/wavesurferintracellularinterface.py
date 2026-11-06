"""Interface for intracellular electrophysiology recorded with WaveSurfer."""

import numpy as np
from pydantic import FilePath, validate_call

from ._wavesurfer_reader import WaveSurferFile
from ..baseicephysinterface import BaseIcephysInterface
from ....tools.icephys import _IcephysSeriesData
from ....utils import DeepDict, get_conversion_from_unit, to_camel_case


class WaveSurferIntracellularInterface(BaseIcephysInterface):
    """
    Interface for intracellular electrophysiology recorded with WaveSurfer 0.945 (.h5).

    One interface instance corresponds to one electrode in one WaveSurfer file, which holds one run of one protocol.
    The clamp mode and the response channel come from the electrode's settings in the file header. The response is
    written as a single continuous ``PatchClampSeries`` of raw int16 counts, with each sweep recorded through the
    NWB ``IntracellularRecordings`` table by ``(start_index, count)`` ranges. The conversion uses the constant and
    linear terms of the acquisition card's calibration, and a file whose quadratic and cubic terms change values by
    more than one count raises. For an electrode of type ``Manual``, WaveSurfer records the clamp mode the user set,
    not one read from the amplifier.
    """

    display_name = "WaveSurfer Intracellular"
    keywords = ("intracellular electrophysiology", "patch clamp", "icephys", "wavesurfer")
    associated_suffixes = (".h5",)
    info = "Interface for intracellular electrophysiology recorded with WaveSurfer (Janelia), version 0.945."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        electrode_name: str | None = None,
        stimulus_channel_name: str | None = None,
        reconstruct_stimulus: bool = False,
        repetition: str | None = None,
        condition: str | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to the WaveSurfer .h5 file.
        electrode_name : str, optional
            The WaveSurfer electrode to convert, by its name in the Electrodes window (for example
            ``"Electrode 1"``). Required when the file has more than one electrode.
        stimulus_channel_name : str, optional
            An active analog input that recorded the command delivered to the electrode (the amplifier's command
            monitor, or the DAQ output wired back to an input). Written as the stimulus.
        reconstruct_stimulus : bool, default: False
            Rebuild the command the stimulus library specified for the electrode's command channel and write it as
            the stimulus template. Supported for the SquarePulse, SquarePulseTrain, TwoSquarePulses, Ramp, Sine and
            Chirp stimulus types, in runs with finite sweeps whose stimulation uses the acquisition trigger.
        repetition : str, optional
            Label grouping this run's sequential recording with others into a ``Repetitions`` entry. Used only when
            combining interfaces in a converter; if set on any interface it must be set on all of them.
        condition : str, optional
            Label grouping this run's repetition with others into an ``ExperimentalConditions`` entry. Used only
            when combining interfaces in a converter; if set on any interface it must be set on all of them.
        metadata_key : str, optional
            Identity of this interface's response ``PatchClampSeries`` in the metadata dict. Defaults to the file
            stem plus the electrode name.
        verbose : bool, default: False
        """
        super().__init__(verbose=verbose)
        self._file_path = file_path
        self.source_data = dict(
            file_path=file_path,
            electrode_name=electrode_name,
            stimulus_channel_name=stimulus_channel_name,
            reconstruct_stimulus=reconstruct_stimulus,
            repetition=repetition,
            condition=condition,
            metadata_key=metadata_key,
            verbose=verbose,
        )
        self._file = WaveSurferFile(file_path=file_path, electrode_name=electrode_name)
        self._mode = self._file.mode
        if self._mode == "izero" and (stimulus_channel_name is not None or reconstruct_stimulus):
            raise ValueError(
                "The electrode is in I=0 mode, which has no stimulus; remove 'stimulus_channel_name' and "
                "'reconstruct_stimulus'."
            )
        self._stimulus_channel_index = None
        if stimulus_channel_name is not None:
            self._stimulus_channel_index = self._file.get_stimulus_channel_index(stimulus_channel_name)
        self._reconstruct_stimulus = reconstruct_stimulus
        if reconstruct_stimulus:
            self._file.check_command_can_be_rebuilt()
        self._repetition = repetition
        self._condition = condition
        self._metadata_key = metadata_key
        self._electrode_name = self._file.electrode["Name"]

        # The run identity is the file stem; a converter combining several files overrides it with a unique label.
        self._run_identity = self._file.file_path.stem
        self._recording_start_datetime = self._file.run_start_time
        self._alignment_key = self._series_metadata_key
        self.temporal_alignment._register(
            key=self._alignment_key,
            get_native_times=self._get_native_times,
            default_start_time=0.0,
            get_number_of_samples=lambda: sum(self._file.sweep_sample_counts),
        )

    @classmethod
    def get_channel_names(cls, file_path: FilePath, electrode_name: str | None = None) -> list[str]:
        """
        Names of the active analog inputs in a WaveSurfer file: the options for ``stimulus_channel_name``. Call this
        before constructing the interface to see what is available.

        Parameters
        ----------
        file_path : FilePath
            Path to the WaveSurfer .h5 file.
        electrode_name : str, optional
            The WaveSurfer electrode, required when the file has more than one.

        Returns
        -------
        list of str
            The active analog input names, in the order of the rows of each sweep's ``analogScans``.
        """
        return WaveSurferFile(file_path=file_path, electrode_name=electrode_name).input_channel_names

    @classmethod
    def get_clamp_mode(cls, file_path: FilePath, electrode_name: str | None = None) -> str:
        """
        The clamp mode of an electrode in a WaveSurfer file, which decides whether a stimulus can be requested.

        Parameters
        ----------
        file_path : FilePath
            Path to the WaveSurfer .h5 file.
        electrode_name : str, optional
            The WaveSurfer electrode, required when the file has more than one.

        Returns
        -------
        str
            ``"voltage_clamp"``, ``"current_clamp"`` or ``"izero"``.
        """
        return WaveSurferFile(file_path=file_path, electrode_name=electrode_name).mode

    @property
    def _device_metadata_key(self) -> str | None:
        # Keyed by the amplifier type, which runs share. A Manual electrode names no amplifier.
        electrode_type = self._file.electrode["Type"]
        if electrode_type == "Manual":
            return None
        return electrode_type.lower().replace(" ", "_")

    @property
    def _electrode_metadata_key(self) -> str:
        return f"{self._run_identity}_{self._electrode_name.replace(' ', '_')}"

    @property
    def _series_metadata_key(self) -> str:
        return self._metadata_key or self._electrode_metadata_key

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = self._recording_start_datetime
        metadata["Icephys"] = {}

        device_metadata_key = self._device_metadata_key
        electrode_metadata_key = self._electrode_metadata_key
        series_metadata_key = self._series_metadata_key
        name_suffix = to_camel_case(electrode_metadata_key)

        electrode_metadata = {
            "name": f"IntracellularElectrode{name_suffix}",
            "description": f"Patch-clamp electrode '{self._electrode_name}' in WaveSurfer.",
        }
        if device_metadata_key is not None:
            electrode_type = self._file.electrode["Type"]
            metadata["Devices"] = {
                device_metadata_key: {
                    "name": electrode_type.replace(" ", ""),
                    "description": f"{electrode_type} amplifier, as set for the electrode in WaveSurfer.",
                }
            }
            electrode_metadata["device_metadata_key"] = device_metadata_key
        metadata["Icephys"]["IntracellularElectrodes"] = {electrode_metadata_key: electrode_metadata}

        response_type_name = {
            "voltage_clamp": "VoltageClampSeries",
            "current_clamp": "CurrentClampSeries",
            "izero": "IZeroClampSeries",
        }[self._mode]
        metadata["Icephys"]["PatchClampSeries"] = {
            series_metadata_key: {
                "name": f"{response_type_name}{name_suffix}",
                "description": f"Intracellular response ({self._mode}) on '{self._file.electrode['MonitorChannelName']}'.",
                "electrode_metadata_key": electrode_metadata_key,
            }
        }
        stimulus_type_name = {
            "voltage_clamp": "VoltageClampStimulusSeries",
            "current_clamp": "CurrentClampStimulusSeries",
            "izero": None,
        }[self._mode]
        if self._stimulus_channel_index is not None:
            channel_name = self._file.input_channel_names[self._stimulus_channel_index]
            metadata["Icephys"]["PatchClampStimulusSeries"] = {
                series_metadata_key: {
                    "name": f"{stimulus_type_name}{name_suffix}",
                    "description": f"Command delivered to the electrode, recorded on '{channel_name}'.",
                }
            }
        if self._reconstruct_stimulus:
            metadata["Icephys"]["PatchClampStimulusTemplateSeries"] = {
                series_metadata_key: {
                    "name": f"{stimulus_type_name}Template{name_suffix}",
                    "description": (
                        "Command the WaveSurfer stimulus library specified for "
                        f"'{self._file.electrode['CommandChannelName']}'."
                    ),
                }
            }
        return metadata

    def _get_native_times(self) -> np.ndarray:
        return self._file.get_times(
            sample_counts=self._file.sweep_sample_counts, sampling_rate=self._file.sampling_rate
        )

    def _read_input_series_data(self, channel_index: int) -> _IcephysSeriesData:
        conversion, offset, unit = self._file.get_input_channel_conversion(channel_index)
        unit_conversion = get_conversion_from_unit(unit)
        return _IcephysSeriesData(
            data=self._file.read_input_channel(channel_index),
            timestamps=self._get_native_times(),
            conversion=conversion * unit_conversion,
            offset=offset * unit_conversion,
        )

    def _get_icephys_series_data(self):
        """Map the WaveSurfer response and optional recorded stimulus into the base writer representation."""
        response_data = self._read_input_series_data(self._file.response_channel_index)
        stimulus_data = None
        if self._stimulus_channel_index is not None:
            stimulus_data = self._read_input_series_data(self._stimulus_channel_index)
        sweep_sample_ranges = self._file.get_sweep_sample_ranges(self._file.sweep_sample_counts)
        return response_data, stimulus_data, sweep_sample_ranges

    def _get_icephys_stimulus_template_data(self) -> _IcephysSeriesData | None:
        """The command rebuilt from the stimulus library, at the stimulation rate, with its own sweep ranges."""
        if not self._reconstruct_stimulus:
            return None
        command, sample_counts = self._file.calculate_command()
        return _IcephysSeriesData(
            data=command.astype("float32"),
            timestamps=self._file.get_times(
                sample_counts=sample_counts, sampling_rate=self._file.stimulation_sampling_rate
            ),
            conversion=get_conversion_from_unit(self._file.get_command_unit()),
            sweep_sample_ranges=self._file.get_sweep_sample_ranges(sample_counts),
        )

    def _get_stimulus_type(self) -> str | None:
        return self._file.protocol_name
