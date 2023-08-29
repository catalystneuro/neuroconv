"""Collection of helper functions related to NWB."""
import json
import uuid
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Tuple, Union, Literal, Dict, Type, Any
from warnings import warn

import h5py
import hdf5plugin
import jsonschema
import numpy as np
import zarr
from hdmf.data_utils import DataIO
from hdmf.utils import get_data_shape
from hdmf_zarr import NWBZarrIO
from pydantic import BaseModel, root_validator
from pynwb import NWBHDF5IO, NWBFile, TimeSeries
from pynwb.base import DynamicTable
from pynwb.file import Subject
from nwbinspector.utils import is_module_installed
from numcodecs.registry import codec_registry

from ..utils import FilePathType, dict_deep_update
from ..utils.dict import DeepDict, load_dict_from_file
from ..utils.json_schema import validate_metadata


def get_module(nwbfile: NWBFile, name: str, description: str = None):
    """Check if processing module exists. If not, create it. Then return module."""
    if name in nwbfile.processing:
        if description is not None and nwbfile.processing[name].description != description:
            warn(
                "Custom description given to get_module does not match existing module description! "
                "Ignoring custom description."
            )
        return nwbfile.processing[name]
    else:
        if description is None:
            description = "No description."
        return nwbfile.create_processing_module(name=name, description=description)


def get_default_nwbfile_metadata() -> DeepDict:
    """
    Return structure with defaulted metadata values required for a NWBFile.

    These standard defaults are
        metadata["NWBFile"]["session_description"] = "no description"
        metadata["NWBFile"]["identifier"] = str(uuid.uuid4())
    Proper conversions should override these fields prior to calling NWBConverter.run_conversion()
    """
    metadata = DeepDict()
    metadata["NWBFile"].deep_update(
        session_description="no description",
        identifier=str(uuid.uuid4()),
    )

    return metadata


def make_nwbfile_from_metadata(metadata: dict) -> NWBFile:
    """Make NWBFile from available metadata."""

    # Validate metadata
    schema_path = Path(__file__).resolve().parent.parent / "schemas/base_metadata_schema.json"
    base_metadata_schema = load_dict_from_file(file_path=schema_path)
    validate_metadata(metadata=metadata, schema=base_metadata_schema)

    nwbfile_kwargs = deepcopy(metadata["NWBFile"])
    # convert ISO 8601 string to datetime
    if isinstance(nwbfile_kwargs.get("session_start_time"), str):
        nwbfile_kwargs["session_start_time"] = datetime.fromisoformat(nwbfile_kwargs["session_start_time"])
    if "session_description" not in nwbfile_kwargs:
        nwbfile_kwargs["session_description"] = "No description."
    if "identifier" not in nwbfile_kwargs:
        nwbfile_kwargs["identifier"] = str(uuid.uuid4())
    if "Subject" in metadata:
        nwbfile_kwargs["subject"] = metadata["Subject"]
        # convert ISO 8601 string to datetime
        if "date_of_birth" in nwbfile_kwargs["subject"] and isinstance(nwbfile_kwargs["subject"]["date_of_birth"], str):
            nwbfile_kwargs["subject"]["date_of_birth"] = datetime.fromisoformat(
                nwbfile_kwargs["subject"]["date_of_birth"]
            )
        nwbfile_kwargs["subject"] = Subject(**nwbfile_kwargs["subject"])

    return NWBFile(**nwbfile_kwargs)


def add_device_from_metadata(nwbfile: NWBFile, modality: str = "Ecephys", metadata: dict = None):
    """
    Add device information from metadata to NWBFile object.

    Will always ensure nwbfile has at least one device, but multiple
    devices within the metadata list will also be created.

    Parameters
    ----------
    nwbfile: NWBFile
        nwb file to which the new device information is to be added
    modality: str
        Type of data recorded by device. Options:
        - Ecephys (default)
        - Icephys
        - Ophys
        - Behavior
    metadata: dict
        Metadata info for constructing the NWBFile (optional).
        Should be of the format
            metadata[modality]['Device'] = [
                {
                    'name': my_name,
                    'description': my_description
                },
                ...
            ]
        Missing keys in an element of metadata['Ecephys']['Device'] will be auto-populated with defaults.
    """
    assert isinstance(nwbfile, NWBFile), "'nwbfile' should be of type pynwb.NWBFile"
    assert modality in [
        "Ecephys",
        "Icephys",
        "Ophys",
        "Behavior",
    ], f"Invalid modality {modality} when creating device."

    defaults = dict(name=f"Device{modality}", description=f"{modality} device. Automatically generated.")

    if metadata is None:
        metadata = dict()
    if modality not in metadata:
        metadata[modality] = dict()
    if "Device" not in metadata[modality]:
        metadata[modality]["Device"] = [defaults]

    for dev in metadata[modality]["Device"]:
        if dev.get("name", defaults["name"]) not in nwbfile.devices:
            nwbfile.create_device(**dict(defaults, **dev))


@contextmanager
def make_or_load_nwbfile(
    nwbfile_path: Optional[FilePathType] = None,
    nwbfile: Optional[NWBFile] = None,
    metadata: Optional[dict] = None,
    overwrite: bool = False,
    verbose: bool = True,
):
    """
    Context for automatically handling decision of write vs. append for writing an NWBFile.

    Parameters
    ----------
    nwbfile_path: FilePathType
        Path for where to write or load (if overwrite=False) the NWBFile.
        If specified, the context will always write to this location.
    nwbfile: NWBFile, optional
        An in-memory NWBFile object to write to the location.
    metadata: dict, optional
        Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
    overwrite: bool, optional
        Whether to overwrite the NWBFile if one exists at the nwbfile_path.
        The default is False (append mode).
    verbose: bool, optional
        If 'nwbfile_path' is specified, informs user after a successful write operation.
        The default is True.
    """
    nwbfile_path_in = Path(nwbfile_path) if nwbfile_path else None
    assert not (nwbfile_path is None and nwbfile is None and metadata is None), (
        "You must specify either an 'nwbfile_path', or an in-memory 'nwbfile' object, "
        "or provide the metadata for creating one."
    )
    assert not (overwrite is False and nwbfile_path_in and nwbfile_path_in.exists() and nwbfile is not None), (
        "'nwbfile_path' exists at location, 'overwrite' is False (append mode), but an in-memory 'nwbfile' object was "
        "passed! Cannot reconcile which nwbfile object to write."
    )

    load_kwargs = dict()
    success = True
    file_initially_exists = nwbfile_path_in.is_file() if nwbfile_path_in is not None else None
    if nwbfile_path_in:
        load_kwargs.update(path=nwbfile_path_in)
        if file_initially_exists and not overwrite:
            load_kwargs.update(mode="r+", load_namespaces=True)
        else:
            load_kwargs.update(mode="w")
        io = NWBHDF5IO(**load_kwargs)
    try:
        if load_kwargs.get("mode", "") == "r+":
            nwbfile = io.read()
        elif nwbfile is None:
            nwbfile = make_nwbfile_from_metadata(metadata=metadata)
        yield nwbfile
    except Exception as e:
        success = False
        raise e
    finally:
        if nwbfile_path_in:
            try:
                if success:
                    io.write(nwbfile)

                    if verbose:
                        print(f"NWB file saved at {nwbfile_path_in}!")
            finally:
                io.close()

                if not success and not file_initially_exists:
                    nwbfile_path_in.unlink()


class Dataset(BaseModel):
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


def _get_dataset_metadata(neurodata_object: Union[TimeSeries, DynamicTable], field_name: str) -> Dataset:
    """Fill in the Dataset model with as many values as can be automatically detected or inferred."""
    field_value = getattr(neurodata_object, field_name)
    if field_value is not None and not isinstance(field_value, DataIO):
        return Dataset(
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


def get_io_datasets(nwbfile: NWBFile) -> Iterable[Dataset]:
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


class DatasetConfiguration(BaseModel):
    """A data model for configruing options about an object that will become a HDF5 or Zarr Dataset in the file."""

    object_id: str
    object_name: str
    parent: str
    field: Literal["data", "timestamps"]
    chunk_shape: Tuple[int, ...]
    buffer_shape: Tuple[int, ...]
    maxshape: Tuple[int, ...]
    compression_method: str
    compression_options: Dict[str, Any]
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


_available_hdf5_filters = set(h5py.filters.decode) - set(("shuffle", "fletcher32", "scaleoffset"))
if is_module_installed(module_name="hdf5plugin"):
    _available_hdf5_filters = _available_hdf5_filters | set(
        (filter_.filter_name for filter_ in hdf5plugin.get_filters())
    )
AVAILABLE_HDF5_COMPRESSION_METHODS = Literal[tuple(_available_hdf5_filters)]


class HDF5DatasetConfiguration(BaseModel):
    """A data model for configruing options about an object that will become a HDF5 Dataset in the file."""

    object_id: str
    object_name: str
    parent: str
    field: Literal["data", "timestamps"]
    chunk_shape: Tuple[int, ...]
    buffer_shape: Tuple[int, ...]
    maxshape: Tuple[int, ...]
    compression_method: AVAILABLE_HDF5_COMPRESSION_METHODS = "gzip"
    # TODO: actually provide better schematic rendering of options. Only support defaults in GUIDE for now
    # Looks like they'll have to be hand-typed however... Can try parsing the google docstrings but no annotation typing
    compression_options: Dict[str, Any]
    dtype: str  # Think about how to constrain/specify this more


_available_zarr_filters = set(codec_registry.keys()) - set(("json2", "pickle"))
AVAILABLE_ZARR_COMPRESSION_METHODS = Literal[tuple(_available_zarr_filters)]


class ZarrDatasetConfiguration(BaseModel):
    """A data model for configruing options about an object that will become a Zarr Dataset in the file."""

    object_id: str
    object_name: str
    parent: str
    field: Literal["data", "timestamps"]
    chunk_shape: Tuple[int, ...]
    buffer_shape: Tuple[int, ...]
    maxshape: Tuple[int, ...]
    filter_methods: Tuple[AVAILABLE_ZARR_COMPRESSION_METHODS, ...]
    filter_options: Tuple[Dict[str, Any]]
    compression_method: AVAILABLE_ZARR_COMPRESSION_METHODS
    # TODO: actually provide better schematic rendering of options. Only support defaults in GUIDE for now
    # Looks like they'll have to be hand-typed however... Can try parsing the google docstrings but no annotation typing
    compression_option: Dict[str, Any]
    dtype: str  # Think about how to constrain/specify this more

    @root_validator()
    def verify_filter_methods_and_options_match(cls, values):
        password = values.get("password")
        confirm_password = values.get("confirm_password")

        if password != confirm_password:
            raise ValueError("The two passwords did not match.")
        return values


class BackendConfiguration(BaseModel):
    """A model for matching collections of DatasetConfigurations specific to a backend with its name and DataIO."""

    backend_type: Literal["hdf5", "zarr"]
    data_io: Type[DataIO]
    dataset_configurations: Iterable[DatasetConfiguration]


def get_default_dataset_configurations(nwbfile: NWBFile) -> Dict[Dataset, DatasetConfiguration]:
    pass  # TODO
