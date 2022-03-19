User Guide
==========================

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
and :class:`~.nwbconverter.NWBConverter`.

DataInterface
--------------

:class:`.BaseDataInterface` is a unified API for converting data from
any single input stream. There are corresponding DataInterface objects for
each ``SpikeExtractor`` and ``RoiExtractor``, and additional ``DataInterface`` objects
for other types of data not supported by these packages, like videos for behavior monitoring.

``SpikeExtractor`` and ``RoiExtractor`` data readers can miss key metadata that should
go into the NWB file. DataInterface objects solve this by each providing a
:meth:`~.BaseDataInterface.get_metadata` method that inspect the source files
and pulls out any additional metadata into a JSON-like dictionary-of-dictionaries.
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

    To get the form of source_data, run :meth:`.BaseDataInterface.get_source_schema`,
    which returns a JSON-schema-like dictionary informing the user of the required and
    optional input arguments to the downstream readers.

The metadata dictionary follows a specific form, which maps certain pieces of
metadata to specific places in the NWB file. The form of this dictionary is defined
by a json-schema that you can get with :meth:`.BaseDataInterface.get_metadata_schema()`.

``DataInterface`` objects serve as building blocks for the :class:`.NWBConverter`,
which orchestrates a conversion that integrates data across multiple interfaces.

NWBConverter
-------------

In neurophysiology, it is common to use multiple different acquisition or
preprocessing systems with different proprietary formats in the same session.
For instance, in a given extracellular electrophysiology experiment, you might
have raw and processed data. The NWBConverter class streamlines this
conversion process. This single NWBConversion object is responsible for
combining those multiple read/write operations. An example of how to define
a ``NWBConverter`` would be::

    from nwb_conversion_tools import (
        NWBConverter,
        BlackrockRecordingExtractorInterface,
        PhySortingInterface
    )

    class ExampleNWBConverter(NWBConverter):
        data_interface_classes = dict(
            BlackrockRecording=BlackrockRecordingExtractorInterface,
            PhySorting=PhySortingInterface
        )

:py:class:`.NWBConverter` classes define a :py:attr:`.data_interface_classes` dictionary, a class
attribute that specifies all of the ``DataInterface`` classes used by this
converter. Then you just need to input ``source_data``, which specifies the
input data to each ``DataInterface``. The keys to this dictionary are arbitrary,
but must match between ``data_interface_classes`` and the ``source_data``::

    source_data = dict(
        BlackrockRecording=dict(
            file_path="raw_dataset_path"
        ),
        PhySorting=dict(
            folder_path="sorted_dataset_path"
        )
    )

    example_nwb_converter = ExampleNWBConverter(source_data)

This creates an ``NWBConverter`` object that can aggregate and distribute across
the data interfaces. To fetch metadata across all of the interfaces and merge
them together, call::

    metadata = converter.get_metadata()

The metadata can then be manually modified with any additional user-input::

    metadata["NWBFile"]["session_description"] = "NWB Conversion Tools tutorial."
    metadata["NWBFile"]["experimenter"] = "My name"
    metadata["Subject"]["subject_id"] ="ID of experimental subject"

The final metadata dictionary should follow the form defined by
``converter.get_metadata_schema()``. Now run the entire conversion with::

    converter.run_conversion(metadata=metadata, nwbfile_path="my_nwbfile.nwb")

Though this example was only for two data streams (recording and spike-sorted
data), it can easily extend to any number of sources, including video of a
subject, extracted position estimates, stimuli, or any other data source.




