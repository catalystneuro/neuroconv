.. _convert_video_formats_with_ffmpeg:

Converting Video Formats with FFmpeg for DANDI Upload
=====================================================

This guide explains how to convert bespoke video file formats to DANDI-compatible formats using FFmpeg,
enabling successful conversion to NWB format and upload to the DANDI Archive.

Why Convert Video Formats?
--------------------------

DANDI requires videos to be in specific formats for upload. The supported video file extensions are:

- ``.mp4`` (recommended)
- ``.avi``
- ``.wmv``
- ``.mov``
- ``.flv``
- ``.mkv``

.. note::
   NeuroConv's video interface currently lists ``.flx`` instead of ``.flv`` in its supported formats.
   If you have ``.flv`` files, they should work fine with DANDI after conversion, but you may need
   to rename them to ``.flx`` for NeuroConv or convert them to ``.mp4`` using the examples below.

If your behavioral videos are in other formats (e.g., ``.m4v``, ``.webm``, ``.3gp``, proprietary formats),
you'll need to convert them before using NeuroConv's video interfaces.

Installing FFmpeg
-----------------

FFmpeg is a powerful, open-source multimedia framework that can handle video conversion tasks.

**Installation:**

- **Windows**: Download from https://ffmpeg.org/download.html or use ``winget install ffmpeg``
- **macOS**: Use Homebrew: ``brew install ffmpeg``
- **Linux**: Use your package manager, e.g., ``sudo apt install ffmpeg`` (Ubuntu/Debian)

Verify installation by running:

.. code-block:: bash

    ffmpeg -version

Basic Video Conversion Examples
-------------------------------

Convert to MP4 (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

MP4 with H.264 codec is the most widely supported format:

.. code-block:: bash

    # Basic conversion to MP4
    ffmpeg -i input_video.webm output_video.mp4

    # Convert with quality control (CRF 18-23 for high quality)
    ffmpeg -i input_video.m4v -c:v libx264 -crf 20 -c:a aac output_video.mp4

Convert Multiple Files
~~~~~~~~~~~~~~~~~~~~~

Convert all files in a directory:

.. code-block:: bash

    # Convert all .webm files to .mp4
    for file in *.webm; do
        ffmpeg -i "$file" -c:v libx264 -crf 20 -c:a aac "${file%.webm}.mp4"
    done

    # Windows batch command
    for %i in (*.webm) do ffmpeg -i "%i" -c:v libx264 -crf 20 -c:a aac "%~ni.mp4"

Format Compatibility Note
~~~~~~~~~~~~~~~~~~~~~~~~~

While DANDI supports ``.flv`` files, NeuroConv's current interface lists ``.flx`` format.
For maximum compatibility, it's recommended to convert to ``.mp4`` format:

.. code-block:: bash

    # Convert .flv to .mp4 (recommended for both DANDI and NeuroConv)
    ffmpeg -i input_video.flv -c:v libx264 -crf 20 -c:a aac output_video.mp4

Advanced Conversion Options
---------------------------

Lossless Conversion
~~~~~~~~~~~~~~~~~~

For critical research data where quality preservation is essential:

.. code-block:: bash

    # Lossless H.264 encoding
    ffmpeg -i input_video.avi -c:v libx264 -preset veryslow -crf 0 -c:a copy output_video.mp4

    # FFV1 codec for true lossless compression (larger files)
    ffmpeg -i input_video.avi -c:v ffv1 -level 3 -c:a copy output_video.mkv

Preserve Original Quality
~~~~~~~~~~~~~~~~~~~~~~~~

When you want to maintain the original video quality while changing the container:

.. code-block:: bash

    # Copy video and audio streams without re-encoding
    ffmpeg -i input_video.m4v -c copy output_video.mp4

    # This is fast but may not work if codecs are incompatible with target format

Resize Videos
~~~~~~~~~~~~

Reduce file size by resizing (useful for large behavioral videos):

.. code-block:: bash

    # Resize to 720p while maintaining aspect ratio
    ffmpeg -i input_video.avi -vf scale=-1:720 -c:v libx264 -crf 23 output_video.mp4

    # Resize to specific dimensions
    ffmpeg -i input_video.avi -vf scale=1280:720 -c:v libx264 -crf 23 output_video.mp4

Extract Video Segments
~~~~~~~~~~~~~~~~~~~~~

If you only need specific portions of your video:

.. code-block:: bash

    # Extract 30 seconds starting from 1 minute mark
    ffmpeg -i input_video.mp4 -ss 00:01:00 -t 00:00:30 -c copy output_segment.mp4

    # Extract using frame numbers (if you know the frame rate)
    ffmpeg -i input_video.mp4 -vf select='between(n\,1000\,2000)' -vsync vfr output_frames.mp4

Quality and Compression Considerations
-------------------------------------

For Behavioral Analysis
~~~~~~~~~~~~~~~~~~~~~~

- **Recommended**: Use CRF 20-23 for good quality with reasonable file sizes
- **High quality**: Use CRF 18 or lower (larger files)
- **Web streaming**: Use CRF 24-28 (smaller files, suitable for previews)

.. code-block:: bash

    # Balanced quality for behavioral analysis
    ffmpeg -i input_video.avi -c:v libx264 -crf 22 -preset medium -c:a aac -b:a 128k output_video.mp4

For Neural Data Videos
~~~~~~~~~~~~~~~~~~~~~

When videos contain neural data or require precise frame-by-frame analysis:

.. code-block:: bash

    # Lossless conversion preserving every detail
    ffmpeg -i input_video.avi -c:v libx264 -preset veryslow -crf 0 -c:a copy output_video.mp4

Integration with NeuroConv
-------------------------

After converting your videos to DANDI-compatible formats, use them with NeuroConv's video interfaces:

.. code-block:: python

    from neuroconv.datainterfaces import ExternalVideoInterface
    from pathlib import Path

    # Use your converted video file
    converted_video_path = Path("path/to/converted_video.mp4")

    # Create interface with converted video
    interface = ExternalVideoInterface(
        file_paths=[converted_video_path],
        verbose=False,
        video_name="BehaviorVideo"
    )

    # Continue with normal NeuroConv workflow
    metadata = interface.get_metadata()
    # ... rest of conversion process

For detailed information on using NeuroConv's video interfaces, see the
:doc:`../conversion_examples_gallery/behavior/video` guide.

Troubleshooting Common Issues
----------------------------

"Codec not supported" errors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you encounter codec errors, try using different codecs:

.. code-block:: bash

    # Try different video codec
    ffmpeg -i input_video.unknown -c:v libx265 -crf 23 -c:a aac output_video.mp4

    # For compatibility with older players
    ffmpeg -i input_video.unknown -c:v libx264 -profile:v baseline -level 3.0 -c:a aac output_video.mp4

Large file sizes
~~~~~~~~~~~~~~~~

To reduce file size without significant quality loss:

.. code-block:: bash

    # Two-pass encoding for better compression
    ffmpeg -i input_video.avi -c:v libx264 -b:v 2M -pass 1 -f null /dev/null
    ffmpeg -i input_video.avi -c:v libx264 -b:v 2M -pass 2 -c:a aac output_video.mp4

Audio sync issues
~~~~~~~~~~~~~~~~

If audio becomes out of sync after conversion:

.. code-block:: bash

    # Re-sync audio
    ffmpeg -i input_video.avi -c:v libx264 -crf 23 -af aresample=async=1 -c:a aac output_video.mp4

Batch Processing Scripts
-----------------------

Python script for batch conversion:

.. code-block:: python

    import subprocess
    from pathlib import Path

    def convert_videos_to_mp4(input_dir, output_dir, quality=22):
        """Convert all video files in a directory to MP4 format."""
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        # Common video extensions that might need conversion
        video_extensions = {'.webm', '.m4v', '.3gp', '.flv', '.wmv', '.avi', '.mov', '.mkv'}

        for video_file in input_path.iterdir():
            if video_file.suffix.lower() in video_extensions:
                output_file = output_path / f"{video_file.stem}.mp4"

                cmd = [
                    'ffmpeg', '-i', str(video_file),
                    '-c:v', 'libx264', '-crf', str(quality),
                    '-c:a', 'aac', '-y',  # -y to overwrite existing files
                    str(output_file)
                ]

                print(f"Converting {video_file.name}...")
                subprocess.run(cmd, check=True)
                print(f"Saved as {output_file.name}")

    # Usage example
    convert_videos_to_mp4("./raw_videos", "./converted_videos", quality=20)

Additional Resources
-------------------

- `FFmpeg Documentation <https://ffmpeg.org/documentation.html>`_
- `DANDI Video Requirements <https://dandi.github.io/dandi-cli/>`_
- `NeuroConv Video Interface Documentation <../conversion_examples_gallery/behavior/video.html>`_
- `NWB Video Best Practices <https://nwbinspector.readthedocs.io/en/dev/best_practices/image_series.html#storage-of-imageseries>`_

.. note::
    Always test your converted videos with a small sample first to ensure they work correctly
    with your specific NeuroConv workflow before converting large batches.
