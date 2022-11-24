"""Authors: Cody Baker."""
import json

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface

from ....utils.types import FilePathType
from ....utils.json_schema import NWBMetaDataEncoder


class MEArecRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting MEArec recording data.

    Uses the :py:class:`~spikeinterface.extractors.MEArecRecordingExtractor`.
    """

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        """
        Load and prepare data for MEArec.

        Parameters
        ----------
        folder_path: string or Path
            Path to the MEArec .h5 file.
        verbose: boolean
            Allows verbose.
            Default is True.
        """
        super().__init__(file_path=file_path, verbose=verbose)

    def get_metadata(self):
        metadata = super().get_metadata()

        # TODO: improve ProbeInterface integration in our writing procedures
        # probe = self.recording_extractor.get_probe()  # TODO: Need to check if this is always available

        # There is a lot of device/electrode/waveform/sorting configuration information...
        # But no session start time...
        mearec_info = self.recording_extractor.neo_reader.raw_annotations["blocks"][0]["mearec_info"]

        electrode_metadata = dict(mearec_info["electrodes"])
        metadata["Ecephys"]["Device"][0].update(name=electrode_metadata.pop("electrode_name"))

        recording_metadata = dict(mearec_info["recordings"])
        for unneeded_key in ["fs", "dtype"]:
            recording_metadata.pop(unneeded_key)
        self.es_key = "ElectricalSeries"
        metadata["Ecephys"].update(
            {
                self.es_key: dict(
                    name="ElectricalSeries", description=json.dumps(recording_metadata, cls=NWBMetaDataEncoder)
                )
            }
        )
        return metadata
