"""Authors: Cody Baker and Ben Dichter."""
from typing import Optional, Union
from pathlib import Path
from pynwb import NWBFile
from pynwb.ecephys import ElectricalSeries
from warnings import warn

from .baserecordingextractorinterface import BaseRecordingExtractorInterface
from ...utils import get_schema_from_hdmf_class, OptionalFilePathType

OptionalPathType = Optional[Union[str, Path]]


class BaseLFPExtractorInterface(BaseRecordingExtractorInterface):
    """Primary class for all LFP data interfaces."""

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeriesLFP=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata["Ecephys"].update(
            ElectricalSeriesLFP=dict(name="ElectricalSeriesLFP", description="Local field potential signal.")
        )
        return metadata

    def run_conversion(
        self,
        nwbfile_path: OptionalFilePathType = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        stub_test: bool = False,
        starting_time: Optional[float] = None,
        use_times: bool = False,  # To-do to remove, deprecation
        compression_options: Optional[dict] = None,
        iterator_options: Optional[dict] = None,
        compression: Optional[str] = None,  # TODO: remove
        compression_opts: Optional[int] = None,  # TODO: remove
        iterator_type: Optional[str] = None,  # TODO: remove
        iterator_opts: Optional[dict] = None,  # TODO: remove
    ):
        if any([x is not None for x in [compression, compression_opts]]):  # pragma: no cover
            assert compression_options is None, (
                "You may not specify both 'compression' and 'compression_opts' with 'compression_options'! "
                "Please use only 'compression_options'."
            )
            warn(
                message=(
                    "The options 'compression' and 'compression_opts' will soon be deprecated! "
                    "Please use 'compression_options' instead."
                ),
                category=DeprecationWarning,
                stacklevel=2,
            )
            compression_options = dict(
                method=compression if isinstance(compression, str) else "gzip",
                method_options=compression_opts,
            )
        if any([x is not None for x in [iterator_type, iterator_opts]]):  # pragma: no cover
            assert iterator_options is None, (
                "You may not specify both 'iterator_type' and 'iterator_opts' with 'iterator_options'! "
                "Please use only 'iterator_options'."
            )
            warn(
                message=(
                    "The options 'iterator_type' and 'iterator_opts' will soon be deprecated! "
                    "Please use 'iterator_options' instead."
                ),
                category=DeprecationWarning,
                stacklevel=2,
            )
            iterator_options = dict(
                method=iterator_type or "v2",
                method_options=iterator_opts or dict(),
            )

        from ...tools.spikeinterface import write_recording

        compression_options = compression_options or dict(method="gzip")
        iterator_options = iterator_options or dict(method="v2")

        if stub_test or self.subset_channels is not None:
            recording = self.subset_recording(stub_test=stub_test)
        else:
            recording = self.recording_extractor
        write_recording(
            recording=recording,
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            verbose=self.verbose,
            starting_time=starting_time,
            use_times=use_times,
            write_as="lfp",
            es_key="ElectricalSeriesLFP",
            compression_options=compression_options,
            iterator_options=iterator_options,
        )
