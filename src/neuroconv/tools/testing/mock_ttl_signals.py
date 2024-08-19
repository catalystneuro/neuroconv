import math
from pathlib import Path
from typing import Optional, Union

import numpy as np
from numpy.typing import DTypeLike
from pydantic import DirectoryPath
from pynwb import NWBHDF5IO, H5DataIO, TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from ..importing import is_package_installed
from ...utils import ArrayType


def _check_parameter_dtype_consistency(
    parameter_name: str,
    parameter_value: Union[int, float],
    generic_dtype: type,  # Literal[np.integer, np.floating]
):
    """Helper for `generate_mock_ttl_signal` to assert consistency between parameters and expected trace dtype."""
    end_format = "an integer" if generic_dtype == np.integer else "a float"
    assert np.issubdtype(type(parameter_value), generic_dtype), (
        f"If specifying the '{parameter_name}' manually, please ensure it matches the 'dtype'! "
        f"Received '{type(parameter_value).__name__}', should be {end_format}."
    )


def generate_mock_ttl_signal(
    signal_duration: float = 7.0,
    ttl_times: Optional[ArrayType] = None,
    ttl_duration: float = 1.0,
    sampling_frequency_hz: float = 25_000.0,
    dtype: DTypeLike = "int16",
    baseline_mean: Optional[Union[int, float]] = None,
    signal_mean: Optional[Union[int, float]] = None,
    channel_noise: Optional[Union[int, float]] = None,
    random_seed: Optional[int] = 0,
) -> np.ndarray:
    """
    Generate a synthetic signal of TTL pulses similar to those seen in .nidq.bin files using SpikeGLX.

    Parameters
    ----------
    signal_duration : float, default: 7.0
        The number of seconds to simulate.
    ttl_times : array of floats, optional
        The times within the `signal_duration` to trigger the TTL pulse.
        In conjunction with the `ttl_duration`, these must produce disjoint 'on' intervals.
        The default generates a periodic 1 second on, 1 second off pattern.
    ttl_duration : float, default: 1.0
        How long the TTL pulse stays in the 'on' state when triggered, in seconds.
        In conjunction with the `ttl_times`, these must produce disjoint 'on' intervals.
    sampling_frequency_hz : float, default: 25,000.0
        The sampling frequency of the signal in Hz.
        The default is 25000 Hz; similar to that of typical .nidq.bin files.
    dtype : numpy data type or one of its accepted string input, default: "int16"
        The data type of the trace.
        Must match the data type of `baseline_mean`, `signal_mean`, and `channel_noise`, if any of those are specified.
        Recommended to be int16 for maximum efficiency, but can also be any size float to represent voltage scalings.
    baseline_mean : integer or float, depending on specified 'dtype', optional
        The average value for the baseline; usually around 0 Volts.
        The default is approximately 0.005645752 Volts, estimated from a real example of a TTL pulse in a .nidq.bin file.
    signal_mean : integer or float, optional
        Type depends on specified 'dtype'. The average value for the signal; usually around 5 Volts.
        The default is approximately 4.980773925 Volts, estimated from a real example of a TTL pulse in a .nidq.bin file.
    channel_noise : integer or float, optional
        Type depends on specified 'dtype'. The standard deviation of white noise in the channel.
        The default is approximately 0.002288818 Volts, estimated from a real example of a TTL pulse in a .nidq.bin file.
    random_seed : int or None, default: 0
        The seed to set for the numpy random number generator.
        Set to None to choose the seed randomly.
        The default is kept at 0 for generating reproducible outputs.

    Returns
    -------
    trace: numpy.ndarray
        The synethic trace representing a channel with TTL pulses.
    """
    dtype = np.dtype(dtype)

    # Default values estimated from real files
    baseline_mean_int16_default = 37
    signal_mean_int16_default = 32642
    channel_noise_int16_default = 15
    default_gain_to_volts = 152.58789062 * 1e-6

    if np.issubdtype(dtype, np.unsignedinteger):
        # If data type is an unsigned integer, increment the signed default values by the midpoint of the unsigned range
        shift = math.floor(np.iinfo(dtype).max / 2)
        baseline_mean_int16_default += shift
        signal_mean_int16_default += shift

    if np.issubdtype(dtype, np.integer):
        baseline_mean = baseline_mean or baseline_mean_int16_default
        signal_mean = signal_mean or signal_mean_int16_default
        channel_noise = channel_noise or channel_noise_int16_default
        generic_dtype = np.integer
    else:
        baseline_mean = baseline_mean or baseline_mean_int16_default * default_gain_to_volts
        signal_mean = signal_mean or signal_mean_int16_default * default_gain_to_volts
        channel_noise = channel_noise or channel_noise_int16_default * default_gain_to_volts
        generic_dtype = np.floating
    parameters_to_check = dict(baseline_mean=baseline_mean, signal_mean=signal_mean, channel_noise=channel_noise)
    for parameter_name, parameter_value in parameters_to_check.items():
        _check_parameter_dtype_consistency(
            parameter_name=parameter_name, parameter_value=parameter_value, generic_dtype=generic_dtype
        )

    np.random.seed(seed=random_seed)
    num_frames = np.ceil(signal_duration * sampling_frequency_hz).astype(int)
    trace = (np.random.randn(num_frames) * channel_noise + baseline_mean).astype(dtype)

    if ttl_times is not None:
        ttl_times = np.array(ttl_times)
    else:
        ttl_times = np.arange(start=1.0, stop=signal_duration, step=2.0)

    assert len(ttl_times) == 1 or not any(  # np.diff errors out when len(ttl_times) < 2
        np.diff(ttl_times) <= ttl_duration
    ), "There are overlapping TTL 'on' intervals! Please specify disjoint on/off periods."

    ttl_start_frames = np.round(ttl_times * sampling_frequency_hz).astype(int)
    num_frames_ttl_duration = np.round(ttl_duration * sampling_frequency_hz).astype(int)
    ttl_intervals = (slice(start, start + num_frames_ttl_duration) for start in ttl_start_frames)

    for ttl_interval in ttl_intervals:
        trace[ttl_interval] += signal_mean

    return trace


def regenerate_test_cases(folder_path: DirectoryPath, regenerate_reference_images: bool = False):  # pragma: no cover
    """
    Regenerate the test cases of the file included in the main testing suite, which is frozen between breaking changes.

    Parameters
    ----------
    folder_path : PathType
        Folder to save the resulting NWB file in. For use in the testing suite, this must be the
        '/test_testing/test_mock_ttl/' subfolder adjacent to the 'test_mock_tt.py' file.
    regenerate_reference_images : bool
        If true, uses the kaleido package with plotly (you may need to install both) to regenerate the images used
        as references in the documentation.
    """
    folder_path = Path(folder_path)

    if regenerate_reference_images:
        assert is_package_installed("plotly") and is_package_installed("kaleido"), (
            "To regenerate the reference images, " "you must install both plotly and kaleido!"
        )
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        image_file_path = folder_path / "example_ttl_reference.png"

    nwbfile_path = folder_path / "mock_ttl_examples.nwb"
    compression_options = dict(compression="gzip", compression_opts=9)
    unit = "Volts"
    rate = 1000.0  # For non-default series to produce less data

    nwbfile = mock_NWBFile()

    # Test Case 1: Default
    default_ttl_signal = generate_mock_ttl_signal()
    nwbfile.add_acquisition(
        TimeSeries(
            name="DefaultTTLSignal",
            unit=unit,
            rate=25000.0,
            data=H5DataIO(data=default_ttl_signal, chunks=default_ttl_signal.shape, **compression_options),
        )
    )

    non_default_series = dict()

    # Test Case 2: Irregular short pulses
    irregular_short_pulses = generate_mock_ttl_signal(
        signal_duration=2.5, ttl_times=[0.22, 1.37], ttl_duration=0.25, sampling_frequency_hz=rate
    )
    non_default_series.update(IrregularShortPulses=irregular_short_pulses)

    # Test Case 3: Non-default regular
    non_default_regular = generate_mock_ttl_signal(
        signal_duration=2.7,
        ttl_times=[0.2, 1.2, 2.2],
        ttl_duration=0.3,
        sampling_frequency_hz=rate,
    )
    non_default_series.update(NonDefaultRegular=non_default_regular)

    # Test Case 4: Non-default regular with adjusted means
    non_default_regular_adjusted_means = generate_mock_ttl_signal(
        signal_duration=2.7,
        ttl_times=[0.2, 1.2, 2.2],
        ttl_duration=0.3,
        sampling_frequency_hz=rate,
        baseline_mean=300,
        signal_mean=20000,
    )
    non_default_series.update(NonDefaultRegularAdjustedMeans=non_default_regular_adjusted_means)

    # Test Case 5: Irregular short pulses with adjusted noise
    irregular_short_pulses_adjusted_noise = generate_mock_ttl_signal(
        signal_duration=2.5,
        ttl_times=[0.22, 1.37],
        ttl_duration=0.25,
        sampling_frequency_hz=rate,
        channel_noise=2,
    )
    non_default_series.update(IrregularShortPulsesAdjustedNoise=irregular_short_pulses_adjusted_noise)

    # Test Case 6: Non-default regular as floats
    non_default_regular_as_floats = generate_mock_ttl_signal(
        signal_duration=2.7,
        ttl_times=[0.2, 1.2, 2.2],
        ttl_duration=0.3,
        sampling_frequency_hz=rate,
        dtype="float32",
    )
    non_default_series.update(NonDefaultRegularFloats=non_default_regular_as_floats)

    # Test Case 7: Non-default regular as floats with adjusted means and noise (which are also, then, floats)
    non_default_regular_as_floats_adjusted_means_and_noise = generate_mock_ttl_signal(
        signal_duration=2.7,
        ttl_times=[0.2, 1.2, 2.2],
        ttl_duration=0.3,
        sampling_frequency_hz=rate,
        dtype="float32",
        baseline_mean=1.1,
        signal_mean=7.2,
        channel_noise=0.4,
    )
    non_default_series.update(FloatsAdjustedMeansAndNoise=non_default_regular_as_floats_adjusted_means_and_noise)

    # Test Case 8: Non-default regular as uint16
    non_default_regular_as_uint16 = generate_mock_ttl_signal(
        signal_duration=2.7,
        ttl_times=[0.2, 1.2, 2.2],
        ttl_duration=0.3,
        sampling_frequency_hz=rate,
        dtype="uint16",
    )
    non_default_series.update(NonDefaultRegularUInt16=non_default_regular_as_uint16)

    # Test Case 9: Irregular short pulses with different seed
    irregular_short_pulses_different_seed = generate_mock_ttl_signal(
        signal_duration=2.5,
        ttl_times=[0.22, 1.37],
        ttl_duration=0.25,
        sampling_frequency_hz=rate,
        random_seed=1,
    )
    non_default_series.update(IrregularShortPulsesDifferentSeed=irregular_short_pulses_different_seed)

    if regenerate_reference_images:
        num_cols = 5
        plot_index = 1
        subplot_titles = ["Default"]
        subplot_titles.extend(list(non_default_series))
        fig = make_subplots(rows=2, cols=num_cols, subplot_titles=subplot_titles)
        fig.add_trace(go.Scatter(y=default_ttl_signal, text="Default"), row=1, col=1)

    for time_series_name, time_series_data in non_default_series.items():
        nwbfile.add_acquisition(
            TimeSeries(
                name=time_series_name,
                unit=unit,
                rate=rate,
                data=H5DataIO(data=time_series_data, chunks=time_series_data.shape, **compression_options),
            )
        )

        if regenerate_reference_images:
            fig.add_trace(
                go.Scatter(y=time_series_data, text=time_series_name),
                row=math.floor(plot_index / num_cols) + 1,
                col=int(plot_index % num_cols) + 1,
            )
            plot_index += 1

    if regenerate_reference_images:
        fig.update_annotations(font_size=6)
        fig.update_layout(showlegend=False)
        fig.update_yaxes(tickfont=dict(size=5))
        fig.update_xaxes(showticklabels=False)
        fig.write_image(file=image_file_path)

    with NWBHDF5IO(path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)
