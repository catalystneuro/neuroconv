import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Literal, Optional, Tuple
from warnings import warn

import hdmf
from hdmf.backends.hdf5.h5tools import H5DataIO
from hdmf.backends.io import HDMFIO
from hdmf.data_utils import DataIO
from hdmf_zarr.nwb import NWBZarrIO
from hdmf_zarr.utils import ZarrDataIO
from pynwb import NWBHDF5IO, NWBContainer, NWBFile, TimeSeries
from pynwb.file import Subject

from ..utils import FilePathType, dict_deep_update
from ..utils.dict import DeepDict


@dataclass
class BackendConfig:
    nwb_io: HDMFIO
    data_io: DataIO
    data_io_defaults: Optional[dict]


backend_configs = dict(
    hdf5=BackendConfig(
        nwb_io=NWBHDF5IO,
        data_io=H5DataIO,
        data_io_defaults=dict(compression="gzip", compression_opts=4),
    ),
    zarr=BackendConfig(
        nwb_io=NWBZarrIO,
        data_io=ZarrDataIO,
        data_io_defaults=None,
    ),
)


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
    metadata = dict_deep_update(get_default_nwbfile_metadata(), metadata)
    nwbfile_kwargs = metadata["NWBFile"]
    if "Subject" in metadata:
        # convert ISO 8601 string to datetime
        if "date_of_birth" in metadata["Subject"] and isinstance(metadata["Subject"]["date_of_birth"], str):
            metadata["Subject"]["date_of_birth"] = datetime.fromisoformat(metadata["Subject"]["date_of_birth"])
        nwbfile_kwargs.update(subject=Subject(**metadata["Subject"]))
    # convert ISO 8601 string to datetime
    assert "session_start_time" in nwbfile_kwargs, (
        "'session_start_time' was not found in metadata['NWBFile']! Please add the correct start time of the "
        "session in ISO8601 format (%Y-%m-%dT%H:%M:%S) to this key of the metadata."
    )
    if isinstance(nwbfile_kwargs.get("session_start_time", None), str):
        nwbfile_kwargs["session_start_time"] = datetime.fromisoformat(metadata["NWBFile"]["session_start_time"])
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
    backend: Literal["hdf5", "zarr"] = "hdf5",
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
    overwrite: bool, default: False
        Whether to overwrite the NWBFile if one exists at the nwbfile_path.
        The default is False (append mode).
    verbose: bool, default: True
        If 'nwbfile_path' is specified, informs user after a successful write operation.
    backend : {"hdf5", "zarr"}, default: "hdf5
        Backend to use for loading and/or saving the NWB file.
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
        io = backend_configs[backend].nwb_io(**load_kwargs)
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


def find_configurable_datasets(nwbfile: NWBFile) -> Iterable[Tuple[NWBContainer, str]]:
    """
    Gather object references and fields for configurable datasets. By default, gathers all TimeSeries.data,
    TimeSeries.timestamps, and columns of DynamicTables.

    Parameters
    ----------
    nwbfile: NWBFile

    Returns
    -------

    """
    for obj in nwbfile.objects.values():
        if isinstance(obj, TimeSeries):
            yield obj, "data"
            if getattr(obj, "timestamps"):
                yield obj, "timestamps"
        elif isinstance(obj, hdmf.common.table.DynamicTable):
            for colname in getattr(obj, "colnames"):
                yield obj, colname


def configure_datasets(
    nwbfile: NWBFile,
    backend: Literal["hdf5", "zarr"] = "hdf5",
    dataset_configurations: Optional[Dict[Tuple[NWBContainer, str], dict]] = None,
):
    """
    Apply dataset configurations. Use the default configuration for the backend if not specified. Modifies the
    NWBfile in place.

    Parameters
    ----------
    nwbfile : NWBFile
    backend : {"hdf5", "zarr"}
    dataset_configurations : dict, optional
        Dict of the form `(nwb_container_object, field): data_io_kwargs`
        To specify that no DataIO configuration should be applied, use `(nwb_container_object, field): None`

    """

    data_io = backend_configs[backend].data_io
    for obj, field in find_configurable_datasets(nwbfile):
        if dataset_configurations and (obj, field) in dataset_configurations:
            if dataset_configurations[obj, field] is not None:
                this_config = dataset_configurations[obj, field]
                setattr(obj, field, data_io(data=getattr(obj, field), **this_config))
        if not isinstance(obj, DataIO):
            setattr(obj, field, data_io(data=getattr(obj, field), **backend_configs[backend].data_io_defaults))
