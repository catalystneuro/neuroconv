#! /bin/env python
#
# Michael Gibson 27 April 2015
# Modified Adrian Foy Sep 2018
# Modified for Jaeger Lab, Fev 2020
# ------------------------------------------------------------------------------


def data_to_result(header, data, data_present):
    """Moves the header and data (if present) into a common object."""

    result = {}
    if header['num_amplifier_channels'] > 0 and data_present:
        result['t_amplifier'] = data['t_amplifier']
    if header['num_aux_input_channels'] > 0 and data_present:
        result['t_aux_input'] = data['t_aux_input']
    if header['num_supply_voltage_channels'] > 0 and data_present:
        result['t_supply_voltage'] = data['t_supply_voltage']
    if header['num_board_adc_channels'] > 0 and data_present:
        result['t_board_adc'] = data['t_board_adc']
    if (header['num_board_dig_in_channels'] > 0 or header['num_board_dig_out_channels'] > 0) and data_present:
        result['t_dig'] = data['t_dig']
    if header['num_temp_sensor_channels'] > 0 and data_present:
        result['t_temp_sensor'] = data['t_temp_sensor']

    if header['num_amplifier_channels'] > 0:
        result['spike_triggers'] = header['spike_triggers']

    result['notes'] = header['notes']
    result['frequency_parameters'] = header['frequency_parameters']

    if header['version']['major'] > 1:
        result['reference_channel'] = header['reference_channel']

    if header['num_amplifier_channels'] > 0:
        result['amplifier_channels'] = header['amplifier_channels']
        if data_present:
            result['amplifier_data'] = data['amplifier_data']
            result['amplifier_data_conversion_factor'] = data['amplifier_data_conversion_factor']

    if header['num_aux_input_channels'] > 0:
        result['aux_input_channels'] = header['aux_input_channels']
        if data_present:
            result['aux_input_data'] = data['aux_input_data']

    if header['num_supply_voltage_channels'] > 0:
        result['supply_voltage_channels'] = header['supply_voltage_channels']
        if data_present:
            result['supply_voltage_data'] = data['supply_voltage_data']

    if header['num_board_adc_channels'] > 0:
        result['board_adc_channels'] = header['board_adc_channels']
        if data_present:
            result['board_adc_data'] = data['board_adc_data']

    if header['num_board_dig_in_channels'] > 0:
        result['board_dig_in_channels'] = header['board_dig_in_channels']
        if data_present:
            result['board_dig_in_data'] = data['board_dig_in_data']

    if header['num_board_dig_out_channels'] > 0:
        result['board_dig_out_channels'] = header['board_dig_out_channels']
        if data_present:
            result['board_dig_out_data'] = data['board_dig_out_data']

    return result
