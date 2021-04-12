"""Authors: Cody Baker and Ben Dichter."""
from typing import Optional, Union
from pathlib import Path

import spikeextractors as se
from pynwb import NWBFile

from .baserecordingextractorinterface import BaseRecordingExtractorInterface

OptionalPathType = Optional[Union[str, Path]]


class BaseLFPExtractorInterface(BaseProcessingExtractorInterface):
    """Previous class, for backward compatibility"""

    def get_metadata(self):
        metadata = dict(
            Ecephys=dict(
                LFPElectricalSeries=dict(
                    name="LFP",
                    description="Local field potential signal."
                )
            )
        )

        return metadata


class BaseProcessingExtractorInterface(BaseRecordingExtractorInterface):
    """Primary class for all processed data interfaces."""

    def run_conversion(
      self,
      nwbfile: NWBFile,
      metadata: dict = None,
      stub_test: bool = False,
      use_times: bool = False,
      save_path: OptionalPathType = None,
      overwrite: bool = False,
      buffer_mb: int = 500
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
        use_times: bool
            If True, the times are saved to the nwb file using recording.frame_to_time(). If False (default),
            the sampling rate is used.
        save_path: PathType
            Required if an nwbfile is not passed. Must be the path to the nwbfile
            being appended, otherwise one is created and written.
        overwrite: bool
            If using save_path, whether or not to overwrite the NWBFile if it already exists.
        stub_test: bool, optional (default False)
            If True, will truncate the data to run the conversion faster and take up less memory.
        buffer_mb: int (optional, defaults to 500MB)
            Maximum amount of memory (in MB) to use per iteration of the internal DataChunkIterator.
            Requires trace data in the RecordingExtractor to be a memmap object.
        """
        if stub_test or self.subset_channels is not None:
            recording = self.subset_recording(stub_test=stub_test)
        else:
            recording = self.recording_extractor
        se.NwbRecordingExtractor.write_recording(
            recording=recording,
            nwbfile=nwbfile,
            metadata=metadata,
            use_times=use_times,
            write_as_processed=True,
            save_path=save_path,
            overwrite=overwrite,
            buffer_mb=buffer_mb
        )
