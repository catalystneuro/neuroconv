"""Authors: Cody Baker and Ben Dichter."""
import spikeextractors as se
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup, ElectricalSeries

from .basedatainterface import BaseDataInterface
from .utils import (get_schema_from_method_signature, get_schema_from_hdmf_class,
                    get_metadata_schema)


class BaseRecordingExtractorInterface(BaseDataInterface):
    RX = None

    @classmethod
    def get_input_schema(cls):
        return get_schema_from_method_signature(cls.RX.__init__)

    def __init__(self, **input_args):
        super().__init__(**input_args)
        self.recording_extractor = self.RX(**input_args)

    def get_metadata_schema(self):
        # Initiate empty metadata schema
        metadata_schema = get_metadata_schema()

        # Initiate Ecephys metadata
        metadata_schema['properties']['Ecephys'] = dict(
            Device=get_schema_from_hdmf_class(Device),
            ElectrodeGroup=get_schema_from_hdmf_class(ElectrodeGroup),
            ElectricalSeries=get_schema_from_hdmf_class(ElectricalSeries)
        )
        metadata_schema['properties']['Ecephys']['required'] = ['Device', 'ElectrodeGroup', 'ElectricalSeries']

        return metadata_schema

    def get_metadata(self):
        out = super().get_metadata()
        out['properties'].update(
            Ecephys=dict(
                ElectricalSeries=dict(
                    name='ElectricalSeries',
                    description='raw acquired data'
                ),
                Device=dict(
                    name='device',
                    description='ecephys probe'
                )
            )
        )

        return out

    def convert_data(self, nwbfile, metadata_dict: None, stub_test=False):
        """
        Primary function for converting recording extractor data to nwb.

        Parameters
        ----------
        nwbfile : NWBFile object
        metadata_dict : dictionary
        stub_test : boolean, optional (default False)
            If True, will truncate the data to run the conversion faster and take up less memory.
        """
        if stub_test:
            num_frames = 100
            test_ids = self.recording_extractor.get_channel_ids()
            end_frame = min([num_frames, self.recording_extractor.get_num_frames()])

            stub_recording_extractor = se.SubRecordingExtractor(
                self.recording_extractor,
                channel_ids=test_ids,
                start_frame=0,
                end_frame=end_frame
            )
        else:
            stub_recording_extractor = self.recording_extractor

        if metadata_dict is not None and 'Ecephys' in metadata_dict and 'subset_channels' in metadata_dict['Ecephys']:
            recording_extractor = se.SubRecordingExtractor(stub_recording_extractor,
                                                           channel_ids=metadata_dict['Ecephys']['subset_channels'])
        else:
            recording_extractor = stub_recording_extractor

        se.NwbRecordingExtractor.write_recording(
            recording_extractor,
            nwbfile=nwbfile,
            metadata=metadata_dict
        )
