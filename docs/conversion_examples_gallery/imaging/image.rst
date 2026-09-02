Image data conversion
---------------------

The NWB standard provides two ways to store an image, and NeuroConv has an interface for each. An
:py:class:`~pynwb.base.ExternalImage` holds the path of an image file and leaves the pixels in it, which is what
the :py:class:`~neuroconv.datainterfaces.image.externalimageinterface.ExternalImageInterface` writes. An
:py:class:`~pynwb.base.Image` holds the pixel data itself, which is what the
:py:class:`~neuroconv.datainterfaces.image.imageinterface.ImageInterface` writes, reading each file to get the
pixels out of it. Either way the images land in the same :py:class:`~pynwb.base.Images` container.

In most cases you should write the images as external. That keeps the full provenance of each file, its
format, its color mode, and the metadata standard image formats carry that NWB's :py:class:`~pynwb.base.Image` type has nowhere
to put, and it avoids duplicating images that more than one NWB file references.

Embed the images when something downstream wants the pixels as an array without decoding a file first, or when
the NWB file has to stand on its own rather than travel next to the folder it points at. Embedding is also
forced when the format is not PNG, JPEG or GIF, which is all NWB accepts by reference.

Both interfaces take either a list of files, ``file_paths=["image1.png", "image2.png"]``, or a folder,
``folder_path="images_directory"``, and both write the images to the acquisition group of the NWB file, or to the
stimulus group when the conversion option ``parent_container="stimulus"`` is given.

Install NeuroConv with the additional dependencies necessary for reading image data:

.. code-block:: bash

    pip install "neuroconv[image]"

Images as References
~~~~~~~~~~~~~~~~~~~~

The :py:class:`~neuroconv.datainterfaces.image.externalimageinterface.ExternalImageInterface` writes the path of
each image into the NWB file instead of its pixels, as an :py:class:`~pynwb.base.ExternalImage`.

NWB accepts only PNG, JPEG and GIF by reference, so any other format has to be embedded instead. Nothing about
the image is converted on the way in, since no pixels are written: the color mode is recorded as the file reports
it, so an LA image stays LA where ``ImageInterface`` would turn it into RGBA.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>>
    >>> from neuroconv.datainterfaces import ExternalImageInterface
    >>>
    >>> # Every PNG, JPEG and GIF in the folder becomes one image in the container
    >>> interface = ExternalImageInterface(folder_path=path_to_folder_with_images)
    >>>
    >>> metadata = interface.get_metadata()
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

Images as Arrays
~~~~~~~~~~~~~~~~

The :py:class:`~neuroconv.datainterfaces.image.imageinterface.ImageInterface` reads the pixels and writes them
into the NWB file.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>>
    >>> from neuroconv.datainterfaces import ImageInterface
    >>>
    >>> # Every image in the folder that PIL can read becomes one image in the container
    >>> interface = ImageInterface(folder_path=path_to_folder_with_images)
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


To avoid an out-of-memory error when processing a large amount of images the interface uses a
:py:class:`~neuroconv.datainterfaces.image.imageinterface.SingleImageIterator`. This loads one image at a time at
writing time, protecting the system from crashing.

Embedding maps the PIL image mode onto the NWB image type:

- L (grayscale) → GrayscaleImage
- RGB → RGBImage
- RGBA → RGBAImage
- LA (luminance + alpha) → RGBAImage (automatically converted)


Naming and Describing the Images
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Metadata here is naming, and there are two things to name. The first is the ``Images`` container that holds the
collection: its name is what the object is called in the NWB file, so it is what somebody browsing the file sees,
and its description says what the collection is, a set of histology sections, the stimuli that were presented,
photographs of the rig. The second is each image inside it, which takes a name, defaulting to the file stem, and
a description of what that particular picture shows. Everything else, the format, the color mode and the size, is
read from the files, so there is nothing else to state. ``ImageInterface`` additionally accepts a ``resolution``
per image in pixels/cm, which ``ExternalImageInterface`` rejects because NWB declares that field on the embedded
image type alone.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>>
    >>> from neuroconv.datainterfaces import ImageInterface
    >>>
    >>> # `metadata_key` is where this interface's block sits in the metadata, and names the container
    >>> metadata_key = "ExperimentalImages"
    >>> interface = ImageInterface(folder_path=path_to_folder_with_images, metadata_key=metadata_key)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> metadata["Images"][metadata_key]["description"] = "Collection of experimental stimulus and baseline images"
    >>>
    >>> # Each image is keyed by its file path
    >>> images_metadata = metadata["Images"][metadata_key]["images"]
    >>> stimulus_image_path, baseline_image_path = sorted(images_metadata)[:2]
    >>> images_metadata[stimulus_image_path].update(
    ...     name="visual_stimulus", description="Visual stimulus presented to subject", resolution=2.5
    ... )
    >>> images_metadata[baseline_image_path].update(
    ...     name="baseline_recording", description="Baseline image before stimulus", resolution=2.5
    ... )
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

.. note::
    Individual image metadata is keyed by the full file path, and the name defaults to the file stem.
