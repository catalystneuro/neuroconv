import warnings
from pathlib import Path

from pydantic import FilePath
from pynwb.ecephys import ElectricalSeries

from ._utils import _warn_if_split_siblings_detected
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import DeepDict, get_schema_from_hdmf_class


class IntanRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface for converting Intan amplifier data from .rhd or .rhs files.

    This interface is used for data that comes from the RHD2000/RHS2000 amplifier channels,
    which are the primary neural recording channels.

    If you have other data streams from your Intan system (e.g., analog inputs, auxiliary inputs, DC amplifiers),
    you should use the :py:class:`~neuroconv.datainterfaces.ecephys.intan.intananaloginterface.IntanAnalogInterface`.
    """

    display_name = "Intan Amplifier"
    keywords = ("intan", "amplifier", "rhd", "rhs", "extracellular electrophysiology", "recording")
    associated_suffixes = (".rhd", ".rhs")
    info = "Interface for converting Intan amplifier data."
    stream_id = "0"  # This are the amplifier channels, corresponding to the stream_name 'RHD2000 amplifier channel'

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = (
            "Path to either a .rhd or a .rhs file. "
            "When ``saved_files_are_split=True``, the file's parent directory is treated as the session "
            "folder and all sibling .rhd/.rhs files are concatenated in filename order."
        )
        return source_schema

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import IntanRecordingExtractor

        return IntanRecordingExtractor

    def _initialize_extractor(self, interface_kwargs: dict):
        """Override to add stream_id and dispatch to the split-files extractor when requested."""
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)
        self.extractor_kwargs.pop("es_key", None)
        saved_files_are_split = self.extractor_kwargs.pop("saved_files_are_split", False)
        self.extractor_kwargs["all_annotations"] = True
        self.extractor_kwargs["stream_id"] = self.stream_id

        if saved_files_are_split:
            from spikeinterface.extractors.extractor_classes import (
                IntanSplitFilesRecordingExtractor,
            )

            file_path = Path(self.extractor_kwargs.pop("file_path"))
            self.extractor_kwargs["folder_path"] = file_path.parent
            return IntanSplitFilesRecordingExtractor(**self.extractor_kwargs)

        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    def __init__(
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
        ignore_integrity_checks: bool = False,
        saved_files_are_split: bool = False,
    ):
        """
        Load and prepare raw data and corresponding metadata from the Intan format (.rhd or .rhs files).

        Parameters
        ----------
        file_path : FilePath
            Path to either a rhd or a rhs file. When ``saved_files_are_split=True``, this is
            any single file in the session folder; its parent directory is scanned for siblings.

        verbose : bool, default: False
            Verbose
        es_key : str, default: "ElectricalSeries"
        ignore_integrity_checks : bool, default: False
            If True, data that violates integrity assumptions will be loaded. At the moment the only integrity
            check performed is that timestamps are continuous. If False, an error will be raised if the check fails.
        saved_files_are_split : bool, default: False
            Set to True when the recording was saved using Intan RHX's "new save file every N minutes"
            option, producing several rotated ``.rhd``/``.rhs`` files in one session folder. All sibling
            files in ``file_path.parent`` are concatenated in filename order (Intan's default
            ``{prefix}_YYMMDD_HHMMSS`` naming makes lexicographic order match chronological order).
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "verbose",
                "es_key",
                "ignore_integrity_checks",
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
                f"Passing arguments positionally to IntanRecordingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            verbose = positional_values.get("verbose", verbose)
            es_key = positional_values.get("es_key", es_key)
            ignore_integrity_checks = positional_values.get("ignore_integrity_checks", ignore_integrity_checks)

        self.file_path = Path(file_path)
        self.saved_files_are_split = saved_files_are_split

        if not saved_files_are_split:
            _warn_if_split_siblings_detected(self.file_path, interface_name="IntanRecordingInterface")

        init_kwargs = dict(
            file_path=self.file_path,
            verbose=verbose,
            es_key=es_key,
            ignore_integrity_checks=ignore_integrity_checks,
            saved_files_are_split=saved_files_are_split,
        )

        super().__init__(**init_kwargs)

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeriesRaw=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        ecephys_metadata = metadata["Ecephys"]

        # Add device

        system = self.file_path.suffix  # .rhd or .rhs
        device_description = {".rhd": "RHD Recording System", ".rhs": "RHS Stim/Recording System"}[system]

        intan_device = dict(
            name="Intan",
            description=device_description,
            manufacturer="Intan",
        )
        device_list = [intan_device]
        ecephys_metadata.update(Device=device_list)

        electrode_group_metadata = ecephys_metadata["ElectrodeGroup"]
        for electrode_group in electrode_group_metadata:
            electrode_group["device"] = intan_device["name"]
        # Add electrodes and electrode groups
        ecephys_metadata.update(
            ElectricalSeriesRaw=dict(name="ElectricalSeriesRaw", description="Raw acquisition traces."),
        )

        return metadata
