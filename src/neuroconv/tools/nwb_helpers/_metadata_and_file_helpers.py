"""Collection of helper functions related to NWB."""

import importlib
import uuid
import warnings
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional
from warnings import warn

from hdmf_zarr import NWBZarrIO
from pydantic import FilePath
from pynwb import NWBHDF5IO, NWBFile
from pynwb.file import Subject

from . import BackendConfiguration, configure_backend, get_default_backend_configuration
from ...utils.dict import DeepDict, load_dict_from_file
from ...utils.json_schema import validate_metadata

BACKEND_NWB_IO = dict(hdf5=NWBHDF5IO, zarr=NWBZarrIO)


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

    These standard defaults are::

        metadata["NWBFile"]["session_description"] = "no description"
        metadata["NWBFile"]["identifier"] = str(uuid.uuid4())

    Proper conversions should override these fields prior to calling ``NWBConverter.run_conversion()``
    """
    neuroconv_version = importlib.metadata.version("neuroconv")

    metadata = DeepDict()
    metadata["NWBFile"].deep_update(
        session_description="no description",
        identifier=str(uuid.uuid4()),
        # Add NeuroConv watermark (overridden if going through the GUIDE)
        source_script=f"Created using NeuroConv v{neuroconv_version}",
        source_script_file_name=__file__,  # Required for validation
    )

    return metadata


def make_nwbfile_from_metadata(metadata: dict) -> NWBFile:
    """Make NWBFile from available metadata."""
    # Validate metadata
    schema_path = Path(__file__).resolve().parent.parent.parent / "schemas" / "base_metadata_schema.json"
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
    if "source_scipt" not in nwbfile_kwargs:
        neuroconv_version = importlib.metadata.version("neuroconv")
        nwbfile_kwargs["source_script"] = f"Created using NeuroConv v{neuroconv_version}"
        nwbfile_kwargs["source_script_file_name"] = __file__  # Required for validation

    if "Subject" in metadata:
        nwbfile_kwargs["subject"] = metadata["Subject"]
        # convert ISO 8601 string to datetime
        if "date_of_birth" in nwbfile_kwargs["subject"] and isinstance(nwbfile_kwargs["subject"]["date_of_birth"], str):
            nwbfile_kwargs["subject"]["date_of_birth"] = datetime.fromisoformat(
                nwbfile_kwargs["subject"]["date_of_birth"]
            )
        nwbfile_kwargs["subject"] = Subject(**nwbfile_kwargs["subject"])

    return NWBFile(**nwbfile_kwargs)


def add_device_from_metadata(nwbfile: NWBFile, modality: str = "Ecephys", metadata: Optional[dict] = None):
    """
    Add device information from metadata to NWBFile object.

    Will always ensure nwbfile has at least one device, but multiple
    devices within the metadata list will also be created.

    Parameters
    ----------
    nwbfile: NWBFile
        NWBFile to which the new device information is to be added
    modality: str
        Type of data recorded by device. Options:
        - Ecephys (default)
        - Icephys
        - Ophys
        - Behavior
    metadata: dict
        Metadata info for constructing the NWBFile (optional).
        Should be of the format::

            metadata[modality]['Device'] = [
                {
                    'name': my_name,
                    'description': my_description
                },
                ...
            ]

        Missing keys in an element of ``metadata['Ecephys']['Device']`` will be auto-populated with defaults.
    """
    metadata_copy = deepcopy(metadata) if metadata is not None else dict()

    assert isinstance(nwbfile, NWBFile), "'nwbfile' should be of type pynwb.NWBFile"
    assert modality in [
        "Ecephys",
        "Icephys",
        "Ophys",
        "Behavior",
    ], f"Invalid modality {modality} when creating device."

    defaults = dict(name=f"Device{modality}", description=f"{modality} device. Automatically generated.")

    if modality not in metadata_copy:
        metadata_copy[modality] = dict()
    if "Device" not in metadata_copy[modality]:
        metadata_copy[modality]["Device"] = [defaults]

    for device_metadata in metadata_copy[modality]["Device"]:
        if device_metadata.get("name", defaults["name"]) not in nwbfile.devices:
            nwbfile.create_device(**dict(defaults, **device_metadata))


@contextmanager
def make_or_load_nwbfile(
    nwbfile_path: Optional[FilePath] = None,
    nwbfile: Optional[NWBFile] = None,
    metadata: Optional[dict] = None,
    overwrite: bool = False,
    backend: Literal["hdf5", "zarr"] = "hdf5",
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
    overwrite: bool, default: False
        Whether to overwrite the NWBFile if one exists at the nwbfile_path.
        The default is False (append mode).
    backend : "hdf5" or "zarr", default: "hdf5"
        The type of backend used to create the file.
    verbose: bool, default: True
        If 'nwbfile_path' is specified, informs user after a successful write operation.
    """
    from . import BACKEND_NWB_IO

    nwbfile_path_in = Path(nwbfile_path) if nwbfile_path else None
    backend_io_class = BACKEND_NWB_IO[backend]

    assert not (nwbfile_path is None and nwbfile is None and metadata is None), (
        "You must specify either an 'nwbfile_path', or an in-memory 'nwbfile' object, "
        "or provide the metadata for creating one."
    )
    assert not (overwrite is False and nwbfile_path_in and nwbfile_path_in.exists() and nwbfile is not None), (
        "'nwbfile_path' exists at location, 'overwrite' is False (append mode), but an in-memory 'nwbfile' object was "
        "passed! Cannot reconcile which nwbfile object to write."
    )
    if overwrite is False and backend == "zarr":
        # TODO: remove when https://github.com/hdmf-dev/hdmf-zarr/issues/182 is resolved
        raise NotImplementedError("Appending a Zarr file is not yet supported!")

    load_kwargs = dict()
    success = True
    file_initially_exists = nwbfile_path_in.exists() if nwbfile_path_in is not None else None
    if nwbfile_path_in:
        load_kwargs.update(path=str(nwbfile_path_in))
        if file_initially_exists and not overwrite:
            load_kwargs.update(mode="r+", load_namespaces=True)
        else:
            load_kwargs.update(mode="w")

        backends_that_can_read = [
            backend_name
            for backend_name, backend_io_class in BACKEND_NWB_IO.items()
            if backend_io_class.can_read(path=str(nwbfile_path_in))
        ]
        # Future-proofing: raise an error if more than one backend can read the file
        assert (
            len(backends_that_can_read) <= 1
        ), "More than one backend is capable of reading the file! Please raise an issue describing your file."
        if load_kwargs["mode"] == "r+" and backend not in backends_that_can_read:
            raise IOError(
                f"The chosen backend ('{backend}') is unable to read the file! "
                f"Please select '{backends_that_can_read[0]}' instead."
            )

        io = backend_io_class(**load_kwargs)

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


def _resolve_backend(
    backend: Optional[Literal["hdf5"]] = None,
    backend_configuration: Optional[BackendConfiguration] = None,
) -> Literal["hdf5"]:
    """
    Resolve the backend to use for writing the NWBFile.

    Parameters
    ----------
    backend: {"hdf5"}, optional
    backend_configuration: BackendConfiguration, optional

    Returns
    -------
    backend: {"hdf5"}

    """

    if backend is not None and backend_configuration is not None:
        if backend == backend_configuration.backend:
            warnings.warn(
                f"Both `backend` and `backend_configuration` were specified as type '{backend}'. "
                "To suppress this warning, specify only `backend_configuration`."
            )
        else:
            raise ValueError(
                f"Both `backend` and `backend_configuration` were specified and are conflicting."
                f"{backend=}, {backend_configuration.backend=}."
                "These values must match. To suppress this error, specify only `backend_configuration`."
            )

    if backend is None:
        backend = backend_configuration.backend if backend_configuration is not None else "hdf5"
    return backend


def configure_and_write_nwbfile(
    nwbfile: NWBFile,
    output_filepath: str,
    backend: Optional[Literal["hdf5"]] = None,
    backend_configuration: Optional[BackendConfiguration] = None,
) -> None:
    """
    Write an NWBFile to a file using a specific backend or backend configuration.

    You must provide either a ``backend`` or a ``backend_configuration``.

    If no ``backend_configuration`` is specified, the default configuration for that backend is used.

    Parameters
    ----------
    nwbfile: NWBFile
    output_filepath: str
    backend: {"hdf5"}, default= "hdf5"
    backend_configuration: BackendConfiguration, optional

    """

    backend = _resolve_backend(backend=backend, backend_configuration=backend_configuration)

    if backend is not None and backend_configuration is None:
        backend_configuration = get_default_backend_configuration(nwbfile, backend=backend)

    if backend_configuration is not None:
        configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    IO = BACKEND_NWB_IO[backend_configuration.backend]

    with IO(output_filepath, mode="w") as io:
        io.write(nwbfile)
