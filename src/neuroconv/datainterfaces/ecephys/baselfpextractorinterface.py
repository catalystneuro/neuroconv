from typing import Literal, Optional

from pynwb import NWBFile

from .baserecordingextractorinterface import BaseRecordingExtractorInterface


class BaseLFPExtractorInterface(BaseRecordingExtractorInterface):
    """Primary class for all LFP data interfaces."""

    keywords = BaseRecordingExtractorInterface.keywords + [
        "extracellular electrophysiology",
        "LFP",
        "local field potential",
        "LF",
    ]

    def __init__(self, verbose: bool = True, es_key: str = "ElectricalSeriesLFP", **source_data):
        super().__init__(verbose=verbose, es_key=es_key, **source_data)

    def add_to_nwbfile(
        self,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        stub_test: bool = False,
        starting_time: Optional[float] = None,
        write_as: Literal["raw", "lfp", "processed"] = "lfp",
        write_electrical_series: bool = True,
        compression: Optional[str] = None,  # TODO: remove on or after March 1, 2024
        compression_opts: Optional[int] = None,  # TODO: remove on or after March 1, 2024
        iterator_type: str = None,  # TODO: remove on or after March 1, 2024
        iterator_opts: Optional[dict] = None,  # TODO: remove on or after March 1, 2024
    ):
        return super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            stub_test=stub_test,
            starting_time=starting_time,
            write_as=write_as,
            write_electrical_series=write_electrical_series,
            compression=compression,  # TODO: remove on or after March 1, 2024
        )
