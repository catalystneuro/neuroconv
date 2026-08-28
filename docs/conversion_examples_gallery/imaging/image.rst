Image data conversion
---------------------

The NWB standard provides two ways to store an image, and NeuroConv has an interface for each. An
``ExternalImage`` holds the path of an image file and leaves the pixels in it, which is what the
:py:class:`~neuroconv.datainterfaces.image.externalimageinterface.ExternalImageInterface` writes. An ``Image``
holds the pixel data itself, which is what the
:py:class:`~neuroconv.datainterfaces.image.imageinterface.ImageInterface` writes, reading each file to get the
pixels out of it. Either way the images land in the same ``Images`` container.

Write the images by reference by default. That keeps the file as the microscope or the camera wrote it, its
format, its color mode and its bytes, where embedding stores decoded pixels instead, so the original file cannot
be recovered from the NWB file and an LA image comes back as RGBA.

Embed the images when they are meant to be read as arrays, either by an analysis or as the stimulus templates that
an ``IndexSeries`` indexes into, and when the NWB file has to stand on its own rather than travel next to the
folder it points at. Embedding is also the only option for a format that NWB does not accept by reference, which
is everything other than PNG, JPEG and GIF, TIFF above all.

Both interfaces take either a list of files, ``file_paths=["image1.png", "image2.png"]``, or a folder,
``folder_path="images_directory"``, and both store the images in the acquisition group of the NWB file, or in the
stimulus group when ``parent_container="stimulus"`` is passed.

Install NeuroConv with the additional dependencies necessary for reading image data:

.. code-block:: bash

    pip install "neuroconv[image]"

Writing Images by Reference
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :py:class:`~neuroconv.datainterfaces.image.externalimageinterface.ExternalImageInterface` writes the path of
each image into the NWB file instead of its pixels, as an ``ExternalImage``.

NWB allows only PNG, JPEG and GIF by reference, and the format is read from the file itself rather than from its
suffix, so a mislabeled file is classified by what it holds. Any other format has to be embedded with
``ImageInterface``. No color mode conversion happens, since no pixels are written: the mode is recorded as PIL
reports it, so an LA image stays LA instead of becoming RGBA.

.. code-block:: python

    >>> from datetime import datetime
    >>> from pathlib import Path
    >>> from tempfile import mkdtemp
    >>> from zoneinfo import ZoneInfo
    >>>
    >>> import numpy as np
    >>> from PIL import Image
    >>>
    >>> from neuroconv.datainterfaces import ExternalImageInterface
    >>>
    >>> # Create a temporary directory holding the images that stay outside of the NWB file
    >>> image_dir = Path(mkdtemp())
    >>> rgb_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    >>> Image.fromarray(rgb_array, mode='RGB').save(image_dir / 'histology.png')
    >>>
    >>> interface = ExternalImageInterface(folder_path=str(image_dir))
    >>>
    >>> metadata = interface.get_metadata()
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

Embedding the Images
~~~~~~~~~~~~~~~~~~~~

The :py:class:`~neuroconv.datainterfaces.image.imageinterface.ImageInterface` reads the pixels and writes them
into the NWB file, which is what a format that cannot be written by reference (TIFF, WebP) requires. The images
are read one at a time as the file is written, so a large collection does not have to fit in memory.

Embedding maps the PIL image mode onto the NWB image type:

- L (grayscale) → GrayscaleImage
- RGB → RGBImage
- RGBA → RGBAImage
- LA (luminance + alpha) → RGBAImage (automatically converted)

.. code-block:: python

    >>> from datetime import datetime
    >>> from pathlib import Path
    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import ImageInterface
    >>> from pynwb import NWBHDF5IO, NWBFile
    >>>
    >>> # Create example images of different modes
    >>> from PIL import Image
    >>> import numpy as np
    >>>
    >>> # Create a temporary directory for our example images
    >>> from tempfile import mkdtemp
    >>> image_dir = Path(mkdtemp())
    >>>
    >>> # Create example images
    >>> # RGB image (3 channels)
    >>> rgb_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    >>> rgb_image = Image.fromarray(rgb_array, mode='RGB')
    >>> rgb_image.save(image_dir / 'rgb_image.png')
    >>>
    >>> # Grayscale image (L mode)
    >>> gray_array = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    >>> gray_image = Image.fromarray(gray_array, mode='L')
    >>> gray_image.save(image_dir / 'gray_image.png')
    >>>
    >>> # RGBA image (4 channels)
    >>> rgba_array = np.random.randint(0, 255, (100, 100, 4), dtype=np.uint8)
    >>> rgba_image = Image.fromarray(rgba_array, mode='RGBA')
    >>> rgba_image.save(image_dir / 'rgba_image.png')
    >>>
    >>> # LA image (luminance + alpha)
    >>> la_array = np.random.randint(0, 255, (100, 100, 2), dtype=np.uint8)
    >>> la_image = Image.fromarray(la_array, mode='LA')
    >>> la_image.save(image_dir / 'la_image.png')
    >>>
    >>> # Initialize the image interface
    >>> interface = ImageInterface(folder_path=str(image_dir))
    >>>
    >>> # Get metadata from the interface
    >>> metadata = interface.get_metadata()
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)


Specifying Metadata
~~~~~~~~~~~~~~~~~~~

The examples above show how to convert image data without specifying any metadata, in which case the metadata will be
automatically generated with default values. To customize the NWB file annotations, specify the metadata
using the formats described below. Both interfaces read the same structure, so the container name and description
and the per-image names and descriptions are given the same way whether the images are written by reference or
embedded. The one field that is not shared is ``resolution``, which NWB declares on the embedded image type alone,
so ``ExternalImageInterface`` rejects it.

You can customize the container name and add descriptions, names, and resolution to individual images in the container:

.. code-block:: python

    >>> from datetime import datetime
    >>> from pathlib import Path
    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import ImageInterface
    >>> from neuroconv.utils import dict_deep_update
    >>> from PIL import Image
    >>> import numpy as np
    >>> from tempfile import mkdtemp
    >>>
    >>> # Create a temporary directory for our example images
    >>> image_dir = Path(mkdtemp())
    >>>
    >>> # Create example images with specific file paths
    >>> stimulus_image_file_path = image_dir / 'stimulus_image.png'
    >>> baseline_image_file_path = image_dir / 'baseline_image.png'
    >>>
    >>> rgb_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    >>> rgb_image = Image.fromarray(rgb_array, mode='RGB')
    >>> rgb_image.save(stimulus_image_file_path)
    >>>
    >>> gray_array = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    >>> gray_image = Image.fromarray(gray_array, mode='L')
    >>> gray_image.save(baseline_image_file_path)
    >>>
    >>> # Create interface with custom container name
    >>> metadata_key = "ExperimentalImages"
    >>> interface = ImageInterface(
    ...     folder_path=str(image_dir),
    ...     metadata_key=metadata_key
    ... )
    >>>
    >>> # Get metadata and customize both container and individual images
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Customize container description
    >>> metadata["Images"][metadata_key]["description"] = "Collection of experimental stimulus and baseline images"
    >>>
    >>> # Customize individual image metadata (names, descriptions, resolution)
    >>> stimulus_image_file_path_str = str(stimulus_image_file_path)
    >>> baseline_image_file_path_str = str(baseline_image_file_path)
    >>> metadata["Images"][metadata_key]["images"][stimulus_image_file_path_str]["name"] = "visual_stimulus"
    >>> metadata["Images"][metadata_key]["images"][stimulus_image_file_path_str]["description"] = "Visual stimulus presented to subject"
    >>> metadata["Images"][metadata_key]["images"][stimulus_image_file_path_str]["resolution"] = 2.5  # pixels/cm
    >>> metadata["Images"][metadata_key]["images"][baseline_image_file_path_str]["name"] = "baseline_recording"
    >>> metadata["Images"][metadata_key]["images"][baseline_image_file_path_str]["description"] = "Baseline image before stimulus"
    >>> metadata["Images"][metadata_key]["images"][baseline_image_file_path_str]["resolution"] = 2.5  # pixels/cm
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

.. note::
    Individual image metadata is specified using the full file path as the key in the "images" dictionary.
    You can customize the name, description, and resolution for each image. Resolution should be specified
    in pixels/cm if provided. If not specified, individual image names default to the filename stem.
