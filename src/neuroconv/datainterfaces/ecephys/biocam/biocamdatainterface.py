import warnings

from pydantic import FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class BiocamRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting Biocam data.

    Uses the :py:func:`~spikeinterface.extractors.read_biocam` reader from SpikeInterface.
    """

    display_name = "Biocam Recording"
    associated_suffixes = (".bwr",)
    info = "Interface for Biocam recording data."

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import BiocamRecordingExtractor

        return BiocamRecordingExtractor

    @classmethod
    def get_source_schema(cls) -> dict:
        schema = super().get_source_schema()
        schema["properties"]["file_path"]["description"] = "Path to the .bwr file."
        return schema

    def __init__(
        self, file_path: FilePath, *args, verbose: bool = False, es_key: str = "ElectricalSeries"
    ):  # TODO: change to * (keyword only) on or after August 2026
        """
        Load and prepare data for Biocam.

        Parameters
        ----------
        file_path : string or Path
            Path to the .bwr file.
        verbose : bool, default: False
            Allows verbose.
        es_key: str, default: "ElectricalSeries"
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
                f"Passing arguments positionally to BiocamRecordingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            verbose = positional_values.get("verbose", verbose)
            es_key = positional_values.get("es_key", es_key)

        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key)
