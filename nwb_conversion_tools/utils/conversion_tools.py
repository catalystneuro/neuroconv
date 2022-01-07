"""Authors: Cody Baker, Alessio Buccino."""
import numpy as np
import uuid
from datetime import datetime
from warnings import warn

from pynwb import NWBFile
from pynwb.file import Subject

from .json_schema import dict_deep_update


def get_module(nwbfile: NWBFile, name: str, description: str = None):
    """Check if processing module exists. If not, create it. Then return module."""
    if name in nwbfile.processing:
        if description is not None and nwbfile.modules[name].description != description:
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
        metadata["NWBFile"]["session_description"] = datetime(1970, 1, 1)

    Proper conversions should override these fields prior to calling NWBConverter.run_conversion()
    """
    metadata = dict(
        NWBFile=dict(
            session_description="no description",
            session_start_time=datetime(1970, 1, 1).isoformat(),
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
    if isinstance(nwbfile_kwargs.get("session_start_time", None), str):
        nwbfile_kwargs["session_start_time"] = datetime.fromisoformat(metadata["NWBFile"]["session_start_time"])
    return NWBFile(**nwbfile_kwargs)


def check_regular_timestamps(ts):
    """Check whether rate should be used instead of timestamps."""
    time_tol_decimals = 9
    uniq_diff_ts = np.unique(np.diff(ts).round(decimals=time_tol_decimals))
    return len(uniq_diff_ts) == 1


def add_devices(nwbfile=None, data_type: str = "Ecephys", metadata: dict = None):
    """
    Adds device information to nwbfile object.
    Will always ensure nwbfile has at least one device, but multiple
    devices within the metadata list will also be created.
    Parameters
    ----------
    nwbfile: NWBFile
        nwb file to which the new device information is to be added
    data_type: str
        Type of data recorded by device. Options:
        - Ecephys (default)
        - Icephys
        - Ophys
        - Behavior
    metadata: dict
        metadata info for constructing the nwb file (optional).
        Should be of the format
            metadata['Ecephys']['Device'] = [
                {
                    'name': my_name,
                    'description': my_description
                },
                ...
            ]
    Missing keys in an element of metadata['Ecephys']['Device'] will be auto-populated with defaults.
    """
    if nwbfile is not None:
        assert isinstance(nwbfile, NWBFile), "'nwbfile' should be of type pynwb.NWBFile"

    assert data_type in [
        "Ecephys",
        "Icephys",
        "Ophys",
        "Behavior",
    ], f"Invalid data_type {data_type} when creating device"

    # Default Device metadata
    defaults = dict(name="Device", description=f"{data_type}. Automatically generated.")

    if metadata is None:
        metadata = dict()

    if data_type not in metadata:
        metadata[data_type] = dict()

    if "Device" not in metadata[data_type]:
        metadata[data_type]["Device"] = [defaults]

    for dev in metadata[data_type]["Device"]:
        if dev.get("name", defaults["name"]) not in nwbfile.devices:
            nwbfile.create_device(**dict(defaults, **dev))