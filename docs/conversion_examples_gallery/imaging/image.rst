Image data conversion
---------------------

The :py:class:`~neuroconv.datainterfaces.image.imageinterface.ImageInterface` allows conversion of various image formats (PNG, JPG, TIFF) to NWB. The interface efficiently handles different color modes and can store images in either the acquisition or stimulus group of the NWB file.

Install NeuroConv with the additional dependencies necessary for reading image data:

.. code-block:: bash

    pip install "neuroconv[image]"

Supported Image Modes
~~~~~~~~~~~~~~~~~~~~~

The interface automatically converts the following PIL image modes to their corresponding NWB types:

- L (grayscale) → GrayscaleImage
- RGB → RGBImage
- RGBA → RGBAImage
- LA (luminance + alpha) → RGBAImage (automatically converted)

Example Usage
~~~~~~~~~~~~~

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
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)


Key Features
~~~~~~~~~~~~

1. **Memory Efficiency**: Uses an iterator pattern to load images only when needed, making it suitable for a large collection of images without consuming excessive memory.

2. **Automatic Mode Conversion**: Handles LA (luminance + alpha) to RGBA conversion automatically.

3. **Input Methods**:
    - List of files: ``interface = ImageInterface(file_paths=["image1.png", "image2.jpg"])``
    - Directory: ``interface = ImageInterface(folder_path="images_directory")``

4. **Storage Location**: Images can be stored in either acquisition or stimulus:

   .. code-block:: python

       # Store in acquisition (default)
       interface = ImageInterface(file_paths=["image.png"], images_location="acquisition")

       # Store in stimulus
       interface = ImageInterface(file_paths=["image.png"], images_location="stimulus")


Specifying Metadata
~~~~~~~~~~~~~~~~~~~

The examples above show how to convert image data without specifying any metadata, in which case the metadata will be
automatically generated with default values. To customize the NWB file annotations, specify the metadata
using the formats described below.

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
