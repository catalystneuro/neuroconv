"""Authors: Cody Baker, Alessio Buccino."""
import uuid
from datetime import datetime
from warnings import warn
from contextlib import contextmanager
from typing import Optional
from pathlib import Path

from pynwb import NWBFile, NWBHDF5IO
from pynwb.file import Subject

from hdmf.backends.hdf5.h5_utils import H5DataIO


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


def wrap_data_in_H5DataIO(data, maxshape=None, chunks=None, compression=None, compression_opts=None) -> H5DataIO:
    """
    Auxiliar function to wrapp data in a :py:class:`hdmf.backends.hdf5.h5_utils.H5DataIO` class. This is used in
    neuroconv to have a centralized place to check for valid parameter combinations.

    Parameters
    ----------
    data : np.darray, list or iterable, optional
        The data to wrapp
    maxshape : tuple, optional
        Dataset will be resizable up to this shape , by default None
    chunks : bool, tuple, optional
        Chunk shape or True to enable auto-chunking, by default None
    compression : str, bool, optional
        Compression strategy. If a bool is given, then gzip compression will be used by default.
        http://docs.h5py.org/en/latest/high/dataset.html#dataset-compression, by default None
    compression_opts : _type_, optional
        Parameter for compression filter, by default None

    Returns
    -------
    H5DataIO
        The wrapped data in an H5DataIO object.
    """

    valid_options_for_compression = [
        "gzip",
        "lzf",
        None,
        True,
    ]
    assert_msg = "Invalid compression type ({compression})! Choose one of 'gzip', 'lzf', None or True."
    assert compression in valid_options_for_compression, assert_msg

    if compression == "gzip":
        if compression_opts is None:
            compression_opts = 4
        else:
            assert compression_opts in range(
                10
            ), "Compression type is 'gzip', but specified compression_opts is not an integer between 0 and 9!"
    elif compression == "lzf" and compression_opts is not None:
        warn(f"Compression_opts ({compression_opts}) were passed, but compression type is 'lzf'! Ignoring options.")
        compression_opts = None

    wrapped_data = H5DataIO(
        data=data, maxshape=maxshape, chunks=chunks, compression=compression, compression_opts=compression_opts
    )

    return wrapped_data


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
        Whether or not to overwrite the NWBFile if one exists at the nwbfile_path.
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
    if nwbfile_path:
        load_kwargs.update(path=nwbfile_path)
        if nwbfile_path_in.is_file() and not overwrite:
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
    finally:
        if nwbfile_path:
            try:
                io.write(nwbfile)

                if verbose:
                    print(f"NWB file saved at {nwbfile_path}!")
            finally:
                io.close()
