from copy import deepcopy
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import DirectoryPath, validate_call
from pynwb.file import NWBFile

from neuroconv.basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from neuroconv.tools.fiber_photometry import add_ophys_device, add_ophys_device_model
from neuroconv.utils import DeepDict

_TIME_UNIT_TO_DIVISOR = {"seconds": 1.0, "milliseconds": 1e3, "microseconds": 1e6}


class BaseNPMFiberPhotometryInterface(BaseTemporalAlignmentInterface):
    """Shared machinery for the Neurophotometrics (NPM) fiber photometry interfaces.

    NPM is a raw acquisition format that stores **interleaved** channels in a single multi-column
    CSV: an isosbestic channel and one or more signal channels are multiplexed frame-by-frame, and
    each remaining column (e.g. ``G0``, ``Region0G``) is a region of interest. Concrete subclasses
    differ only in how files are discovered and how rows are assigned to channels (the two hooks
    :meth:`_npm_data_file_paths` and :meth:`_read_and_demultiplex`); everything downstream -- the
    in-memory demultiplexing into per-channel streams named ``file{i}_chev{j}`` (isosbestic) and
    ``file{i}_chod{j}``/``file{i}_chpr{j}`` (signal channels), the temporal-alignment surface, and
    the ndx-fiber-photometry assembly -- is shared here.

    Notes
    -----
    Like the CSV format, NPM recordings carry no embedded recording-start timestamp, so
    :meth:`get_metadata` does NOT populate ``NWBFile/session_start_time``. The user must supply it
    via editable metadata; the conversion fails loudly if it is missing.
    """

    keywords = ("fiber photometry",)
    associated_suffixes = ("csv",)

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the interface.

        ``NWBFile/session_start_time`` is intentionally left unset: NPM recordings carry no embedded
        recording-start timestamp, so it must be supplied by the user via editable metadata.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()
        return metadata

    # ------------------------------------------------------------------
    # Hooks implemented by the concrete (modern / legacy) subclasses
    # ------------------------------------------------------------------
    def _npm_data_file_paths(self) -> list[Path]:
        """Get the NPM photometry CSV paths in the folder."""
        raise NotImplementedError("Subclasses must implement _npm_data_file_paths.")

    def _read_and_demultiplex(self, path: Path, file_index: int) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
        """Read one raw NPM file and assign its rows to interleaved channels.

        Returns the dataframe reduced to ``[timestamp, region columns...]`` and a mapping from
        channel key (e.g. ``file0_chev``) to the row indices belonging to that channel.
        """
        raise NotImplementedError("Subclasses must implement _read_and_demultiplex.")

    # ------------------------------------------------------------------
    # Shared demultiplexing
    # ------------------------------------------------------------------
    @staticmethod
    def _register_channel_name(
        stream_name: str, channel_key: str, chev_names: list[str], chod_names: list[str], chpr_names: list[str]
    ) -> None:
        """Append ``stream_name`` to the creation-order list for its channel region."""
        if "chev" in channel_key:
            chev_names.append(stream_name)
        elif "chod" in channel_key:
            chod_names.append(stream_name)
        elif "chpr" in channel_key:
            chpr_names.append(stream_name)

    def _decompose(self) -> dict[str, dict]:
        """Demultiplex the raw NPM file(s) into per-channel streams (cached on the instance).

        Returns
        -------
        dict
            Maps stream name to a dict with keys ``timestamps``, ``data``, and ``rate``. Timestamps
            are normalized to start at zero (each ``chev`` channel to its own first timestamp; the
            paired ``chod``/``chpr`` channels borrow their ``chev``'s timestamps and rate).
        """
        if self._decomposed_streams is not None:
            return self._decomposed_streams

        divisor = _TIME_UNIT_TO_DIVISOR[self.source_data["time_unit"]]
        streams: dict[str, dict] = {}
        chev_names: list[str] = []
        chod_names: list[str] = []
        chpr_names: list[str] = []
        for file_index, path in enumerate(self._npm_data_file_paths()):
            dataframe, indices = self._read_and_demultiplex(path, file_index)
            for channel_key, row_indices in indices.items():
                timestamps = np.asarray(dataframe.iloc[:, 0].to_numpy()[row_indices], dtype=float)
                for column_index in range(1, dataframe.shape[1]):
                    stream_name = channel_key + str(column_index)
                    streams[stream_name] = {
                        "timestamps": timestamps,
                        "data": np.asarray(dataframe.iloc[:, column_index].to_numpy()[row_indices], dtype=float),
                    }
                    self._register_channel_name(stream_name, channel_key, chev_names, chod_names, chpr_names)

        region_lengths = {len(names) for names in (chev_names, chod_names, chpr_names) if len(names) > 0}
        if len(region_lengths) > 1:
            raise ValueError(
                "Number of channel files must be the same for all regions. Found per-region counts: "
                f"chev={len(chev_names)}, chod={len(chod_names)}, chpr={len(chpr_names)}."
            )
        # Each chev channel is normalized to its own first raw timestamp; the paired chod/chpr
        # channels borrow chev's normalized timestamps and sampling rate. Interleaving can leave a
        # chod/chpr channel one sample longer than its chev, so the borrowing channels' data is
        # truncated to the chev length to keep every stream's data and timestamps the same size.
        for channel_index in range(len(chev_names)):
            chev_stream = streams[chev_names[channel_index]]
            chev_timestamps = (chev_stream["timestamps"] - chev_stream["timestamps"][0]) / divisor
            sampling_rate = chev_timestamps.shape[0] / (chev_timestamps[-1] - chev_timestamps[0])
            number_of_samples = chev_timestamps.shape[0]
            chev_stream["timestamps"] = chev_timestamps
            chev_stream["data"] = chev_stream["data"][:number_of_samples]
            chev_stream["rate"] = sampling_rate
            for borrowing_names in (chod_names, chpr_names):
                if channel_index < len(borrowing_names):
                    borrowing_stream = streams[borrowing_names[channel_index]]
                    borrowing_stream["timestamps"] = chev_timestamps
                    borrowing_stream["data"] = borrowing_stream["data"][:number_of_samples]
                    borrowing_stream["rate"] = sampling_rate

        self._decomposed_streams = streams
        return streams

    def _get_stream_names(self) -> list[str]:
        """Get the names of the demultiplexed per-channel data streams."""
        return list(self._decompose().keys())

    def _read_stream(self, stream_name: str, stub_test: bool = False) -> dict:
        """Read a single demultiplexed data stream.

        Parameters
        ----------
        stream_name : str
            The name of the stream to read.
        stub_test : bool, optional
            If True, read only the first ~1 second of samples, default = False.

        Returns
        -------
        dict
            Dictionary with keys ``data``, ``timestamps``, and ``rate``.
        """
        stream = self._decompose()[stream_name]
        rate = float(stream["rate"])
        data = stream["data"]
        timestamps = stream["timestamps"]
        if stub_test:
            number_of_samples = int(np.ceil(rate))
            data = data[:number_of_samples]
            timestamps = timestamps[:number_of_samples]
        return dict(data=data, timestamps=timestamps, rate=rate)

    def get_original_timestamps(self) -> dict[str, np.ndarray]:
        """
        Get the original timestamps for the data.

        Returns
        -------
        dict[str, np.ndarray]
            Dictionary of stream names to timestamps.
        """
        return {stream_name: self._read_stream(stream_name)["timestamps"] for stream_name in self._get_stream_names()}

    def get_timestamps(self) -> dict[str, np.ndarray]:
        """
        Get the timestamps for the data.

        Returns
        -------
        dict[str, np.ndarray]
            Dictionary of stream names to timestamps.
        """
        stream_name_to_timestamps = getattr(self, "stream_name_to_timestamps", None)
        if stream_name_to_timestamps is None:
            stream_name_to_timestamps = self.get_original_timestamps()
        return stream_name_to_timestamps

    def set_aligned_timestamps(self, stream_name_to_aligned_timestamps: dict[str, np.ndarray]) -> None:
        """
        Set the aligned timestamps for the data.

        Parameters
        ----------
        stream_name_to_aligned_timestamps : dict[str, np.ndarray]
            Dictionary of stream names to aligned timestamps.
        """
        self.stream_name_to_timestamps = stream_name_to_aligned_timestamps

    def set_aligned_starting_time(self, aligned_starting_time: float) -> None:
        """
        Set the aligned starting time and adjust the timestamps appropriately.

        Parameters
        ----------
        aligned_starting_time : float
            The aligned starting time.
        """
        stream_name_to_timestamps = self.get_timestamps()
        aligned_stream_name_to_timestamps = {
            name: timestamps + aligned_starting_time for name, timestamps in stream_name_to_timestamps.items()
        }
        self.set_aligned_timestamps(aligned_stream_name_to_timestamps)

    def get_original_starting_time_and_rate(self) -> dict[str, tuple[float, float]]:
        """
        Get the original starting time and rate for the data.

        Returns
        -------
        dict[str, tuple[float, float]]
            Dictionary of stream names to (starting_time, rate).
        """
        stream_name_to_starting_time_and_rate = {}
        for stream_name in self._get_stream_names():
            stream = self._read_stream(stream_name, stub_test=True)
            stream_name_to_starting_time_and_rate[stream_name] = (float(stream["timestamps"][0]), stream["rate"])
        return stream_name_to_starting_time_and_rate

    def get_starting_time_and_rate(self) -> dict[str, tuple[float, float]]:
        """
        Get the starting time and rate for the data.

        Returns
        -------
        dict[str, tuple[float, float]]
            Dictionary of stream names to (starting_time, rate).
        """
        stream_name_to_starting_time_and_rate = getattr(self, "stream_name_to_starting_time_and_rate", None)
        if stream_name_to_starting_time_and_rate is None:
            stream_name_to_starting_time_and_rate = self.get_original_starting_time_and_rate()
        return stream_name_to_starting_time_and_rate

    def set_aligned_starting_time_and_rate(
        self, stream_name_to_aligned_starting_time_and_rate: dict[str, tuple[float, float]]
    ) -> None:
        """
        Set the aligned starting time and rate for the data.

        Parameters
        ----------
        stream_name_to_aligned_starting_time_and_rate : dict[str, tuple[float, float]]
            Dictionary of stream names to aligned (starting_time, rate).
        """
        self.stream_name_to_starting_time_and_rate = stream_name_to_aligned_starting_time_and_rate

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        *,
        stub_test: bool = False,
        timing_source: Literal["original", "aligned_timestamps", "aligned_starting_time_and_rate"] = "original",
    ):
        """
        Add the data to an NWBFile.

        Parameters
        ----------
        nwbfile : pynwb.NWBFile
            The in-memory object to add the data to.
        metadata : dict
            Metadata dictionary with information used to create the NWBFile.
        stub_test : bool, optional
            If True, only add a subset of the data (1s) to the NWBFile for testing purposes, default = False.
        timing_source : Literal["original", "aligned_timestamps", "aligned_starting_time_and_rate"], optional
            Source of timing information for the data, default = "original".
        """
        from ndx_fiber_photometry import (
            FiberPhotometry,
            FiberPhotometryIndicators,
            FiberPhotometryResponseSeries,
            FiberPhotometryTable,
            FiberPhotometryViruses,
            FiberPhotometryVirusInjections,
        )
        from ndx_ophys_devices import (
            FiberInsertion,
            Indicator,
            OpticalFiber,
            ViralVector,
            ViralVectorInjection,
        )

        # timing_source is used to determine whether to use the aligned timestamps or starting time and rate.
        if timing_source == "aligned_timestamps":
            stream_name_to_timestamps = self.get_timestamps()
        elif timing_source == "aligned_starting_time_and_rate":
            stream_name_to_starting_time_and_rate = self.get_starting_time_and_rate()
        else:
            assert (
                timing_source == "original"
            ), "timing_source must be one of 'original', 'aligned_timestamps', or 'aligned_starting_time_and_rate'."

        # Add Devices
        device_model_types = [
            "OpticalFiberModel",
            "ExcitationSourceModel",
            "PhotodetectorModel",
            "BandOpticalFilterModel",
            "EdgeOpticalFilterModel",
            "DichroicMirrorModel",
        ]
        for device_type in device_model_types:
            device_models_metadata = metadata["Ophys"]["FiberPhotometry"].get(device_type + "s", [])
            for devices_metadata in device_models_metadata:
                add_ophys_device_model(
                    nwbfile=nwbfile,
                    device_metadata=devices_metadata,
                    device_type=device_type,
                )
        device_types = [
            "ExcitationSource",
            "Photodetector",
            "BandOpticalFilter",
            "EdgeOpticalFilter",
            "DichroicMirror",
        ]
        for device_type in device_types:
            devices_metadata = metadata["Ophys"]["FiberPhotometry"].get(device_type + "s", [])
            for device_metadata in devices_metadata:
                add_ophys_device(
                    nwbfile=nwbfile,
                    device_metadata=device_metadata,
                    device_type=device_type,
                )
        # Add Optical Fibers (special case bc they have additional FiberInsertion objects)
        optical_fibers_metadata = metadata["Ophys"]["FiberPhotometry"].get("OpticalFibers", [])
        for optical_fiber_metadata in optical_fibers_metadata:
            fiber_insertion_metadata = optical_fiber_metadata["fiber_insertion"]
            fiber_insertion = FiberInsertion(**fiber_insertion_metadata)
            optical_fiber_metadata = deepcopy(optical_fiber_metadata)
            optical_fiber_metadata["fiber_insertion"] = fiber_insertion
            assert (
                optical_fiber_metadata["model"] in nwbfile.device_models
            ), f"Device model {optical_fiber_metadata['model']} not found in NWBFile device_models for {optical_fiber_metadata['name']}."
            optical_fiber_metadata["model"] = nwbfile.device_models[optical_fiber_metadata["model"]]
            optical_fiber = OpticalFiber(**optical_fiber_metadata)
            nwbfile.add_device(optical_fiber)

        # Add Viral Vectors, Injections, and Indicators
        viral_vectors_metadata = metadata["Ophys"]["FiberPhotometry"].get("FiberPhotometryViruses", [])
        name_to_viral_vector = {}
        for viral_vector_metadata in viral_vectors_metadata:
            viral_vector = ViralVector(**viral_vector_metadata)
            name_to_viral_vector[viral_vector.name] = viral_vector
        if len(name_to_viral_vector) > 0:
            viruses = FiberPhotometryViruses(viral_vectors=list(name_to_viral_vector.values()))
        else:
            viruses = None

        viral_vector_injections_metadata = metadata["Ophys"]["FiberPhotometry"].get(
            "FiberPhotometryVirusInjections", []
        )
        name_to_viral_vector_injection = {}
        for viral_vector_injection_metadata in viral_vector_injections_metadata:
            viral_vector = name_to_viral_vector[viral_vector_injection_metadata["viral_vector"]]
            viral_vector_injection_metadata = deepcopy(viral_vector_injection_metadata)
            viral_vector_injection_metadata["viral_vector"] = viral_vector
            viral_vector_injection = ViralVectorInjection(**viral_vector_injection_metadata)
            name_to_viral_vector_injection[viral_vector_injection.name] = viral_vector_injection
        if len(name_to_viral_vector_injection) > 0:
            virus_injections = FiberPhotometryVirusInjections(
                viral_vector_injections=list(name_to_viral_vector_injection.values())
            )
        else:
            virus_injections = None

        indicators_metadata = metadata["Ophys"]["FiberPhotometry"].get("FiberPhotometryIndicators", [])
        name_to_indicator = {}
        for indicator_metadata in indicators_metadata:
            if "viral_vector_injection" in indicator_metadata:
                viral_vector_injection = name_to_viral_vector_injection[indicator_metadata["viral_vector_injection"]]
                indicator_metadata = deepcopy(indicator_metadata)
                indicator_metadata["viral_vector_injection"] = viral_vector_injection
            indicator = Indicator(**indicator_metadata)
            name_to_indicator[indicator.name] = indicator
        if len(name_to_indicator) > 0:
            indicators = FiberPhotometryIndicators(indicators=list(name_to_indicator.values()))
        else:
            raise ValueError("At least one indicator must be specified in the metadata.")

        # Fiber Photometry Table
        fiber_photometry_table = FiberPhotometryTable(
            name=metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryTable"]["name"],
            description=metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryTable"]["description"],
        )
        required_fields = [
            "location",
            "excitation_wavelength_in_nm",
            "emission_wavelength_in_nm",
            "indicator",
            "optical_fiber",
            "excitation_source",
            "photodetector",
        ]
        device_fields = [
            "optical_fiber",
            "excitation_source",
            "photodetector",
            "dichroic_mirror",
            "excitation_filter",
            "emission_filter",
        ]
        for row_metadata in metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryTable"]["rows"]:
            for field in required_fields:
                assert (
                    field in row_metadata
                ), f"FiberPhotometryTable metadata row {row_metadata['name']} is missing required field {field}."
            row_data = {field: nwbfile.devices[row_metadata[field]] for field in device_fields if field in row_metadata}
            row_data["location"] = row_metadata["location"]
            row_data["excitation_wavelength_in_nm"] = row_metadata["excitation_wavelength_in_nm"]
            row_data["emission_wavelength_in_nm"] = row_metadata["emission_wavelength_in_nm"]
            if "indicator" in row_metadata:
                row_data["indicator"] = name_to_indicator[row_metadata["indicator"]]
            if "coordinates" in row_metadata:
                row_data["coordinates"] = row_metadata["coordinates"]
            fiber_photometry_table.add_row(**row_data)
        fiber_photometry_table_metadata = FiberPhotometry(
            name="fiber_photometry",
            fiber_photometry_table=fiber_photometry_table,
            fiber_photometry_viruses=viruses,
            fiber_photometry_virus_injections=virus_injections,
            fiber_photometry_indicators=indicators,
        )
        nwbfile.add_lab_meta_data(fiber_photometry_table_metadata)

        # Fiber Photometry Response Series
        all_series_metadata = metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryResponseSeries"]
        for fiber_photometry_response_series_metadata in all_series_metadata:
            stream_name = fiber_photometry_response_series_metadata["stream_name"]
            stream = self._read_stream(stream_name, stub_test=stub_test)
            data = stream["data"]

            # Get the timing information
            if timing_source == "aligned_timestamps":
                timestamps = stream_name_to_timestamps[stream_name][: len(data)]
                timing_kwargs = dict(timestamps=timestamps)
            elif timing_source == "aligned_starting_time_and_rate":
                starting_time, rate = stream_name_to_starting_time_and_rate[stream_name]
                timing_kwargs = dict(starting_time=starting_time, rate=rate)
            else:
                timing_kwargs = dict(starting_time=float(stream["timestamps"][0]), rate=stream["rate"])

            fiber_photometry_table_region = fiber_photometry_table.create_fiber_photometry_table_region(
                description=fiber_photometry_response_series_metadata["fiber_photometry_table_region_description"],
                region=fiber_photometry_response_series_metadata["fiber_photometry_table_region"],
            )

            fiber_photometry_response_series = FiberPhotometryResponseSeries(
                name=fiber_photometry_response_series_metadata["name"],
                description=fiber_photometry_response_series_metadata["description"],
                data=data,
                unit=fiber_photometry_response_series_metadata["unit"],
                fiber_photometry_table_region=fiber_photometry_table_region,
                **timing_kwargs,
            )
            nwbfile.add_acquisition(fiber_photometry_response_series)


class NPMFiberPhotometryInterface(BaseNPMFiberPhotometryInterface):
    """
    Data Interface for converting raw fiber photometry data from modern Neurophotometrics (NPM) files.

    The modern NPM format is a header-bearing CSV whose channel multiplexing is driven by a
    ``LedState``/``Flags`` column: each row belongs to whichever excitation LED was on, and the
    interface uses that column to demultiplex the interleaved channels across the region columns
    (e.g. ``G0``, ``Region0G``). Files are positively identified by the presence of that column.

    For the older header-less NPM format (rows interleaved by a fixed cycling order, no
    ``LedState``/``Flags`` column), use ``NPMLegacyFiberPhotometryInterface`` instead.
    """

    display_name = "NPMFiberPhotometry"
    info = "Data Interface for converting fiber photometry data from modern Neurophotometrics files."

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        timestamp_column_name: str | None = None,
        time_unit: Literal["seconds", "milliseconds", "microseconds"] = "seconds",
        verbose: bool = False,
    ):
        """Initialize the NPMFiberPhotometryInterface.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder containing the raw NPM CSV file(s).
        timestamp_column_name : str, optional
            When a file has multiple timestamp columns (e.g. both ``SystemTimestamp`` and
            ``ComputerTimestamp``), the name of the column to use. If None (default), the first
            timestamp-like column is used.
        time_unit : {"seconds", "milliseconds", "microseconds"}, optional
            The unit of the selected timestamp column, default = "seconds".
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            folder_path=folder_path,
            timestamp_column_name=timestamp_column_name,
            time_unit=time_unit,
            verbose=verbose,
        )
        self._decomposed_streams = None
        # These imports assure that ndx_fiber_photometry and ndx_ophys_devices are in the global
        # namespace when a pynwb.io object is created.
        import ndx_fiber_photometry  # noqa: F401
        import ndx_ophys_devices  # noqa: F401

    def _npm_data_file_paths(self) -> list[Path]:
        """Get the modern NPM photometry CSV paths in the folder.

        A modern NPM photometry file is positively identified by a ``LedState`` or ``Flags`` column
        -- the channel-state column that drives the interleaving and is the defining structural
        feature of the format. Event CSVs and pre-split CSV-format streams do not have it.
        """
        data_paths = []
        for path in sorted(Path(self.source_data["folder_path"]).glob("*.csv")):
            columns = [str(column).lower() for column in pd.read_csv(path, nrows=0).columns]
            if "ledstate" in columns or "flags" in columns:
                data_paths.append(path)
        return data_paths

    def _read_and_demultiplex(self, path: Path, file_index: int) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
        dataframe = pd.read_csv(path, index_col=False)
        dataframe = self._update_dataframe_with_timestamp_column(dataframe, self.source_data["timestamp_column_name"])
        return self._decide_indices(f"file{file_index}_", dataframe)

    @staticmethod
    def _update_dataframe_with_timestamp_column(
        dataframe: pd.DataFrame, timestamp_column_name: str | None
    ) -> pd.DataFrame:
        """Collapse multiple timestamp columns down to a single ``Timestamp`` column.

        If the file has at most one timestamp-like column, it is returned unchanged. Otherwise the
        selected column (``timestamp_column_name``, or the first timestamp-like column if None) is
        kept as ``Timestamp`` at position 1 and the other timestamp columns are dropped.
        """
        timestamp_columns = [column for column in dataframe.columns if "timestamp" in str(column).lower()]
        if len(timestamp_columns) <= 1:
            return dataframe
        selected_column = timestamp_column_name if timestamp_column_name is not None else timestamp_columns[0]
        if selected_column not in timestamp_columns:
            raise ValueError(
                f"Provided timestamp_column_name '{selected_column}' not found in timestamp columns {timestamp_columns}."
            )
        selected_values = dataframe[selected_column].to_numpy()
        dataframe = dataframe.drop(columns=timestamp_columns)
        dataframe.insert(1, "Timestamp", selected_values)
        return dataframe

    @classmethod
    def _decide_indices(cls, file_prefix: str, dataframe: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
        """Assign rows to interleaved channels using the ``Flags``/``LedState`` column.

        Returns the dataframe reduced to ``[Timestamp, region columns...]`` (the ``FrameCounter`` and
        state columns dropped) and a mapping from channel key to that channel's row indices.
        """
        channel_keys = [file_prefix + "chev", file_prefix + "chod", file_prefix + "chpr"]
        columns_lower = np.char.lower(np.array(list(dataframe.columns), dtype=str))
        if "flags" in columns_lower:
            state_column = "Flags"
        elif "ledstate" in columns_lower:
            state_column = "LedState"
        else:
            raise ValueError(
                "Modern NPM files must contain a 'Flags' or 'LedState' column. "
                f"Found columns: {list(dataframe.columns)}."
            )
        state = np.array(dataframe[state_column])
        number_of_channels, channel_states = cls._check_channels(state)
        indices = {}
        for i in range(number_of_channels):
            first_occurrence = np.where(state == channel_states[i])[0]
            indices[channel_keys[i]] = np.arange(first_occurrence[0], dataframe.shape[0], number_of_channels)
        dataframe = dataframe.drop(["FrameCounter", state_column], axis=1)
        return dataframe, indices

    @classmethod
    def _check_channels(cls, state: np.ndarray) -> tuple[int, np.ndarray]:
        """Identify the distinct interleaved channel states in the ``Flags``/``LedState`` column.

        The number of channels is the number of distinct steady-state values. Only rows 2-11 are
        examined so a startup/calibration frame (an all-LEDs-on first frame, e.g. ``LedState`` 7 or
        ``Flags`` 16) does not register as an extra channel.

        NPM recordings are limited here to 1-3 channels. This is inherited from GuPPy, which names the
        interleaved channels ``chev``/``chod``/``chpr`` -- three names for the (at most three)
        excitation LEDs of current Neurophotometrics systems (415 nm isosbestic + up to two signal
        colors). There is no fundamental reason for the cap; if you have a recording with more than
        three channels, please open an issue on NeuroConv and we can generalize the naming.
        """
        state = state.astype(int)
        unique_state = np.unique(state[2:12])
        if unique_state.shape[0] > 3:
            raise ValueError(
                f"NPM file contains {unique_state.shape[0]} unique channel states ({unique_state.tolist()}), "
                "but only 1-3 channels are currently supported (a GuPPy-inherited limit -- the chev/chod/chpr "
                "channel names). If you need more channels, please open an issue: "
                "https://github.com/catalystneuro/neuroconv/issues."
            )
        return unique_state.shape[0], unique_state


class NPMLegacyFiberPhotometryInterface(BaseNPMFiberPhotometryInterface):
    """
    Data Interface for converting raw fiber photometry data from legacy Neurophotometrics (NPM) files.

    The legacy NPM format is a header-less CSV: the first column is the timestamp and the remaining
    columns are region-of-interest values, with the interleaved channels stored in a fixed
    row-cycling order (row ``i`` belongs to channel ``i % number_of_channels``). Because the file
    has no header, there is no ``LedState``/``Flags`` column to key on; the user specifies how many
    channels were interleaved via ``number_of_channels``.

    For the modern header-bearing NPM format (with a ``LedState``/``Flags`` column), use
    ``NPMFiberPhotometryInterface`` instead.
    """

    display_name = "NPMLegacyFiberPhotometry"
    info = "Data Interface for converting fiber photometry data from legacy (header-less) Neurophotometrics files."

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        number_of_channels: int,
        time_unit: Literal["seconds", "milliseconds", "microseconds"],
        verbose: bool = False,
    ):
        """Initialize the NPMLegacyFiberPhotometryInterface.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder containing the raw legacy NPM CSV file(s).
        number_of_channels : int
            The number of interleaved channels (rows cycle through the channels in order). Required:
            the header-less legacy format carries no channel-state column to infer it from. Limited
            to 1-3, the GuPPy-inherited chev/chod/chpr channel names (see
            ``NPMFiberPhotometryInterface._check_channels``).
        time_unit : {"seconds", "milliseconds", "microseconds"}
            The unit of the (first-column) timestamps. Required: the header-less legacy format gives
            no way to infer it (legacy NPM timestamps are typically in milliseconds).
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        if not 1 <= number_of_channels <= 3:
            raise ValueError(
                f"number_of_channels must be 1-3, got {number_of_channels} (a GuPPy-inherited limit -- the "
                "chev/chod/chpr channel names). If you need more channels, please open an issue: "
                "https://github.com/catalystneuro/neuroconv/issues."
            )
        super().__init__(
            folder_path=folder_path,
            number_of_channels=number_of_channels,
            time_unit=time_unit,
            verbose=verbose,
        )
        self._decomposed_streams = None
        # These imports assure that ndx_fiber_photometry and ndx_ophys_devices are in the global
        # namespace when a pynwb.io object is created.
        import ndx_fiber_photometry  # noqa: F401
        import ndx_ophys_devices  # noqa: F401

    def _npm_data_file_paths(self) -> list[Path]:
        """Get the legacy NPM photometry CSV paths in the folder.

        A legacy NPM photometry file is a header-less, all-numeric CSV with more than two columns (a
        timestamp column plus two or more interleaved region columns). Header-bearing files (the
        modern NPM format), single-/two-column event files, and three-column CSV-format streams are
        therefore not picked up here.
        """
        data_paths = []
        for path in sorted(Path(self.source_data["folder_path"]).glob("*.csv")):
            first_row = pd.read_csv(path, header=None, nrows=1)
            if first_row.shape[1] <= 2:
                continue
            if pd.to_numeric(first_row.iloc[0], errors="coerce").notna().all():
                data_paths.append(path)
        return data_paths

    def _read_and_demultiplex(self, path: Path, file_index: int) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
        dataframe = pd.read_csv(path, header=None)
        number_of_channels = self.source_data["number_of_channels"]
        channel_keys = [f"file{file_index}_chev", f"file{file_index}_chod", f"file{file_index}_chpr"]
        indices = {
            channel_keys[i]: np.arange(i, dataframe.shape[0], number_of_channels) for i in range(number_of_channels)
        }
        return dataframe, indices
