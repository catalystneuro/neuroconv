"""Author: Cody Baker."""
from typing import Optional, Union
from pathlib import Path

import numpy as np
from numpy.typing import DTypeLike
from nwbinspector.tools import make_minimal_nwbfile
from nwbinspector.utils import is_module_installed
from pynwb import NWBHDF5IO, TimeSeries, H5DataIO

from ...utils import IntType, FloatType, ArrayType, FolderPathType


def generate_mock_ttl_signal(
    signal_duration: float = 5.5,
    sampling_frequency_hz: float = 25000.0,
    ttl_on_duration: float = 1.0,
    ttl_off_duration: Optional[float] = None,
    ttl_times: Optional[ArrayType] = None,
    dtype: DTypeLike = "int16",
    baseline_mean: Optional[Union[IntType, FloatType]] = None,
    signal_mean: Optional[Union[IntType, FloatType]] = None,
    channel_noise: Optional[Union[IntType, FloatType]] = None,
    random_seed: Optional[int] = 0,
) -> np.ndarray:
    """
    Generate a synthetic signal of TTL pulses similar to those seen in .nidq.bin files using SpikeGLX.

    Parameters
    ----------
    signal_duration: float, optional
        The number of seconds to simulate.
        The default is 5.5 seconds.
    sampling_frequency_hz: float, optional
        The sampling frequency of the signal in Hz.
        The default is 25000 Hz; similar to that of .nidq.bin files.
    ttl_on_duration: float, optional
        How long the TTL pulse stays in the 'on' state when triggered.
        The default is 1 second to match the default frequency of 2 seconds to emulate a regular metronomic pulse.
    ttl_off_duration: float, optional
        How long the TTL pulse stays in the 'off' state when triggered.
        The default is 1 second to match the default frequency of 2 seconds to emulate a regular metronomic pulse.
    ttl_times: array of floats, optional
        If an irregular series of TTL pulses are desired, specify the exact sequence of timings.
        The default assumes regular series with the `ttl_frequency_hz` rate.
    dtype: numpy data type or one of its accepted string input
        The data type of the trace and its specifiable parameters.
        Recommended to be int16 for maximum efficiency, but can also be any size float to represent voltage scalings.
        Defaults to int16.
    baseline_mean: integer or float, depending on specified 'dtype', optional
        The average value for the baseline; usually around 0 Volts.
        The default is apprimxately 0.005645752 Volts, estimated from a real example of a TTL pulse in a .nidq.bin file.
    signal_mean: integer or float, depending on specified 'dtype', optional
        The average value for the signal; usually around 5 Volts.
        The default is apprimxately 4.980773925 Volts, estimated from a real example of a TTL pulse in a .nidq.bin file.
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
    if ttl_times is not None:
        assert ttl_off_duration is None, "When specifying `ttl_times`, you do not need to specify `ttl_off_duration`."
    else:  # Default is to specify a regular TTL signal
        ttl_off_duration = ttl_off_duration or 1.0

    dtype = np.dtype(dtype)

    # Default values estimated from real files
    baseline_mean_int16_default = 37
    signal_mean_int16_default = 32642
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
    num_frames = np.ceil(signal_duration * sampling_frequency_hz).astype(int)
    trace = (np.random.randn(num_frames) * channel_noise + baseline_mean).astype(dtype)

    if ttl_times is not None:
        ttl_times = np.array(ttl_times)
    else:
        # Start halfway through an off pulse
        total_cycle_duration = ttl_off_duration + ttl_on_duration
        cycle_start_times = np.arange(0, signal_duration, total_cycle_duration)
        num_cycles = len(cycle_start_times)
        num_ttl_pulses = (
            num_cycles if signal_duration - cycle_start_times[-1] - ttl_off_duration > 0 else num_cycles - 1
        )
        ttl_times = np.linspace(start=ttl_off_duration / 2, stop=signal_duration, num=num_ttl_pulses)

    ttl_start_frames = np.round(ttl_times * sampling_frequency_hz).astype(int)
    num_frames_ttl_on_duration = np.round(ttl_on_duration * sampling_frequency_hz).astype(int)
    ttl_on_durations = (slice(start, start + num_frames_ttl_on_duration) for start in ttl_start_frames)

    for ttl_frames in ttl_on_durations:
        trace[ttl_frames] += signal_mean

    return trace


def regenerate_test_cases(folder_path: FolderPathType, regenerate_reference_images: bool = False):
    """
    Regenerate the test cases of the file included in the main testing suite, which is frozen between breaking changes.

    Parameters
    ----------
    folder_path: PathType
        Folder to save the resulting NWB file in. For use in the testing suite, this must be the
        '/test_testing/test_mock_ttl/' subfolder adjacent to the 'test_mock_tt.py' file.
    regenerate_reference_images: boolean
        If true, uses the kaleido package with plotly (you may need to install both) to regenerate the images used
        as references in the documentation.
    """
    folder_path = Path(folder_path)

    if regenerate_reference_images:
        assert is_module_installed("kaleido") and is_module_installed(
            "kaleido"
        ), "To regenerate the reference images, you must install both plotly and kaleido!"
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        image_file_path = folder_path / "example_ttl_reference.png"

    nwbfile_path = folder_path / "mock_ttl_examples.nwb"
    compression_options = dict(compression="gzip", compression_opts=9)
    unit = "Volts"
    rate = 1000.0  # For non-default series to produce less data

    nwbfile = make_minimal_nwbfile()

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

    # Test Case 2: Irregular short pulses
    non_default_series = dict()
    irregular_short_pulses = generate_mock_ttl_signal(
        sampling_frequency_hz=rate, signal_duration=2.5, ttl_times=[0.22, 1.37], ttl_on_duration=0.25
    )
    non_default_series.update(IrregularShortPulses=irregular_short_pulses)

    # Test Case 3: Non-default regular
    non_default_regular = generate_mock_ttl_signal(
        sampling_frequency_hz=rate,
        signal_duration=3.5,
        ttl_on_duration=0.3,
        ttl_off_duration=0.6,
    )
    non_default_series.update(NonDefaultRegular=non_default_regular)

    # Test Case 4: Non-default regular with adjusted means
    non_default_regular_adjusted_means = generate_mock_ttl_signal(
        sampling_frequency_hz=rate,
        signal_duration=3.5,
        ttl_on_duration=0.3,
        ttl_off_duration=0.6,
        baseline_mean=300,
        signal_mean=20000,
    )
    non_default_series.update(NonDefaultRegularAdjustedMeans=non_default_regular_adjusted_means)

    # Test Case 5: Irregular short pulses with adjusted noise
    irregular_short_pulses_adjusted_noise = generate_mock_ttl_signal(
        sampling_frequency_hz=rate,
        signal_duration=2.5,
        ttl_times=[0.22, 1.37],
        ttl_on_duration=0.25,
        channel_noise=2,
    )
    non_default_series.update(IrregularShortPulsesAdjustedNoise=irregular_short_pulses_adjusted_noise)

    # Test Case 6: Non-default regular as floats
    non_default_regular_as_floats = generate_mock_ttl_signal(
        sampling_frequency_hz=rate, signal_duration=3.5, ttl_on_duration=0.3, ttl_off_duration=0.6, dtype="float32"
    )
    non_default_series.update(NonDefaultRegularFloats=non_default_regular_as_floats)

    # Test Case 7: Irregular short pulses with different seed
    irregular_short_pulses_different_seed = generate_mock_ttl_signal(
        sampling_frequency_hz=rate,
        signal_duration=2.5,
        ttl_times=[0.22, 1.37],
        ttl_on_duration=0.25,
        random_seed=1,
    )
    non_default_series.update(IrregularShortPulsesDifferentSeed=irregular_short_pulses_different_seed)

    if regenerate_reference_images:
        num_cols = 4
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
                row=np.floor(plot_index / num_cols).astype(int) + 1,
                col=int(plot_index % num_cols) + 1,
            )
            plot_index += 1

    if regenerate_reference_images:
        fig.update_annotations(font_size=8)
        fig.write_image(file=image_file_path)

    with NWBHDF5IO(path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)
