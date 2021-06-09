"""Authors: Cody Baker and Ben Dichter."""
from typing import Optional, Union
from pathlib import Path
import numpy as np 

from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup

from .baserecordingextractorinterface import BaseRecordingExtractorInterface
from ...utils.spike_interface import write_recording
from ...utils.json_schema import (
    get_schema_from_hdmf_class,
    get_base_schema
)

OptionalPathType = Optional[Union[str, Path]]


class BaseLFPExtractorInterface(BaseRecordingExtractorInterface):
    """Primary class for all LFP data interfaces."""

    def get_metadata_schema(self):
        """Compile metadata schema for the RecordingExtractor."""
        metadata_schema = super().get_metadata_schema()

        # Initiate Ecephys metadata
        metadata_schema['properties']['Ecephys'] = get_base_schema(tag='Ecephys')
        metadata_schema['properties']['Ecephys']['required'] = ['Device', 'ElectrodeGroup']
        metadata_schema['properties']['Ecephys']['properties'] = dict(
            Device=dict(
                type="array",
                minItems=1,
                items={"$ref": "#/properties/Ecephys/properties/definitions/Device"}
            ),
            ElectrodeGroup=dict(
                type="array",
                minItems=1,
                items={"$ref": "#/properties/Ecephys/properties/definitions/ElectrodeGroup"}
            )
        )
        # Schema definition for arrays
        metadata_schema['properties']['Ecephys']['properties']["definitions"] = dict(
            Device=get_schema_from_hdmf_class(Device),
            ElectrodeGroup=get_schema_from_hdmf_class(ElectrodeGroup)
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata['Ecephys'] = dict(
            Device=[
                dict(
                    name='Device_ecephys',
                    description='no description'
                )
            ],
            ElectrodeGroup=[
                dict(
                    name=str(group_id),
                    description="no description",
                    location="unknown",
                    device='Device_ecephys'
                )
                for group_id in np.unique(self.recording_extractor.get_channel_groups())
            ],
            ElectricalSeries_lfp=dict(
                name="LFP",
                description="Local field potential signal."
            )
        )
        return metadata

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
        write_recording(
            recording=recording,
            nwbfile=nwbfile,
            metadata=metadata,
            use_times=use_times,
            write_as="lfp",
            es_key="ElectricalSeries_lfp",
            save_path=save_path,
            overwrite=overwrite,
            buffer_mb=buffer_mb
        )
