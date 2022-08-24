"""Authors: Heberto Mayorquin, Cody Baker."""
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import FilePathType, OptionalFilePathType, OptionalArrayType


class SpikeGadgetsRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting the SpikeGadgets format."""

    @classmethod
    def get_source_schema(cls):
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"].update(description="Path to SpikeGadgets (.rec) file.")
        source_schema["properties"]["probe_file_path"].update(
            description="Optional path to a probe (.prb) file describing electrode features."
        )
        return source_schema

    def __init__(
        self,
        file_path: FilePathType,
        gains: OptionalArrayType = None,
        probe_file_path: OptionalFilePathType = None,
        verbose: bool = True,
        spikeextractors_backend: bool = False,
    ):
        """
        Recording Interface for the SpikeGadgets Format.

        Parameters
        ----------
        file_path : FilePathType
            Path to the .rec file.
        gains : ArrayType, optional
            The early versions of SpikeGadgest do not automatically record the conversion factor ('gain') of the
            acquisition system. Thus it must be specified either as a single value (if all channels have the same gain)
            or an array of values for each channel.
        probe_file_path : FilePathType, optional
            Set channel properties and geometry through a .prb file.
            See https://github.com/SpikeInterface/probeinterface for more information.
        spikeextractors_backend : bool
            False by default. When True the interface uses the old extractor from the spikextractors library instead
            of a new spikeinterface object.
        """

        if spikeextractors_backend:
            from spikeextractors import SpikeGadgetsRecordingExtractor, load_probe_file
            from spikeinterface.core.old_api_utils import OldToNewRecording

            self.Extractor = SpikeGadgetsRecordingExtractor
            if probe_file_path is not None:
                self.recording_extractor = load_probe_file(
                    recording=self.recording_extractor, probe_file=probe_file_path
                )

            super().__init__(filename=file_path, verbose=verbose)
            self.recording_extractor = OldToNewRecording(oldapi_recording_extractor=self.recording_extractor)
        else:
            super().__init__(file_path=file_path, stream_id="trodes", verbose=verbose)

        self.source_data = dict(file_path=file_path, verbose=verbose)
        if gains is not None:
            if len(gains) == 1:
                gains = [gains[0]] * self.recording_extractor.get_num_channels()
            self.recording_extractor.set_channel_gains(gains=gains)
