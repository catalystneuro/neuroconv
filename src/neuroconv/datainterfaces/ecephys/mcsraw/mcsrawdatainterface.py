import warnings

from pydantic import FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class MCSRawRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting MCSRaw data.

    Uses the :py:func:`~spikeinterface.extractors.read_mcsraw` reader from SpikeInterface.
    """

    display_name = "MCSRaw Recording"
    associated_suffixes = (".raw",)
    info = "Interface for MCSRaw recording data."

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import MCSRawRecordingExtractor

        return MCSRawRecordingExtractor

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the .raw file."
        return source_schema

    def __init__(
        self, file_path: FilePath, *args, verbose: bool = False, es_key: str = "ElectricalSeries"
    ):  # TODO: change to * (keyword only) on or after August 2026
        """
        Load and prepare data for MCSRaw.

        Parameters
        ----------
        file_path: string or Path
            Path to the .raw file.
        verbose: bool, default: True
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
                f"Passing arguments positionally to MCSRawRecordingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            verbose = positional_values.get("verbose", verbose)
            es_key = positional_values.get("es_key", es_key)

        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key)
