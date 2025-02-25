import tempfile
from pathlib import Path

from neuroconv.tools.audio import get_wav_bit_depth
from neuroconv.tools.testing.audio import create_24bit_wav_file


class TestAudioUtils:
    """Test the audio utility functions."""

    def test_get_wav_bit_depth(self):
        """Test that get_wav_bit_depth correctly identifies the bit depth of WAV files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a 24-bit WAV file
            file_path = Path(temp_dir) / "test_24bit.wav"
            create_24bit_wav_file(file_path)

            # Check that the bit depth is correctly identified as 24
            bit_depth = get_wav_bit_depth(file_path)
            assert bit_depth == 24, f"Expected bit depth of 24, got {bit_depth}"


if __name__ == "__main__":
    # Run the test directly
    test = TestAudioUtils()
    test.test_get_wav_bit_depth()
    print("All tests passed!")
