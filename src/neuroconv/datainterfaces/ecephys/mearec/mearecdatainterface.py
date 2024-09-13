import json

from pydantic import FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils.json_schema import _NWBMetaDataEncoder


class MEArecRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting MEArec recording data.

    Uses the :py:class:`~spikeinterface.extractors.MEArecRecordingExtractor`.
    """

    display_name = "MEArec Recording"
    associated_suffixes = (".h5",)
    info = "Interface for MEArec recording data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the MEArec .h5 file."
        return source_schema

    def __init__(self, file_path: FilePath, verbose: bool = True, es_key: str = "ElectricalSeries"):
        """
        Load and prepare data for MEArec.

        Parameters
        ----------
        folder_path : str or Path
            Path to the MEArec .h5 file.
        verbose : bool, default: True
            Allows verbose.
        es_key : str, default: "ElectricalSeries"
        """
        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()

        # TODO: improve ProbeInterface integration in our writing procedures
        # probe = self.recording_extractor.get_probe()  # TODO: Need to check if this is always available

        # There is a lot of device/electrode/waveform/sorting configuration information...
        # But no session start time...
        mearec_info = self.recording_extractor.neo_reader.raw_annotations["blocks"][0]["mearec_info"]

        electrode_metadata = dict(mearec_info["electrodes"])
        device_name = electrode_metadata.pop(
            "electrode_name"
        )  # 'electrode_name' seems to be a misnomer for the probe name
        metadata["Ecephys"]["Device"][0].update(
            name=device_name, description="The ecephys device for the MEArec recording."
        )
        for electrode_group_metadata in metadata["Ecephys"]["ElectrodeGroup"]:
            electrode_group_metadata.update(device=device_name)

        recording_metadata = dict(mearec_info["recordings"])
        for unneeded_key in ["fs", "dtype"]:
            recording_metadata.pop(unneeded_key)
        metadata["Ecephys"].update(
            {self.es_key: dict(name=self.es_key, description=json.dumps(recording_metadata, cls=_NWBMetaDataEncoder))}
        )

        return metadata
