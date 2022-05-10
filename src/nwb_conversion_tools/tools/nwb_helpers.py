"""Authors: Cody Baker, Alessio Buccino."""
import uuid
from datetime import datetime
from warnings import warn
from contextlib import contextmanager
from typing import Optional
from pathlib import Path

from pynwb import NWBFile, NWBHDF5IO
from pynwb.file import Subject

from ..utils import dict_deep_update, FilePathType


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


def get_default_nwbfile_metadata():
    """
    Return structure with defaulted metadata values required for a NWBFile.

    These standard defaults are
        metadata["NWBFile"]["session_description"] = "no description"
        metadata["NWBFile"]["session_start_time"] = datetime(1970, 1, 1)
    Proper conversions should override these fields prior to calling NWBConverter.run_conversion()
    """
    metadata = dict(
        NWBFile=dict(
            session_description="no description",
            identifier=str(uuid.uuid4()),
        )
    )
    return metadata


def make_nwbfile_from_metadata(metadata: dict):
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
    nwbfile_path: FilePathType, metadata: Optional[dict] = None, nwbfile: NWBFile = None, overwrite: bool = False
):
    """
    Context for automatically handling decision of write vs. append for writing an NWBFile.

    Parameters
    ----------
    nwbfile_path: FilePathType
        Path for where to write the NWBFile.
    metadata: dict, optional
        Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
    nwbfile: NWBFile, optional
        An in-memory NWBFile object to write to the location.
    overwrite: bool, optional
        Whether nor not to overwrite the NWBFile if one exists at the nwbfile_path.
        The default is False (append mode).
    """
    assert not (overwrite is False and Path(nwbfile_path).exists() and nwbfile is not None), (
        "'nwbfile_path' exists at location, 'overwrite' is False (append mode), but an in-memory 'nwbfile' object was "
        "passed! Cannot reconcile which nwbfile object to write."
    )
    if metadata is not None and nwbfile is not None:
        warn(
            "Passing an in-memory NWBFile object, but also passing metadata for building a fresh NWBFile. "
            "Metadata will be ignored."
        )
    if metadata is not None and overwrite is False and Path(nwbfile_path).exists():
        warn(
            f"Writing to 'nwbfile_path' ({nwbfile_path}) in append mode, but also passing metadata for building a "
            "fresh NWBFile. Metadata will be ignored and the existing file will be appended."
        )

    load_kwargs = dict(path=nwbfile_path)
    if Path(nwbfile_path).is_file() and not overwrite:
        load_kwargs.update(mode="r+", load_namespaces=True)
    else:
        load_kwargs.update(mode="w")
    io = NWBHDF5IO(**load_kwargs)
    try:
        if load_kwargs["mode"] == "r+":
            nwbfile = io.read()
        elif nwbfile is None:
            nwbfile = make_nwbfile_from_metadata(metadata=metadata)
        yield nwbfile
    finally:
        try:
            io.write(nwbfile)
        finally:
            io.close()
