import warnings
from datetime import datetime
from warnings import warn

from pydantic import DirectoryPath, validate_call

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import DeepDict


class OpenEphysLegacyRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface for converting legacy Open Ephys data (.continuous files).

    Uses :py:func:`~spikeinterface.extractors.read_openephys`.
    """

    display_name = "OpenEphys Legacy Recording"
    associated_suffixes = (".continuous", ".openephys", ".xml")
    info = "Interface for converting legacy OpenEphys recording data."

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import (
            OpenEphysLegacyRecordingExtractor,
        )

        return OpenEphysLegacyRecordingExtractor

    @classmethod
    def get_stream_names(cls, folder_path: DirectoryPath) -> list[str]:
        """
        Get the names of available recording streams in the OpenEphys legacy folder.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to directory containing OpenEphys legacy files.

        Returns
        -------
        list of str
            The names of the available recording streams.
        """
        from spikeinterface.extractors.extractor_classes import (
            OpenEphysLegacyRecordingExtractor,
        )

        stream_names, _ = OpenEphysLegacyRecordingExtractor.get_streams(folder_path=folder_path)
        return stream_names

    @classmethod
    def get_source_schema(cls):
        """
        Compile input schema for the RecordingExtractor.

        Returns
        -------
        dict
            The JSON schema for the OpenEphys legacy recording interface source data,
            containing folder path and other configuration parameters. The schema
            inherits from the base recording extractor interface schema.
        """
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to directory containing OpenEphys legacy files."

        return source_schema

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        stream_name: str | None = None,
        block_index: int | None = None,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
    ):
        """
        Initialize reading of OpenEphys legacy recording (.continuous files).


        Parameters
        ----------
        folder_path : DirectoryPath
            Path to OpenEphys directory.
        stream_name : str, optional
            The name of the recording stream.
        block_index : int, optional, default: None
            The index of the block to extract from the data.
        verbose : bool, default: False
        es_key : str, default: "ElectricalSeries"
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "stream_name",
                "block_index",
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
                f"Passing arguments positionally to OpenEphysLegacyRecordingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            stream_name = positional_values.get("stream_name", stream_name)
            block_index = positional_values.get("block_index", block_index)
            verbose = positional_values.get("verbose", verbose)
            es_key = positional_values.get("es_key", es_key)

        available_streams = self.get_stream_names(folder_path=folder_path)
        if len(available_streams) > 1 and stream_name is None:
            raise ValueError(
                "More than one stream is detected! "
                "Please specify which stream you wish to load with the `stream_name` argument. "
                "To see what streams are available, call "
                "`OpenEphysRecordingInterface.get_stream_names(folder_path=...)`."
            )
        if stream_name is not None and stream_name not in available_streams:
            raise ValueError(
                f"The selected stream '{stream_name}' is not in the available streams '{available_streams}'!"
            )

        super().__init__(
            folder_path=folder_path, stream_name=stream_name, block_index=block_index, verbose=verbose, es_key=es_key
        )

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        neo_reader = self.recording_extractor.neo_reader
        block_annotations = neo_reader.raw_annotations.get("blocks", [])
        if block_annotations:
            segment_annotations = block_annotations[0].get("segments", [])
            if segment_annotations:
                expected_date_format = "%d-%b-%Y %H%M%S"
                date_created = segment_annotations[0]["date_created"]
                date_created = date_created.strip("'")
                extracted_date, extracted_timestamp = date_created.split(" ")
                if len(extracted_timestamp) != len("%H%M%S"):
                    warn(
                        "The timestamp for starting time from openephys metadata is ambiguous "
                        f"('{extracted_timestamp}')! Only the date will be auto-populated in metadata. "
                        "Please update the timestamp manually to record this value with the highest known "
                        "temporal resolution."
                    )
                    session_start_time = datetime.strptime(extracted_date, "%d-%b-%Y")
                else:
                    session_start_time = datetime.strptime(date_created, expected_date_format)
                metadata["NWBFile"].update(session_start_time=session_start_time)

        return metadata
