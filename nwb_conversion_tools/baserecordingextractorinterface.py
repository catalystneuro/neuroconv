"""Authors: Cody Baker and Ben Dichter."""
from abc import ABC

import spikeextractors as se
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup, ElectricalSeries

from .basedatainterface import BaseDataInterface
from .utils import get_schema_from_hdmf_class, subset_recording
from .json_schema_utils import get_schema_from_method_signature, fill_defaults


class BaseRecordingExtractorInterface(BaseDataInterface, ABC):
    """Primary class for all RecordingExtractorInterfaces."""

    RX = None

    @classmethod
    def get_source_schema(cls):
        """Compile input schema for the RecordingExtractor."""
        return get_schema_from_method_signature(cls.RX.__init__)

    def __init__(self, **source_data):
        super().__init__(**source_data)
        self.recording_extractor = self.RX(**source_data)
        self.subset_channels = None

    def get_metadata_schema(self):
        """Compile metadata schema for the RecordingExtractor."""
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
        """Auto-fill as much of the metadata as possible. Must comply with metadata schema."""
        metadata = super().get_metadata()
        metadata.update(
            Ecephys=dict(
                Device=[],
                ElectrodeGroup=[],
                Electrodes=[],
                ElectricalSeries=dict(),
            )
        )
        return metadata

    def run_conversion(self, nwbfile: NWBFile, metadata: dict = None, stub_test: bool = False):
        """
        Primary function for converting recording extractor data to nwb.

        Parameters
        ----------
        nwbfile: pynwb.NWBFile
        metadata: dict
        stub_test: bool, optional (default False)
            If True, will truncate the data to run the conversion faster and take up less memory.
        """
        recording_extractor = subset_recording(
            recording_extractor=self.recording_extractor,
            stub_test=stub_test,
            subset_channels=self.subset_channels
        )
        se.NwbRecordingExtractor.write_recording(
            recording_extractor,
            nwbfile=nwbfile,
            metadata=metadata
        )
