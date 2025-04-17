NWBConverter
============

In neurophysiology, it is common to use multiple different acquisition or
preprocessing systems with different proprietary formats in the same session.
For instance, in a given extracellular electrophysiology experiment, you might
have raw and processed data. The :py:class:`.NWBConverter` class streamlines this
conversion process. This single :py:class:`.NWBConverter` object is responsible for
combining those multiple read/write operations. Here is an example definition of a
:py:class:`.NWBConverter`:

.. code-block:: python

    from neuroconv import NWBConverter,
    from neuroconv.datainterfaces import (
        SpikeGLXRecordingInterface,
        PhySortingInterface
    )

    class ExampleNWBConverter(NWBConverter):
        data_interface_classes = dict(
            SpikeGLXRecording=SpikeGLXRecordingInterface,
            PhySorting=PhySortingInterface
        )

:py:class:`.NWBConverter` classes define a :py:attr:`.data_interface_classes` dictionary, a class
attribute that specifies all of the ``DataInterface`` classes used by this
converter. Then you just need to input ``source_data``, which specifies the
input data to each ``DataInterface``. The keys to this dictionary must match the
keys of``data_interface_classes``.

.. code-block:: python

    source_data = dict(
        SpikeGLXRecording=dict(
            file_path="raw_dataset_path"
        ),
        PhySorting=dict(
            folder_path="sorted_dataset_path"
        )
    )

    example_nwb_converter = ExampleNWBConverter(source_data)

This creates an :py:class:`.NWBConverter`. To fetch metadata across all of the interfaces and merge
them together, call:

.. code-block:: python

    metadata = converter.get_metadata()

The metadata can then be manually modified with any additional user-input, just like ``DataInterface`` objects:

.. code-block:: python

    metadata["NWBFile"]["session_description"] = "NeuroConv tutorial."
    metadata["NWBFile"]["experimenter"] = "My name"
    metadata["Subject"]["subject_id"] = "ID of experimental subject"

The final metadata dictionary should follow the form defined by :meth:`.NWBConverter.get_metadata_schema`.

You can also specify conversion options for each data interface to control how the data is written to the NWB file:

.. code-block:: python

    conversion_options = dict(
        SpikeGLXRecording=dict(
            # Control memory usage with iterator options
            iterator_opts=dict(
                buffer_gb=1.0,  # Amount of memory to use
                chunk_mb=10.0,  # Size of chunks for writing
                display_progress=True  # Show progress bar
            ),
            # Write as raw, processed, or LFP data
            write_as="raw",
            # For testing with a small subset of data
            stub_test=False,
            # For manual control of timestamps
            always_write_timestamps=False
        ),
        PhySorting=dict(
            # For testing with a small subset of data
            stub_test=False,
            # Exclude particular units
            exclude_unit_ids=[],
            # Write all available unit properties
            write_unit_properties=True,
            # Write unit spike waveforms
            write_waveforms=False
        )
    )

Note that they keys of the dictionary must match the keys of
``data_interface_classes``. The values are dictionaries that specify the
conversion options for each data interface. The available options depend on the specific data interface being used.
You can find them by looking at the interface `add_to_nwbfile` method.

Now run the entire conversion with:

.. code-block:: python

    converter.run_conversion(
        metadata=metadata,
        nwbfile_path="my_nwbfile.nwb",
        conversion_options=conversion_options
    )

Like ``DataInterface`` objects, :py:class:`.NWBConverter` objects can output an in-memory :py:class:`.NWBFile` object by
calling :meth:`.NWBConverter.create_nwbfile`. This can be useful for debugging, for adding metadata to the file, or for
further processing.

Though this example was only for two data streams (recording and spike-sorted
data), it can easily extend to any number of sources, including video of a
subject, extracted position estimates, stimuli, or any other data source.
