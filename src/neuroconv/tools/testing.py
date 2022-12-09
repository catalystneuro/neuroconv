"""Author: Cody Baker."""
from typing import Optional, Union

import numpy as np

from ..utils import IntType, FloatType, ArrayType


def generate_mock_ttl_signal(
    num_seconds: float = 5.5,
    sampling_frequency_hz: float = 25000.0,
    ttl_frequency_hz: Optional[float] = 2.0,
    ttl_times: Optional[ArrayType] = None,
    ttl_on_duration_seconds: float = 1.0,
    ttl_off_duration_seconds: float = 1.0,
    dtype: np.typing.DTypeLike = "int16",
    baseline_mean: Optional[Union[IntType, FloatType]] = None,
    signal_mean: Optional[Union[IntType, FloatType]] = None,
    channel_noise: Optional[Union[IntType, FloatType]] = None,
    random_seed: Optional[int] = 0,
) -> np.ndarray:
    """
    Generate a synthetic signal of TTL pulses similar to those seen in .nidq.bin files using SpikeGLX.

    Parameters
    ----------
    num_seconds: float, optional
        The number of seconds to simulate.
        The default is 5.5 seconds.
    sampling_frequency_hz: float, optional
        The sampling frequency of the signal in Hz.
        The default is 25000 Hz; similar to that of .nidq.bin files.
    ttl_frequency_hz: float, optional
        How often the TTL pulse of `ttl_duration_seconds` is sent.
        The default is 2 second to match the default duration of 1 second to emulate a regular metronomic pulse.
    ttl_times: array of floats, optional
        If an irregular series of TTL pulses are desired, specify the exact sequence of timings.
        The default assumes regular series with the `ttl_frequency_hz` rate.
    ttl_on_duration_seconds: float, optional
        How long the TTL pulse stays in the 'on' state when triggered.
        The default is 1 second to match the default frequency of 2 seconds to emulate a regular metronomic pulse.
    ttl_off_duration_seconds: float, optional
        How long the TTL pulse stays in the 'off' state when triggered.
        The default is 1 second to match the default frequency of 2 seconds to emulate a regular metronomic pulse.
    dtype: numpy data type or one of its accepted string input
        The data type of the trace and its specifiable parameters.
        Recommended to be int16 for maximum efficiency, but can also be any size float to represent voltage scalings.
        Defaults to int16.
    baseline_mean: integer or float, depending on specified 'dtype', optional
        The average value for the baseline; usually around 0 Volts.
        The default is apprimxately 0.005645752 Volts, estimated from a real example of a TTL pulse in a .nidq.bin file.
    signal_mean: integer or float, depending on specified 'dtype', optional
        The average value for the signal; usually around 5 Volts.
        The default is apprimxately 4.996032715 Volts, estimated from a real example of a TTL pulse in a .nidq.bin file.
    channel_noise: integer or float, depending on specified 'dtype', optional
        The average value for the noise of the channel.
        The default is apprimxately 0.002288818 Volts, estimated from a real example of a TTL pulse in a .nidq.bin file.
    random_seed: int or None, optional
        The seed to set for the numpy random number generator.
        Set to None to choose the seed randomly.
        The default is zero for reproducibility.

    Returns
    -------
    trace: numpy.ndarray
        The trace signal as int16.
    """
    assert (
        ttl_frequency_hz is not None or ttl_times is not None
    ), "You must specify either a `ttl_frequency_hz` or an array of `ttl_times`!"
    assert (
        ttl_frequency_hz is None or ttl_times is None
    ), "Please specify either a `ttl_frequency_hz` or an array of `ttl_times`, but not both!"

    dtype = np.dtype(dtype)

    # Default values estimated from real files
    baseline_mean_int16_default = 37
    signal_mean_int16_default = 32742
    channel_noise_int16_default = 15
    default_gain_to_volts = 152.58789062 * 1e-6

    if np.issubdtype(dtype, np.unsignedinteger):
        # If data type is an unsigned integer, increment the signed default values by the midpoint of the unsigned range
        shift = np.floor(np.iinfo(dtype).max / 2)
        baseline_mean_int16_default += shift
        signal_mean_int16_default += shift

    if np.issubdtype(dtype, np.integer):
        baseline_mean = baseline_mean or baseline_mean_int16_default
        signal_mean = signal_mean or signal_mean_int16_default
        channel_noise = channel_noise or channel_noise_int16_default

        assert np.issubdtype(type(baseline_mean), np.integer), (
            "If specifying the 'baseline_mean' manually, please ensure it matches the 'dtype'! "
            f"Received {type(baseline_mean)} should be an integer."
        )
        assert np.issubdtype(type(signal_mean), np.integer), (
            "If specifying the 'signal_mean' manually, please ensure it matches the 'dtype'! "
            f"Received {type(signal_mean)} should be an integer."
        )
        assert np.issubdtype(type(channel_noise), np.integer), (
            "If specifying the 'channel_noise' manually, please ensure it matches the 'dtype'! "
            f"Received {type(baseline_mean)} should be an integer."
        )
    else:
        baseline_mean = baseline_mean or baseline_mean_int16_default * default_gain_to_volts
        signal_mean = signal_mean or signal_mean_int16_default * default_gain_to_volts
        channel_noise = channel_noise or channel_noise_int16_default * default_gain_to_volts

        assert np.issubdtype(type(baseline_mean), np.floating), (
            "If specifying the 'baseline_mean' manually, please ensure it matches the 'dtype'! "
            f"Received {type(baseline_mean)} should be a float."
        )
        assert np.issubdtype(type(signal_mean), np.floating), (
            "If specifying the 'signal_mean' manually, please ensure it matches the 'dtype'! "
            f"Received {type(signal_mean)} should be a float."
        )
        assert np.issubdtype(type(channel_noise), np.floating), (
            "If specifying the 'channel_noise' manually, please ensure it matches the 'dtype'! "
            f"Received {type(baseline_mean)} should be a float."
        )

    np.random.seed(seed=random_seed)
    num_frames = num_seconds * sampling_frequency_hz
    trace = (np.random.randn(num_frames) * channel_noise + baseline_mean).astype(dtype)

    if ttl_times is None:
        # Start off halfway through an off pulse
        total_cycle_duration = ttl_off_duration_seconds + ttl_on_duration_seconds
        cycle_start_times = np.arange(0, num_seconds, total_cycle_duration)
        num_cycles = len(cycle_start_times)
        num_ttl_pulses = (
            num_cycles if num_seconds - cycle_start_times[-1] - ttl_off_duration_seconds > 0 else num_cycles - 1
        )
        ttl_times = np.linspace(start=0.5, stop=4.5, num=num_ttl_pulses)
    ttl_frames = 1

    # Set frame indices of trace to signal mean
    trace[ttl_framess] += signal_mean

    return trace
