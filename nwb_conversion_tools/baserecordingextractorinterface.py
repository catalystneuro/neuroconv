"""Authors: Cody Baker and Ben Dichter."""
from abc import ABC

import spikeextractors as se
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup, ElectricalSeries

from .basedatainterface import BaseDataInterface
from .utils import get_schema_from_hdmf_class
from .json_schema_utils import get_schema_from_method_signature, fill_defaults


class BaseRecordingExtractorInterface(BaseDataInterface, ABC):
    RX = None

    @classmethod
    def get_source_schema(cls):
        return get_schema_from_method_signature(cls.RX.__init__)

    def __init__(self, **source_data):
        super().__init__(**source_data)
        self.recording_extractor = self.RX(**source_data)
        self.subset_channels = None

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()

        # Initiate Ecephys metadata
        metadata_schema['properties']['Ecephys'] = dict(
            Device=get_schema_from_hdmf_class(Device),
            ElectrodeGroup=get_schema_from_hdmf_class(ElectrodeGroup),
            ElectricalSeries=get_schema_from_hdmf_class(ElectricalSeries)
        )
        metadata_schema['properties']['Ecephys']['required'] = ['Device', 'ElectrodeGroup', 'ElectricalSeries']
        fill_defaults(metadata_schema, self.get_metadata())
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

    def run_conversion(self, nwbfile, metadata: None, stub_test=False):
        """
        Primary function for converting recording extractor data to nwb.

        Parameters
        ----------
        nwbfile: pynwb.NWBFile
        metadata: dict
        stub_test: bool, optional (default False)
            If True, will truncate the data to run the conversion faster and take up less memory.
        """

        recording_extractor = self.recording_extractor
        if stub_test or self.subset_channels is not None:
            kwargs = dict()

            if stub_test:
                num_frames = 100
                end_frame = min([num_frames, self.recording_extractor.get_num_frames()])
                kwargs.update(end_frame=end_frame)

            if self.subset_channels is not None:
                kwargs.update(channel_ids=self.subset_channels)

            recording_extractor = se.SubRecordingExtractor(
                self.recording_extractor,
                **kwargs
            )

        se.NwbRecordingExtractor.write_recording(
            recording_extractor,
            nwbfile=nwbfile,
            metadata=metadata
        )
