"""Authors: Heberto Mayorquin, Cody Baker, Ben Dichter and Julia Sprenger."""
import json
from typing import List, Dict

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import FolderPathType
from ....utils.json_schema import dict_deep_update


class NeuralynxRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface for converting Neuralynx data. Uses
    :py:class:`~spikeinterface.extractors.NeuralynxRecordingExtractor`."""

    def __init__(self, folder_path: FolderPathType, verbose: bool = True):
        super().__init__(folder_path=folder_path, verbose=verbose)
        neo_reader = self.recording_extractor.neo_reader
        self.recording_extractor = self.recording_extractor.select_segments(segment_indices=0)
        # preserve neo_reader attribute for SelectSegmentRecording
        self.recording_extractor.neo_reader = neo_reader
        self.add_recording_extractor_properties()

    def add_recording_extractor_properties(self):
        filtering = extract_filtering_metadata(self.recording_extractor.neo_reader)
        self.recording_extractor.set_property(key="filtering", values=filtering)

    def get_metadata(self):
        # extracting general session metadata exemplary from first recording
        neo_metadata = extract_neo_header_metadata(self.recording_extractor.neo_reader)

        # remove filter related entries already covered by `add_recording_extractor_properties`
        neo_metadata = {k: v for k, v in neo_metadata.items() if not k.lower().startswith("dsp")}

        # map Neuralynx metadata to NWB
        nwb_metadata = {"NWBFile": {}, "Ecephys": {"Device": []}}
        neuralynx_device = None
        if "SessionUUID" in neo_metadata:
            # note: SessionUUID can not be used as 'identifier' as this requires uuid4
            nwb_metadata["NWBFile"]["session_id"] = neo_metadata.pop("SessionUUID")
        if "recording_opened" in neo_metadata:
            nwb_metadata["NWBFile"]["session_start_time"] = neo_metadata.pop("recording_opened")
        if "AcquisitionSystem" in neo_metadata:
            neuralynx_device = {"name": neo_metadata.pop("AcquisitionSystem")}
        elif "HardwareSubSystemType" in neo_metadata:
            neuralynx_device = {"name": neo_metadata.pop("HardwareSubSystemType")}
        if neuralynx_device is not None:
            if "ApplicationName" in neo_metadata or "ApplicationVersion" in neo_metadata:
                description = (
                    neo_metadata.pop("ApplicationName", "") + " " + str(neo_metadata.pop("ApplicationVersion", ""))
                )
                neuralynx_device["description"] = description
            nwb_metadata["Ecephys"]["Device"].append(neuralynx_device)

        neo_metadata = {k: str(v) for k, v in neo_metadata.items()}
        nwb_metadata["NWBFile"]["notes"] = json.dumps(neo_metadata, ensure_ascii=True)

        return dict_deep_update(super().get_metadata(), nwb_metadata)


class NeuralynxSortingInterface(BaseSortingExtractorInterface):
    def __init__(self, folder_path: FolderPathType, sampling_frequency: float = None, verbose: bool = True):
        """_summary_

        Parameters
        ----------
        folder_path : str, Path
            The path to the folder/directory containing the data files for the session (nse, ntt, nse, nev)
        sampling_frequency : float, optional
            If a specific sampling_frequency is desired it can be set with this argument.
        verbose : bool, optional
            Enables verbosity
        """

        super().__init__(folder_path=folder_path, sampling_frequency=sampling_frequency, verbose=verbose)


def extract_filtering_metadata(neo_reader) -> List[str]:
    """
    Get the filtering metadata from a neo reader containing multiple channels.

    Parameters
    ----------
    neo_reader: NeuralynxRawIO
        Neo IO to extract the filtering metadata from

    Returns
    -------
    list:
        list of (str) json dump of filter parameters of each channel.
         Uses the mu character, which may cause problems
        for downstream things that expect ASCII.
    """
    neo_annotations = neo_reader.raw_annotations

    # extracting infos of each signal (channel)
    filter_info = []
    stream_infos = neo_annotations["blocks"][0]["segments"][0]["signals"]
    # iterate across streams
    for stream_info in stream_infos:
        stream_annotations = stream_info["__array_annotations__"]
        filter_dict = {k: v for k, v in stream_annotations.items() if k.lower().startswith("dsp")}
        # iterate across channels in stream
        for chan_idx in range(len(stream_info["__array_annotations__"]["channel_names"])):
            channel_filter_dict = {k: v[chan_idx] for k, v in filter_dict.items()}
            # conversion to string values
            for key, value in channel_filter_dict.items():
                if not isinstance(value, str):
                    value = " ".join(value)
                channel_filter_dict[key] = value
            filter_info.append(json.dumps(channel_filter_dict, ensure_ascii=True))

    return filter_info


def extract_neo_header_metadata(neo_reader) -> dict:
    """
    Extract the session metadata from a NeuralynxRawIO object

    Parameters
    ----------
    neo_reader: NeuralynxRawIO object
        Neo IO to extract the metadata from

    Returns
    -------
    dict:
        dictionary containing the session metadata across channels
        Uses the mu character, which may cause problems
        for downstream things that expect ASCII.
    """

    # check if neuralynx file header objects are present and use these metadata extraction
    if hasattr(neo_reader, "file_headers"):
        # use only ncs files as only continuous signals are extracted
        headers = [header for filename, header in neo_reader.file_headers.items() if filename.lower().endswith(".ncs")]

    # use metadata provided as array_annotations for each channel (neo version <=0.11.0)
    else:
        headers = []
        neo_annotations = neo_reader.raw_annotations
        for stream_annotations in neo_annotations["blocks"][0]["segments"][0]["signals"]:
            for chan_idx in range(len(stream_annotations["__array_annotations__"]["channel_names"])):
                headers.append({k: v[chan_idx] for k, v in stream_annotations["__array_annotations__"].items()})

    # extract common attributes across channels by preserving only shared header keys and values
    common_header = _dict_intersection(headers)

    # reintroduce recording times as these are typically not exactly identical
    # use minimal recording_opened and maximal recording_closed value
    if "recording_opened" not in common_header and all(["recording_opened" in h for h in headers]):
        common_header["recording_opened"] = min([h["recording_opened"] for h in headers])
    if "recording_closed" not in common_header and all(["recording_closed" in h for h in headers]):
        common_header["recording_closed"] = max([h["recording_closed"] for h in headers])

    return common_header


def _dict_intersection(dict_list: List) -> Dict:
    """
    Intersect dict_list and return only common keys and values
    Parameters
    ----------
    dict_list: list of dicitionaries each representing a header
    Returns
    -------
    dict:
        Dictionary containing key-value pairs common to all input dicitionary_list
    """
    if len(dict_list) == 0:
        return {}

    # Collect keys appearing in all dictionaries
    common_keys = list(set.intersection(*[set(h.keys()) for h in dict_list]))

    # Add values for common keys if the value is identical across all headers (dict_list)
    first_dict = dict_list[0]
    all_dicts_have_same_value_for = lambda key: all([first_dict[key] == dict[key] for dict in dict_list])
    common_header = {key: first_dict[key] for key in common_keys if all_dicts_have_same_value_for(key)}
    return common_header
