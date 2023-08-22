import json
import uuid
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Optional
from warnings import warn

import jsonschema
from pynwb import NWBHDF5IO, NWBFile
from pynwb.file import Subject

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
