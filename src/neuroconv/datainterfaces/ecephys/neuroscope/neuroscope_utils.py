"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path
from datetime import datetime
from dateutil import parser

from ....tools import get_package


def get_xml_file_path(data_file_path: str):
    """
    Infer the xml_file_path from the data_file_path (.dat or .eeg).

    Assumes the two are in the same folder and follow the session_id naming convention.
    """
    session_path = Path(data_file_path).parent
    return str(session_path / f"{session_path.stem}.xml")


def get_xml(xml_file_path: str):
    """Auxiliary function for retrieving root of xml."""
    lxml = get_package(package_name="lxml")

    return lxml.etree.parse(xml_file_path).getroot()


def safe_find(root, key: str, findall: bool = False):
    """Auxiliary function for safe retrieval of single key from next level of lxml tree."""
    if root is not None:
        if findall:
            return root.findall(key)
        else:
            return root.find(key)


def safe_nested_find(root, keys: list):
    """Auxiliary function for safe retrieval of keys at multiple depths in lxml tree."""
    for key in keys:
        root = safe_find(root, key)
    if root is not None:
        return root


def get_shank_channels(xml_file_path: str) -> list:
    """
    Retrieve the list of structured shank-only channels.

    These are channels involved into spike detection.
    These are a subset of channels obtained in`get_channel_goups`.

    Returns
    -------
        List reflecting the group structure of the channels.
    """
    root = get_xml(xml_file_path)
    channel_groups = safe_find(safe_nested_find(root, ["spikeDetection", "channelGroups"]), "group", findall=True)
    if channel_groups and all([safe_find(group, "channels") is not None for group in channel_groups]):
        shank_channels = [[int(channel.text) for channel in group.find("channels")] for group in channel_groups]
        return shank_channels


def get_channel_groups(xml_file_path: str) -> list:
    """
    Auxiliary function for retrieving a list of groups, each containing a list of channels.

    These are all of the channels that are connected to the probe.

    Returns
    -------
        List reflecting the group structure of the channels.
    """
    root = get_xml(xml_file_path)
    channel_groups = [
        [int(channel.text) for channel in group.findall("channel")]
        for group in root.find("anatomicalDescription").find("channelGroups").findall("group")
    ]
    return channel_groups


def get_session_start_time(xml_file_path: str) -> datetime:
    """
    Auxiliary function for retrieving the session start tiem from the xml file.

    Returns
    -------
        datetime object describing the start time
    """
    root = get_xml(xml_file_path)
    date_elem = safe_nested_find(root, ["generalInfo", "date"])
    if date_elem is not None:
        return parser.parse(date_elem.text)
