import warnings

from pydantic import DirectoryPath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import DeepDict


class AlphaOmegaRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting AlphaOmega recording data.

    Uses the :py:func:`~spikeinterface.extractors.read_alphaomega` reader from SpikeInterface.
    """

    display_name = "AlphaOmega Recording"
    associated_suffixes = (".mpx",)
    info = "Interface class for converting AlphaOmega recording data."
    stream_id = "RAW"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"]["description"] = "Path to the folder of .mpx files."
        return source_schema

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import (
            AlphaOmegaRecordingExtractor,
        )

        return AlphaOmegaRecordingExtractor

    def _initialize_extractor(self, interface_kwargs: dict):
        """Override to add stream_id parameter."""
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)
        self.extractor_kwargs.pop("es_key", None)
        self.extractor_kwargs["stream_id"] = self.stream_id
        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    def __init__(
        self,
        folder_path: DirectoryPath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
        metadata_key: str | None = None,
    ):
        """
        Load and prepare data for AlphaOmega.

        Parameters
        ----------
        folder_path: string or Path
            Path to the folder of .mpx files.
        verbose: boolean
            Allows verbose.
            Default is False.
        es_key: str, default: "ElectricalSeries"
        metadata_key : str, optional
            Key that indexes this interface's entries in the dict-based metadata. Defaults to
            ``"alpha_omega_recording"``.
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "verbose",
                "es_key",
            ]
            num_positional_args_before_args = 1  # folder_path
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
                f"Passing arguments positionally to AlphaOmegaRecordingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            verbose = positional_values.get("verbose", verbose)
            es_key = positional_values.get("es_key", es_key)

        super().__init__(folder_path=folder_path, verbose=verbose, es_key=es_key, metadata_key=metadata_key)

        if metadata_key is None:
            self.metadata_key = "alpha_omega_recording"

    def get_metadata(self, *, use_new_metadata_format: bool = True) -> DeepDict:
        metadata = super().get_metadata(use_new_metadata_format=use_new_metadata_format)
        annotation = self.recording_extractor.neo_reader.raw_annotations
        metadata["NWBFile"].update(session_start_time=annotation["blocks"][0]["rec_datetime"])
        return metadata
