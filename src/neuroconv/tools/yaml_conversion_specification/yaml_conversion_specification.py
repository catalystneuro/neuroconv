"""Authors: Cody Baker, Alessio Buccino."""
import sys
from pathlib import Path
from importlib import import_module
from itertools import chain
from jsonschema import validate, RefResolver
from typing import Optional
from warnings import warn

import click
from dandi.organize import create_unique_filenames_from_metadata
from dandi.metadata import _get_pynwb_metadata

from ...nwbconverter import NWBConverter
from ...utils import dict_deep_update, load_dict_from_file, FilePathType, OptionalFolderPathType


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
    specification_file_path: FilePathType,
    data_folder_path: OptionalFolderPathType = None,
    output_folder_path: OptionalFolderPathType = None,
    overwrite: bool = False,
    data_folder: OptionalFolderPathType = None,
    output_folder: OptionalFolderPathType = None,
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
    overwrite : bool, optional
        If True, replaces any existing NWBFile at the nwbfile_path location, if save_to_file is True.
        If False, appends the existing NWBFile at the nwbfile_path location, if save_to_file is True.
        The default is False.
    """
    deprecation_warning_string = (
        "'data_folder' and 'output_folder' keyword arguments are deprecated and will be removed on or before "
        "August 2022! Please use 'data_folder_path' and 'output_folder_path' instead."
    )
    if data_folder is not None:
        assert data_folder_path is None, "Cannot specify both 'data_folder' and 'data_folder_path'. "
        "Please use 'data_folder_path'."
        data_folder_path = data_folder
        warn(deprecation_warning_string)
    if output_folder is not None:
        assert output_folder_path is None, "Cannot specify both 'output_folder' and 'output_folder_path'. "
        "Please use 'output_folder_path'."
        output_folder_path = output_folder
        warn(deprecation_warning_string)

    if data_folder_path is None:
        data_folder_path = Path(specification_file_path).parent
    if output_folder_path is None:
        output_folder_path = Path(specification_file_path).parent
    else:
        output_folder_path = Path(output_folder_path)
    specification = load_dict_from_file(file_path=specification_file_path)
    schema_folder = Path(__file__).parent.parent.parent / "schemas"
    specification_schema = load_dict_from_file(file_path=schema_folder / "yaml_conversion_specification_schema.json")
    sys_uri_base = "file://"
    if sys.platform.startswith("win32"):
        sys_uri_base = "file:/"
    validate(
        instance=specification,
        schema=specification_schema,
        resolver=RefResolver(base_uri=sys_uri_base + str(schema_folder) + "/", referrer=specification_schema),
    )

    global_metadata = specification.get("metadata", dict())
    global_data_interfaces = specification.get("data_interfaces")
    neuroconv_datainterfaces = import_module(name=".datainterfaces", package="neuroconv")
    file_counter = 0
    for experiment in specification["experiments"].values():
        experiment_metadata = experiment.get("metadata", dict())
        experiment_data_interfaces = experiment.get("data_interfaces")
        for session in experiment["sessions"]:
            file_counter += 1
            session_data_interfaces = session.get("data_interfaces")
            data_interface_classes = dict()
            data_interfaces_names_chain = chain(
                *[
                    data_interfaces
                    for data_interfaces in [global_data_interfaces, experiment_data_interfaces, session_data_interfaces]
                    if data_interfaces is not None
                ]
            )
            for data_interface_name in data_interfaces_names_chain:
                data_interface_classes.update(
                    {data_interface_name: getattr(neuroconv_datainterfaces, data_interface_name)}
                )
            CustomNWBConverter = type(
                "CustomNWBConverter", (NWBConverter,), dict(data_interface_classes=data_interface_classes)
            )

            source_data = session["source_data"]
            for interface_name, interface_source_data in session["source_data"].items():
                for key, value in interface_source_data.items():
                    if key == "file_paths":
                        source_data[interface_name].update({key: [str(Path(data_folder_path) / x) for x in value]})
                    else:
                        source_data[interface_name].update({key: str(Path(data_folder_path) / value)})
            converter = CustomNWBConverter(source_data=source_data)
            metadata = converter.get_metadata()
            for metadata_source in [global_metadata, experiment_metadata, session.get("metadata", dict())]:
                metadata = dict_deep_update(metadata, metadata_source)
            nwbfile_name = session.get("nwbfile_name", f"temp_nwbfile_name_{file_counter}").strip(".nwb")
            converter.run_conversion(
                nwbfile_path=output_folder_path / f"{nwbfile_name}.nwb",
                metadata=metadata,
                overwrite=overwrite,
                conversion_options=session.get("conversion_options", dict()),
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
