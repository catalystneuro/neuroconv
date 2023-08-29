"""Collection of helper functions related to configuration of datasets dependent on backend."""
from typing import Iterable, Literal, Tuple, Union

import h5py
import zarr
from hdmf.data_utils import DataIO
from hdmf.utils import get_data_shape
from hdmf_zarr import NWBZarrIO
from pydantic import BaseModel
from pynwb import NWBHDF5IO, NWBFile, TimeSeries
from pynwb.base import DynamicTable


class ConfigurableDataset(BaseModel):
    """A data model for summarizing information about an object that will become a HDF5 or Zarr Dataset in the file."""

    object_id: str
    object_name: str
    parent: str
    field: Literal["data", "timestamps"]
    maxshape: Tuple[int, ...]
    dtype: str  # Think about how to constrain/specify this more

    def __str__(self) -> str:
        """Not overriding __repr__ as this is intended to render only when wrapped in print()."""
        string = (
            f"{self.object_name} of {self.parent}\n"
            + f"{'-' * (len(self.object_name) + 4 + len(self.parent))}\n"
            + f"  {self.field}\n"
            + f"    maxshape: {self.maxshape}\n"
            + f"    dtype: {self.dtype}"
        )
        return string


def _get_dataset_metadata(neurodata_object: Union[TimeSeries, DynamicTable], field_name: str) -> ConfigurableDataset:
    """Fill in the Dataset model with as many values as can be automatically detected or inferred."""
    field_value = getattr(neurodata_object, field_name)
    if field_value is not None and not isinstance(field_value, DataIO):
        return ConfigurableDataset(
            object_id=neurodata_object.object_id,
            object_name=neurodata_object.name,
            parent=neurodata_object.get_ancestor().name,
            field=field_name,
            maxshape=get_data_shape(data=field_value),
            # think on cases that don't have a dtype attr
            dtype=str(getattr(field_value, "dtype", "unknown")),
        )


def _value_already_written_to_file(
    value: Union[h5py.Dataset, zarr.Array],
    backend_type: Literal["hdf5", "zarr"],
    existing_file: Union[h5py.File, zarr.Group, None],
) -> bool:
    """
    Determine if the neurodata object is already written to the file on disk.

    This object should then be skipped by the `get_io_datasets` function when working in append mode.
    """
    return (
        isinstance(value, h5py.Dataset)  # If the source data is an HDF5 Dataset
        and backend_type == "hdf5"  # If working in append mode
        and value.file == existing_file  # If the source HDF5 Dataset is the appending NWBFile
    ) or (
        isinstance(value, zarr.Array)  # If the source data is an Zarr Array
        and backend_type == "zarr"  # If working in append mode
        and value.store == existing_file  # If the source Zarr 'file' is the appending NWBFile
    )


def get_configurable_datasets(nwbfile: NWBFile) -> Iterable[ConfigurableDataset]:
    """
    Method for automatically detecting all objects in the file that could be wrapped in a DataIO.

    Parameters
    ----------
    nwbfile : pynwb.NWBFile
        An in-memory NWBFile object, either generated from the base class or read from an existing file of any backend.

    Yields
    ------
    Dataset
        A summary of each detected object that can be wrapped in a DataIO.
    """
    backend_type = None  # Used for filtering out datasets that have already been written to disk when appending
    existing_file = None
    if isinstance(nwbfile.read_io, NWBHDF5IO):
        backend_type = "hdf5"
        existing_file = nwbfile.read_io._file
    elif isinstance(nwbfile.read_io, NWBZarrIO):
        backend_type = "zarr"
        existing_file = nwbfile.read_io.file.store

    for _, neurodata_object in nwbfile.objects.items():
        # TODO: edge case of ImageSeries with external file mode?
        if isinstance(neurodata_object, TimeSeries):
            for field_name in ("data", "timestamps"):
                if field_name not in neurodata_object.fields:  # timestamps is optional
                    continue
                if _value_already_written_to_file(
                    value=getattr(neurodata_object, field_name),
                    backend_type=backend_type,
                    existing_file=existing_file,
                ):
                    continue  # skip

                yield _get_dataset_metadata(neurodata_object=neurodata_object, field_name=field_name)
        elif isinstance(neurodata_object, DynamicTable):
            for column_name in getattr(neurodata_object, "colnames"):
                if _value_already_written_to_file(
                    value=getattr(neurodata_object, column_name), backend_type=backend_type, existing_file=existing_file
                ):
                    continue  # skip

                yield _get_dataset_metadata(neurodata_object=neurodata_object[column_name], field_name="data")
