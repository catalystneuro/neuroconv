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


class CSVFiberPhotometryInterface(BaseTemporalAlignmentInterface):
    """
    Data Interface for converting raw fiber photometry data from CSV files.

    This CSV format is a raw acquisition format, with one CSV per stream (e.g. a signal channel, an
    isosbestic control channel). Each data CSV has three columns -- ``timestamps`` (seconds),
    ``data`` (fluorescence), and ``sampling_rate`` (populated only on the first row) -- and is named
    after its stream (``<stream_name>.csv``). This interface reads those CSV streams and parses them
    into the ndx-fiber-photometry format.

    Notes
    -----
    Unlike the TDT format, CSV recordings carry no embedded recording-start timestamp, so
    :meth:`get_metadata` does NOT populate ``NWBFile/session_start_time``. The user must supply it
    via editable metadata; the conversion fails loudly if it is missing.
    """

    keywords = ("fiber photometry",)
    display_name = "CSVFiberPhotometry"
    info = "Data Interface for converting fiber photometry data from CSV files."
    associated_suffixes = ("csv",)

    @validate_call
    def __init__(self, folder_path: DirectoryPath, *, verbose: bool = False):
        """Initialize the CSVFiberPhotometryInterface.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder containing the per-stream CSV files.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            folder_path=folder_path,
            verbose=verbose,
        )
        # These imports assure that ndx_fiber_photometry and ndx_ophys_devices are in the global
        # namespace when a pynwb.io object is created.
        import ndx_fiber_photometry  # noqa: F401
        import ndx_ophys_devices  # noqa: F401

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the CSVFiberPhotometryInterface.

        ``NWBFile/session_start_time`` is intentionally left unset: CSV recordings carry no embedded
        recording-start timestamp, so it must be supplied by the user via editable metadata.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()
        return metadata

    def _stream_csv_path(self, stream_name: str) -> Path:
        """Get the path to the CSV file backing the given stream."""
        return Path(self.source_data["folder_path"]) / f"{stream_name}.csv"

    def _get_stream_names(self) -> list[str]:
        """Get the names of the data streams (3-column data CSVs) in the folder.

        Event CSVs (a single ``timestamps`` column, e.g. TTLs) are excluded -- those belong to a
        separate events interface.
        """
        stream_names = []
        for path in sorted(Path(self.source_data["folder_path"]).glob("*.csv")):
            columns = [column.lower() for column in pd.read_csv(path, nrows=0).columns]
            if "data" in columns:
                stream_names.append(path.stem)
        return stream_names

    def _read_stream(self, stream_name: str, stub_test: bool = False) -> dict:
        """Read a single data stream from its CSV file.

        Parameters
        ----------
        stream_name : str
            The name of the stream (CSV file stem) to read.
        stub_test : bool, optional
            If True, read only the first ~1 second of samples, default = False.

        Returns
        -------
        dict
            Dictionary with keys ``data``, ``timestamps``, and ``rate``.
        """
        path = self._stream_csv_path(stream_name)
        rate = float(pd.read_csv(path, nrows=1, usecols=["sampling_rate"])["sampling_rate"].to_numpy()[0])
        nrows = int(np.ceil(rate)) if stub_test else None
        dataframe = pd.read_csv(path, nrows=nrows)
        return dict(
            data=dataframe["data"].to_numpy(),
            timestamps=dataframe["timestamps"].to_numpy(),
            rate=rate,
        )

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
