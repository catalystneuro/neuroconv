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

MP4 is the most widely supported format. Use ``-c copy`` to copy streams without re-encoding for fastest conversion:

.. code-block:: bash

    # Basic conversion to MP4 (copies streams without re-encoding)
    ffmpeg -i input_video.webm -c copy output_video.mp4

Batch Processing
~~~~~~~~~~~~~~~~

Convert all files in a directory:

.. code-block:: bash

    # Convert all .webm files to .mp4 (Linux/macOS)
    for file in *.webm; do
        ffmpeg -i "$file" -c copy "${file%.webm}.mp4"
    done

    # Windows batch command
    for %i in (*.webm) do ffmpeg -i "%i" -c copy "%~ni.mp4"

Python script for batch conversion:

.. code-block:: python

    import subprocess
    from pathlib import Path

    def convert_videos_to_mp4(input_dir, output_dir):
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
                    '-c', 'copy', '-y',  # -y to overwrite existing files
                    str(output_file)
                ]

                print(f"Converting {video_file.name}...")
                subprocess.run(cmd, check=True)
                print(f"Saved as {output_file.name}")

    # Usage example
    convert_videos_to_mp4("./raw_videos", "./converted_videos")

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

Additional Resources
--------------------

- `FFmpeg Documentation <https://ffmpeg.org/documentation.html>`_
- `DANDI CLI Issue #1328 (FLV format support) <https://github.com/dandi/dandi-cli/issues/1328>`_
- `NeuroConv Video Interface Documentation <../conversion_examples_gallery/behavior/video.html>`_
- `NWB Video Best Practices <https://nwbinspector.readthedocs.io/en/dev/best_practices/image_series.html#storage-of-imageseries>`_

.. note::
    Always test your converted videos with a small sample first to ensure they work correctly
    with your specific NeuroConv workflow before converting large batches.
