Part 4, NWB Conversion Tools
============================

NWB files often combine data from multiple sources- neurophysiology raw and processed data,
behavior video and extracted position, stimuli, etc.
A full conversion means handling all of these different data types at the same time,
and it can get tricky to ensure that timing is synchronized across different
acquisition systems. While the automated proprietary format conversions build upon
PyNWB to solve the challenges of variety of data formats and size of data,
NWB Conversion Tools build upon these automated conversion tools to provide a
system for combining data across multiple streams.

This workflow is as follows:

#. Extract metadata from existing proprietary files
#. Adjust or add any missing metadata
#. Run the conversion, inserting this metadata in the appropriate place.

In order to accomplish these three tasks, the NWB Conversion Tools relies on two tiers
of structure, represented by the two main classes in the package: :class:`.BaseDataInterface`
(and its subclasses) and :class:`~.nwbconverter.NWBConverter`.

DataInterface
--------------

:class:`.BaseDataInterface` is a unified API for converting data from
any single input stream. There are corresponding DataInterface objects for
each ``SpikeExtractor`` and ``RoiExtractor``, and additional DataInterface objects
for other types of data not supported by these packages, like videos for behavior monitoring.

SpikeExtractor and RoiExtractor data readers can miss key metadata that should
go into the NWB file. DataInterface objects solve this by each providing a
:meth:`~.BaseDataInterface.get_metadata` method that inspect the source files
and pulling out any additional metadata into a JSON-like dictionary-of-dictionaries.
This metadata object can then be passed into :meth:`~.BaseDataInterface.run_conversion`,
which will write the metadata in the appropriate places in the NWB file along with
the data from the interfaces.

Here is an example of how to use a DataInterface::

    from nwb_conversion_tools import SpikeGLXRecordingInterface

    source_data = dict(file_path="path/to/towersTask_g0_t0.imec0.ap.bin")

    spike_glx_recording_interface = SpikeGLXRecordingInterface(source_data)

    metadata = spike_glx_recording_interface.get_metadata()

    spike_glx_recording_interface.run_conversion(
        save_path="path/to/destination.nwb",
        metadata=metadata
    )

.. note::

    To get the form of source_data, run :meth:`.SpikeGLXRecordingInterface.get_source_schema`,
    which returns a JSON-schema-like dictionary informing the user of the required and
    optional input arguments to the downstream readers.

The metadata dictionary follows a specific form, which maps certain pieces of
metadata to specific places in the NWB file.

DataInterface objects serve as building blocks for the NWBConverter,
which orchestrates a conversion that integrates data across multiple interfaces.

NWBConverter
-------------

In the cases where there are multiple data sources each deserving of a place in
the final NWB file, the :class:`.NWBConverter` class can be used to streamline the process
that would otherwise require multiple repetitions of operations from Part 3.
The most important aspect of the NWBConverter is the internal container of
DataInterface classes, which are later instantiated in a container of DataInterface objects.

An example of how to define a NWBConverter that combines the modalities
of the examples from Part 3 would be::

    from nwb_conversion_tools import (
        BlackrockRecordingExtractorInterface,
        KlustaSortingExtractorInterface
    )

    class ExampleNWBConverter(NWBConverter):
        data_interface_classes = dict(
            BlackrockRecording=BlackrockRecordingExtractorInterface,
            KlustaSorting=KlustaSortingExtractorInterface
        )

We now have a single conversion class that is capable of combining those
multiple read/write operations! Utilizing that classes functionality
for the full conversion is as simple as creating another JSON-like
``source_data`` dictionary-of-dictionaries to specify the input arguments
for each interface, which will allow us to instantiate the NWBConverter object::

    source_data = dict(
        BlackrockRecordingExtractorInterface=dict(
            filename="raw_dataset_path"
        ),
        KlustaSortingExtractoreInterface=dict(
            file_or_folder_path="sorted_dataset_path"
        )
    )

    example_nwb_converter = ExampleNWBConverter(source_data)

The NWBConverter object has now automatically performed all of the previous
read operations for all of its interfaces. To fetch all of the metadata across
interfaces we simply call::

    metadata = converter.get_metadata()

which queries each :meth:`~.BaseDataInterface.get_metadata` function,
returning a single dictionary that is the total intersection of all
the usable metadata. This can be useful when there is heavy overlap across modalities,
such as between high-pass and low-pass extracellular data.
The metadata can, at this stage, be manually modified with any additional user-input
such as::

    metadata["NWBFile"]["session_description"] = "NWB Conversion Tools tutorial."
    metadata["NWBFile"]["experimenter"] = "My name"
    metadata["Subject"]["subject_id"] ="ID of experimental subject"

and running the entire conversion becomes as easy as calling::

    converter.run_conversion(metadata=metadata, nwbfile_path="my_nwbfile.nwb")

Though this example was only for two data streams (recording and spike-sorted data), it can very easily extend to any number of sources, which vastly reduces the complexity of such a conversion to NWB.




