from datetime import datetime
from pathlib import Path

from lxml import etree

from neuroconv.utils import FolderPathType


def get_session_start_time(element: etree.Element) -> datetime:
    """
    Get the session start time from the settings.xml file.

    Parameters
    ----------
    element : etree.Element
        The root element of the XML tree.
    """
    date_str = element.findtext("./INFO/DATE")
    if date_str is None:
        raise ValueError("Could not fetch session start time from settings.xml file.")

    session_start_time = datetime.strptime(date_str, "%d %b %Y %H:%M:%S")
    return session_start_time


def read_settings_xml(folder_path: FolderPathType) -> etree.Element:
    """
    Read the settings.xml file from an OpenEphys binary recording folder.
    Returns the root element of the XML tree.

    Parameters
    ----------
    folder_path : FolderPathType
        The path to the folder containing the settings.xml file.
    """
    folder_path = Path(folder_path)
    file_path = next(folder_path.rglob("settings.xml"), None)
    if file_path is None:
        raise FileNotFoundError(f"The settings.xml file not found in '{folder_path}'.")
    if ".xml" not in file_path.suffixes:
        raise ValueError("The file is not an XML file.")
    tree = etree.parse(str(file_path))
    return tree.getroot()
