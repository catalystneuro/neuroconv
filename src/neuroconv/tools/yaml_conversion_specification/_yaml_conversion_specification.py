import json
import os
from importlib import import_module
from pathlib import Path
from typing import Optional

import click
from jsonschema import validate
from pydantic import DirectoryPath, FilePath
from referencing import Registry, Resource

from ..data_transfers import automatic_dandi_upload
from ...nwbconverter import NWBConverter
from ...utils import dict_deep_update, load_dict_from_file


@click.command()
@click.argument("specification-file-path")
@click.option(
    "--data-folder-path",
    help="Path to folder where the source data may be found.",
    type=click.Path(writable=True),
)
@click.option(
    "--output-folder-path",
    default=None,
    help="Path to folder where you want to save the output NWBFile.",
    type=click.Path(writable=True),
)
@click.option("--overwrite", help="Overwrite an existing NWBFile at the location.", is_flag=True)
def run_conversion_from_yaml_cli(
    specification_file_path: str,
    data_folder_path: Optional[str] = None,
    output_folder_path: Optional[str] = None,
    overwrite: bool = False,
):
    """
    Run the tool function 'run_conversion_from_yaml' via the command line.

    specification-file-path :
    Path to the .yml specification file.
    """
    run_conversion_from_yaml(
        specification_file_path=specification_file_path,
        data_folder_path=data_folder_path,
        output_folder_path=output_folder_path,
        overwrite=overwrite,
    )


def run_conversion_from_yaml(
    specification_file_path: FilePath,
    data_folder_path: Optional[DirectoryPath] = None,
    output_folder_path: Optional[DirectoryPath] = None,
    overwrite: bool = False,
) -> None:
    """
    Run conversion to NWB given a yaml specification file.

    Parameters
    ----------
    specification_file_path : FilePath
        File path leading to .yml specification file for NWB conversion.
    data_folder_path : FolderPathType, optional
        Folder path leading to root location of the data files.
        The default is the parent directory of the specification_file_path.
    output_folder_path : FolderPathType, optional
        Folder path leading to the desired output location of the .nwb files.
        The default is the parent directory of the specification_file_path.
    overwrite : bool, default: False
        If True, replaces any existing NWBFile at the nwbfile_path location, if save_to_file is True.
        If False, appends the existing NWBFile at the nwbfile_path location, if save_to_file is True.
    """
    from dandi.organize import create_unique_filenames_from_metadata
    from dandi.pynwb_utils import _get_pynwb_metadata

    if data_folder_path is None:
        data_folder_path = Path(specification_file_path).parent
    else:
        data_folder_path = Path(data_folder_path)
        data_folder_path.mkdir(exist_ok=True)

    if output_folder_path is None:
        output_folder_path = specification_file_path.parent
    else:
        output_folder_path = Path(output_folder_path)
        output_folder_path.mkdir(exist_ok=True)

    specification = load_dict_from_file(file_path=specification_file_path)
    schema_folder = Path(__file__).parent.parent.parent / "schemas"

    # Load all required schemas
    specification_schema = load_dict_from_file(file_path=schema_folder / "yaml_conversion_specification_schema.json")
    metadata_schema = load_dict_from_file(file_path=schema_folder / "metadata_schema.json")

    # The yaml specification references the metadata schema, so we need to load it into the registry
    registry = Registry().with_resource("metadata_schema.json", Resource.from_contents(metadata_schema))

    # Validate using the registry
    validate(
        instance=specification,
        schema=specification_schema,
        registry=registry,
    )

    upload_to_dandiset = "upload_to_dandiset" in specification
    if upload_to_dandiset and "DANDI_API_KEY" not in os.environ:
        message = (
            "The 'upload_to_dandiset' prompt was found in the YAML specification, "
            "but the environment variable 'DANDI_API_KEY' was not set."
        )
        raise ValueError(message)

    global_metadata = specification.get("metadata", dict())
    global_conversion_options = specification.get("conversion_options", dict())
    data_interfaces_spec = specification.get("data_interfaces")
    data_interfaces_module = import_module(name=".datainterfaces", package="neuroconv")
    data_interface_classes = {key: getattr(data_interfaces_module, name) for key, name in data_interfaces_spec.items()}

    CustomNWBConverter = type(
        "CustomNWBConverter", (NWBConverter,), dict(data_interface_classes=data_interface_classes)
    )

    file_counter = 0
    for experiment in specification["experiments"].values():
        experiment_metadata = experiment.get("metadata", dict())
        for session in experiment["sessions"]:
            file_counter += 1

            source_data = session["source_data"]
            for interface_name, interface_source_data in session["source_data"].items():
                for key, value in interface_source_data.items():
                    if key == "file_paths":
                        source_data[interface_name].update({key: [str(Path(data_folder_path) / x) for x in value]})
                    elif key in ("file_path", "folder_path"):
                        source_data[interface_name].update({key: str(Path(data_folder_path) / value)})

            converter = CustomNWBConverter(source_data=source_data)

            metadata = converter.get_metadata()
            for metadata_source in [global_metadata, experiment_metadata, session.get("metadata", dict())]:
                metadata = dict_deep_update(metadata, metadata_source)

            session_id = session.get("metadata", dict()).get("NWBFile", dict()).get("session_id", None)
            if upload_to_dandiset and session_id is None:
                message = (
                    "The 'upload_to_dandiset' prompt was found in the YAML specification, "
                    "but the 'session_id' was not found for session with info block: "
                    f"\n\n {json.dumps(obj=session, indent=2)}\n\n"
                    "File intended for DANDI upload must include a session ID."
                )
                raise ValueError(message)

            session_conversion_options = session.get("conversion_options", dict())
            conversion_options = dict()
            for key in converter.data_interface_objects:
                conversion_options[key] = dict(session_conversion_options.get(key, dict()), **global_conversion_options)

            nwbfile_name = session.get("nwbfile_name", f"temp_nwbfile_name_{file_counter}").strip(".nwb")
            converter.run_conversion(
                nwbfile_path=output_folder_path / f"{nwbfile_name}.nwb",
                metadata=metadata,
                overwrite=overwrite,
                conversion_options=conversion_options,
            )

    if upload_to_dandiset:
        dandiset_id = specification["upload_to_dandiset"]
        staging = int(dandiset_id) >= 200_000
        automatic_dandi_upload(
            dandiset_id=dandiset_id,
            nwb_folder_path=output_folder_path,
            staging=staging,
        )

        return None  # We can early return since organization below will occur within the upload step

    # To properly mimic a true dandi organization, the full directory must be populated with NWBFiles.
    all_nwbfile_paths = [nwbfile_path for nwbfile_path in output_folder_path.iterdir() if nwbfile_path.suffix == ".nwb"]
    nwbfile_paths_to_set = [
        nwbfile_path for nwbfile_path in all_nwbfile_paths if "temp_nwbfile_name_" in nwbfile_path.stem
    ]
    if any(nwbfile_paths_to_set):
        dandi_metadata_list = list()
        for nwbfile_path_to_set in nwbfile_paths_to_set:
            dandi_metadata = _get_pynwb_metadata(path=nwbfile_path_to_set)
            dandi_metadata.update(path=nwbfile_path_to_set)
            dandi_metadata_list.append(dandi_metadata)
        dandi_metadata_with_set_paths = create_unique_filenames_from_metadata(metadata=dandi_metadata_list)

        for nwbfile_path_to_set, dandi_metadata_with_set_path in zip(
            nwbfile_paths_to_set, dandi_metadata_with_set_paths
        ):
            dandi_filename = dandi_metadata_with_set_path["dandi_filename"]

            assert (
                dandi_filename != ".nwb"
            ), f"Not enough metadata available to assign name to {str(nwbfile_path_to_set)}!"

            # Rename file on system
            nwbfile_path_to_set.rename(str(output_folder_path / dandi_filename))
