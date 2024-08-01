import os
from contextlib import redirect_stdout
from pathlib import Path
from typing import Literal

import numpy as np
from pynwb.file import NWBFile

from neuroconv.basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from neuroconv.tools import get_package
from neuroconv.tools.fiber_photometry import add_fiber_photometry_device
from neuroconv.utils import DeepDict, FilePathType


class TDTFiberPhotometryInterface(BaseTemporalAlignmentInterface):
    """
    Data Interface for converting fiber photometry data from TDT.
    """

    keywords = ["fiber photometry"]
    display_name = "TDTFiberPhotometry"
    info = "Data Interface for converting fiber photometry data from TDT."
    associated_suffixes = ("Tbk", "Tdx", "tev", "tin", "tsq")

    def __init__(self, folder_path: FilePathType, verbose: bool = True):
        super().__init__(
            folder_path=folder_path,
            verbose=verbose,
        )
        import ndx_fiber_photometry  # noqa: F401

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        tdt_photometry = self.load(evtype=["scalars"])  # This evtype quickly loads info without loading all the data.
        metadata["NWBFile"]["session_start_time"] = tdt_photometry.info.start_date.isoformat()
        return metadata

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        return metadata_schema

    def load(self, t1: float = 0.0, t2: float = 0.0, evtype: list[str] = ["all"]):
        """Load the TDT data from the folder path.

        Parameters
        ----------
        t1 : float, optional
            Retrieve data starting at t1 (in seconds), default = 0 for start of recording.
        t2 : float, optional
            Retrieve data ending at t2 (in seconds), default = 0 for end of recording.
        evtype : list[str], optional
            List of strings, specifies what type of data stores to retrieve from the tank.
            Can contain 'all' (default), 'epocs', 'snips', 'streams', or 'scalars'. Ex. ['epocs', 'snips']

        Returns
        -------
        tdt.StructType
            TDT data object
        """
        tdt = get_package("tdt", installation_instructions="pip install tdt")
        folder_path = Path(self.source_data["folder_path"])
        assert folder_path.is_dir(), f"Folder path {folder_path} does not exist."
        for evtype_string in evtype:
            assert evtype_string in ["all", "epocs", "snips", "streams", "scalars"], (
                f"evtype must be a list containing some combination of 'all', 'epocs', 'snips', 'streams', or 'scalars', "
                f"but got {evtype_string}."
            )
        with open(os.devnull, "w") as f, redirect_stdout(f):
            tdt_photometry = tdt.read_block(str(folder_path), t1=t1, t2=t2, evtype=evtype)
        return tdt_photometry

    def get_original_timestamps(self, t1: float = 0.0, t2: float = 0.0) -> dict[str, np.ndarray]:
        tdt_photometry = self.load(t1=t1, t2=t2)
        stream_name_to_timestamps = {}
        for stream_name in tdt_photometry.streams:
            rate = tdt_photometry.streams[stream_name].fs
            starting_time = 0.0
            timestamps = np.arange(starting_time, tdt_photometry.streams[stream_name].data.shape[-1] / rate, 1 / rate)
            stream_name_to_timestamps[stream_name] = timestamps
        return stream_name_to_timestamps

    def get_timestamps(self, t1: float = 0.0, t2: float = 0.0) -> dict[str, np.ndarray]:
        stream_to_timestamps = getattr(self, "stream_name_to_timestamps", self.get_original_timestamps(t1=t1, t2=t2))
        stream_to_timestamps = {name: timestamps[timestamps >= t1] for name, timestamps in stream_to_timestamps.items()}
        if t2 == 0.0:
            return stream_to_timestamps
        stream_to_timestamps = {name: timestamps[timestamps <= t2] for name, timestamps in stream_to_timestamps.items()}
        return stream_to_timestamps

    def set_aligned_timestamps(self, stream_name_to_aligned_timestamps: dict[str, np.ndarray]) -> None:
        self.stream_name_to_timestamps = stream_name_to_aligned_timestamps

    def set_aligned_starting_time(self, aligned_starting_time: float, t1: float = 0.0, t2: float = 0.0) -> None:
        stream_name_to_timestamps = self.get_timestamps(t1=t1, t2=t2)
        aligned_stream_name_to_timestamps = {
            name: timestamps + aligned_starting_time for name, timestamps in stream_name_to_timestamps.items()
        }
        self.set_aligned_timestamps(aligned_stream_name_to_timestamps)

    def get_original_starting_time_and_rate(self, t1: float = 0.0, t2: float = 0.0) -> dict[str, tuple[float, float]]:
        tdt_photometry = self.load(t1=t1, t2=t2)
        stream_name_to_starting_time_and_rate = {}
        for stream_name in tdt_photometry.streams.keys():
            rate = tdt_photometry.streams[stream_name].fs
            starting_time = tdt_photometry.streams[stream_name].start_time
            stream_name_to_starting_time_and_rate[stream_name] = (starting_time, rate)
        return stream_name_to_starting_time_and_rate

    def get_starting_time_and_rate(self) -> tuple[float, float]:
        return self.stream_name_to_starting_time_and_rate

    def set_aligned_starting_time_and_rate(
        self, stream_name_to_aligned_starting_time_and_rate: dict[str, tuple[float, float]]
    ) -> None:
        self.stream_name_to_starting_time_and_rate = stream_name_to_aligned_starting_time_and_rate

    def get_events(self) -> dict:
        """
        Useful for extracting events (e.g. camera TTL pulses) from the TDT files.

        Returns:
            dict: Dictionary of events.
        """
        events = {}
        tdt_photometry = self.load(evtype=["epocs"])
        for stream_name in tdt_photometry.epocs.keys():
            events[stream_name] = {
                "onset": tdt_photometry.epocs[stream_name].onset,
                "offset": tdt_photometry.epocs[stream_name].offset,
                "data": tdt_photometry.epocs[stream_name].data,
            }
        return events

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        t1: float = 0.0,
        t2: float = 0.0,
        timing_source: Literal["original", "aligned_timestamps", "aligned_starting_time_and_rate"] = "original",
    ):
        from ndx_fiber_photometry import (
            CommandedVoltageSeries,
            FiberPhotometry,
            FiberPhotometryResponseSeries,
            FiberPhotometryTable,
        )

        # Load Data
        tdt_photometry = self.load(t1=t1, t2=t2)

        # timing_source is used to avoid loading the data twice if alignment is NOT used.
        # It is also used to determine whether or not to use the aligned timestamps or starting time and rate.
        if timing_source == "aligned_timestamps":
            stream_name_to_timestamps = self.get_timestamps()
        elif timing_source == "aligned_starting_time_and_rate":
            stream_name_to_starting_time_and_rate = self.get_starting_time_and_rate()
        else:
            assert (
                timing_source == "original"
            ), "timing_source must be one of 'original', 'aligned_timestamps', or 'aligned_starting_time_and_rate'."

        # Add Devices
        device_types = [
            "OpticalFiber",
            "ExcitationSource",
            "Photodetector",
            "BandOpticalFilter",
            "EdgeOpticalFilter",
            "DichroicMirror",
            "Indicator",
        ]
        for device_type in device_types:
            devices_metadata = metadata["Ophys"]["FiberPhotometry"].get(device_type + "s", [])
            for device_metadata in devices_metadata:
                add_fiber_photometry_device(
                    nwbfile=nwbfile,
                    device_metadata=device_metadata,
                    device_type=device_type,
                )

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
            "indicator",
            "optical_fiber",
            "excitation_source",
            "photodetector",
            "dichroic_mirror",
        ]
        device_fields = [
            "optical_fiber",
            "excitation_source",
            "photodetector",
            "dichroic_mirror",
            "indicator",
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
            if "coordinates" in row_metadata:
                row_data["coordinates"] = row_metadata["coordinates"]
            if "commanded_voltage_series" in row_metadata:
                row_data["commanded_voltage_series"] = nwbfile.acquisition[row_metadata["commanded_voltage_series"]]
            fiber_photometry_table.add_row(**row_data)
        fiber_photometry_table_metadata = FiberPhotometry(
            name="fiber_photometry",
            fiber_photometry_table=fiber_photometry_table,
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
            if stream_indices and data.ndim == 2:
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
