"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path

import numpy as np
from lxml import etree as et
from spikeextractors import RecordingExtractor


def get_xml_file_path(data_file_path: str):
    """
    Infer the xml_file_path from the data_file_path (.dat or .eeg).

    Assumes the two are in the same folder and follow the session_id naming convention.
    """
    session_path = Path(data_file_path).parent
    return str(session_path / f"{session_path.stem}.xml")


def get_xml(xml_file_path: str):
    """Auxiliary function for retrieving root of xml."""
    return et.parse(xml_file_path).getroot()


def safe_find(root: et._Element, key: str, findall: bool = False):
    """Auxiliary function for safe retrieval of single key from next level of lxml tree."""
    if root is not None:
        if findall:
            return root.findall(key)
        else:
            return root.find(key)


def safe_nested_find(root: et._Element, keys: list):
    """Auxiliary function for safe retrieval of keys at multiple depths in lxml tree."""
    for key in keys:
        root = safe_find(root, key)
    if root is not None:
        return root


def get_shank_channels(xml_file_path: str):
    """Auxiliary function for retrieving the list of structured shank-only channels."""
    root = get_xml(xml_file_path)
    channel_groups = safe_find(safe_nested_find(root, ["spikeDetection", "channelGroups"]), "group", findall=True)
    if channel_groups and all([safe_find(group, "channels") is not None for group in channel_groups]):
        shank_channels = [[int(channel.text) for channel in group.find("channels")] for group in channel_groups]
        return shank_channels


def get_channel_groups(xml_file_path: str):
    """Auxiliary function for retrieving a list of groups, each containing a list of channels."""
    root = get_xml(xml_file_path)
    channel_groups = [
        [int(channel.text) for channel in group.findall("channel")]
        for group in root.find("anatomicalDescription").find("channelGroups").findall("group")
    ]
    return channel_groups


def add_recording_extractor_properties(recording_extractor: RecordingExtractor, xml_file_path: str):
    """Automatically add properties to RecordingExtractor object."""
    channel_groups = get_channel_groups(xml_file_path=xml_file_path)
    channel_map = {
        channel_id: idx
        for idx, channel_id in enumerate([channel_id for group in channel_groups for channel_id in group])
    }
    shank_channels = get_shank_channels(xml_file_path=xml_file_path)
    if shank_channels:
        shank_channels = [channel_id for group in shank_channels for channel_id in group]
    group_electrode_numbers = [x for channels in channel_groups for x, _ in enumerate(channels)]
    group_nums = [n + 1 for n, channels in enumerate(channel_groups) for _ in channels]
    group_names = [f"Group{n + 1}" for n in group_nums]
    for channel_id in recording_extractor.get_channel_ids():
        recording_extractor.set_channel_groups(channel_ids=[channel_id], groups=group_nums[channel_map[channel_id]])
        recording_extractor.set_channel_property(
            channel_id=channel_id, property_name="group_name", value=group_names[channel_map[channel_id]]
        )
        recording_extractor.set_channel_property(
            channel_id=channel_id,
            property_name="shank_electrode_number",
            value=group_electrode_numbers[channel_map[channel_id]],
        )
        if shank_channels is not None:
            recording_extractor.set_channel_property(
                channel_id=channel_id, property_name="spike_detection", value=channel_id in shank_channels
            )
