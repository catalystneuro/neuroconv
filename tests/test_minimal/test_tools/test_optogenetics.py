import numpy as np
from numpy.testing import assert_array_equal

from neuroconv.tools.optogenetics import create_optogenetic_stimulation_timeseries


def test_create_ogen_stimulation_timeseries():
    stimulation_onset_times = [10, 20, 30]
    duration = 1
    frequency = 4
    pulse_width = 0.01
    power = 1
    expected_timestamps = [
        0,
        10,
        10.01,
        10.25,
        10.26,
        10.5,
        10.51,
        10.75,
        10.76,
        20,
        20.01,
        20.25,
        20.26,
        20.5,
        20.51,
        20.75,
        20.76,
        30,
        30.01,
        30.25,
        30.26,
        30.5,
        30.51,
        30.75,
        30.76,
    ]
    expected_data = [i % 2 for i in range(len(expected_timestamps))]  # 0, 1, 0, 1, ...
    expected_timestamps = np.array(expected_timestamps, dtype=np.float64)
    expected_data = np.array(expected_data, dtype=np.float64)

    timestamps, data = create_optogenetic_stimulation_timeseries(
        stimulation_onset_times=stimulation_onset_times,
        duration=duration,
        frequency=frequency,
        pulse_width=pulse_width,
        power=power,
    )

    assert_array_equal(timestamps, expected_timestamps)
    assert_array_equal(data, expected_data)


def test_create_ogen_stimulation_timeseries_cts():
    stimulation_onset_times = [10, 20, 30]
    duration = 1
    frequency = 1
    pulse_width = 1
    power = 1
    expected_timestamps = [0, 10, 11, 20, 21, 30, 31]
    expected_data = [i % 2 for i in range(len(expected_timestamps))]  # 0, 1, 0, 1, ...
    expected_timestamps = np.array(expected_timestamps, dtype=np.float64)
    expected_data = np.array(expected_data, dtype=np.float64)

    timestamps, data = create_optogenetic_stimulation_timeseries(
        stimulation_onset_times=stimulation_onset_times,
        duration=duration,
        frequency=frequency,
        pulse_width=pulse_width,
        power=power,
    )

    assert_array_equal(timestamps, expected_timestamps)
    assert_array_equal(data, expected_data)
