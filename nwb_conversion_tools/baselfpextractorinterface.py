"""Authors: Cody Baker and Ben Dichter."""
import spikeextractors as se
from pynwb import NWBFile

from .baserecordingextractorinterface import BaseRecordingExtractorInterface


class BaseLFPExtractorInterface(BaseRecordingExtractorInterface):
    """Primary class for all LFP data interfaces."""

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


    def run_conversion(self, nwbfile: NWBFile, metadata: dict = None, stub_test: bool = False):
        if stub_test or self.subset_channels is not None:
            recording = self.subset_recording(stub_test=stub_test)
        else:
            recording = self.recording_extractor
        se.NwbRecordingExtractor.write_recording(
            recording=recording,
            nwbfile=nwbfile,
            metadata=metadata,
            write_as_lfp=True
        )
