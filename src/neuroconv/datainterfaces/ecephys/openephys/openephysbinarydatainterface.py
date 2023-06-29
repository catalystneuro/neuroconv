from contextlib import redirect_stdout
from io import StringIO
from typing import List, Optional

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import FolderPathType, get_schema_from_method_signature


def _open_with_pyopenephys(folder_path: FolderPathType):
    """
    Defined here to reduce duplication; used twice in the interface below.

    The pyopenephys package has a couple of annoyances, one of which is blanket print statements on file load.
    """
    import pyopenephys

    with redirect_stdout(StringIO()):
        pyopenephys_file = pyopenephys.File(foldername=folder_path)
    return pyopenephys_file


class OpenEphysBinaryRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface for converting binary OpenEphys data (.dat files). Uses
    :py:class:`~spikeinterface.extractors.OpenEphysBinaryRecordingExtractor`."""

    ExtractorName = "OpenEphysBinaryRecordingExtractor"

    @classmethod
    def get_stream_names(cls, folder_path: FolderPathType) -> List[str]:
        from spikeinterface.extractors import OpenEphysBinaryRecordingExtractor

        stream_names, _ = OpenEphysBinaryRecordingExtractor.get_streams(folder_path=folder_path)
        return stream_names

    @classmethod
    def get_source_schema(cls) -> dict:
        """Compile input schema for the RecordingExtractor."""
        source_schema = get_schema_from_method_signature(
            method=cls.__init__, exclude=["recording_id", "experiment_id", "stub_test"]
        )
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to directory containing OpenEphys binary files."
        return source_schema

    def __init__(
        self,
        folder_path: FolderPathType,
        stream_name: Optional[str] = None,
        stub_test: bool = False,
        verbose: bool = True,
        es_key: str = "ElectricalSeries",
    ):
        """
        Initialize reading of OpenEphys binary recording.

        Parameters
        ----------
        folder_path: FolderPathType
            Path to OpenEphys directory.
        stream_name : str, optional
            The name of the recording stream to load; only required if there is more than one stream detected.
            Call `OpenEphysRecordingInterface.get_stream_names(folder_path=...)` to see what streams are available.
        stub_test : bool, default: False
        verbose : bool, default: True
        es_key : str, default: "ElectricalSeries"
        """

        try:
            _open_with_pyopenephys(folder_path=folder_path)
        except Exception as error:
            # Type of error might depend on pyopenephys version and/or platform
            error_case_1 = (
                type(error) == Exception
                and str(error) == "Only 'binary' and 'openephys' format are supported by pyopenephys"
            )
            error_case_2 = type(error) == OSError and "Unique settings file not found in" in str(error)
            if error_case_1 or error_case_2:  # Raise a more informative error instead.
                raise ValueError(
                    "Unable to identify the OpenEphys folder structure! Please check that your `folder_path` contains sub-folders of the "
                    "following form: 'experiment<index>' -> 'recording<index>' -> 'continuous'."
                )
            else:
                raise error

        available_streams = self.get_stream_names(folder_path=folder_path)
        if len(available_streams) > 1 and stream_name is None:
            raise ValueError(
                "More than one stream is detected! Please specify which stream you wish to load with the `stream_name` argument. "
                "To see what streams are available, call `OpenEphysRecordingInterface.get_stream_names(folder_path=...)`."
            )
        if stream_name is not None and stream_name not in available_streams:
            raise ValueError(
                f"The selected stream '{stream_name}' is not in the available streams '{available_streams}'!"
            )

        super().__init__(folder_path=folder_path, stream_name=stream_name, verbose=verbose, es_key=es_key)

        if stub_test:
            self.subset_channels = [0, 1]

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()

        pyopenephys_file = _open_with_pyopenephys(folder_path=self.source_data["folder_path"])
        session_start_time = pyopenephys_file.experiments[0].datetime

        metadata["NWBFile"].update(session_start_time=session_start_time)
        return metadata
