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
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
        metadata_key: str | None = None,
    ):
        """
        Load and prepare data for MEArec.

        Parameters
        ----------
        folder_path : str or Path
            Path to the MEArec .h5 file.
        verbose : bool, default: False
            Allows verbose.
        es_key : str, default: "ElectricalSeries"
        metadata_key : str, optional
            Key that indexes this interface's entries in the dict-based metadata. Defaults to
            ``"mearec_recording"``.
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

        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key, metadata_key=metadata_key)

        if metadata_key is None:
            self.metadata_key = "mearec_recording"

    def get_metadata(self, *, use_new_metadata_format: bool = True) -> DeepDict:
        metadata = super().get_metadata(use_new_metadata_format=use_new_metadata_format)

        # TODO: improve ProbeInterface integration in our writing procedures
        # probe = self.recording_extractor.get_probe()  # TODO: Need to check if this is always available

        # There is a lot of device/electrode/waveform/sorting configuration information...
        # But no session start time...
        mearec_info = self.recording_extractor.neo_reader.raw_annotations["blocks"][0]["mearec_info"]

        electrode_metadata = dict(mearec_info["electrodes"])
        device_name = electrode_metadata.pop(
            "electrode_name"
        )  # 'electrode_name' seems to be a misnomer for the probe name

        recording_metadata = dict(mearec_info["recordings"])
        for unneeded_key in ["fs", "dtype"]:
            recording_metadata.pop(unneeded_key)
        series_description = json.dumps(recording_metadata, cls=_NWBMetaDataEncoder)

        if use_new_metadata_format:
            from ....tools.spikeinterface.spikeinterface import _get_group_name

            # The name is what the file records (``info/electrodes/electrode_name``, the electrode template
            # the simulation used). The old format's "The ecephys device for the MEArec recording."
            # description is not in the file and is dropped rather than replaced.
            device_metadata_key = "mearec_device"
            metadata["Devices"] = {device_metadata_key: dict(name=device_name)}

            channel_group_names = set(_get_group_name(recording=self.recording_extractor).tolist())
            metadata["Ecephys"]["ElectrodeGroups"] = {
                group_name: dict(name=group_name, device_metadata_key=device_metadata_key)
                for group_name in channel_group_names
            }

            # The simulation parameters are what this recording's provenance actually is.
            metadata["Ecephys"]["ElectricalSeries"][self.metadata_key].update(description=series_description)

            return metadata

        metadata["Ecephys"]["Device"][0].update(
            name=device_name, description="The ecephys device for the MEArec recording."
        )
        for electrode_group_metadata in metadata["Ecephys"]["ElectrodeGroup"]:
            electrode_group_metadata.update(device=device_name)

        metadata["Ecephys"].update({self.es_key: dict(name=self.es_key, description=series_description)})

        return metadata
