from datetime import datetime
from pathlib import Path
from warnings import warn

from pydantic import DirectoryPath


def _get_session_start_time(element: "lxml.etree.Element") -> datetime | None:
    """
    Get the session start time from the settings.xml file.
    Returns the session start time as a datetime object.
    When the session start time is not found in the XML, a warning is issued and None is returned.

    Parameters
    ----------
    element : etree.Element
        The root element of the XML tree.
    """
    date_str = element.findtext("./INFO/DATE")
    if date_str is None:
        warn(message="Could not fetch session start time from settings.xml file.", category=UserWarning)
        return None

    session_start_time = datetime.strptime(date_str, "%d %b %Y %H:%M:%S")
    return session_start_time


def _read_settings_xml(folder_path: DirectoryPath) -> "lxml.etree.Element":
    """
    Read the settings.xml file from an OpenEphys binary recording folder.
    Returns the root element of the XML tree.

    Parameters
    ----------
    folder_path : DirectoryPath
        The path to the folder containing the settings.xml file.
    """
    folder_path = Path(folder_path)

    xml_file_paths = list(folder_path.rglob("settings.xml"))
    if not len(xml_file_paths) == 1:
        raise ValueError(
            f"Unable to identify the OpenEphys folder structure! "
            f"Please check that your `folder_path` contains a settings.xml file and sub-folders of the "
            "following form: 'experiment<index>' -> 'recording<index>' -> 'continuous'."
        )
    xml_file_path = xml_file_paths[0]
    from lxml import etree

    tree = etree.parse(str(xml_file_path))
    return tree.getroot()
