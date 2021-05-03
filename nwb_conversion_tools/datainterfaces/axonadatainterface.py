"""Authors: Steffen Buergers"""
import re
import datetime
import spikeextractors as se

from pynwb.ecephys import ElectricalSeries
from ..utils import get_schema_from_hdmf_class
from ..basedatainterface import BaseDataInterface
from ..baserecordingextractorinterface import (
    BaseRecordingExtractorInterface
)


def parse_generic_header(filename, params):
    """
    Given a binary file with phrases and line breaks, enters the
    first word of a phrase as dictionary key and the following
    string (without linebreaks) as value. Returns the dictionary.

    INPUT
    filename (str): .set file path and name.
    params (list or set): parameter names to search for.

    OUTPUT
    header (dict): dictionary with keys being the parameters that
                   were found & values being strings of the data.

    EXAMPLE
    parse_generic_header('myset_file.set', ['experimenter', 'trial_time'])
    """
    header = {}
    params = set(params)
    with open(filename, 'rb') as f:
        for bin_line in f:
            if b'data_start' in bin_line:
                break
            line = bin_line.decode('cp1252').replace('\r\n', '').\
                replace('\r', '').strip()
            parts = line.split(' ')
            key = parts[0]
            if key in params:
                header[key] = ' '.join(parts[1:])

    return header


def read_iso_datetime(set_file):
    """
    Creates datetime object (y, m, d, h, m, s) from .set file header
    and converts it to ISO 8601 format
    """
    with open(set_file, 'r', encoding='cp1252') as f:
        for line in f:
            if line.startswith('trial_date'):
                date_string = re.findall(r'\d+\s\w+\s\d{4}$', line)[0]
            if line.startswith('trial_time'):
                time_string = line[len('trial_time')+1::].replace('\n', '')

    return datetime.datetime.strptime(date_string + ', ' + time_string,
                                      "%d %b %Y, %H:%M:%S").isoformat()


class AxonaRecordingExtractorInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a AxonaRecordingExtractor"""

    RX = se.AxonaRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        source_schema = {
            'required': ['filename'],
            'properties': {
                'filename': {
                    'type': 'string',
                    'format': 'file',
                    'description': 'Path to Axona files.'
                }
            },
            'type': 'object',
            'additionalProperties': True
        }
        return source_schema

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()

        # Update Ecephys metadata
        Electrodes = {
            "required": [
                "name",
                "description",
                "data"
            ],
            "properties": {
                "name": {
                    "description": "Electrode group name this electrode is a part of.",
                    "type": "string"
                },
                "description": {
                    "description": "Description of this electrode group",
                    "type": "string"
                },
                "data": {
                    "description": "Electrode group name for each electrode.",
                    "type": "array",
                }
            },
            "type": "array",
            "additionalProperties": False,
            "tag": "Electrodes"
        }

        metadata_schema['properties']['Ecephys']['properties'].update(
            Electrodes=Electrodes,
            ElectricalSeries=get_schema_from_hdmf_class(ElectricalSeries),
        )

        return metadata_schema

    def get_metadata(self):

        # Extract information for specific parameters from .set file
        params_of_interest = [
            'experimenter',
            'comments',
            'duration',
            'sw_version'
        ]
        set_file = self.source_data['filename'].split('.')[0]+'.set'
        par = parse_generic_header(set_file, params_of_interest)

        # Extract information from AxonaRecordingExtractor
        elec_group_names = self.recording_extractor.get_channel_groups()
        unique_elec_group_names = set(elec_group_names)

        # Add available metadata
        metadata = super().get_metadata()
        metadata['NWBFile'] = dict(
            session_start_time=read_iso_datetime(set_file),
            session_description=par['comments'],
            experimenter=[par['experimenter']]
        )

        metadata['Ecephys'] = dict(
            Device=[
                dict(
                    name="Axona",
                    description="Axona DacqUSB, sw_version={}"
                                .format(par['sw_version']),
                    manufacturer="Axona"
                ),
            ],
            ElectrodeGroup=[
                dict(
                    name=f'Group{group_name}',
                    location='',
                    device='Axona',
                    description=f"Group {group_name} electrodes.",
                )
                for group_name in unique_elec_group_names
            ],
            Electrodes=[
                dict(
                    name='group_name',
                    description="The name of the ElectrodeGroup this electrode is a part of.",
                    data=[f"Group{x}" for x in elec_group_names]
                )
            ],
            ElectricalSeries=dict(
                name='ElectricalSeries',
                description="Raw acquisition traces."
            )
        )

        return metadata


class AxonaPositionDataInterface(BaseDataInterface):
    """Primary data interface class for converting a AxonaRecordingExtractor"""
    pass
