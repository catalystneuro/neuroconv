"""Authors: Cody Baker and Ben Dichter."""
from typing import Optional, Union
from pathlib import Path
from pynwb import NWBFile
from pynwb.ecephys import ElectricalSeries

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
        compression: Optional[str] = None,
        compression_opts: Optional[int] = None,
        iterator_type: Optional[str] = "v2",
        iterator_opts: Optional[dict] = None,
    ):
        from ...tools.spikeinterface import write_recording

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
            compression=compression,
            compression_opts=compression_opts,
            iterator_type=iterator_type,
            iterator_opts=iterator_opts,
        )
