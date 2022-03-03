"""Authors: Cody Baker and Ben Dichter."""
from typing import Optional, Union
from pathlib import Path
from pynwb import NWBFile
from pynwb.ecephys import ElectricalSeries

from .baserecordingextractorinterface import BaseRecordingExtractorInterface
from ...tools.spikeinterface import write_recording
from ...utils import get_schema_from_hdmf_class, OptionalFilePathType

OptionalPathType = Optional[Union[str, Path]]


class BaseLFPExtractorInterface(BaseRecordingExtractorInterface):
    """Primary class for all LFP data interfaces."""

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeries_lfp=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata["Ecephys"].update(
            ElectricalSeries_lfp=dict(name="ElectricalSeries_lfp", description="Local field potential signal.")
        )
        return metadata

    def run_conversion(
        self,
        nwbfile: NWBFile,
        metadata: dict = None,
        stub_test: bool = False,
        starting_time: Optional[float] = None,
        use_times: bool = False,
        save_path: OptionalFilePathType = None,
        overwrite: bool = False,
        compression: Optional[str] = "gzip",
        compression_opts: Optional[int] = None,
        iterator_type: Optional[str] = None,
        iterator_opts: Optional[dict] = None,
    ):
        """
        Primary function for converting low-pass recording extractor data to nwb.

        Parameters
        ----------
        nwbfile: NWBFile
            nwb file to which the recording information is to be added
        metadata: dict
            metadata info for constructing the nwb file (optional).
            Should be of the format
                metadata['Ecephys']['ElectricalSeries'] = dict(name=my_name, description=my_description)
        starting_time: float (optional)
            Sets the starting time of the ElectricalSeries to a manually set value.
            Increments timestamps if use_times is True.
        use_times: bool
            If True, the times are saved to the nwb file using recording.frame_to_time(). If False (default),
            the sampling rate is used.
        save_path: OptionalFilePathType
            Required if an nwbfile is not passed. Must be the path to the nwbfile
            being appended, otherwise one is created and written.
        overwrite: bool
            If using save_path, whether or not to overwrite the NWBFile if it already exists.
        stub_test: bool, optional (default False)
            If True, will truncate the data to run the conversion faster and take up less memory.
        compression: str (optional, defaults to "gzip")
            Type of compression to use. Valid types are "gzip" and "lzf".
            Set to None to disable all compression.
        compression_opts: int (optional, defaults to 4)
            Only applies to compression="gzip". Controls the level of the GZIP.
        iterator_type: str (optional, defaults to 'v2')
            The type of DataChunkIterator to use.
            'v1' is the original DataChunkIterator of the hdmf data_utils.
            'v2' is the locally developed RecordingExtractorDataChunkIterator, which offers full control over chunking.
        iterator_opts: dict (optional)
            Dictionary of options for the RecordingExtractorDataChunkIterator (iterator_type='v2').
            Valid options are
                buffer_gb : float (optional, defaults to 1 GB)
                    Recommended to be as much free RAM as available). Automatically calculates suitable buffer shape.
                chunk_mb : float (optional, defaults to 1 MB)
                    Should be below 1 MB. Automatically calculates suitable chunk shape.
            If manual specification of buffer_shape and chunk_shape are desired, these may be specified as well.
        """
        if stub_test or self.subset_channels is not None:
            recording = self.subset_recording(stub_test=stub_test)
        else:
            recording = self.recording_extractor
        write_recording(
            recording=recording,
            nwbfile=nwbfile,
            metadata=metadata,
            starting_time=starting_time,
            use_times=use_times,
            write_as="lfp",
            es_key="ElectricalSeries_lfp",
            save_path=save_path,
            overwrite=overwrite,
            compression=compression,
            compression_opts=compression_opts,
            iterator_type=iterator_type,
            iterator_opts=iterator_opts,
        )
