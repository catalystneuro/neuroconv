import os
from contextlib import redirect_stdout
from pathlib import Path
from typing import Literal, Optional

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
        return metadata

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        return metadata_schema

    def load(self):
        tdt = get_package("tdt", installation_instructions="pip install tdt")
        folder_path = Path(self.source_data["folder_path"])
        assert folder_path.is_dir(), f"Folder path {folder_path} does not exist."
        with open(os.devnull, "w") as f, redirect_stdout(f):
            tdt_photometry = tdt.read_block(str(folder_path))
        return tdt_photometry

    def get_original_timestamps(self) -> dict[str, np.ndarray]:
        tdt_photometry = self.load()
        stream_name_to_timestamps = {}
        for stream_name in tdt_photometry.streams:
            rate = tdt_photometry.streams[stream_name].fs
            starting_time = 0.0
            timestamps = np.arange(starting_time, tdt_photometry.streams[stream_name].data.shape[-1] / rate, 1 / rate)
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
            starting_time = 0.0
            stream_name_to_starting_time_and_rate[stream_name] = (starting_time, rate)
        return stream_name_to_starting_time_and_rate

    def get_starting_time_and_rate(self) -> tuple[float, float]:
        return self.stream_name_to_starting_time_and_rate

    def set_aligned_starting_time_and_rate(
        self, stream_name_to_aligned_starting_time_and_rate: dict[str, tuple[float, float]]
    ) -> None:
        self.stream_name_to_starting_time_and_rate = stream_name_to_aligned_starting_time_and_rate

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        t2: Optional[float] = None,
        timing_source: Literal["original", "aligned_timestamps", "aligned_starting_time_and_rate"] = "original",
    ):
        from ndx_fiber_photometry import (
            CommandedVoltageSeries,
            FiberPhotometry,
            FiberPhotometryResponseSeries,
            FiberPhotometryTable,
        )

        # Load Data
        tdt_photometry = self.load()

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
            "DichroicMirror",
            "Indicator",
        ]
        for device_type in device_types:
            for device_metadata in metadata["Ophys"]["FiberPhotometry"][device_type + "s"]:
                add_fiber_photometry_device(
                    nwbfile=nwbfile,
                    device_metadata=device_metadata,
                    device_type=device_type,
                )

        # Commanded Voltage Series
        for commanded_voltage_series_metadata in metadata["Ophys"]["FiberPhotometry"]["CommandedVoltageSeries"]:
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
            fiber_photometry_table.add_row(
                location=row_metadata["location"],
                coordinates=row_metadata["coordinates"],
                commanded_voltage_series=nwbfile.acquisition[row_metadata["commanded_voltage_series"]],
                indicator=nwbfile.devices[row_metadata["indicator"]],
                optical_fiber=nwbfile.devices[row_metadata["optical_fiber"]],
                excitation_source=nwbfile.devices[row_metadata["excitation_source"]],
                photodetector=nwbfile.devices[row_metadata["photodetector"]],
                excitation_filter=nwbfile.devices[row_metadata["excitation_filter"]],
                emission_filter=nwbfile.devices[row_metadata["emission_filter"]],
                dichroic_mirror=nwbfile.devices[row_metadata["dichroic_mirror"]],
            )
        fiber_photometry_table_metadata = FiberPhotometry(
            name="fiber_photometry",
            fiber_photometry_table=fiber_photometry_table,
        )
        nwbfile.add_lab_meta_data(fiber_photometry_table_metadata)

        # Fiber Photometry Response Series
        first_stream_name = metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryResponseSeries"][0]["stream_names"][0]
        if timing_source == "aligned_timestamps":
            first_timestamps = stream_name_to_timestamps[first_stream_name]
            timing_kwargs = dict(timestamps=first_timestamps)
        elif timing_source == "aligned_starting_time_and_rate":
            first_starting_time, first_rate = stream_name_to_starting_time_and_rate[first_stream_name]
            timing_kwargs = dict(starting_time=first_starting_time, rate=first_rate)
        else:
            first_rate = tdt_photometry.streams[first_stream_name].fs
            first_starting_time = 0.0
            timing_kwargs = dict(starting_time=first_starting_time, rate=first_rate)
        for fiber_photometry_response_series_metadata in metadata["Ophys"]["FiberPhotometry"][
            "FiberPhotometryResponseSeries"
        ]:
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
