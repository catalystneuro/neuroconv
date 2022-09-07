NWBConverter
============

In neurophysiology, it is common to use multiple different acquisition or
preprocessing systems with different proprietary formats in the same session.
For instance, in a given extracellular electrophysiology experiment, you might
have raw and processed data. The NWBConverter class streamlines this
conversion process. This single NWBConversion object is responsible for
combining those multiple read/write operations. An example of how to define
a ``NWBConverter`` would be::

    from neuroconv import NWBConverter,
    from neuroconv.datainterfaces import (
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

    metadata["NWBFile"]["session_description"] = "NeuroConv tutorial."
    metadata["NWBFile"]["experimenter"] = "My name"
    metadata["Subject"]["subject_id"] = "ID of experimental subject"

The final metadata dictionary should follow the form defined by
``converter.get_metadata_schema()``. Now run the entire conversion with::

    converter.run_conversion(metadata=metadata, nwbfile_path="my_nwbfile.nwb")

Though this example was only for two data streams (recording and spike-sorted
data), it can easily extend to any number of sources, including video of a
subject, extracted position estimates, stimuli, or any other data source.

The sections below describe source schema and metadata schema in more detail through
another example for two data streams (ophys and ecephys data).
