"""Authors: Cody Baker and Ben Dichter."""
from abc import ABC
from typing import Optional
import numpy as np

import spikeextractors as se
import spikeinterface as si

from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup

from ...basedatainterface import BaseDataInterface
from ...utils.json_schema import (
    get_schema_from_hdmf_class,
    get_schema_from_method_signature,
    get_base_schema,
    OptionalFilePathType,
)
from ...utils.spike_interface import write_recording


class BaseRecordingExtractorInterface(BaseDataInterface, ABC):
    """Primary class for all RecordingExtractorInterfaces."""

    RX = None

    def __init__(self, **source_data):
        super().__init__(**source_data)
        self.recording_extractor = self.RX(**source_data)
        self.subset_channels = None

    def get_metadata_schema(self):
        """Compile metadata schema for the RecordingExtractor."""
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"] = get_base_schema(tag="Ecephys")
        metadata_schema["properties"]["Ecephys"]["required"] = ["Device", "ElectrodeGroup"]
        metadata_schema["properties"]["Ecephys"]["properties"] = dict(
            Device=dict(type="array", minItems=1, items={"$ref": "#/properties/Ecephys/properties/definitions/Device"}),
            ElectrodeGroup=dict(
                type="array", minItems=1, items={"$ref": "#/properties/Ecephys/properties/definitions/ElectrodeGroup"}
            ),
            Electrodes=dict(
                type="array",
                minItems=0,
                renderForm=False,
                items={"$ref": "#/properties/Ecephys/properties/definitions/Electrodes"},
            ),
        )
        # Schema definition for arrays
        metadata_schema["properties"]["Ecephys"]["properties"]["definitions"] = dict(
            Device=get_schema_from_hdmf_class(Device),
            ElectrodeGroup=get_schema_from_hdmf_class(ElectrodeGroup),
            Electrodes=dict(
                type="object",
                additionalProperties=False,
                required=["name"],
                properties=dict(
                    name=dict(type="string", description="name of this electrodes column"),
                    description=dict(type="string", description="description of this electrodes column"),
                ),
            ),
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata["Ecephys"] = dict(
            Device=[dict(name="Device_ecephys", description="no description")],
            ElectrodeGroup=[
                dict(name=str(group_id), description="no description", location="unknown", device="Device_ecephys")
                for group_id in np.unique(self.recording_extractor.get_channel_groups())
            ],
        )
        return metadata

    def subset_recording(self, stub_test: bool = False):
        """
        Subset a recording extractor according to stub and channel subset options.

        Parameters
        ----------
        stub_test : bool, optional (default False)
        """
        kwargs = dict()

        if stub_test:
            num_frames = 100
            end_frame = min([num_frames, self.recording_extractor.get_num_frames()])
            kwargs.update(end_frame=end_frame)

        if self.subset_channels is not None:
            kwargs.update(channel_ids=self.subset_channels)

        if isinstance(self.recording_extractor, se.RecordingExtractor):
            recording_extractor = se.SubRecordingExtractor(self.recording_extractor, **kwargs)
        elif isinstance(self.recording_extractor, si.BaseRecording):
            recording_extractor = self.recording_extractor.frame_slice(start_frame=0, end_frame=end_frame)
        else:
            raise TypeError(f"{self.recording_extractor} should be either se.RecordingExtractor or si.BaseRecording")

        return recording_extractor

    def run_conversion(
        self,
        nwbfile: NWBFile,
        metadata: dict = None,
        stub_test: bool = False,
        starting_time: Optional[float] = None,
        use_times: bool = False,
        save_path: OptionalFilePathType = None,
        overwrite: bool = False,
        write_as: str = "raw",
        write_electrical_series: bool = True,
        es_key: str = None,
        compression: Optional[str] = "gzip",
        compression_opts: Optional[int] = None,
        iterator_type: Optional[str] = None,
        iterator_opts: Optional[dict] = None,
    ):
        """
        Primary function for converting raw (unprocessed) RecordingExtractor data to the NWB standard.

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
        write_as: str (optional, defaults to 'raw')
            Options: 'raw', 'lfp' or 'processed'
        write_electrical_series: bool (optional)
            If True (default), electrical series are written in acquisition. If False, only device, electrode_groups,
            and electrodes are written to NWB.
        es_key: str (optional)
            Key in metadata dictionary containing metadata info for the specific electrical series
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
            write_as=write_as,
            write_electrical_series=write_electrical_series,
            es_key=es_key,
            save_path=save_path,
            overwrite=overwrite,
            compression=compression,
            compression_opts=compression_opts,
            iterator_type=iterator_type,
            iterator_opts=iterator_opts,
        )
