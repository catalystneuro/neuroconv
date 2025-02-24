"""Functions for handling MP3 audio files."""

import numpy as np


def read_mp3(filename):
    """
    Read an MP3 file and return the sampling rate and audio data.

    Parameters
    ----------
    filename : str or Path
        Path to the MP3 file.

    Returns
    -------
    sampling_rate : int
        The sampling rate of the audio file in Hz.
    data : numpy.ndarray
        The audio data as a numpy array.
    """
    from pydub import AudioSegment

    # Load the MP3 file
    audio = AudioSegment.from_mp3(str(filename))

    # Get the sampling rate
    sampling_rate = audio.frame_rate

    # Convert to numpy array
    # AudioSegment stores audio data as signed 16-bit integers
    # We need to convert it to a numpy array
    samples = np.array(audio.get_array_of_samples())

    # If stereo, reshape to a 2D array (samples, channels)
    if audio.channels == 2:
        samples = samples.reshape((-1, 2))

    return sampling_rate, samples
