"""Authors: Luiz Tauffer"""
import random
import string
import pytz
from typing import Union, Optional
from pathlib import Path
import spikeextractors as se
from pynwb import NWBFile

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ..json_schema_utils import get_schema_from_method_signature
from .interface_utils.brpylib import NsxFile

PathType = Union[str, Path, None]


class BlackrockRecordingExtractorInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a BlackrockRecordingExtractor."""

    RX = se.BlackrockRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        """Compile input schema for the RecordingExtractor."""
        metadata_schema = get_schema_from_method_signature(
            class_method=cls.RX.__init__,
            exclude=['block_index', 'seg_index']
        )
        metadata_schema['additionalProperties'] = True
        metadata_schema['properties']['filename']['format'] = 'file'
        metadata_schema['properties']['filename']['description'] = 'Path to Blackrock file.'
        return metadata_schema
    
    def __init__(self, filename: PathType, nsx_to_load: Optional[int] = None):
        super().__init__(filename=filename, nsx_to_load=nsx_to_load)

    def get_metadata(self):
        """Auto-fill as much of the metadata as possible. Must comply with metadata schema."""
        metadata = super().get_metadata()

        # Open file and extract headers
        nsx_file = NsxFile(datafile=self.source_data['filename'])
        session_start_time = nsx_file.basic_header['TimeOrigin']
        session_start_time_tzaware = pytz.timezone('EST').localize(session_start_time)
        comment = nsx_file.basic_header['Comment']

        metadata['NWBFile'] = dict(
            session_start_time=session_start_time_tzaware,
            session_description=comment,
            identifier=''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        )

        metadata['Ecephys'] = dict(
            Device=[dict(
                name='Device_ecephys',
                description='no description'
            )],
            ElectrodeGroup=[],
        )

        if self.source_data['nsx_to_load'] != 6:
            metadata['Ecephys']['LFPElectricalSeries'] = dict()
        else:
            metadata['Ecephys']['ElectricalSeries'] = dict()

        return metadata

    def run_conversion(self, nwbfile: NWBFile, metadata: dict = None, use_times: bool = False, 
                       write_as_lfp: bool = False, save_path: PathType = None, overwrite: bool = False, 
                       stub_test: bool = False):
        """
        Primary function for converting recording extractor data to nwb.

        Parameters
        ----------
        nwbfile: NWBFile
            nwb file to which the recording information is to be added
        metadata: dict
            metadata info for constructing the nwb file (optional).
            Should be of the format
                metadata['Ecephys']['ElectricalSeries'] = {'name': my_name,
                                                           'description': my_description}
        use_times: bool
            If True, the timestamps are saved to the nwb file using recording.frame_to_time(). If False (default),
            the sampling rate is used.
        write_as_lfp: bool (optional, defaults to False)
            If True, writes the traces under a processing LFP module in the NWBFile instead of acquisition.
        save_path: PathType
            Required if an nwbfile is not passed. Must be the path to the nwbfile
            being appended, otherwise one is created and written.
        overwrite: bool
            If using save_path, whether or not to overwrite the NWBFile if it already exists.
        stub_test: bool, optional (default False)
            If True, will truncate the data to run the conversion faster and take up less memory.
        """
        if self.source_data['nsx_to_load'] != 6:
            write_as_lfp = True

        super().run_conversion(
            nwbfile=nwbfile, 
            metadata=metadata, 
            use_times=use_times, 
            write_as_lfp=write_as_lfp,
            save_path=save_path, 
            overwrite=overwrite,
            stub_test=stub_test
        )


class BlackrockSortingExtractorInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting Blackrock spiking data."""

    SX = se.BlackrockSortingExtractor

    @classmethod
    def get_source_schema(cls):
        """Compile input schema for the RecordingExtractor."""
        metadata_schema = get_schema_from_method_signature(
            class_method=cls.SX.__init__,
            exclude=['block_index', 'seg_index', 'nsx_to_load']
        )
        metadata_schema['additionalProperties'] = True
        metadata_schema['properties']['filename']['format'] = 'file'
        metadata_schema['properties']['filename']['description'] = 'Path to Blackrock file.'
        return metadata_schema

    def __init__(self, filename: PathType, nsx_to_load: Optional[int] = None):
        super().__init__(filename=filename, nsx_to_load=nsx_to_load)