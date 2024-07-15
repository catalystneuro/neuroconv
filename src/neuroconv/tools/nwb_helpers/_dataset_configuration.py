"""Collection of helper functions related to configuration of datasets dependent on backend."""

from typing import Generator, Literal, Union

import h5py
import numpy as np
import zarr
from hdmf import Container
from hdmf.data_utils import DataIO
from hdmf.utils import get_data_shape
from hdmf_zarr import NWBZarrIO
from pynwb import NWBHDF5IO, NWBFile
from pynwb.base import DynamicTable, TimeSeriesReferenceVectorData
from pynwb.file import NWBContainer

from ._configuration_models import DATASET_IO_CONFIGURATIONS
from ._configuration_models._base_dataset_io import DatasetIOConfiguration


def _get_io_mode(io: Union[NWBHDF5IO, NWBZarrIO]) -> str:
    """NWBHDF5IO and NWBZarrIO have different ways of storing the io mode (e.g. "r", "a", "w") they used on a path."""
    if isinstance(io, NWBHDF5IO):
        return io.mode
    elif isinstance(io, NWBZarrIO):
        return io._ZarrIO__mode


def _is_dataset_written_to_file(
    candidate_dataset: Union[h5py.Dataset, zarr.Array],
    backend: Literal["hdf5", "zarr"],
    existing_file: Union[h5py.File, zarr.Group, None],
) -> bool:
    """
    Determine if the neurodata object is already written to the file on disk.

    This object should then be skipped by the `get_io_datasets` function when working in append mode.
    """
    if existing_file is None:
        return False

    return (
        isinstance(candidate_dataset, h5py.Dataset)  # If the source data is an HDF5 Dataset
        and backend == "hdf5"
        and candidate_dataset.file == existing_file  # If the source HDF5 Dataset is the appending NWBFile
    ) or (
        isinstance(candidate_dataset, zarr.Array)  # If the source data is a Zarr Array
        and backend == "zarr"
        and candidate_dataset.store == existing_file  # If the source Zarr 'file' is the appending NWBFile
    )


def get_default_dataset_io_configurations(
    nwbfile: NWBFile,
    backend: Union[None, Literal["hdf5", "zarr"]] = None,  # None for auto-detect from append mode, otherwise required
) -> Generator[DatasetIOConfiguration, None, None]:
    """
    Generate DatasetIOConfiguration objects for wrapping NWB file objects with a specific backend.

    This method automatically detects all objects in an NWB file that can be wrapped in a hdmf.DataIO.
    If the NWB file is in append mode, it supports auto-detection of the backend.
    Otherwise, it requires a backend specification.

    Parameters
    ----------
    nwbfile : pynwb.NWBFile
        An in-memory NWBFile object, either generated from the base class or read from an existing file of any backend.
    backend : "hdf5" or "zarr"
        Which backend format type you would like to use in configuring each dataset's compression methods and options.

    Yields
    ------
    DatasetIOConfiguration
        A summary of each detected object that can be wrapped in a hdmf.DataIO.
    """

    DatasetIOConfigurationClass = DATASET_IO_CONFIGURATIONS[backend]

    if backend is None and nwbfile.read_io is None:
        raise ValueError(
            "Keyword argument `backend` (either 'hdf5' or 'zarr') must be specified if the `nwbfile` was not "
            "read from an existing file!"
        )
    if backend is None and nwbfile.read_io is not None and nwbfile.read_io.mode not in ("r+", "a"):
        raise ValueError(
            "Keyword argument `backend` (either 'hdf5' or 'zarr') must be specified if the `nwbfile` is being appended."
        )

    detected_backend = None
    existing_file = None
    if isinstance(nwbfile.read_io, NWBHDF5IO) and _get_io_mode(io=nwbfile.read_io) in ("r+", "a"):
        detected_backend = "hdf5"
        existing_file = nwbfile.read_io._file
    elif isinstance(nwbfile.read_io, NWBZarrIO) and _get_io_mode(io=nwbfile.read_io) in ("r+", "a"):
        detected_backend = "zarr"
        existing_file = nwbfile.read_io.file.store
    backend = backend or detected_backend

    if detected_backend is not None and detected_backend != backend:
        raise ValueError(
            f"Detected backend '{detected_backend}' for appending file, but specified `backend` "
            f"({backend}) does not match! Set `backend=None` or remove the keyword argument to allow it to auto-detect."
        )

    known_dataset_fields = ("data", "timestamps")
    for neurodata_object in nwbfile.objects.values():
        if isinstance(neurodata_object, DynamicTable):
            dynamic_table = neurodata_object  # For readability

            for column in dynamic_table.columns:
                candidate_dataset = column.data  # VectorData object
                # noinspection PyTypeChecker
                if _is_dataset_written_to_file(
                    candidate_dataset=candidate_dataset, backend=backend, existing_file=existing_file
                ):
                    continue  # Skip

                # Skip over columns that are already wrapped in DataIO
                if isinstance(candidate_dataset, DataIO):
                    continue  # Skip

                # Skip over columns whose values are links, such as the 'group' of an ElectrodesTable
                if any(isinstance(value, Container) for value in candidate_dataset):
                    continue  # Skip

                # Skip when columns whose values are a reference type
                if isinstance(column, TimeSeriesReferenceVectorData):
                    continue

                # Skip datasets with any zero-length axes
                dataset_name = "data"
                candidate_dataset = getattr(column, dataset_name)
                full_shape = get_data_shape(data=candidate_dataset)
                if any(axis_length == 0 for axis_length in full_shape):
                    continue

                dataset_io_configuration = DatasetIOConfigurationClass.from_neurodata_object(
                    neurodata_object=column, dataset_name=dataset_name
                )

                yield dataset_io_configuration
        elif isinstance(neurodata_object, NWBContainer):
            for known_dataset_field in known_dataset_fields:
                # Skip optional fields that aren't present
                if known_dataset_field not in neurodata_object.fields:
                    continue

                candidate_dataset = getattr(neurodata_object, known_dataset_field)

                # Skip if already written to file
                # noinspection PyTypeChecker
                if _is_dataset_written_to_file(
                    candidate_dataset=candidate_dataset, backend=backend, existing_file=existing_file
                ):
                    continue

                # Skip over datasets that are already wrapped in DataIO
                if isinstance(candidate_dataset, DataIO):
                    continue

                # Skip edge case of in-memory ImageSeries with external mode; data is in fields and is empty array
                if isinstance(candidate_dataset, np.ndarray) and candidate_dataset.size == 0:
                    continue

                # Skip datasets with any zero-length axes
                candidate_dataset = getattr(neurodata_object, known_dataset_field)
                full_shape = get_data_shape(data=candidate_dataset)
                if any(axis_length == 0 for axis_length in full_shape):
                    continue

                dataset_io_configuration = DatasetIOConfigurationClass.from_neurodata_object(
                    neurodata_object=neurodata_object, dataset_name=known_dataset_field
                )

                yield dataset_io_configuration
