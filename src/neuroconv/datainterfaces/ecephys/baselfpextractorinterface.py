import warnings
from typing import Literal

from pynwb import NWBFile

from .baserecordingextractorinterface import BaseRecordingExtractorInterface


class BaseLFPExtractorInterface(BaseRecordingExtractorInterface):
    """Primary class for all LFP data interfaces."""

    keywords = BaseRecordingExtractorInterface.keywords + (
        "extracellular electrophysiology",
        "LFP",
        "local field potential",
        "LF",
    )

    def __init__(self, verbose: bool = False, es_key: str = "ElectricalSeriesLFP", **source_data):
        super().__init__(verbose=verbose, es_key=es_key, **source_data)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile | None = None,
        metadata: dict | None = None,
        stub_test: bool = False,
        write_as: Literal["raw", "lfp", "processed"] = "lfp",
        write_electrical_series: bool = True,
        iterator_type: str = "v2",
        iterator_options: dict | None = None,
        iterator_opts: dict | None = None,
    ):
        # Handle deprecated iterator_opts parameter
        if iterator_opts is not None:
            warnings.warn(
                "The 'iterator_opts' parameter is deprecated and will be removed in May 2026 or after. "
                "Use 'iterator_options' instead.",
                FutureWarning,
                stacklevel=2,
            )
            if iterator_options is not None:
                raise ValueError("Cannot specify both 'iterator_opts' and 'iterator_options'. Use 'iterator_options'.")
            iterator_options = iterator_opts

        return super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            stub_test=stub_test,
            write_as=write_as,
            write_electrical_series=write_electrical_series,
            iterator_type=iterator_type,
            iterator_options=iterator_options,
        )
