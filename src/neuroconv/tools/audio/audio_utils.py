import wave
from pathlib import Path


def get_wav_bit_depth(file_path):
    """
    Get the bit depth of a WAV file.
    
    Parameters
    ----------
    file_path : str or Path
        Path to the WAV file
        
    Returns
    -------
    int
        Bit depth of the WAV file (8, 16, 24, 32, etc.)
    """
    with wave.open(str(file_path), 'rb') as wav_file:
        sample_width = wav_file.getsampwidth()
        bit_depth = sample_width * 8
    return bit_depth
