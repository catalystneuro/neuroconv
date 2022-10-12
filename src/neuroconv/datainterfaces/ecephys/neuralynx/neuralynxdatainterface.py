"""Authors: Heberto Mayorquin, Cody Baker and Ben Dichter and Julia Sprenger."""
import json
import warnings
from pathlib import Path
from typing import List

from natsort import natsorted

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import FolderPathType
from ....utils.json_schema import dict_deep_update


class NeuralynxRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface for converting Neuralynx data. Uses
    :py:class:`~spikeinterface.extractors.NeuralynxRecordingExtractor`."""

    def __init__(self, folder_path: FolderPathType, spikeextractors_backend: bool = False, verbose: bool = True):

        self.ncs_files = natsorted([str(x) for x in Path(folder_path).iterdir() if ".ncs" in x.suffixes])

        if spikeextractors_backend:
            from spikeinterface.core.old_api_utils import OldToNewRecording

            self.initialize_in_spikeextractors(folder_path=folder_path, verbose=verbose)
            self.recording_extractor = OldToNewRecording(oldapi_recording_extractor=self.recording_extractor)
            self.recording_extractor.neo_readers = self.neo_readers
        else:
            super().__init__(folder_path=folder_path, verbose=verbose)

        # General
        self.add_recording_extractor_properties()

    def initialize_in_spikeextractors(self, folder_path, verbose):
        from spikeextractors import MultiRecordingChannelExtractor, NeuralynxRecordingExtractor

        self.Extractor = MultiRecordingChannelExtractor
        self.subset_channels = None
        self.source_data = dict(folder_path=folder_path, verbose=verbose)
        self.verbose = verbose

        # generate extractors for first segments across all files
        recordings = [NeuralynxRecordingExtractor(filename=filename, seg_index=0) for filename in self.ncs_files]

        max_seg = max([r.neo_reader.segment_count(block_index=0) for r in recordings])
        # add extractors for additional segments
        for seg_idx in range(1, max_seg):
            for i, filename in enumerate(self.ncs_files):
                n_seg = recordings[i].neo_reader.segment_count(block_index=0)
                if seg_idx <= n_seg:
                    recordings.append(NeuralynxRecordingExtractor(filename=filename, seg_index=seg_idx))
                else:
                    # Use None as placeholder if the segment does not exist for requested ncs file
                    recordings.append(None)

        self.neo_readers = [r.neo_reader for r in recordings]
        self.recording_extractor = self.Extractor(recordings)

        gains = [recording.get_channel_gains()[0] for recording in recordings]
        for recording in recordings:
            recording.clear_channel_gains()
        self.recording_extractor.set_channel_gains(gains=gains)

    def add_recording_extractor_properties(self):
        if hasattr(self.recording_extractor, "neo_reader"):
            filtering = get_filtering_multi_channel(self.recording_extractor.neo_reader)
        elif hasattr(self.recording_extractor, "neo_readers"):
            filtering = get_filtering_single_channels(self.recording_extractor.neo_readers)
        else:
            raise ValueError("Unable to identify neo readers")

        try:
            self.recording_extractor.set_property(key="filtering", values=filtering)
        except Exception:
            warnings.warn("filtering could not be extracted.")

    def get_metadata(self):
        # extracting general session metadata exemplary from first recording
        if hasattr(self.recording_extractor, "neo_reader"):
            neo_metadata = extract_metadata_single_reader(self.recording_extractor.neo_reader)
        elif hasattr(self.recording_extractor, "neo_readers"):
            neo_metadata = extract_metadata_multi_reader(self.recording_extractor.neo_readers)
        else:
            raise ValueError("Unable to idenfity neo reader")

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


def get_filtering_multi_channel(neo_reader) -> List[str]:
    """
    Get the filtering metadata from neo reader containing a multiple channels.

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


def get_filtering_single_channels(neo_readers) -> str:
    """
    Get the filtering metadata from multiple neo readers containing a
    single channel each

    Parameters
    ----------
    neo_readers: list of NeuralynxRawIO objects
        Neo IOs to extract the filtering metadata from

    Returns
    -------
    list:
        list of (str) json dump of filter parameters of each channel.
         Uses the mu character, which may cause problems
        for downstream things that expect ASCII.
    """
    filter_info = []
    for neo_reader in neo_readers:
        # extracting filter annotations
        neo_annotations = neo_reader.raw_annotations
        # extracting only first signal as Extractor handles only a single stream at a time
        signal_info = neo_annotations["blocks"][0]["segments"][0]["signals"][0]

        signal_annotations = signal_info["__array_annotations__"]
        filter_dict = {k: v for k, v in signal_annotations.items() if k.lower().startswith("dsp")}

        # conversion to string values
        for key, value in filter_dict.items():
            filter_dict[key] = " ".join(value)
        filter_info.append(json.dumps(filter_dict, ensure_ascii=True))

    return filter_info


def extract_metadata_single_reader(neo_reader) -> dict:
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

    # extract common attributes across channels
    common_header = _dict_intersection(headers)

    # reintroduce recording times as these are typically not exactly identical
    # use minimal recording_opened and max recording_closed value
    if "recording_opened" not in common_header and all(["recording_opened" in h for h in headers]):
        common_header["recording_opened"] = min([h["recording_opened"] for h in headers])
    if "recording_closed" not in common_header and all(["recording_closed" in h for h in headers]):
        common_header["recording_closed"] = max([h["recording_closed"] for h in headers])

    return common_header


def extract_metadata_multi_reader(neo_readers) -> dict:
    """
    Extract the session metadata from multiple NeuralynxRawIO object containing
    a single channel each

    Parameters
    ----------
    neo_readers: NeuralynxRawIO objects
        Neo IOs to extract the metadata from

    Returns
    -------
    dict:
        dictionary containing the session metadata across channels
        Uses the mu character, which may cause problems
        for downstream things that expect ASCII.
    """

    # check if neuralynx file header objects are present and use these metadata extraction
    if hasattr(neo_readers[0], "file_headers"):
        headers = [list(reader.file_headers.values())[0] for reader in neo_readers]

    # use metadata provided as array_annotations for each channel (neo version <=0.11.0)
    else:
        neo_annotations = [r.raw_annotations for r in neo_readers]
        headers = [anno["blocks"][0]["segments"][0]["signals"][0]["__array_annotations__"] for anno in neo_annotations]

    common_header = _dict_intersection(headers)
    return common_header


def _dict_intersection(dictionaries):
    """
    Intersect dictionaries and return only common keys and values

    Parameters
    ----------
    dictionaries: list of dictionaries

    Returns
    -------
    dict:
        Dictionary containing key-value pairs common to all input dictionaries
    """
    if len(dictionaries) == 0:
        return {}
    if len(dictionaries) == 1:
        return dictionaries[0]

    common_keys = list(set.intersection(*[set(h.keys()) for h in dictionaries]))
    common_header = {
        k: dictionaries[0][k] for k in common_keys if all([dictionaries[0][k] == h[k] for h in dictionaries])
    }
    return common_header
