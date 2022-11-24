"""Authors: Cody Baker."""
import json

from pynwb.ecephys import ElectricalSeries

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils.types import FilePathType
from ....utils.json_schema import NWBMetaDataEncoder, get_schema_from_hdmf_class


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

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()

        self.es_key = "ElectricalSeries"
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeries=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()

        # TODO: improve ProbeInterface integration in our writing procedures
        # probe = self.recording_extractor.get_probe()  # TODO: Need to check if this is always available

        # There is a lot of device/electrode/waveform/sorting configuration information...
        # But no session start time...
        mearec_info = self.recording_extractor.neo_reader.raw_annotations["blocks"][0]["mearec_info"]

        electrode_metadata = dict(mearec_info["electrodes"])
        metadata["Ecephys"]["Device"][0].update(
            name=electrode_metadata.pop("electrode_name"), description="The ecephys device for the MEArec recording."
        )

        recording_metadata = dict(mearec_info["recordings"])
        for unneeded_key in ["fs", "dtype"]:
            recording_metadata.pop(unneeded_key)
        metadata["Ecephys"].update(
            {self.es_key: dict(name=self.es_key, description=json.dumps(recording_metadata, cls=NWBMetaDataEncoder))}
        )
        return metadata
