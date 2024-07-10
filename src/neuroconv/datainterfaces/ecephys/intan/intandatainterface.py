import warnings
from typing import Optional

from packaging.version import Version
from pynwb.ecephys import ElectricalSeries

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....tools import get_package_version
from ....utils import FilePathType, get_schema_from_hdmf_class


class IntanRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting Intan data using the

    :py:class:`~spikeinterface.extractors.IntanRecordingExtractor`.
    """

    display_name = "Intan Recording"
    associated_suffixes = (".rhd", ".rhs")
    info = "Interface for Intan recording data."
    stream_id = "0"  # This are the amplifier channels, corresponding to the stream_name 'RHD2000 amplifier channel'

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to either a .rhd or a .rhs file"
        return source_schema

    def __init__(
        self,
        file_path: FilePathType,
        stream_id: Optional[str] = None,
        verbose: bool = True,
        es_key: str = "ElectricalSeries",
        ignore_integrity_checks: bool = False,
    ):
        """
        Load and prepare raw data and corresponding metadata from the Intan format (.rhd or .rhs files).

        Parameters
        ----------
        file_path : FilePathType
            Path to either a rhd or a rhs file
        stream_id : str, optional
            The stream of the data for spikeinterface, "0" by default.
        verbose : bool, default: True
            Verbose
        es_key : str, default: "ElectricalSeries"
        ignore_integrity_checks, bool, default: False.
            If True, data that violates integrity assumptions will be loaded. At the moment the only integrity
            check performed is that timestamps are continuous. If False, an error will be raised if the check fails.
        """

        if stream_id is not None:
            warnings.warn(
                "Use of the 'stream_id' parameter is deprecated and it will be removed after September 2024.",
                DeprecationWarning,
            )
            self.stream_id = stream_id
        else:
            self.stream_id = "0"  # These are the amplifier channels or to the stream_name 'RHD2000 amplifier channel'

        init_kwargs = dict(
            file_path=file_path,
            stream_id=self.stream_id,
            verbose=verbose,
            es_key=es_key,
            all_annotations=True,
        )

        neo_version = get_package_version(name="neo")
        spikeinterface_version = get_package_version(name="spikeinterface")
        if neo_version < Version("0.13.1") or spikeinterface_version < Version("0.100.10"):
            if ignore_integrity_checks:
                warnings.warn(
                    "The 'ignore_integrity_checks' parameter is not supported for neo versions < 0.13.1. "
                    "or spikeinterface versions < 0.101.0.",
                    UserWarning,
                )
        else:
            init_kwargs["ignore_integrity_checks"] = ignore_integrity_checks

        super().__init__(**init_kwargs)

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeriesRaw=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        ecephys_metadata = metadata["Ecephys"]

        # Add device
        device = dict(
            name="Intan",
            description="Intan recording",
            manufacturer="Intan",
        )
        device_list = [device]
        ecephys_metadata.update(Device=device_list)

        # Add electrodes and electrode groups
        ecephys_metadata.update(
            ElectricalSeriesRaw=dict(name="ElectricalSeriesRaw", description="Raw acquisition traces."),
        )

        return metadata
