DataInterfaces
==============

The :py:class:`.BaseDataInterface` class provides a unified API for converting
data from any single input stream. See the
:ref:`Conversion Gallery <conversion_gallery>` for existing ``DataInterface``
classes and example usage. The standard workflow for using a ``DataInterface``
is as follows:

1. Installation
~~~~~~~~~~~~~~~
Each ``DataInterface`` may have custom dependencies for reading that specific
file format. To ensure that you have all the appropriate dependencies, you can
install NeuroConv in this specific configuration using pip extra requirements.
For instance, to install the dependencies for SpikeGLX, run:

.. code-block::

    pip install "neuroconv[spikeglx]"

.. note::

     If you are using a Z-shell (`zsh`) terminal (the default for MacOS), then you will have to use quotes to specify the custom dependency.

     .. code-block::

         pip install 'neuroconv[spikeglx]'

2. Construction
~~~~~~~~~~~~~~~
Initialize a class and direct it to the appropriate source data:

.. code-block:: python

    from neuroconv.datainterfaces import SpikeGLXRecordingInterface

    interface = SpikeGLXRecordingInterface(file_path="path/to/towersTask_g0_t0.imec0.ap.bin")

This will open the files and read header information, setting up the system for conversion,
but generally will not read the underlying data.

.. note::

     To get the form of source_data, run :meth:`.BaseDataInterface.get_source_schema`,
     which returns the :ref:`source schema <source_schema>` as a JSON-schema-like dictionary informing
     the user of the required and optional input arguments to the downstream readers.

3. Get and adjust metadata
~~~~~~~~~~~~~~~~~~~~~~~~~~
Each ``DataInterface`` can extract relevant metadata from the source files and
organize it in a ``metadata`` hierarchical dictionary:

.. code-block:: python

    metadata = interface.get_metadata()

This dictionary can be edited to include data not available in the source files.
The DANDI Archive requires subject ID, sex, age, and species, which are rarely present in the source data. Here is how you would add them.

.. code-block:: python

    metadata["Subject"] = dict(
        subject_id="M001",
        sex="M",
        age="P30D",
        species="Mus musculus",
    )

``subject_id`` is a unique identifier for the subject.

``sex`` is the biological sex of the subject and can take the values:

- ``M`` for Male
- ``F`` for Female
- ``U`` for Unknown
- ``O`` for Other

``age`` follows the `ISO 8601 duration format <https://en.wikipedia.org/wiki/ISO_8601#Durations>`_.
For example, ``P30D`` is 30 days old, and ``P1Y`` would be 1 year old.
To express a range of ages, you can use a slash, for example ``P30D/P35D`` for 30 to 35 days old.

``species`` is the scientific Latin binomial name of the species. For example, ``Mus musculus``
for a mouse.

See :ref:`Subject Best Practices <best_practice_subject_exists>` for details.

The ``session_start_time`` is also required. This is sometimes found in the source data.
If it is not found, you must add it:

.. code-block:: python

    from datetime import datetime
    from zoneinfo import ZoneInfo

    metadata["NWBFile"]["session_start_time"] = datetime(2021, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("US/Pacific"))

You can use ``tz.tzlocal()`` to get the local timezone.

If the ``session_start_time`` is extracted from the source data, it is often missing a timezone.
This is not required but is a recommended best practice. Here is how you would add it:

.. code-block:: python

    metadata["NWBFile"]["session_start_time"] = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))

NWB Best Practices also recommends several other fields that are rarely present in the extracted metadata.
The metadata dictionary is the place to add this information:

.. code-block:: python

    metadata["NWBFile"].update(
        session_id="session_1",
        session_description="Observations of desert plants and reptiles on the island of San Cristobal.",
        experiment_description="Observations of wildlife across the Galapagos Islands.",
        experimenter="Darwin, Charles",
        lab="Evolutionary Biology",
        institution="University of Cambridge",
        keywords=["finches", "evolution", "Galapagos"],
    )

The ``metadata`` dictionary also contains metadata that pertain to the specific data being converted.
In this example, the ``Ecephys`` key contains metadata that pertains to the electrophysiology data being converted.
This metadata can be edited in the same way:

.. code-block:: python

    metadata["Ecephys"]

    {'Device': [{'name': 'Neuropixel-Imec',
       'description': '{"probe_type": "0", "probe_type_description": "NP1.0", "flex_part_number": "NP2_FLEX_0", "connected_base_station_part_number": "NP2_QBSC_00"}',
       'manufacturer': 'Imec'}],
     'ElectrodeGroup': [{'name': 's0',
       'description': 'a group representing shank s0',
       'location': 'unknown',
       'device': 'Neuropixel-Imec'}],
     'ElectricalSeriesAP': {'name': 'ElectricalSeriesAP',
      'description': 'Acquisition traces for the ElectricalSeriesAP.'},
     'Electrodes': [{'name': 'shank_electrode_number',
       'description': '0-indexed channel within a shank.'},
      {'name': 'group_name',
       'description': 'Name of the ElectrodeGroup this electrode is a part of.'},
      {'name': 'contact_shapes', 'description': 'The shape of the electrode'}]}

Here we can see that ``metadata["Ecephys"]["ElectrodeGroup"][0]["location"]`` is ``unknown``.
We can add this information as follows:

.. code-block:: python

    metadata["Ecephys"]["ElectrodeGroup"]["location"] = "V1"


Use ``.get_metadata_schema()`` to get the schema of the metadata dictionary.
This schema is a JSON-schema-like dictionary that specifies required and optional fields in the metadata dictionary.
See :ref:`metadata schema <metadata_schema>` for more information.

4a. Run conversion
~~~~~~~~~~~~~~~~~~
The ``.run_conversion`` method takes the (edited) metadata dictionary and
the path of an NWB file, and launches the actual data conversion into NWB:

.. code-block:: python

    spikeglx_interface.run_conversion(
        save_path="path/to/destination.nwb",
        metadata=metadata
    )

This method reads and writes large datasets piece-by-piece, so you
can convert large datasets without overloading the computer's available RAM.
It also uses good defaults for data chunking and lossless compression, reducing
the file size of the output NWB file and optimizing the file for cloud compute.

4b. Create an in-memory NWB file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You can also create an in-memory NWB file:

.. code-block:: python

    nwbfile = spikeglx_interface.create_nwbfile(metadata=metadata)

This is useful for adding extra data such as trials, epochs, or other time intervals to the NWB file.
See :ref:`Adding Time Intervals to NWB Files <adding_trials>` for more information.

This does not load large datasets into memory.
Those remain in the source files and are read piece-by-piece during the write process.
Once you make all the modifications you want to the NWBfile, you can save it to disk.
The following code automatically optimizes datasets for cloud compute and writes the file to disk:

.. code-block:: python

    from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile

    configure_and_write_nwbfile(
        nwbfile, save_path="path/to/destination.nwb", backend="hdf5"
    )
