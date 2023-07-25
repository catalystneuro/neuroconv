"""Common utility functions for the Intan format."""
from pathlib import Path

from ....tools import get_package


def extract_electrode_metadata_with_pyintan(file_path) -> dict:
    pyintan = get_package(package_name="pyintan")

    if ".rhd" in Path(file_path).suffixes:
        intan_file_metadata = pyintan.intan.read_rhd(file_path)[1]
    else:
        intan_file_metadata = pyintan.intan.read_rhs(file_path)[1]

    exclude_chan_types = ["AUX", "ADC", "VDD", "_STIM", "ANALOG"]

    valid_channels = [
        x for x in intan_file_metadata if not any([y in x["native_channel_name"] for y in exclude_chan_types])
    ]

    group_names = [channel["native_channel_name"].split("-")[0] for channel in valid_channels]
    unique_group_names = set(group_names)
    group_electrode_numbers = [channel["native_order"] for channel in valid_channels]
    custom_names = [channel["custom_channel_name"] for channel in valid_channels]

    electrodes_metadata = dict(
        group_names=group_names,
        unique_group_names=unique_group_names,
        group_electrode_numbers=group_electrode_numbers,
        custom_names=custom_names,
    )

    return electrodes_metadata


def extract_electrode_metadata(recording_extractor) -> dict:
    channel_name_array = recording_extractor.get_property("channel_name")

    group_names = [channel.split("-")[0] for channel in channel_name_array]
    unique_group_names = set(group_names)
    group_electrode_numbers = [int(channel.split("-")[1]) for channel in channel_name_array]
    custom_names = list()

    electrodes_metadata = dict(
        group_names=group_names,
        unique_group_names=unique_group_names,
        group_electrode_numbers=group_electrode_numbers,
        custom_names=custom_names,
    )

    return electrodes_metadata
