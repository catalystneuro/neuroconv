"""Collection of helper functions related to NWB."""

import importlib
import uuid
import warnings
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from hdmf_zarr import NWBZarrIO
from pydantic import FilePath
from pynwb import NWBHDF5IO, NWBFile
from pynwb.file import Subject

from . import BackendConfiguration, configure_backend, get_default_backend_configuration
from ...utils.dict import DeepDict, load_dict_from_file
from ...utils.json_schema import validate_metadata

BACKEND_NWB_IO = dict(hdf5=NWBHDF5IO, zarr=NWBZarrIO)


def get_module(nwbfile: NWBFile, name: str, description: str = None):
    """
    Check if processing module exists. If not, create it. Then return module.

    Parameters
    ----------
    nwbfile : NWBFile
        The NWB file to check or add the module to.
    name : str
        The name of the processing module.
    description : str, optional
        Description of the module. Only used if creating a new module.

    Returns
    -------
    ProcessingModule
        The existing or newly created processing module.
    """
    if name in nwbfile.processing:
        if description is not None and nwbfile.processing[name].description != description:
            warnings.warn(
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

    Returns
    -------
    DeepDict
        A dictionary containing default metadata values for an NWBFile, including
        session description, identifier, and NeuroConv version information.
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
    """
    Make NWBFile from available metadata.

    Parameters
    ----------
    metadata : dict
        Dictionary containing metadata for creating the NWBFile.
        Must contain an 'NWBFile' key with required fields.

    Returns
    -------
    NWBFile
        A newly created NWBFile object initialized with the provided metadata.
    """
    # Validate metadata
    schema_path = Path(__file__).resolve().parent.parent.parent / "schemas" / "base_metadata_schema.json"
    base_metadata_schema = load_dict_from_file(file_path=schema_path)
    assert metadata is not None, "Metadata is required to create an NWBFile but metadata=None was passed."
    validate_metadata(metadata=metadata, schema=base_metadata_schema)

    nwbfile_kwargs = deepcopy(metadata["NWBFile"])
    # convert ISO 8601 string to datetime
    if isinstance(nwbfile_kwargs.get("session_start_time"), str):
        nwbfile_kwargs["session_start_time"] = datetime.fromisoformat(nwbfile_kwargs["session_start_time"])
    if "session_description" not in nwbfile_kwargs:
        nwbfile_kwargs["session_description"] = "No description."
    if "identifier" not in nwbfile_kwargs:
        nwbfile_kwargs["identifier"] = str(uuid.uuid4())
    if "source_script" not in nwbfile_kwargs:
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


def _attempt_cleanup_of_existing_nwbfile(nwbfile_path: Path) -> None:
    if not nwbfile_path.exists():
        return

    try:
        nwbfile_path.unlink()
    # Windows in particular can encounter errors at this step
    except PermissionError:  # pragma: no cover
        message = f"Unable to remove NWB file located at {nwbfile_path.absolute()}! Please remove it manually."
        warnings.warn(message=message, stacklevel=2)


@contextmanager
def make_or_load_nwbfile(
    nwbfile_path: Optional[FilePath] = None,
    nwbfile: Optional[NWBFile] = None,
    metadata: Optional[dict] = None,
    overwrite: bool = False,
    backend: Literal["hdf5", "zarr"] = "hdf5",
    verbose: bool = False,
):
    """
    Context for automatically handling decision of write vs. append for writing an NWBFile.

    Parameters
    ----------
    nwbfile_path: FilePath
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

    nwbfile_path_is_provided = nwbfile_path is not None
    nwbfile_path_in = Path(nwbfile_path) if nwbfile_path_is_provided else None

    nwbfile_is_provided = nwbfile is not None
    nwbfile_in = nwbfile if nwbfile_is_provided else None

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
    file_initially_exists = nwbfile_path_in.exists() if nwbfile_path_is_provided else False
    append_mode = file_initially_exists and not overwrite
    if nwbfile_path_is_provided:
        load_kwargs.update(path=str(nwbfile_path_in))

        if append_mode:
            load_kwargs.update(mode="r+", load_namespaces=True)

            # Check if the selected backend is the backend of the file in nwfile_path
            backends_that_can_read = [
                backend_name
                for backend_name, backend_io_class in BACKEND_NWB_IO.items()
                if backend_io_class.can_read(path=str(nwbfile_path_in))
            ]
            # Future-proofing: raise an error if more than one backend can read the file
            assert (
                len(backends_that_can_read) <= 1
            ), "More than one backend is capable of reading the file! Please raise an issue describing your file."
            if backend not in backends_that_can_read:
                raise IOError(
                    f"The chosen backend ('{backend}') is unable to read the file! "
                    f"Please select '{backends_that_can_read[0]}' instead."
                )
        else:
            load_kwargs.update(mode="w")

        io = backend_io_class(**load_kwargs)

    read_nwbfile = nwbfile_path_is_provided and append_mode
    create_nwbfile = not read_nwbfile and not nwbfile_is_provided

    nwbfile_loaded_succesfully = True
    nwbfile_written_succesfully = True
    try:
        if nwbfile_is_provided:
            nwbfile = nwbfile_in
        elif read_nwbfile:
            nwbfile = io.read()
        elif create_nwbfile:
            if metadata is None:
                error_msg = "Metadata is required for creating an nwbfile "
                raise ValueError(error_msg)
            default_metadata = get_default_nwbfile_metadata()
            default_metadata.deep_update(metadata)

            nwbfile = make_nwbfile_from_metadata(metadata=metadata)

        yield nwbfile
    except Exception as load_error:
        nwbfile_loaded_succesfully = False
        raise load_error
    finally:
        if nwbfile_path_is_provided and nwbfile_loaded_succesfully:
            try:
                io.write(nwbfile)

                if verbose:
                    print(f"NWB file saved at {nwbfile_path_in}!")
            except Exception as write_error:
                nwbfile_written_succesfully = False
                raise write_error
            finally:
                io.close()
                del io

                if not nwbfile_written_succesfully:
                    _attempt_cleanup_of_existing_nwbfile(nwbfile_path=nwbfile_path_in)
        elif nwbfile_path_is_provided and not nwbfile_loaded_succesfully:
            # The instantiation of the IO object can itself create a file
            _attempt_cleanup_of_existing_nwbfile(nwbfile_path=nwbfile_path_in)

        else:
            # This is the case where nwbfile is provided but not nwbfile_path
            # Note that io never gets created in this case, so no need to close or delete it
            pass

        # Final attempt to cleanup an unintended file creation, just to be sure
        any_load_or_write_error = not nwbfile_loaded_succesfully or not nwbfile_written_succesfully
        file_was_freshly_created = not file_initially_exists and nwbfile_path_is_provided and nwbfile_path_in.exists()
        attempt_to_cleanup = any_load_or_write_error and file_was_freshly_created
        if attempt_to_cleanup:
            _attempt_cleanup_of_existing_nwbfile(nwbfile_path=nwbfile_path_in)


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
    output_filepath: Optional[FilePath] = None,
    nwbfile_path: Optional[FilePath] = None,
    backend: Optional[Literal["hdf5", "zarr"]] = None,
    backend_configuration: Optional[BackendConfiguration] = None,
) -> None:
    """
    Write an NWB file using a specific backend or backend configuration.

    A ``backend`` or a ``backend_configuration`` must be provided. To use the default backend configuration for
    the specified backend, provide only ``backend``. To use a custom backend configuration, provide
    ``backend_configuration``. If both are provided, ``backend`` must match ``backend_configuration.backend``.

    Parameters
    ----------
    nwbfile: NWBFile
    output_filepath: Optional[FilePath], optional. Deprecated
    nwbfile_path: Optional[FilePath], optional
    backend: {"hdf5", "zarr"}, optional
        The type of backend used to create the file. This option uses the default ``backend_configuration`` for the
        specified backend. If no ``backend`` is specified, the ``backend_configuration`` is used.
    backend_configuration: BackendConfiguration, optional
        Specifies the backend type and the chunking and compression parameters of each dataset. If no
        ``backend_configuration`` is specified, the default configuration for the specified ``backend`` is used.

    """

    if nwbfile_path is not None and output_filepath is not None:
        raise ValueError(
            "Both 'output_filepath' and 'nwbfile_path' were specified! " "Please specify only `nwbfile_path`."
        )

    if output_filepath is not None:
        warnings.warn(
            "The 'output_filepath' parameter is deprecated in or after September 2025. " "Use 'nwbfile_path' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        nwbfile_path = output_filepath

    if nwbfile_path is None:
        raise ValueError("The 'nwbfile_path' parameter must be specified.")

    backend = _resolve_backend(backend=backend, backend_configuration=backend_configuration)

    if backend is not None and backend_configuration is None:
        backend_configuration = get_default_backend_configuration(nwbfile, backend=backend)

    if backend_configuration is not None:
        configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    IO = BACKEND_NWB_IO[backend_configuration.backend]

    with IO(nwbfile_path, mode="w") as io:
        io.write(nwbfile)
