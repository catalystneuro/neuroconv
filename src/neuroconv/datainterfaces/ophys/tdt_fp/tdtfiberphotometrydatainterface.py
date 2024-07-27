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
        with open(os.devnull, "w") as f, redirect_stdout(f):
            tdt_photometry = tdt.read_block(str(folder_path), t1=t1, t2=t2, evtype=evtype)
        return tdt_photometry

    def get_original_timestamps(self) -> dict[str, np.ndarray]:
        tdt_photometry = self.load()
        stream_name_to_timestamps = {}
        for stream_name in tdt_photometry.streams:
            rate = tdt_photometry.streams[stream_name].fs
            starting_time = 0.0
            timestamps = np.arange(
                starting_time, tdt_photometry.streams[stream_name].data.shape[-1] / rate, 1 / rate
            )
            stream_name_to_timestamps[stream_name] = timestamps
        return stream_name_to_timestamps

    def get_timestamps(self) -> dict[str, np.ndarray]:
        return self.stream_name_to_timestamps

    def set_aligned_timestamps(self, stream_name_to_aligned_timestamps: dict[str, np.ndarray]) -> None:
        self.stream_name_to_timestamps = stream_name_to_aligned_timestamps

    def get_original_starting_time_and_rate(self) -> dict[str, tuple[float, float]]:
        tdt_photometry = self.load()
        stream_name_to_starting_time_and_rate = {}
        for stream_name in tdt_photometry.streams:
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
        for row_metadata in metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryTable"]["rows"]:
            row_data = dict()
            # Required fields
            row_data["location"] = row_metadata["location"]
            row_data["indicator"] = nwbfile.devices[row_metadata["indicator"]]
            row_data["optical_fiber"] = nwbfile.devices[row_metadata["optical_fiber"]]
            row_data["excitation_source"] = nwbfile.devices[row_metadata["excitation_source"]]
            row_data["photodetector"] = nwbfile.devices[row_metadata["photodetector"]]
            row_data["dichroic_mirror"] = nwbfile.devices[row_metadata["dichroic_mirror"]]
            # Optional fields
            if row_metadata.get("coordinates"):
                row_data["coordinates"] = row_metadata["coordinates"]
            if row_metadata.get("commanded_voltage_series"):
                row_data["commanded_voltage_series"] = nwbfile.acquisition[row_metadata["commanded_voltage_series"]]
            if row_metadata.get("excitation_filter"):
                row_data["excitation_filter"] = nwbfile.devices[row_metadata["excitation_filter"]]
            if row_metadata.get("emission_filter"):
                row_data["emission_filter"] = nwbfile.devices[row_metadata["emission_filter"]]
            fiber_photometry_table.add_row(**row_data)
        fiber_photometry_table_metadata = FiberPhotometry(
            name="fiber_photometry",
            fiber_photometry_table=fiber_photometry_table,
        )
        nwbfile.add_lab_meta_data(fiber_photometry_table_metadata)

        # Fiber Photometry Response Series
        all_series_metadata = metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryResponseSeries"]
        for fiber_photometry_response_series_metadata in all_series_metadata:
            # Get the timing information from the first series in the stream
            first_stream_name = fiber_photometry_response_series_metadata["stream_names"][0]
            if timing_source == "aligned_timestamps":
                first_timestamps = stream_name_to_timestamps[first_stream_name]
                timing_kwargs = dict(timestamps=first_timestamps)
            elif timing_source == "aligned_starting_time_and_rate":
                first_starting_time, first_rate = stream_name_to_starting_time_and_rate[first_stream_name]
                timing_kwargs = dict(starting_time=first_starting_time, rate=first_rate)
            else:
                first_rate = tdt_photometry.streams[first_stream_name].fs
                first_starting_time = tdt_photometry.streams[first_stream_name].start_time
                timing_kwargs = dict(starting_time=first_starting_time, rate=first_rate)
            # Get the data for each series in the stream
            data_traces = []
            for stream_name, stream_index in zip(
                fiber_photometry_response_series_metadata["stream_names"],
                fiber_photometry_response_series_metadata["stream_indices"],
            ):
                if timing_source == "aligned_timestamps":
                    assert np.array_equal(
                        stream_name_to_timestamps[stream_name], first_timestamps
                    ), f"All streams in the same FiberPhotometryResponseSeries must have the same timestamps. But stream {stream_name} has different timestamps than {first_stream_name}."
                elif timing_source == "aligned_starting_time_and_rate":
                    assert stream_name_to_starting_time_and_rate[stream_name] == (
                        first_starting_time,
                        first_rate,
                    ), f"All streams in the same FiberPhotometryResponseSeries must have the same starting time and rate. But stream {stream_name} has different starting time and rate than {first_stream_name}."
                else:
                    assert (
                        tdt_photometry.streams[stream_name].fs == first_rate
                    ), f"All streams in the same FiberPhotometryResponseSeries must have the same sampling rate. But stream {stream_name} has a different sampling rate than {first_stream_name}."
                if stream_index is None:
                    data_trace = tdt_photometry.streams[stream_name].data
                    # Transpose the data if it is in the wrong shape
                    if data_trace.ndim == 2 and data_trace.shape[0] < data_trace.shape[1]:
                        data_trace = data_trace.T
                else:
                    data_trace = tdt_photometry.streams[stream_name].data[stream_index, :]
                data_traces.append(data_trace)
            data = np.column_stack(data_traces)

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