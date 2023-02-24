"""Authors: Heberto Mayorquin, Cody Baker."""
from warnings import warn
from typing import Optional

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import FilePathType, ArrayType


class SpikeGadgetsRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting data in the SpikeGadgets format.
    Uses :py:class:`~spikeinterface.extractors.SpikeGadgetsRecordingExtractor`."""

    @classmethod
    def get_source_schema(cls):
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"].update(description="Path to SpikeGadgets (.rec) file.")
        return source_schema

    def __init__(
        self,
        file_path: FilePathType,
        gains: Optional[ArrayType] = None,
        verbose: bool = True,
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
        """

        super().__init__(file_path=file_path, stream_id="trodes", verbose=verbose)

        self.source_data = dict(file_path=file_path, verbose=verbose)
        if gains is not None:
            if len(gains) == 1:
                gains = [gains[0]] * self.recording_extractor.get_num_channels()
            self.recording_extractor.set_channel_gains(gains=gains)
