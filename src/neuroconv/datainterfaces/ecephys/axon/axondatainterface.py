import warnings
from datetime import datetime, timedelta
from pathlib import Path
from warnings import warn

from pydantic import FilePath
from pynwb.ecephys import ElectricalSeries

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import DeepDict, get_schema_from_hdmf_class


class AxonRecordingInterface(BaseRecordingExtractorInterface):
    """
    Data interface class for converting extracellular data recorded in Axon Binary Format (ABF) data.

    Uses the :py:func:`~spikeinterface.extractors.read_axon` reader from SpikeInterface.
    """

    display_name = "Axon Recording"
    keywords = BaseRecordingExtractorInterface.keywords + ("axon", "abf")
    associated_suffixes = (".abf",)
    info = "Interface for extracellular data recorded in Axon Binary Format (ABF) recordings."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to an Axon Binary Format (.abf) file"
        return source_schema

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import AxonRecordingExtractor

        return AxonRecordingExtractor

    def __init__(
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        verbose: bool = False,
        es_key: str | None = None,
        metadata_key: str | None = None,
    ):
        """
        Load and prepare raw data and corresponding metadata from the Axon Binary Format (.abf files).

        Parameters
        ----------
        file_path : FilePath
            Path to an Axon Binary Format (.abf) file
        verbose : bool, default: False
            Verbose
        es_key : str, default: "ElectricalSeries"
        metadata_key : str, optional
            Key that indexes this interface's entries in the dict-based metadata. Defaults to
            ``"axon_recording"``.
            The key for the ElectricalSeries in the metadata
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
                f"Passing arguments positionally to AxonRecordingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            verbose = positional_values.get("verbose", verbose)
            es_key = positional_values.get("es_key", es_key)

        self.file_path = Path(file_path)

        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key, metadata_key=metadata_key)

        if metadata_key is None:
            self.metadata_key = "axon_recording"

    def _get_start_datetime(self, neo_reader):
        """
        Get start datetime for ABF file.

        Parameters
        ----------
        neo_reader : neo.io.AxonIO
            The Neo reader object for the ABF file.

        Returns
        -------
        datetime
            The start date and time of the recording.
        """
        if all(k in neo_reader._axon_info for k in ["uFileStartDate", "uFileStartTimeMS"]):
            startDate = str(neo_reader._axon_info["uFileStartDate"])
            startTime = round(neo_reader._axon_info["uFileStartTimeMS"] / 1000)
            startDate = datetime.strptime(startDate, "%Y%m%d")
            startTime = timedelta(seconds=startTime)
            return startDate + startTime
        else:
            warn(
                f"uFileStartDate or uFileStartTimeMS not found in {neo_reader.filename.split('/')[-1]}, datetime for "
                "recordings might be wrongly stored."
            )
            return neo_reader._axon_info["rec_datetime"]

    def _get_metadata_schema_for_old_list_format(self) -> dict:
        metadata_schema = super()._get_metadata_schema_for_old_list_format()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeriesRaw=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self, *, use_new_metadata_format: bool = True) -> DeepDict:
        metadata = super().get_metadata(use_new_metadata_format=use_new_metadata_format)

        # Extract session start time from ABF file using the existing neo_reader
        neo_reader = self.recording_extractor.neo_reader
        session_start_time = self._get_start_datetime(neo_reader)
        session_start_time_str = session_start_time.strftime("%Y-%m-%dT%H:%M:%S%z")
        metadata["NWBFile"].update(session_start_time=session_start_time_str)

        axon_device = dict(
            name="Axon Instruments",
            description="Axon Instruments data acquisition system (pCLAMP/AxoScope)",
            manufacturer="Molecular Devices",
        )
        if use_new_metadata_format:
            from ....tools.spikeinterface.spikeinterface import _get_group_name

            device_metadata_key = "axon_device"
            metadata["Devices"] = {device_metadata_key: axon_device}

            # Link every channel group to the device so it reaches the file: devices are created lazily
            # when an electrode group references them. Only the fields the source carries are emitted;
            # the required description and location are defaulted by the write pipeline.
            channel_group_names = set(_get_group_name(recording=self.recording_extractor).tolist())
            metadata["Ecephys"]["ElectrodeGroups"] = {
                group_name: dict(name=group_name, device_metadata_key=device_metadata_key)
                for group_name in channel_group_names
            }

            metadata["Ecephys"]["ElectricalSeries"][self.metadata_key].update(
                name="ElectricalSeriesRaw", description="Raw acquisition traces from Axon Binary Format file."
            )

            return metadata

        ecephys_metadata = metadata["Ecephys"]
        ecephys_metadata.update(Device=[axon_device])

        # Update electrode groups with device information
        electrode_group_metadata = ecephys_metadata["ElectrodeGroup"]
        for electrode_group in electrode_group_metadata:
            electrode_group["device"] = axon_device["name"]

        # Add electrical series metadata
        ecephys_metadata.update(
            ElectricalSeriesRaw=dict(
                name="ElectricalSeriesRaw", description="Raw acquisition traces from Axon Binary Format file."
            ),
        )

        return metadata
