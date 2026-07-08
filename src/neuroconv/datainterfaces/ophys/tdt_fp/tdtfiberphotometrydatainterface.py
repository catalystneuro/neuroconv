import os
import warnings
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
from typing import Literal

import numpy as np
from pydantic import DirectoryPath, validate_call
from pynwb.file import NWBFile

from neuroconv.basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from neuroconv.tools import get_package
from neuroconv.tools.fiber_photometry import add_ophys_device, add_ophys_device_model
from neuroconv.utils import DeepDict

from ._tdt_mixin import TDTLoadMixin
from ..basefiberphotometryinterface import BaseFiberPhotometryInterface


class _TDTFiberPhotometryInterfaceMultiStream(TDTLoadMixin, BaseTemporalAlignmentInterface):
    """
    Data Interface for converting fiber photometry data from a TDT output folder.

    The output folder from TDT consists of a variety of TDT-specific file types (e.g. Tbk, Tdx, tev, tin, tsq).
    This data is read by the tdt.read_block function, and then parsed into the ndx-fiber-photometry format.
    """

    keywords = ("fiber photometry",)
    display_name = "TDTFiberPhotometry"
    info = "Data Interface for converting fiber photometry data from TDT files."
    associated_suffixes = ("Tbk", "Tdx", "tev", "tin", "tsq")

    @validate_call
    def __init__(
        self, folder_path: DirectoryPath, *args, verbose: bool = False
    ):  # TODO: change to * (keyword only) on or after August 2026
        """Initialize the TDTFiberPhotometryInterface.

        Parameters
        ----------
        folder_path : FilePath
            The path to the folder containing the TDT data.
        verbose : bool, optional
            Whether to print status messages, default = True.
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "verbose",
            ]
            num_positional_args_before_args = 1  # folder_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to TDTFiberPhotometryInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            verbose = positional_values.get("verbose", verbose)

        super().__init__(
            folder_path=folder_path,
            verbose=verbose,
        )
        # This module should be here so ndx_fiber_photometry is in the global namespace when an pynwb.io object is created
        import ndx_fiber_photometry  # noqa: F401
        import ndx_ophys_devices  # noqa: F401

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the TDTFiberPhotometryInterface.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()
        tdt_photometry = self.load(evtype=["scalars"])  # This evtype quickly loads info without loading all the data.
        start_timestamp = tdt_photometry.info.start_date.timestamp()
        session_start_datetime = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
        metadata["NWBFile"]["session_start_time"] = session_start_datetime.isoformat()
        return metadata

    def get_metadata_schema(self) -> dict:
        """
        Get the metadata schema for the TDTFiberPhotometryInterface.

        Returns
        -------
        dict
            The metadata schema for this interface.
        """
        metadata_schema = super().get_metadata_schema()
        return metadata_schema

    def get_original_timestamps(self, t1: float = 0.0, t2: float = 0.0) -> dict[str, np.ndarray]:
        """
        Get the original timestamps for the data.

        Parameters
        ----------
        t1 : float, optional
            Retrieve data starting at t1 (in seconds), default = 0 for start of recording.
        t2 : float, optional
            Retrieve data ending at t2 (in seconds), default = 0 for end of recording.

        Returns
        -------
        dict[str, np.ndarray]
            Dictionary of stream names to timestamps.
        """
        tdt_photometry = self.load(t1=t1, t2=t2)
        stream_name_to_timestamps = {}
        for stream_name in tdt_photometry.streams.keys():
            rate = tdt_photometry.streams[stream_name].fs
            starting_time = 0.0
            timestamps = np.arange(starting_time, tdt_photometry.streams[stream_name].data.shape[-1] / rate, 1 / rate)
            stream_name_to_timestamps[stream_name] = timestamps
        return stream_name_to_timestamps

    def get_timestamps(self, t1: float = 0.0, t2: float = 0.0) -> dict[str, np.ndarray]:
        """
        Get the timestamps for the data.

        Parameters
        ----------
        t1 : float, optional
            Retrieve data starting at t1 (in seconds), default = 0 for start of recording.
        t2 : float, optional
            Retrieve data ending at t2 (in seconds), default = 0 for end of recording.

        Returns
        -------
        dict[str, np.ndarray]
            Dictionary of stream names to timestamps.
        """
        stream_to_timestamps = getattr(self, "stream_name_to_timestamps", None)
        if (
            stream_to_timestamps is None
        ):  # Can't use getattr default bc it will call get_original_timestamps even if stream_name_to_timestamps is set
            stream_to_timestamps = self.get_original_timestamps(t1=t1, t2=t2)
        stream_to_timestamps = {name: timestamps[timestamps >= t1] for name, timestamps in stream_to_timestamps.items()}
        if t2 == 0.0:
            return stream_to_timestamps
        stream_to_timestamps = {name: timestamps[timestamps <= t2] for name, timestamps in stream_to_timestamps.items()}
        return stream_to_timestamps

    def set_aligned_timestamps(self, stream_name_to_aligned_timestamps: dict[str, np.ndarray]) -> None:
        """
        Set the aligned timestamps for the data.

        Parameters
        ----------
        stream_name_to_aligned_timestamps : dict[str, np.ndarray]
            Dictionary of stream names to aligned timestamps.
        """
        self.stream_name_to_timestamps = stream_name_to_aligned_timestamps

    def set_aligned_starting_time(self, aligned_starting_time: float, t1: float = 0.0, t2: float = 0.0) -> None:
        """
        Set the aligned starting time and adjust the timestamps appropriately.

        Parameters
        ----------
        aligned_starting_time : float
            The aligned starting time.
        t1 : float, optional
            Retrieve data starting at t1 (in seconds), default = 0 for start of recording.
        t2 : float, optional
            Retrieve data ending at t2 (in seconds), default = 0 for end of recording.
        """
        stream_name_to_timestamps = self.get_timestamps(t1=t1, t2=t2)
        aligned_stream_name_to_timestamps = {
            name: timestamps + aligned_starting_time for name, timestamps in stream_name_to_timestamps.items()
        }
        self.set_aligned_timestamps(aligned_stream_name_to_timestamps)

    def get_original_starting_time_and_rate(self, t1: float = 0.0, t2: float = 0.0) -> dict[str, tuple[float, float]]:
        """
        Get the original starting time and rate for the data.

        Parameters
        ----------
        t1 : float, optional
            Retrieve data starting at t1 (in seconds), default = 0 for start of recording.
        t2 : float, optional
            Retrieve data ending at t2 (in seconds), default = 0 for end of recording.

        Returns
        -------
        dict[str, tuple[float, float]]
            Dictionary of stream names to starting time and rate.
        """
        tdt_photometry = self.load(t1=t1, t2=t2)
        stream_name_to_starting_time_and_rate = {}
        for stream_name in tdt_photometry.streams.keys():
            rate = tdt_photometry.streams[stream_name].fs
            starting_time = tdt_photometry.streams[stream_name].start_time
            stream_name_to_starting_time_and_rate[stream_name] = (starting_time, rate)
        return stream_name_to_starting_time_and_rate

    def get_starting_time_and_rate(self, t1: float = 0.0, t2: float = 0.0) -> tuple[float, float]:
        """
        Get the starting time and rate for the data.

        Parameters
        ----------
        t1 : float, optional
            Retrieve data starting at t1 (in seconds), default = 0 for start of recording.
        t2 : float, optional
            Retrieve data ending at t2 (in seconds), default = 0 for end of recording.

        Returns
        -------
        dict[str, tuple[float, float]]
            Dictionary of stream names to starting time and rate.
        """
        stream_name_to_starting_time_and_rate = getattr(self, "stream_name_to_starting_time_and_rate", None)
        if (
            stream_name_to_starting_time_and_rate is None
        ):  # Can't use getattr default bc it will call get_original_starting_time_and_rate even if stream_name_to_timestamps is set
            stream_name_to_starting_time_and_rate = self.get_original_starting_time_and_rate(t1=t1, t2=t2)
        return stream_name_to_starting_time_and_rate

    def set_aligned_starting_time_and_rate(
        self, stream_name_to_aligned_starting_time_and_rate: dict[str, tuple[float, float]]
    ) -> None:
        """
        Set the aligned starting time and rate for the data.

        Parameters
        ----------
        stream_name_to_aligned_starting_time_and_rate : dict[str, tuple[float, float]]
            Dictionary of stream names to aligned starting time and rate.
        """
        self.stream_name_to_starting_time_and_rate = stream_name_to_aligned_starting_time_and_rate

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        stub_test: bool = False,
        t1: float = 0.0,
        t2: float = 0.0,
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
        t1 : float, optional
            Retrieve data starting at t1 (in seconds), default = 0 for start of recording.
        t2 : float, optional
            Retrieve data ending at t2 (in seconds), default = 0 for end of recording.
        timing_source : Literal["original", "aligned_timestamps", "aligned_starting_time_and_rate"], optional
            Source of timing information for the data, default = "original".

        Raises
        ------
        AssertionError
            If the timing_source is not one of "original", "aligned_timestamps", or "aligned_starting_time_and_rate".
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "stub_test",
                "t1",
                "t2",
                "timing_source",
            ]
            num_positional_args_before_args = 2  # nwbfile, metadata
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"add_to_nwbfile() takes at most {len(parameter_names) + num_positional_args_before_args} positional arguments but "
                    f"{len(args) + num_positional_args_before_args} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to TDTFiberPhotometryInterface.add_to_nwbfile() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            stub_test = positional_values.get("stub_test", stub_test)
            t1 = positional_values.get("t1", t1)
            t2 = positional_values.get("t2", t2)
            timing_source = positional_values.get("timing_source", timing_source)

        from ndx_fiber_photometry import (
            CommandedVoltageSeries,
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

        # Load Data
        if stub_test:
            assert (
                t2 == 0.0
            ), f"stub_test cannot be used with a specified t2 ({t2}). Use t2=0.0 for stub_test or set stub_test=False."
            t2 = t1 + 1.0

        tdt_photometry = self.load(t1=t1, t2=t2)

        # timing_source is used to avoid loading the data twice if alignment is NOT used.
        # It is also used to determine whether or not to use the aligned timestamps or starting time and rate.
        if timing_source == "aligned_timestamps":
            stream_name_to_timestamps = self.get_timestamps(t1=t1, t2=t2)
        elif timing_source == "aligned_starting_time_and_rate":
            stream_name_to_starting_time_and_rate = self.get_starting_time_and_rate(t1=t1, t2=t2)
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

        # Commanded Voltage Series
        for commanded_voltage_series_metadata in metadata["Ophys"]["FiberPhotometry"].get("CommandedVoltageSeries", []):
            index = commanded_voltage_series_metadata["index"]
            if index is None:
                data = tdt_photometry.streams[commanded_voltage_series_metadata["stream_name"]].data
            else:
                data = tdt_photometry.streams[commanded_voltage_series_metadata["stream_name"]].data[index, :]
            if timing_source == "aligned_timestamps":
                timestamps = stream_name_to_timestamps[commanded_voltage_series_metadata["stream_name"]]
                timing_kwargs = dict(timestamps=timestamps)
            elif timing_source == "aligned_starting_time_and_rate":
                starting_time, rate = stream_name_to_starting_time_and_rate[
                    commanded_voltage_series_metadata["stream_name"]
                ]
                timing_kwargs = dict(starting_time=starting_time, rate=rate)
            else:
                starting_time = 0.0
                rate = tdt_photometry.streams[commanded_voltage_series_metadata["stream_name"]].fs
                timing_kwargs = dict(starting_time=starting_time, rate=rate)
            commanded_voltage_series = CommandedVoltageSeries(
                name=commanded_voltage_series_metadata["name"],
                description=commanded_voltage_series_metadata["description"],
                data=data,
                unit=commanded_voltage_series_metadata["unit"],
                frequency=commanded_voltage_series_metadata["frequency"],
                **timing_kwargs,
            )
            nwbfile.add_acquisition(commanded_voltage_series)

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
            if "commanded_voltage_series" in row_metadata:
                row_data["commanded_voltage_series"] = nwbfile.acquisition[row_metadata["commanded_voltage_series"]]
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
            stream_indices = fiber_photometry_response_series_metadata.get("stream_indices", None)

            # Get the timing information
            if timing_source == "aligned_timestamps":
                timestamps = stream_name_to_timestamps[stream_name]
                timing_kwargs = dict(timestamps=timestamps)
            elif timing_source == "aligned_starting_time_and_rate":
                starting_time, rate = stream_name_to_starting_time_and_rate[stream_name]
                timing_kwargs = dict(starting_time=starting_time, rate=rate)
            else:
                rate = tdt_photometry.streams[stream_name].fs
                starting_time = tdt_photometry.streams[stream_name].start_time
                timing_kwargs = dict(starting_time=starting_time, rate=rate)

            # Get the data
            data = tdt_photometry.streams[stream_name].data
            if stream_indices is not None:
                data = tdt_photometry.streams[stream_name].data[stream_indices, :]
                # Transpose the data if it is in the wrong shape
                if data.shape[0] < data.shape[1]:
                    data = data.T

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


class _TDTFiberPhotometryInterfaceSingleStream(TDTLoadMixin, BaseFiberPhotometryInterface):
    """Single-stream TDT fiber photometry interface (writes one FiberPhotometryResponseSeries)."""

    display_name = "TDTFiberPhotometry"
    info = "Data Interface for converting fiber photometry data from TDT files."
    associated_suffixes = ("Tbk", "Tdx", "tev", "tin", "tsq")

    @validate_call
    def __init__(
        self,
        *,
        folder_path: DirectoryPath,
        stream_name: str | list[str],
        metadata_key: str | None = None,
        stream_indices: list[int] | None = None,
        verbose: bool = False,
    ):
        self.stream_indices = stream_indices
        super().__init__(
            folder_path=folder_path,
            stream_name=stream_name,
            metadata_key=metadata_key,
            verbose=verbose,
        )

    @classmethod
    def get_available_streams(cls, folder_path: DirectoryPath) -> list[str]:
        """Return the names of the stream stores available in a TDT tank."""
        tdt = get_package("tdt", installation_instructions="pip install tdt")
        with open(os.devnull, "w", encoding="utf-8") as f, redirect_stdout(f):
            tdt_photometry = tdt.read_block(str(folder_path), evtype=["streams"], t2=1.0)
        return sorted(tdt_photometry.streams.keys())

    @staticmethod
    def _stream_name_to_store_code(stream_name: str) -> str:
        """Map a tdt stream key to the store code accepted by ``read_block(store=...)``.

        ``tdt`` prefixes an underscore to keys whose store codes start with a digit (e.g. store
        ``405R`` is keyed ``_405R``), but the ``store`` filter expects the raw code, so strip a
        single leading underscore.
        """
        return stream_name[1:] if stream_name.startswith("_") else stream_name

    def _load_stream(self, stream_name: str, t1: float = 0.0, t2: float = 0.0):
        store_code = self._stream_name_to_store_code(stream_name)
        tdt_photometry = self.load(t1=t1, t2=t2, store=store_code)
        return tdt_photometry.streams[stream_name]

    def _get_stream_data(self, *, stream_name: str, t1: float = 0.0, t2: float = 0.0) -> np.ndarray:
        stream = self._load_stream(stream_name, t1=t1, t2=t2)
        data = np.asarray(stream.data)
        if data.ndim == 2:
            data = data.T  # TDT stores are (channels, samples); make time-major.
            if self.stream_indices is not None:
                data = data[:, self.stream_indices]
        return data

    def _get_stream_timestamps(self, *, stream_name: str, t1: float = 0.0, t2: float = 0.0) -> np.ndarray:
        stream = self._load_stream(stream_name, t1=t1, t2=t2)
        rate = float(stream.fs)
        starting_time = float(stream.start_time)
        num_samples = np.asarray(stream.data).shape[-1]
        return starting_time + np.arange(num_samples) / rate

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        tdt_photometry = self.load(evtype=["scalars"])  # Quickly loads info without loading all the data.
        start_timestamp = tdt_photometry.info.start_date.timestamp()
        session_start_datetime = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
        metadata["NWBFile"]["session_start_time"] = session_start_datetime.isoformat()
        return metadata


class TDTFiberPhotometryInterface(BaseTemporalAlignmentInterface):
    """Data Interface for converting fiber photometry data from a TDT output folder.

    Each interface writes a single ``FiberPhotometryResponseSeries``; use multiple interfaces (with
    distinct ``metadata_key`` values) in a converter to write several series sharing one
    ``FiberPhotometryTable``. Call :meth:`get_available_streams` to discover stream names.

    .. deprecated::
        Constructing without ``stream_name`` routes to the deprecated multi-stream implementation,
        which writes every stream at once and will be removed on or after August 2026. Pass
        ``stream_name`` to use the single-stream interface.
    """

    keywords = ("fiber photometry",)
    display_name = "TDTFiberPhotometry"
    info = "Data Interface for converting fiber photometry data from TDT files."
    associated_suffixes = ("Tbk", "Tdx", "tev", "tin", "tsq")

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        stream_name: str | list[str] | None = None,
        metadata_key: str | None = None,
        stream_indices: list[int] | None = None,
        verbose: bool = False,
    ):
        """Initialize the TDTFiberPhotometryInterface.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder containing the TDT data.
        stream_name : str or list of str, optional
            The stream store(s) whose samples become this interface's single
            ``FiberPhotometryResponseSeries``. If omitted, the deprecated multi-stream behavior is
            used (see class docstring).
        metadata_key : str, optional
            Key under ``metadata["Ophys"]["FiberPhotometry"]`` holding this interface's response-series
            metadata. When ``None`` (default), it is generated from ``stream_name``.
        stream_indices : list of int, optional
            Channel indices to select from a multi-channel stream store.
        verbose : bool, default: False
            Whether to print status messages.
        """
        if stream_name is None:
            warnings.warn(
                "Constructing TDTFiberPhotometryInterface without `stream_name` uses the deprecated "
                "multi-stream behavior, which will be removed on or after August 2026. Pass "
                "`stream_name=` to write a single FiberPhotometryResponseSeries "
                "(see TDTFiberPhotometryInterface.get_available_streams).",
                DeprecationWarning,
                stacklevel=2,
            )
            self._delegate = _TDTFiberPhotometryInterfaceMultiStream(folder_path=folder_path, verbose=verbose)
        else:
            self._delegate = _TDTFiberPhotometryInterfaceSingleStream(
                folder_path=folder_path,
                stream_name=stream_name,
                metadata_key=metadata_key,
                stream_indices=stream_indices,
                verbose=verbose,
            )
        self.verbose = verbose
        self.source_data = self._delegate.source_data

    @classmethod
    def get_available_streams(cls, folder_path: DirectoryPath) -> list[str]:
        """Return the names of the stream stores available in a TDT tank."""
        return _TDTFiberPhotometryInterfaceSingleStream.get_available_streams(folder_path)

    def __getattr__(self, name: str):
        # Forward any attribute not defined on the router (load, get_events, stream_names, ...)
        # to the active delegate. __getattr__ only fires when normal lookup fails, so the explicit
        # forwarders below and the router's own attributes take precedence.
        return getattr(self.__dict__["_delegate"], name)

    def get_metadata(self) -> DeepDict:
        return self._delegate.get_metadata()

    def get_metadata_schema(self) -> dict:
        return self._delegate.get_metadata_schema()

    def get_conversion_options_schema(self) -> dict:
        return self._delegate.get_conversion_options_schema()

    def get_original_timestamps(self, *args, **kwargs):
        return self._delegate.get_original_timestamps(*args, **kwargs)

    def get_timestamps(self, *args, **kwargs):
        return self._delegate.get_timestamps(*args, **kwargs)

    def set_aligned_timestamps(self, *args, **kwargs) -> None:
        return self._delegate.set_aligned_timestamps(*args, **kwargs)

    def set_aligned_starting_time(self, *args, **kwargs) -> None:
        return self._delegate.set_aligned_starting_time(*args, **kwargs)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None, **conversion_options) -> None:
        return self._delegate.add_to_nwbfile(nwbfile, metadata, **conversion_options)
