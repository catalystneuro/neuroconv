import os
from contextlib import redirect_stdout
from pathlib import Path
from typing import Optional

import numpy as np
from ndx_fiber_photometry import (
    BandOpticalFilter,
    CommandedVoltageSeries,
    DichroicMirror,
    ExcitationSource,
    FiberPhotometry,
    FiberPhotometryResponseSeries,
    FiberPhotometryTable,
    Indicator,
    OpticalFiber,
    Photodetector,
)
from pynwb.file import NWBFile
from tdt import read_block

from neuroconv.basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from neuroconv.utils import DeepDict, FilePathType


class TDTFiberPhotometryInterface(BaseTemporalAlignmentInterface):
    """
    Data Interface for converting fiber photometry data from TDT.
    """

    keywords = ["fiber photometry"]

    def __init__(self, folder_path: FilePathType, verbose: bool = True):
        super().__init__(
            folder_path=folder_path,
            verbose=verbose,
        )

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        return metadata

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        return metadata_schema

    def get_original_timestamps(self) -> np.ndarray:
        return NotImplementedError

    def get_timestamps(self) -> np.ndarray:
        return NotImplementedError

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        return NotImplementedError

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        t2: Optional[float] = None,
    ):
        # Load Data
        folder_path = Path(self.source_data["folder_path"])
        assert folder_path.is_dir(), f"Folder path {folder_path} does not exist."
        with open(os.devnull, "w") as f, redirect_stdout(f):
            if t2 is None:
                tdt_photometry = read_block(str(folder_path))

        # Optical Fibers
        for optical_fiber_metadata in metadata["Ophys"]["FiberPhotometry"]["OpticalFibers"]:
            optical_fiber = OpticalFiber(
                name=optical_fiber_metadata["name"],
                description=optical_fiber_metadata["description"],
                manufacturer=optical_fiber_metadata["manufacturer"],
                model=optical_fiber_metadata["model"],
                core_diameter_in_um=optical_fiber_metadata["core_diameter_in_um"],
                numerical_aperture=optical_fiber_metadata["numerical_aperture"],
            )
            nwbfile.add_device(optical_fiber)

        # Excitation Sources
        for excitation_source_metadata in metadata["Ophys"]["FiberPhotometry"]["ExcitationSources"]:
            excitation_source = ExcitationSource(
                name=excitation_source_metadata["name"],
                description=excitation_source_metadata["description"],
                manufacturer=excitation_source_metadata["manufacturer"],
                model=excitation_source_metadata["model"],
                illumination_type=excitation_source_metadata["illumination_type"],
                excitation_wavelength_in_nm=excitation_source_metadata["excitation_wavelength_in_nm"],
            )
            nwbfile.add_device(excitation_source)

        # Photodetectors
        for photodetector_metadata in metadata["Ophys"]["FiberPhotometry"]["Photodetectors"]:
            photodetector = Photodetector(
                name=photodetector_metadata["name"],
                description=photodetector_metadata["description"],
                manufacturer=photodetector_metadata["manufacturer"],
                model=photodetector_metadata["model"],
                detector_type=photodetector_metadata["detector_type"],
                detected_wavelength_in_nm=photodetector_metadata["detected_wavelength_in_nm"],
                gain=photodetector_metadata["gain"],
            )
            nwbfile.add_device(photodetector)

        # Optical Filters
        for optical_filter_metadata in metadata["Ophys"]["FiberPhotometry"]["BandOpticalFilters"]:
            optical_filter = BandOpticalFilter(
                name=optical_filter_metadata["name"],
                description=optical_filter_metadata["description"],
                manufacturer=optical_filter_metadata["manufacturer"],
                model=optical_filter_metadata["model"],
                center_wavelength_in_nm=optical_filter_metadata["center_wavelength_in_nm"],
                bandwidth_in_nm=optical_filter_metadata["bandwidth_in_nm"],
                filter_type=optical_filter_metadata["filter_type"],
            )
            nwbfile.add_device(optical_filter)

        # Dichroic Mirror
        for dichroic_mirror_metadata in metadata["Ophys"]["FiberPhotometry"]["DichroicMirrors"]:
            dichroic_mirror = DichroicMirror(
                name=dichroic_mirror_metadata["name"],
                description=dichroic_mirror_metadata["description"],
                manufacturer=dichroic_mirror_metadata["manufacturer"],
                model=dichroic_mirror_metadata["model"],
            )
            nwbfile.add_device(dichroic_mirror)

        # Indicators (aka Fluorophores)
        for indicator_metadata in metadata["Ophys"]["FiberPhotometry"]["Indicators"]:
            indicator = Indicator(
                name=indicator_metadata["name"],
                description=indicator_metadata["description"],
                manufacturer=indicator_metadata["manufacturer"],
                label=indicator_metadata["label"],
                injection_location=indicator_metadata["injection_location"],
                injection_coordinates_in_mm=indicator_metadata["injection_coordinates_in_mm"],
            )
            nwbfile.add_device(indicator)

        # Commanded Voltage Series
        for commanded_voltage_series_metadata in metadata["Ophys"]["FiberPhotometry"]["CommandedVoltageSeries"]:
            data = tdt_photometry.streams[commanded_voltage_series_metadata["stream_name"]].data[
                commanded_voltage_series_metadata["index"], :
            ]
            commanded_voltage_series = CommandedVoltageSeries(
                name=commanded_voltage_series_metadata["name"],
                description=commanded_voltage_series_metadata["description"],
                data=data,
                unit=commanded_voltage_series_metadata["unit"],
                frequency=commanded_voltage_series_metadata["frequency"],
                starting_time=0.0,
                rate=tdt_photometry.streams[commanded_voltage_series_metadata["stream_name"]].fs,
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
        rate = tdt_photometry.streams[first_stream_name].fs
        for fiber_photometry_response_series_metadata in metadata["Ophys"]["FiberPhotometry"][
            "FiberPhotometryResponseSeries"
        ]:
            data_traces = []
            for stream_name, stream_index in zip(
                fiber_photometry_response_series_metadata["stream_names"],
                fiber_photometry_response_series_metadata["stream_indices"],
            ):
                assert (
                    tdt_photometry.streams[stream_name].fs == rate
                ), f"All streams in the same FiberPhotometryResponseSeries must have the same sampling rate. But stream {stream_name} has a different sampling rate than {first_stream_name}."
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
                rate=rate,
                fiber_photometry_table_region=fiber_photometry_table_region,
            )
            nwbfile.add_acquisition(fiber_photometry_response_series)
