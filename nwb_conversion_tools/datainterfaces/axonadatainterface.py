"""Authors: Steffen Buergers"""
import random
import re
import datetime
import string
import spikeextractors as se

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


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
    """
    Primary data interface class for converting a AxonaRecordingExtractor
    """

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

    def __init__(self, **source_data):
        super().__init__(**source_data)

    def get_metadata(self):
        """
        Auto-fill metadata where possible. Must comply with metadata schema.
        """

        # Extract information for specific parameters from .set file
        # TODO not all are currently used or part of the metadata_schema
        params_of_interest = [
            'experimenter',
            'comments',
            'duration',
            'sw_version',
            'tracker_version',
            'stim_version',
            'audio_version'
        ]
        set_file = self.source_data['filename']+'.set'
        par = parse_generic_header(set_file, params_of_interest)

        # Add available metadata
        # NOTE that this interface is meant to be used within an NWBconverter,
        # which contains a much larger metadata_schema. As such a datainterface
        # metadata by itself does not necessarily validate with its own schema!
        metadata = super().get_metadata()
        metadata['NWBFile'] = dict(
            session_start_time=read_iso_datetime(set_file),
            session_description=par['comments'],
            identifier=''.join(random.choices(string.ascii_uppercase +
                                              string.digits, k=12)),
            experimenter=[par['experimenter']]
        )

        metadata['Ecephys'] = dict(
            Device=dict(
                    name="Axona",
                    description="Axona DacqUSB, sw_version={}".format(
                        par['sw_version']),
                    manufacturer="Axona"
                ),
            ElectrodeGroup=dict(
                name='Group0',
                location='',
                device='Axona',
                description="Group0 - all electrodes grouped together.",
            ),
            ElectricalSeries=dict(
                name='ElectricalSeries',
                description="Raw acquisition traces."
            )
        )

        return metadata
