import os
import sys
from importlib import import_module
from pathlib import Path
from typing import Optional

from jsonschema import RefResolver, validate

from ..data_transfers import (
    automatic_dandi_upload,
    delete_efs_volume,
    update_table_status,
)
from ..importing import get_package
from ...nwbconverter import NWBConverter
from ...utils import FilePathType, FolderPathType, dict_deep_update, load_dict_from_file


def run_conversion_from_yaml(
    specification_file_path: FilePathType,
    data_folder_path: Optional[FolderPathType] = None,
    output_folder_path: Optional[FolderPathType] = None,
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
        If True, replaces the existing corresponding NWBFile at the `output_folder_path`.
        If False, appends the existing corresponding NWBFile at the `output_folder_path`.
    """
    from dandi.organize import create_unique_filenames_from_metadata
    from dandi.pynwb_utils import _get_pynwb_metadata

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


def run_ec2_conversion_from_yaml(
    specification_file_path: FilePathType,
    upload_to_dandiset: str,
    update_tracking_table: str,
    tracking_table_submission_id: str,
    efs_volume_name_to_cleanup: str,
):
    """
    Run conversion to NWB given a yaml specification file.

    Parameters
    ----------
    specification_file_path : FilePathType
        File path leading to .yml specification file for NWB conversion.
    upload_to_dandiset : str
        If you wish to upload the resulting NWB file to a particular Dandiset, specify the six-digit ID here.
        When using this feature, the `DANDI_API_KEY` environment variable must be set.
    update_tracking_table : str
        The name of the DynamoDB status tracking table to send a completion update to when the conversion is finished.
    tracking_table_submission_id : str
        The unique submission ID specifying the row (job) of the DynamoDB status tracking table to update the status of.
    efs_volume_name_to_cleanup : str
        The name of any associated EFS volume to cleanup upon successful conversion or upload.
        This is only intended for use when running in EC2 Batch, but is necessary to include here in order to ensure
        synchronicity.
    """
    # Ensure boto3 is installed before beginning procedure
    get_package(package_name="boto3")

    # This check is technically a part of the automatic dandi upload, but good to check as early as possible
    # to avoid wasting time.
    dandi_api_token = os.getenv("DANDI_API_KEY")
    assert dandi_api_token is not None and dandi_api_token != "", (
        "Unable to read environment variable 'DANDI_API_KEY'. "
        "Please retrieve your token from DANDI and set this environment variable."
    )

    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    assert aws_access_key_id is not None and aws_access_key_id != "", (
        "Unable to read environment variable 'AWS_ACCESS_KEY_ID'. "
        "Please create and set AWS credentials if you wish to update a tracking table."
    )
    assert aws_secret_access_key is not None and aws_secret_access_key != "", (
        "Unable to read environment variable 'AWS_SECRET_ACCESS_KEY'. "
        "Please create and set AWS credentials if you wish to update a tracking table."
    )

    if update_tracking_table is not None and tracking_table_submission_id is None:
        raise ValueError(
            f"The table '{update_tracking_table}' was specified to be updated but no submission ID was specified! "
            "Please specify the `tracking_table_submission_id` keyword argument."
        )
    if update_tracking_table is None and tracking_table_submission_id is not None:
        raise ValueError(
            f"The submission ID '{tracking_table_submission_id}' was specified to be updated but no table name was "
            "specified! Please specify the `update_tracking_table` keyword argument."
        )

    # Convert
    run_conversion_from_yaml(specification_file_path=specification_file_path)

    # Upload
    output_folder_path = Path(specification_file_path).parent
    staging = int(upload_to_dandiset) >= 200_000
    automatic_dandi_upload(dandiset_id=upload_to_dandiset, nwb_folder_path=output_folder_path, staging=staging)

    # Update tracker
    update_table_status(
        status_tracker_table_name=update_tracking_table, submission_id=tracking_table_submission_id, status="Uploaded"
    )

    # Cleanup
    delete_efs_volume(efs_volume_name=efs_volume_name_to_cleanup)
