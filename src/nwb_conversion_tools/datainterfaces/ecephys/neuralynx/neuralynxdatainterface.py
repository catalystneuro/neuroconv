"""Authors: Cody Baker and Ben Dichter."""
import warnings
from pathlib import Path
from natsort import natsorted
from dateutil import parser
import json

from spikeextractors import MultiRecordingChannelExtractor, NeuralynxRecordingExtractor

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import FolderPathType
from ....utils.json_schema import dict_deep_update


def parse_header(header):
    header_dict = dict()
    for line in header.split("\n")[1:]:
        if line:
            if line[0] == "-":
                key, val = line[1:].split(" ", 1)
                header_dict[key] = val
    return header_dict


def get_metadata(folder_path: FolderPathType) -> dict:
    """
    Parse the header of one of the .ncs files to get the session start time (without
    timezone) and the session_id.
    Parameters
    ----------
    folder_path: str or Path
    Returns
    -------
    dict
    """
    folder_path = Path(folder_path)
    csc_files = sorted(folder_path.glob("*.[nN]cs"))
    file_path = csc_files[0]
    with file_path.open(encoding="latin1") as file:
        raw_header = file.read(1024)
    header = parse_header(raw_header)
    if header.get("FileVersion") == "3.4":
        return dict(
            session_start_time=parser.parse(header["TimeCreated"]),
            session_id=header["SessionUUID"],
        )
    if header.get("FileVersion", "").startswith("3.3") or header["CheetahRev"].startswith("5.4"):
        open_line = raw_header.split("\n")[2]
        spliced_line = open_line[24:35] + open_line[-13:]
        return dict(session_start_time=parser.parse(spliced_line, dayfirst=False))


def get_filtering(channel_path: FolderPathType) -> str:
    """Get the filtering metadata from an .nsc file.
    Parameters
    ----------
    channel_path: str or Path
        Filepath for an .nsc file
    Returns
    -------
    str:
        json dump of filter parameters. Uses the mu character, which may cause problems
        for downstream things that expect ASCII.
    """
    channel_path = Path(channel_path)
    with open(channel_path, "r", encoding="latin1") as file:
        raw_header = file.read(1024)
    header = parse_header(raw_header)

    return json.dumps(
        {key: val.strip(" ") for key, val in header.items() if key.lower().startswith("dsp")}, ensure_ascii=False
    )


class NeuralynxRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting the Neuralynx format."""

    RX = MultiRecordingChannelExtractor

    def __init__(self, folder_path: FolderPathType):
        self.subset_channels = None
        self.source_data = dict(folder_path=folder_path)
        nsc_files = natsorted([str(x) for x in Path(folder_path).iterdir() if ".ncs" in x.suffixes])
        extractors = [NeuralynxRecordingExtractor(filename=filename, seg_index=0) for filename in nsc_files]
        gains = [extractor.get_channel_gains()[0] for extractor in extractors]
        for extractor in extractors:
            extractor.clear_channel_gains()
        self.recording_extractor = self.RX(extractors)
        self.recording_extractor.set_channel_gains(gains=gains)
        try:
            for i, filename in enumerate(nsc_files):
                self.recording_extractor.set_channel_property(
                    i,
                    "filtering",
                    get_filtering(filename),
                )
        except:
            warnings.warn("filtering could not be extracted.")

    def get_metadata(self):
        new_metadata = dict(NWBFile=get_metadata(self.source_data["folder_path"]))
        return dict_deep_update(super().get_metadata(), new_metadata)