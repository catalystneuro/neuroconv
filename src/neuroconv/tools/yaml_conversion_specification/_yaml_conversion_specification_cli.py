from typing import Optional

import click

from ._yaml_conversion_specification import (
    run_conversion_from_yaml,
    run_ec2_conversion_from_yaml,
)


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


@click.command()
@click.argument("specification-file-path")
@click.option(
    "--upload-to-dandiset-id",
    help=(
        "Do you want to upload the result to DANDI? If so, specify the six-digit Dandiset ID. "
        "Also ensure you have your DANDI_API_KEY set as an environment variable."
    ),
    type=str,
    required=False,
)
@click.option(
    "--update-tracking-table",
    help=(
        "The name of the DynamoDB status tracking table to send a completion update to when the conversion is finished."
    ),
    type=str,
    required=False,
)
@click.option(
    "--tracking-table-submission-id",
    help=(
        "The unique submission ID specifying the row (job) of the DynamoDB status tracking table "
        "to update the status of."
    ),
    type=str,
    required=False,
)
@click.option(
    "--efs-volume-name-to-cleanup",
    help="The name of any associated EFS volume to cleanup upon successful conversion or upload.",
    type=str,
    required=False,
)
def run_ec2_conversion_from_yaml_cli(
    specification_file_path: str,
    upload_to_dandiset: Optional[str] = None,
    update_tracking_table: Optional[str] = None,
    tracking_table_submission_id: Optional[str] = None,
    efs_volume_name_to_cleanup: Optional[str] = None,
):
    """Run the tool function `run_ec2_conversion_from_yaml` via the command line."""
    run_ec2_conversion_from_yaml(
        specification_file_path=specification_file_path,
        upload_to_dandiset=upload_to_dandiset,
        update_tracking_table=update_tracking_table,
        tracking_table_submission_id=tracking_table_submission_id,
        efs_volume_name_to_cleanup=efs_volume_name_to_cleanup,
    )
