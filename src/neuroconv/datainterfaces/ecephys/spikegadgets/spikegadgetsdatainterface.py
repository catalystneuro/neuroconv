from typing import Optional

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import ArrayType, FilePathType


class SpikeGadgetsRecordingInterface(BaseRecordingExtractorInterface):
    """Data interface class for converting data in the SpikeGadgets format.
    Uses :py:class:`~spikeinterface.extractors.SpikeGadgetsRecordingExtractor`."""

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"].update(description="Path to SpikeGadgets (.rec) file.")
        return source_schema

    def __init__(
        self,
        file_path: FilePathType,
        stream_id: str = "trodes",
        gains: Optional[ArrayType] = None,
        verbose: bool = True,
        es_key: str = "ElectricalSeries",
    ):
        """
        Recording Interface for the SpikeGadgets Format.

        Parameters
        ----------
        file_path : FilePathType
            Path to the .rec file.
        gains : array_like, optional
            The early versions of SpikeGadgets do not automatically record the conversion factor ('gain') of the
            acquisition system. Thus it must be specified either as a single value (if all channels have the same gain)
            or an array of values for each channel.
        es_key : str, default: "ElectricalSeries"
        """
        super().__init__(file_path=file_path, stream_id=stream_id, verbose=verbose, es_key=es_key)

        if gains is not None:
            if len(gains) == 1:
                gains = [gains[0]] * self.recording_extractor.get_num_channels()
            self.recording_extractor.set_channel_gains(gains=gains)
