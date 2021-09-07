"""Authors: Cody Baker."""
from pathlib import Path
from natsort import natsorted
from typing import Union

from spikeextractors import MultiRecordingChannelExtractor, NeuralynxRecordingExtractor


from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils.json_schema import get_schema_from_method_signature

PathType = Union[str, Path]


class NeuralynxRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting the Neuralynx format."""

    RX = MultiRecordingChannelExtractor

    @classmethod
    def get_source_schema(cls):
        """Compile input schema for the RecordingExtractor."""
        source_schema = get_schema_from_method_signature(cls.__init__)
        source_schema["properties"]["folder_path"]["format"] = "directory"
        return source_schema

    def __init__(self, folder_path: PathType):
        self.subset_channels = None
        self.source_data = dict(folder_path=folder_path)
        neuralynx_files = natsorted([str(x) for x in Path(folder_path).iterdir() if ".ncs" in x.suffixes])
        extractors = [NeuralynxRecordingExtractor(filename=filename, seg_index=0) for filename in neuralynx_files]
        gains = [extractor.get_channel_gains()[0] for extractor in extractors]
        for extractor in extractors:
            extractor.clear_channel_gains()
        self.recording_extractor = self.RX(extractors)
        self.recording_extractor.set_channel_gains(gains=gains)
