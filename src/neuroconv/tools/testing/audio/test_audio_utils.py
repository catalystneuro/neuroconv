import struct
import wave
from pathlib import Path

import numpy as np


def create_24bit_wav_file(output_path, duration=1.0, sample_rate=44100, frequency=440):
    """
    Create a 24-bit (3-byte) WAV file with a sine wave.

    Parameters
    ----------
    output_path : str or Path
        Path to save the WAV file
    duration : float, default: 1.0
        Duration of the audio in seconds
    sample_rate : int, default: 44100
        Sample rate in Hz
    frequency : int, default: 440
        Frequency of the sine wave in Hz

    Returns
    -------
    str
        Path to the created WAV file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate a sine wave
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    audio_data = np.sin(2 * np.pi * frequency * t)

    # Scale to 24-bit range (-2^23 to 2^23-1)
    max_value = 2**23 - 1
    audio_data = (audio_data * max_value).astype(np.int32)

    # Create WAV file
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(3)  # 3 bytes per sample (24-bit)
        wav_file.setframerate(sample_rate)

        # Pack the data manually as 24-bit (3-byte) values
        for sample in audio_data:
            # Convert to bytes, little-endian, 3 bytes
            packed_value = struct.pack("<i", sample)[:3]  # Take only the first 3 bytes
            wav_file.writeframes(packed_value)

    return str(output_path)


def create_test_wav_files(output_dir, num_files=1):
    """
    Create multiple test WAV files with different bit depths.

    Parameters
    ----------
    output_dir : str or Path
        Directory to save the WAV files
    num_files : int, default: 1
        Number of files to create

    Returns
    -------
    list
        Paths to the created WAV files
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    file_paths = []

    # Create 24-bit WAV files
    for i in range(num_files):
        file_path = output_dir / f"test_24bit_{i}.wav"
        create_24bit_wav_file(file_path)
        file_paths.append(str(file_path))

    return file_paths


if __name__ == "__main__":
    # Create a test directory in the current working directory
    test_dir = Path("test_wav_files")

    # Create test WAV files
    file_paths = create_test_wav_files(test_dir, num_files=2)

    print(f"Created {len(file_paths)} 24-bit WAV files:")
    for path in file_paths:
        print(f"  - {path}")
