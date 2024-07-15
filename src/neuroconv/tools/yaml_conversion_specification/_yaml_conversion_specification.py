import os
import sys
from importlib import import_module
from pathlib import Path
from typing import Literal, Optional
from uuid import uuid4

import click
from dandi.metadata import _get_pynwb_metadata
from dandi.organize import create_unique_filenames_from_metadata
from jsonschema import RefResolver, validate
from pydantic import FilePath

from ..data_transfers import automatic_dandi_upload, submit_aws_batch_job
from ...nwbconverter import NWBConverter
from ...utils import FilePathType, FolderPathType, dict_deep_update, load_dict_from_file


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
@click.option(
    "--upload-to-dandiset",
    help="Do you want to upload the result to DANDI? Specify the dandiset ID if so. "
    "Also ensure you have your DANDI_API_KEY set as an environment variable.",
)
@click.option("--overwrite", help="Overwrite an existing NWBFile at the location.", is_flag=True)
def run_conversion_from_yaml_cli(
    specification_file_path: str,
    data_folder_path: Optional[str] = None,
    output_folder_path: Optional[str] = None,
    upload_to_dandiset: Optional[str] = None,
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
        upload_to_dandiset=upload_to_dandiset,
        overwrite=overwrite,
    )


def run_conversion_from_yaml(
    specification_file_path: FilePathType,
    data_folder_path: Optional[FolderPathType] = None,
    output_folder_path: Optional[FolderPathType] = None,
    upload_to_dandiset: Optional[str] = None,
    overwrite: bool = False,
):
    """
    Run conversion to NWB given a yaml specification file.

    Parameters
    ----------
    specification_file_path : FilePathType
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
    # This check is technically a part of the automatic dandi upload, but good to check as early as possible
    # to avoid wasting time.
    if upload_to_dandiset:
        assert os.getenv("DANDI_API_KEY"), (
            "Unable to find environment variable 'DANDI_API_KEY'. "
            "Please retrieve your token from DANDI and set this environment variable."
        )

    if data_folder_path is None:
        data_folder_path = Path(specification_file_path).parent
    if output_folder_path is None:
        output_folder_path = Path(specification_file_path).parent
    else:
        output_folder_path = Path(output_folder_path)
    specification = load_dict_from_file(file_path=specification_file_path)
    schema_folder = Path(__file__).parent.parent.parent / "schemas"
    specification_schema = load_dict_from_file(file_path=schema_folder / "yaml_conversion_specification_schema.json")
    sys_uri_base = "file:/" if sys.platform.startswith("win32") else "file://"
    validate(
        instance=specification,
        schema=specification_schema,
        resolver=RefResolver(base_uri=sys_uri_base + str(schema_folder) + "/", referrer=specification_schema),
    )

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
            nwbfile_name = session.get("nwbfile_name", f"temp_nwbfile_name_{file_counter}").strip(".nwb")
            session_conversion_options = session.get("conversion_options", dict())
            conversion_options = dict()
            for key in converter.data_interface_objects:
                conversion_options[key] = dict(session_conversion_options.get(key, dict()), **global_conversion_options)
            converter.run_conversion(
                nwbfile_path=output_folder_path / f"{nwbfile_name}.nwb",
                metadata=metadata,
                overwrite=overwrite,
                conversion_options=conversion_options,
            )
    # To properly mimic a true dandi organization, the full directory must be populated with NWBFiles.
    all_nwbfile_paths = [nwbfile_path for nwbfile_path in output_folder_path.iterdir() if nwbfile_path.suffix == ".nwb"]
    if any(["temp_nwbfile_name_" in nwbfile_path.stem for nwbfile_path in all_nwbfile_paths]):
        dandi_metadata_list = []
        for nwbfile_path in all_nwbfile_paths:
            dandi_metadata = _get_pynwb_metadata(path=nwbfile_path)
            dandi_metadata.update(path=nwbfile_path)
            dandi_metadata_list.append(dandi_metadata)
        named_dandi_metadata_list = create_unique_filenames_from_metadata(metadata=dandi_metadata_list)

        for named_dandi_metadata in named_dandi_metadata_list:
            if "temp_nwbfile_name_" in named_dandi_metadata["path"].stem:
                dandi_filename = named_dandi_metadata["dandi_filename"].replace(" ", "_")
                assert (
                    dandi_filename != ".nwb"
                ), f"Not enough metadata available to assign name to {str(named_dandi_metadata['path'])}!"
                named_dandi_metadata["path"].rename(str(output_folder_path / dandi_filename))

    if upload_to_dandiset:
        staging = int(upload_to_dandiset) < 100000  # temporary heuristic
        automatic_dandi_upload(dandiset_id=upload_to_dandiset, nwb_folder_path=output_folder_path, staging=staging)


def deploy_conversion_from_yaml_and_upload_to_dandi(  # the 'and upload to DANDI' part should ultimately be embedded in the YAML syntax
    specification_file_path: FilePath,
    efs_name: str,
    dandiset_id: str,
    transfer_method: Literal["rclone"],
    transfer_commands: str,
    transfer_config_file_path: FilePath,
):
    job_name = Path(specification_file_path).stem + "-" + str(uuid4())
    with open(file=specification_file_path) as file:
        yaml_as_string = "".join(file.readlines())  # Loaded as raw string, not as dict

    if transfer_method == "rclone":
        docker_container = "ghcr.io/catalystneuro/neuroconv:with_rclone"
        with open(file=transfer_config_file_path) as file:
            config_as_string = "".join(file.readlines())  # TODO - check newlines are OK cross-platform
        environment_variables = [
            dict(name="CONFIG_STREAM", value=config_as_string),
            dict(name="RCLONE_COMMANDS", value=transfer_commands),
            dict(name="YAML_STREAM", value=yaml_as_string),
            dict(name="DANDI_API_KEY", value=os.environ["DANDI_API_KEY"]),
            dict(name="DANDISET_ID", value=dandiset_id),
        ]
    else:
        raise NotImplementedError(f"The transfer method {transfer_method} is not yet supported!")
    submit_aws_batch_job(
        job_name=job_name,
        docker_container=docker_container,
        efs_name=efs_name,
        environment_variables=environment_variables,
    )  # TODO - setup something here with status tracker table - might have to be on YAML level
