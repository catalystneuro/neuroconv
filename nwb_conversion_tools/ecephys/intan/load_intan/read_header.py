#! /bin/env python
#
# Michael Gibson 23 April 2015
# Modified Adrian Foy Sep 2018
# Modified for NWBN conversion tools, March 2020
# ------------------------------------------------------------------------------

import sys
import struct
from .qstring import read_qstring


def read_header(fid, print_details=False):
    """Reads the Intan File Format header from the given file."""

    # Check 'magic number' at beginning of file to make sure this is an Intan
    # Technologies RHD2000 data file.
    magic_number, = struct.unpack('<I', fid.read(4))
    if magic_number != int('c6912702', 16):
        raise Exception('Unrecognized file type.')

    header = {}
    # Read version number.
    version = {}
    (version['major'], version['minor']) = struct.unpack('<hh', fid.read(4))
    header['version'] = version

    if print_details:
        print('')
        print('Reading Intan Technologies RHD2000 Data File, Version {}.{}'.format(version['major'], version['minor']))
        print('')

    freq = {}

    # Read information of sampling rate and amplifier frequency settings.
    header['sample_rate'], = struct.unpack('<f', fid.read(4))
    (freq['dsp_enabled'], freq['actual_dsp_cutoff_frequency'], freq['actual_lower_bandwidth'], freq['actual_upper_bandwidth'],
    freq['desired_dsp_cutoff_frequency'], freq['desired_lower_bandwidth'], freq['desired_upper_bandwidth']) = struct.unpack('<hffffff', fid.read(26))

    # This tells us if a software 50/60 Hz notch filter was enabled during
    # the data acquisition.
    notch_filter_mode, = struct.unpack('<h', fid.read(2))
    header['notch_filter_frequency'] = 0
    if notch_filter_mode == 1:
        header['notch_filter_frequency'] = 50
    elif notch_filter_mode == 2:
        header['notch_filter_frequency'] = 60
    freq['notch_filter_frequency'] = header['notch_filter_frequency']

    (freq['desired_impedance_test_frequency'], freq['actual_impedance_test_frequency']) = struct.unpack('<ff', fid.read(8))

    note1 = read_qstring(fid)
    note2 = read_qstring(fid)
    note3 = read_qstring(fid)
    header['notes'] = {'note1': note1, 'note2': note2, 'note3': note3}

    # If data file is from GUI v1.1 or later, see if temperature sensor data was saved.
    header['num_temp_sensor_channels'] = 0
    if (version['major'] == 1 and version['minor'] >= 1) or (version['major'] > 1):
        header['num_temp_sensor_channels'], = struct.unpack('<h', fid.read(2))

    # If data file is from GUI v1.3 or later, load eval board mode.
    header['eval_board_mode'] = 0
    if ((version['major'] == 1) and (version['minor'] >= 3)) or (version['major'] > 1):
        header['eval_board_mode'], = struct.unpack('<h', fid.read(2))

    header['num_samples_per_data_block'] = 60
    # If data file is from v2.0 or later (Intan Recording Controller), load name of digital reference channel
    if (version['major'] > 1):
        header['reference_channel'] = read_qstring(fid)
        header['num_samples_per_data_block'] = 128

    # Place frequency-related information in data structure. (Note: much of this structure is set above)
    freq['amplifier_sample_rate'] = header['sample_rate']
    freq['aux_input_sample_rate'] = header['sample_rate'] / 4
    freq['supply_voltage_sample_rate'] = header['sample_rate'] / header['num_samples_per_data_block']
    freq['board_adc_sample_rate'] = header['sample_rate']
    freq['board_dig_in_sample_rate'] = header['sample_rate']

    header['frequency_parameters'] = freq

    # Create structure arrays for each type of data channel.
    header['spike_triggers'] = []
    header['amplifier_channels'] = []
    header['aux_input_channels'] = []
    header['supply_voltage_channels'] = []
    header['board_adc_channels'] = []
    header['board_dig_in_channels'] = []
    header['board_dig_out_channels'] = []

    # Read signal summary from data file header.

    number_of_signal_groups, = struct.unpack('<h', fid.read(2))
    if print_details:
        print('n signal groups {}'.format(number_of_signal_groups))

    for signal_group in range(1, number_of_signal_groups + 1):
        signal_group_name = read_qstring(fid)
        signal_group_prefix = read_qstring(fid)
        (signal_group_enabled, signal_group_num_channels, signal_group_num_amp_channels) = struct.unpack('<hhh', fid.read(6))

        if (signal_group_num_channels > 0) and (signal_group_enabled > 0):
            for signal_channel in range(0, signal_group_num_channels):
                new_channel = {
                    'port_name': signal_group_name,
                    'port_prefix': signal_group_prefix,
                    'port_number': signal_group
                }
                new_channel['native_channel_name'] = read_qstring(fid)
                new_channel['custom_channel_name'] = read_qstring(fid)
                (new_channel['native_order'], new_channel['custom_order'], signal_type, channel_enabled, new_channel['chip_channel'], new_channel['board_stream']) = struct.unpack('<hhhhhh', fid.read(12))
                new_trigger_channel = {}
                (new_trigger_channel['voltage_trigger_mode'], new_trigger_channel['voltage_threshold'], new_trigger_channel['digital_trigger_channel'], new_trigger_channel['digital_edge_polarity']) = struct.unpack('<hhhh', fid.read(8))
                (new_channel['electrode_impedance_magnitude'], new_channel['electrode_impedance_phase']) = struct.unpack('<ff', fid.read(8))

                if channel_enabled:
                    if signal_type == 0:
                        header['amplifier_channels'].append(new_channel)
                        header['spike_triggers'].append(new_trigger_channel)
                    elif signal_type == 1:
                        header['aux_input_channels'].append(new_channel)
                    elif signal_type == 2:
                        header['supply_voltage_channels'].append(new_channel)
                    elif signal_type == 3:
                        header['board_adc_channels'].append(new_channel)
                    elif signal_type == 4:
                        header['board_dig_in_channels'].append(new_channel)
                    elif signal_type == 5:
                        header['board_dig_out_channels'].append(new_channel)
                    else:
                        raise Exception('Unknown channel type.')

    # Summarize contents of data file.
    header['num_amplifier_channels'] = len(header['amplifier_channels'])
    header['num_aux_input_channels'] = len(header['aux_input_channels'])
    header['num_supply_voltage_channels'] = len(header['supply_voltage_channels'])
    header['num_board_adc_channels'] = len(header['board_adc_channels'])
    header['num_board_dig_in_channels'] = len(header['board_dig_in_channels'])
    header['num_board_dig_out_channels'] = len(header['board_dig_out_channels'])

    return header


if __name__ == '__main__':
    h = read_header(open(sys.argv[1], 'rb'))
    # print(h)
