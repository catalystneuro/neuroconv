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
   NeuroConv's video interfaces now correctly support ``.flv`` format files.
   If you have videos in other formats (e.g., ``.m4v``, ``.webm``, ``.3gp``, proprietary formats),
   you'll need to convert them to a DANDI-compatible format before using NeuroConv.

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

Basic Video Conversion
----------------------

Convert to MP4 (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

MP4 with H.264 codec is the most widely supported format:

.. code-block:: bash

    # Basic conversion to MP4
    ffmpeg -i input_video.webm output_video.mp4

    # Convert with quality control (CRF 18-23 for high quality)
    ffmpeg -i input_video.m4v -c:v libx264 -crf 20 -c:a aac output_video.mp4

Batch Processing
~~~~~~~~~~~~~~~~

Convert all files in a directory:

.. code-block:: bash

    # Convert all .webm files to .mp4 (Linux/macOS)
    for file in *.webm; do
        ffmpeg -i "$file" -c:v libx264 -crf 20 -c:a aac "${file%.webm}.mp4"
    done

    # Windows batch command
    for %i in (*.webm) do ffmpeg -i "%i" -c:v libx264 -crf 20 -c:a aac "%~ni.mp4"

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

Integration with NeuroConv
--------------------------

After converting your videos to DANDI-compatible formats, use them with NeuroConv's video interfaces.

For behavioral videos (recommended to store as external files):

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

For neural data videos (store internally when lossless compression is needed):

.. code-block:: python

    from neuroconv.datainterfaces import InternalVideoInterface

    # Create interface for internal video storage
    interface = InternalVideoInterface(
        file_path=converted_video_path,
        verbose=False,
        video_name="NeuralVideo"
    )

For detailed information on using NeuroConv's video interfaces, see the
:doc:`../conversion_examples_gallery/behavior/video` guide.

Common Conversion Options
-------------------------

**For behavioral analysis videos:**

.. code-block:: bash

    # Balanced quality for behavioral analysis
    ffmpeg -i input_video.avi -c:v libx264 -crf 22 -preset medium -c:a aac output_video.mp4

**For lossless conversion (neural data):**

.. code-block:: bash

    # Lossless H.264 encoding
    ffmpeg -i input_video.avi -c:v libx264 -preset veryslow -crf 0 -c:a copy output_video.mp4

**Troubleshooting codec errors:**

.. code-block:: bash

    # Try different codecs if conversion fails
    ffmpeg -i input_video.unknown -c:v libx265 -crf 23 -c:a aac output_video.mp4

Additional Resources
--------------------

- `FFmpeg Documentation <https://ffmpeg.org/documentation.html>`_
- `DANDI Video Requirements <https://dandi.github.io/dandi-cli/>`_
- `DANDI CLI Issue #1328 (FLV format support) <https://github.com/dandi/dandi-cli/issues/1328>`_
- `NeuroConv Video Interface Documentation <../conversion_examples_gallery/behavior/video.html>`_
- `NWB Video Best Practices <https://nwbinspector.readthedocs.io/en/dev/best_practices/image_series.html#storage-of-imageseries>`_

.. note::
    Always test your converted videos with a small sample first to ensure they work correctly
    with your specific NeuroConv workflow before converting large batches.
