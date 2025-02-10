Image Interface
==============

The ImageInterface allows you to convert various image formats (PNG, JPG, TIFF) to NWB. It supports different color modes and efficiently handles image loading to minimize memory usage.

Supported Image Modes
-------------------

The interface supports the following PIL image modes:

- L (grayscale) → GrayscaleImage
- RGB → RGBImage
- RGBA → RGBAImage
- LA (luminance + alpha) → RGBAImage (automatically converted)

Example Usage
------------

Here's an example demonstrating how to use the ImageInterface with different image modes:

.. code-block:: python

    from datetime import datetime
    from pathlib import Path
    from neuroconv.datainterfaces import ImageInterface
    from pynwb import NWBHDF5IO, NWBFile

    # Create example images of different modes
    from PIL import Image
    import numpy as np

    # Create a temporary directory for our example images
    from tempfile import mkdtemp
    image_dir = Path(mkdtemp())

    # Create example images
    # RGB image (3 channels)
    rgb_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    rgb_image = Image.fromarray(rgb_array, mode='RGB')
    rgb_image.save(image_dir / 'rgb_image.png')

    # Grayscale image (L mode)
    gray_array = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    gray_image = Image.fromarray(gray_array, mode='L')
    gray_image.save(image_dir / 'gray_image.png')

    # RGBA image (4 channels)
    rgba_array = np.random.randint(0, 255, (100, 100, 4), dtype=np.uint8)
    rgba_image = Image.fromarray(rgba_array, mode='RGBA')
    rgba_image.save(image_dir / 'rgba_image.png')

    # LA image (luminance + alpha)
    la_array = np.random.randint(0, 255, (100, 100, 2), dtype=np.uint8)
    la_image = Image.fromarray(la_array, mode='LA')
    la_image.save(image_dir / 'la_image.png')

    # Initialize the image interface
    interface = ImageInterface(folder_path=str(image_dir))

    # Create a basic NWBFile
    nwbfile = NWBFile(
        session_description="Image interface example session",
        identifier="IMAGE123",
        session_start_time=datetime.now().astimezone(),
        experimenter="Dr. John Doe",
        lab="Image Processing Lab",
        institution="Neural Image Institute",
        experiment_description="Example experiment demonstrating image conversion",
    )

    # Add the images to the NWB file
    interface.add_to_nwbfile(nwbfile)

    # Write the NWB file
    nwb_path = Path("image_example.nwb")
    with NWBHDF5IO(nwb_path, "w") as io:
        io.write(nwbfile)

    # Read the NWB file to verify
    with NWBHDF5IO(nwb_path, "r") as io:
        nwbfile = io.read()
        # Access the images container
        images_container = nwbfile.acquisition["images"]
        print(f"Number of images: {len(images_container.images)}")
        # Print information about each image
        for name, image in images_container.images.items():
            print(f"\nImage name: {name}")
            print(f"Image type: {type(image).__name__}")
            print(f"Image shape: {image.data.shape}")

Key Features
-----------

1. **Memory Efficiency**: Uses an iterator pattern to load images only when needed, making it suitable for large images or multiple images.

2. **Automatic Mode Conversion**: Handles LA (luminance + alpha) to RGBA conversion automatically while maintaining image information.

3. **Input Methods**:
   - List of files: ``interface = ImageInterface(file_paths=["image1.png", "image2.jpg"])``
   - Directory: ``interface = ImageInterface(folder_path="images_directory")``

4. **Flexible Storage Location**: Images can be stored in either acquisition or stimulus:
   .. code-block:: python

       # Store in acquisition (default)
       interface = ImageInterface(file_paths=["image.png"], images_location="acquisition")

       # Store in stimulus
       interface = ImageInterface(file_paths=["image.png"], images_location="stimulus")

Installation
-----------

To use the ImageInterface, install neuroconv with the image extra:

.. code-block:: bash

    pip install "neuroconv[image]"
