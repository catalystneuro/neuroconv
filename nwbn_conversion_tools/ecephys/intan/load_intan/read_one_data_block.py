#! /bin/env python
#
# Michael Gibson 23 April 2015
# Modified Adrian Foy Sep 2018

import sys, struct
import numpy as np

def read_one_data_block(data, header, indices, fid):
    """Reads one 60 or 128 sample data block from fid into data, at the location indicated by indices."""

    # In version 1.2, we moved from saving timestamps as unsigned
    # integers to signed integers to accommodate negative (adjusted)
    # timestamps for pretrigger data['
    if (header['version']['major'] == 1 and header['version']['minor'] >= 2) or (header['version']['major'] > 1):
        data['t_amplifier'][indices['amplifier']:(indices['amplifier'] + header['num_samples_per_data_block'])] = np.array(struct.unpack('<' + 'i' * header['num_samples_per_data_block'], fid.read(4 * header['num_samples_per_data_block'])))
    else:
        data['t_amplifier'][indices['amplifier']:(indices['amplifier'] + header['num_samples_per_data_block'])] = np.array(struct.unpack('<' + 'I' * header['num_samples_per_data_block'], fid.read(4 * header['num_samples_per_data_block'])))

    if header['num_amplifier_channels'] > 0:
        tmp = np.fromfile(fid, dtype='uint16', count= header['num_samples_per_data_block'] * header['num_amplifier_channels'])
        data['amplifier_data'][range(header['num_amplifier_channels']), (indices['amplifier']):(indices['amplifier']+ header['num_samples_per_data_block'])] = tmp.reshape(header['num_amplifier_channels'], header['num_samples_per_data_block'])

    if header['num_aux_input_channels'] > 0:
        tmp = np.fromfile(fid, dtype='uint16', count= int((header['num_samples_per_data_block'] / 4) * header['num_aux_input_channels']))
        data['aux_input_data'][range(header['num_aux_input_channels']), indices['aux_input']:int(indices['aux_input']+ (header['num_samples_per_data_block']/4))] = tmp.reshape(header['num_aux_input_channels'], int(header['num_samples_per_data_block']/4))

    if header['num_supply_voltage_channels'] > 0:
        tmp = np.fromfile(fid, dtype='uint16', count=1 * header['num_supply_voltage_channels'])
        data['supply_voltage_data'][range(header['num_supply_voltage_channels']), indices['supply_voltage']:(indices['supply_voltage']+1)] = tmp.reshape(header['num_supply_voltage_channels'], 1)

    if header['num_temp_sensor_channels'] > 0:
        tmp = np.fromfile(fid, dtype='uint16', count=1 * header['num_temp_sensor_channels'])
        data['temp_sensor_data'][range(header['num_temp_sensor_channels']), indices['supply_voltage']:(indices['supply_voltage']+1)] = tmp.reshape(header['num_temp_sensor_channels'], 1)

    if header['num_board_adc_channels'] > 0:
        tmp = np.fromfile(fid, dtype='uint16', count= (header['num_samples_per_data_block']) * header['num_board_adc_channels'])
        data['board_adc_data'][range(header['num_board_adc_channels']), indices['board_adc']:(indices['board_adc']+ header['num_samples_per_data_block'])] = tmp.reshape(header['num_board_adc_channels'], header['num_samples_per_data_block'])

    if header['num_board_dig_in_channels'] > 0:
        data['board_dig_in_raw'][indices['board_dig_in']:(indices['board_dig_in']+ header['num_samples_per_data_block'])] = np.array(struct.unpack('<' + 'H' * header['num_samples_per_data_block'], fid.read(2 * header['num_samples_per_data_block'])))

    if header['num_board_dig_out_channels'] > 0:
        data['board_dig_out_raw'][indices['board_dig_out']:(indices['board_dig_out']+ header['num_samples_per_data_block'])] = np.array(struct.unpack('<' + 'H' * header['num_samples_per_data_block'], fid.read(2 * header['num_samples_per_data_block'])))

