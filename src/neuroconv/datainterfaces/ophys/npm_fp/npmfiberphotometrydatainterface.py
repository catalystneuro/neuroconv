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


class NPMFiberPhotometryInterface(BaseTemporalAlignmentInterface):
    """
    Data Interface for converting raw fiber photometry data from Neurophotometrics (NPM) files.

    The NPM format is a raw acquisition format that stores **interleaved** channels in a single
    multi-column CSV: an isosbestic channel and one or more signal channels are multiplexed
    row-by-row, distinguished either by a ``Flags``/``LedState`` column (newer files) or by a fixed
    row-cycling order (older files). Each remaining column (e.g. ``G0``, ``Region0G``) is a region
    of interest. This interface demultiplexes the raw file in memory into per-channel streams named
    ``file{i}_chev{j}`` (isosbestic), ``file{i}_chod{j}``, and ``file{i}_chpr{j}`` (signal
    channels), where ``i`` indexes the source file and ``j`` indexes the region column, and parses
    them into the ndx-fiber-photometry format.

    Notes
    -----
    Like the CSV format, NPM recordings carry no embedded recording-start timestamp, so
    :meth:`get_metadata` does NOT populate ``NWBFile/session_start_time``. The user must supply it
    via editable metadata; the conversion fails loudly if it is missing.
    """

    keywords = ("fiber photometry",)
    display_name = "NPMFiberPhotometry"
    info = "Data Interface for converting fiber photometry data from Neurophotometrics files."
    associated_suffixes = ("csv",)

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        number_of_channels: int = 2,
        timestamp_column_name: str | None = None,
        time_unit: Literal["seconds", "milliseconds", "microseconds"] = "seconds",
        verbose: bool = False,
    ):
        """Initialize the NPMFiberPhotometryInterface.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder containing the raw NPM CSV file(s).
        number_of_channels : int, optional
            The number of interleaved channels expected in older (row-cycling) NPM files, default =
            2. For newer files this is auto-detected from the ``Flags``/``LedState`` column and this
            value is ignored.
        timestamp_column_name : str, optional
            When a file has multiple timestamp columns (e.g. both ``SystemTimestamp`` and
            ``ComputerTimestamp``), the name of the column to use. If None (default), the first
            timestamp-like column is used.
        time_unit : {"seconds", "milliseconds", "microseconds"}, optional
            The unit of the selected timestamp column for newer NPM files, default = "seconds".
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            folder_path=folder_path,
            number_of_channels=number_of_channels,
            timestamp_column_name=timestamp_column_name,
            time_unit=time_unit,
            verbose=verbose,
        )
        self._decomposed_streams = None
        # These imports assure that ndx_fiber_photometry and ndx_ophys_devices are in the global
        # namespace when a pynwb.io object is created.
        import ndx_fiber_photometry  # noqa: F401
        import ndx_ophys_devices  # noqa: F401

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the NPMFiberPhotometryInterface.

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
    # Demultiplexing (ported from GuPPy's NpmRecordingExtractor, self-contained)
    # ------------------------------------------------------------------
    def _candidate_data_paths(self) -> list[Path]:
        """Get the raw NPM data CSV paths in the folder.

        Single-column ``timestamps`` CSVs (NPM event files / CSV TTLs) and 3-column
        ``timestamps,data,sampling_rate`` CSVs (the pre-split CSV fiber photometry format) are
        excluded -- those belong to the events and CSV fiber photometry interfaces respectively.
        """
        data_paths = []
        for path in sorted(Path(self.source_data["folder_path"]).glob("*.csv")):
            columns = [str(column).lower() for column in pd.read_csv(path, nrows=0).columns]
            if len(columns) == 1:
                continue
            if len(columns) == 3 and columns == ["timestamps", "data", "sampling_rate"]:
                continue
            data_paths.append(path)
        return data_paths

    @staticmethod
    def _columns_are_numeric(dataframe: pd.DataFrame) -> bool:
        """Return True if the column labels are numeric (i.e. the file has no text header row)."""
        numeric_labels = []
        for label in dataframe.columns:
            try:
                numeric_labels.append(float(label))
            except (TypeError, ValueError):
                pass
        return len(numeric_labels) > 0

    @classmethod
    def _check_channels(cls, state: np.ndarray) -> tuple[int, np.ndarray]:
        """Count the unique interleaved channel states in an NPM ``Flags``/``LedState`` column.

        Only rows 2-11 are examined to skip potential startup artefacts (e.g. an all-LEDs-on first
        frame).
        """
        state = state.astype(int)
        unique_state = np.unique(state[2:12])
        if unique_state.shape[0] > 3:
            raise ValueError(
                f"NPM file contains {unique_state.shape[0]} unique channel states ({unique_state.tolist()}), "
                "but only 1-3 channels are supported."
            )
        return unique_state.shape[0], unique_state

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
    def _decide_indices(
        cls, file_prefix: str, dataframe: pd.DataFrame, layout: str, number_of_channels: int = 2
    ) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
        """Determine the row indices belonging to each interleaved channel.

        For older NPM layouts (``data_np``), rows are assumed to cycle through channels in order.
        For newer layouts (``data_np_v2``), the ``Flags``/``LedState`` column assigns rows to
        channels. Returns the (possibly column-reduced) DataFrame and a mapping from channel key
        (e.g. ``file0_chev``) to the array of row indices for that channel.
        """
        channel_keys = [file_prefix + "chev", file_prefix + "chod", file_prefix + "chpr"]
        if layout == "data_np":
            indices = {
                channel_keys[i]: np.arange(i, dataframe.shape[0], number_of_channels) for i in range(number_of_channels)
            }
            return dataframe, indices

        columns_lower = np.char.lower(np.array(list(dataframe.columns), dtype=str))
        if "flags" in columns_lower:
            state_column = "Flags"
        elif "ledstate" in columns_lower:
            state_column = "LedState"
        else:
            raise ValueError(
                "File type indicates a newer Neurophotometrics version but the columns do not contain a "
                f"'Flags' or 'LedState' column. Found columns: {list(dataframe.columns)}."
            )
        state = np.array(dataframe[state_column])
        number_of_channels, channel_states = cls._check_channels(state)
        indices = {}
        for i in range(number_of_channels):
            first_occurrence = np.where(state == channel_states[i])[0]
            indices[channel_keys[i]] = np.arange(first_occurrence[0], dataframe.shape[0], number_of_channels)
        dataframe = dataframe.drop(["FrameCounter", state_column], axis=1)
        return dataframe, indices

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

        number_of_channels = self.source_data["number_of_channels"]
        timestamp_column_name = self.source_data["timestamp_column_name"]
        time_unit = self.source_data["time_unit"]

        streams: dict[str, dict] = {}
        chev_names: list[str] = []
        chod_names: list[str] = []
        chpr_names: list[str] = []
        layouts: list[str] = []
        for file_index, path in enumerate(self._candidate_data_paths()):
            dataframe = pd.read_csv(path, index_col=False)
            columns_are_numeric = self._columns_are_numeric(dataframe)
            if columns_are_numeric:
                dataframe = pd.read_csv(path, header=None, index_col=False)
            columns = np.array(list(dataframe.columns), dtype=str)

            # Determine the file layout (older row-cycling vs newer Flags/LedState; event vs data).
            if len(columns) == 2:
                layout = "event_or_data_np"
            else:
                layout = "data_np"
            if (not columns_are_numeric) and (
                "flags" in np.char.lower(columns) or "ledstate" in np.char.lower(columns)
            ):
                layout = layout + "_v2"
            if layout == "event_or_data_np":
                second_column = list(dataframe.iloc[:, 1])
                all_float = all(isinstance(value, float) for value in second_column)
                layout = "data_np" if (all_float and columns_are_numeric) else "event_np"
            layouts.append(layout)

            # Event files (2-column with a non-numeric type label) are handled by NPMEventsInterface.
            if layout == "event_np":
                continue

            file_prefix = f"file{file_index}_"
            if layout == "data_np":
                dataframe, indices = self._decide_indices(file_prefix, dataframe, layout, number_of_channels)
            else:
                dataframe = self._update_dataframe_with_timestamp_column(dataframe, timestamp_column_name)
                dataframe, indices = self._decide_indices(file_prefix, dataframe, layout)

            for channel_key, row_indices in indices.items():
                timestamps = np.asarray(dataframe.iloc[:, 0].to_numpy()[row_indices], dtype=float)
                for column_index in range(1, dataframe.shape[1]):
                    stream_name = channel_key + str(column_index)
                    streams[stream_name] = {
                        "timestamps": timestamps,
                        "data": np.asarray(dataframe.iloc[:, column_index].to_numpy()[row_indices], dtype=float),
                    }
                    self._register_channel_name(stream_name, channel_key, chev_names, chod_names, chpr_names)

        # Normalize timestamps relative to the chev reference and compute per-channel sampling rates.
        if "data_np_v2" in layouts:
            divisor = {"seconds": 1.0, "milliseconds": 1e3, "microseconds": 1e6}[time_unit]
        elif "data_np" in layouts:
            divisor = 1000.0
        else:
            divisor = None

        if divisor is not None:
            region_lengths = {len(names) for names in (chev_names, chod_names, chpr_names) if len(names) > 0}
            if len(region_lengths) > 1:
                raise ValueError(
                    "Number of channel files must be the same for all regions. Found per-region counts: "
                    f"chev={len(chev_names)}, chod={len(chod_names)}, chpr={len(chpr_names)}."
                )
            # Each chev channel is normalized to its own first raw timestamp; the paired chod/chpr
            # channels borrow chev's normalized timestamps and sampling rate. Interleaving can leave
            # a chod/chpr channel one sample longer than its chev, so the borrowing channels' data is
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
