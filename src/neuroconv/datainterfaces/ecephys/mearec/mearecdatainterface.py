import json
import warnings

from pydantic import FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import DeepDict
from ....utils.json_schema import _NWBMetaDataEncoder


class MEArecRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting MEArec recording data.

    Uses the :py:func:`~spikeinterface.extractors.read_mearec` from SpikeInterface.
    """

    display_name = "MEArec Recording"
    associated_suffixes = (".h5",)
    info = "Interface for MEArec recording data."

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import MEArecRecordingExtractor

        return MEArecRecordingExtractor

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the MEArec .h5 file."
        return source_schema

    def __init__(
        self, file_path: FilePath, *args, verbose: bool = False, es_key: str = "ElectricalSeries"
    ):  # TODO: change to * (keyword only) on or after August 2026
        """
        Load and prepare data for MEArec.

        Parameters
        ----------
        folder_path : str or Path
            Path to the MEArec .h5 file.
        verbose : bool, default: False
            Allows verbose.
        es_key : str, default: "ElectricalSeries"
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "verbose",
                "es_key",
            ]
            num_positional_args_before_args = 1  # file_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to MEArecRecordingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            verbose = positional_values.get("verbose", verbose)
            es_key = positional_values.get("es_key", es_key)

        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key)

    def get_metadata(self) -> DeepDict:
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
