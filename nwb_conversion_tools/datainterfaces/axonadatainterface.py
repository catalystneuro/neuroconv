"""Authors: Steffen Buergers"""
import os
import dateutil
import contextlib
import mmap
import numpy as np

import spikeextractors as se
from pynwb import NWBFile
from pynwb.behavior import Position, SpatialSeries
from pynwb.ecephys import ElectricalSeries

from ..utils.json_schema import get_schema_from_hdmf_class
from ..basedatainterface import BaseDataInterface
from ..baserecordingextractorinterface import (
    BaseRecordingExtractorInterface
)

from nwb_conversion_tools.conversion_tools import get_module


# Helper functions for AxonaRecordingExtractorInterface
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
    header = dict()
    params = set(params)
    with open(filename, 'rb') as f:
        for bin_line in f:
            if b'data_start' in bin_line:
                break
            line = bin_line.decode('cp1252').replace('\r\n', '').replace('\r', '').strip()
            parts = line.split(' ')
            key = parts[0]
            if key in params:
                header[key] = ' '.join(parts[1:])

    return header


def read_axona_iso_datetime(set_file):
    """
    Creates datetime object (y, m, d, h, m, s) from .set file header
    and converts it to ISO 8601 format
    """
    with open(set_file, 'r', encoding='cp1252') as f:
        for line in f:
            if line.startswith('trial_date'):
                date_string = line[len('trial_date')+1::].replace('\n', '')
            if line.startswith('trial_time'):
                time_string = line[len('trial_time')+1::].replace('\n', '')

    return dateutil.parser.parse(date_string + ' ' + time_string).isoformat()


class AxonaRecordingExtractorInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a AxonaRecordingExtractor"""

    RX = se.AxonaRecordingExtractor

    @classmethod
    def get_source_schema(cls):

        source_schema = dict(
            required=['filename'],
            properties=dict(
                filename=dict(
                    type='string',
                    format='file',
                    description='Full path to Axona .set file.'
                )
            ),
            type='object',
            additionalProperties=True
        )
        return source_schema

    def get_metadata_schema(self):
        """Compile metadata schema for the RecordingExtractor."""
        metadata_schema = super().get_metadata_schema()
        metadata_schema['properties']['Ecephys']['properties'].update(
            ElectricalSeries_raw=get_schema_from_hdmf_class(ElectricalSeries)
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
            session_start_time=read_axona_iso_datetime(set_file),
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
                    description="""The name of the ElectrodeGroup this electrode
                                is a part of.""",
                    data=[f"Group{x}" for x in elec_group_names]
                )
            ],
            ElectricalSeries_raw=dict(
                name='ElectricalSeries_raw',
                description="Raw acquisition traces."
            )
        )

        return metadata


# Helper functions for AxonaPositionDataInterface
def establish_mmap_to_position_data(filename):
    '''
    Generates a memory map (mmap) object connected to an Axona .bin
    file, referencing only the animal position data (if present).

    When no .bin file is available or no position data is included,
    returns None.

    TODO: Also allow using .pos file (currently only support .bin)

    Parameters:
    -------
    filename (Path or Str): Full filename of Axona file with any
        extension.

    Returns:
    -------
    mm (mmap or None): Memory map to .bin file position data
    '''
    mmpos = None

    bin_file = filename.split('.')[0]+'.bin'
    set_file = filename.split('.')[0]+'.set'
    par = parse_generic_header(set_file, ['rawRate', 'duration'])
    sr_ecephys = int(par['rawRate'])
    sr_pos = 100
    bytes_packet = 432

    num_packets = int(os.path.getsize(bin_file) / bytes_packet)
    num_ecephys_samples = num_packets * 3
    dur_ecephys = num_ecephys_samples / sr_ecephys
    assert dur_ecephys == float(par['duration'])

    # Check if position data exists in .bin file
    with open(bin_file, 'rb') as f:
        with contextlib.closing(
            mmap.mmap(f.fileno(), sr_ecephys // 3 // sr_pos
                      * bytes_packet, access=mmap.ACCESS_READ)
        ) as mmap_obj:
            contains_pos_tracking = mmap_obj.find(b'ADU2') > -1

    # Establish memory map to .bin file, considering only position data
    if contains_pos_tracking:
        fbin = open(bin_file, 'rb')
        mmpos = mmap.mmap(fbin.fileno(), 0, access=mmap.ACCESS_READ)

    return mmpos


def read_bin_file_position_data(filename):
    '''
    Reads position data from Axona .bin file (if present in
    recording) and returns it as a numpy.array.

    Parameters:
    -------
    filename (Path or Str): Full filename of Axona file with any
        extension.

    Returns:
    -------
    pos (np.array)
    '''
    bin_file = filename.split('.')[0]+'.bin'
    mm = establish_mmap_to_position_data(bin_file)

    bytes_packet = 432
    num_packets = int(os.path.getsize(bin_file) / bytes_packet)

    set_file = filename.split('.')[0]+'.set'
    par = parse_generic_header(set_file, ['rawRate', 'duration'])
    sr_ecephys = int(par['rawRate'])

    pos = np.array([]).astype(float)

    flags = np.ndarray((num_packets,), 'S4', mm, 0, bytes_packet)
    ADU2_idx = np.where(flags == b'ADU2')

    pos = np.ndarray(
        (num_packets,), (np.int16, (1, 8)), mm, 16, (bytes_packet,)
    ).reshape((-1, 8))[ADU2_idx][:]

    pos = np.hstack((ADU2_idx[0].reshape((-1, 1)), pos)).astype(float)

    # The timestamp from the recording is dubious, create our own
    packets_per_ms = sr_ecephys / 3000
    pos[:, 0] = pos[:, 0] / packets_per_ms
    pos = np.delete(pos, 1, 1)

    return pos


def generate_position_data(filename):
    '''
    Read position data from .bin or .pos file and convert to
    pynwb.behavior.SpatialSeries objects.

    Parameters:
    -------
    filename (Path or Str): Full filename of Axona file with any
        extension.

    Returns:
    -------
    position (pynwb.behavior.Position)
    '''
    position = Position()

    position_channel_names = 't,x1,y1,x2,y2,numpix1,numpix2,unused'.split(',')
    position_data = read_bin_file_position_data(filename)
    position_timestamps = position_data[:, 0]

    for ichan in range(0, position_data.shape[1]):

        spatial_series = SpatialSeries(
            name=position_channel_names[ichan],
            timestamps=position_timestamps,
            data=position_data[:, ichan],
            reference_frame='start of raw aquisition (.bin file)'
        )
        position.add_spatial_series(spatial_series)

    return position


class AxonaPositionDataInterface(BaseDataInterface):
    """Primary data interface class for converting Axona position data"""

    @classmethod
    def get_source_schema(cls):

        source_schema = super().get_source_schema()
        source_schema.update(
            required=['filename'],
            properties=dict(
                filename=dict(
                    type='string',
                    format='file',
                    description='Full filename of Axona .bin or .pos file'
                )
            ),
            type='object',
            additionalProperties=True
        )

        return source_schema

    def run_conversion(self, nwbfile: NWBFile, metadata: dict):
        """
        Run conversion for this data interface.

        Parameters
        ----------
        nwbfile : NWBFile
        metadata : dict
        """
        filename = self.source_data['filename']
        position = generate_position_data(filename)

        # Create or update processing module for behavioral data
        get_module(nwbfile=nwbfile, name='behavior', description='behavioral data')
        nwbfile.processing['behavior'].add(position)
