pyPhotometry Fiber Photometry data conversion
---------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading pyPhotometry data.

.. code-block:: bash

    pip install "neuroconv[pyphotometry_fp]"

pyPhotometry is an open acquisition system, also sold as hardware by Open Ephys, which writes a binary
``.ppd`` file holding every signal the board recorded. How many signals that is depends on the
acquisition mode the recording was made in, and ``get_available_streams`` reports them before
construction, each named for the photodetector that was read and the excitation source that was lit.
Streams sharing a ``detector`` prefix came off one fiber.

``PyPhotometryFiberPhotometryInterface`` reads one signal into a single
``FiberPhotometryResponseSeries``.

The board reads its analog inputs one after the other rather than at the same instant, so each signal is
written with the start time its own slot in the sampling cycle implies. In the continuous modes that gap
is not recorded anywhere in the file, and the pyPhotometry developers measured it at about 393
microseconds on `their issue tracker <https://github.com/pyPhotometry/code/issues/39>`_. It is not
included in the timestamps, and each series states it in its ``comments``.

Convert pyPhotometry Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert pyPhotometry Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.fiber_photometry.pyphotometry.pyphotometrydatainterface.PyPhotometryFiberPhotometryInterface`.

.. code-block:: python

    >>> from neuroconv.datainterfaces import PyPhotometryFiberPhotometryInterface

    >>> file_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "pyphotometry" / "mode_named_in_prose" / "one_colour_time_division.ppd"

    >>> # Which signals a file holds depends on the acquisition mode it was recorded in.
    >>> PyPhotometryFiberPhotometryInterface.get_available_streams(file_path=file_path)
    ['detector_1_excitation_1', 'detector_1_excitation_2']

    >>> # One interface reads one signal.
    >>> interface = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="detector_1_excitation_1", metadata_key="signal")
    >>> metadata = interface.get_metadata()
    >>> # The recording start time is in the file's header, so it does not have to be supplied.
    >>> metadata["NWBFile"]["session_start_time"]
    datetime.datetime(2021, 6, 8, 16, 52, 48)

    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

One interface reads one signal. To write several into one file, sharing a single
``FiberPhotometryTable``, pass one interface per signal to a
:py:class:`~neuroconv.nwbconverter.ConverterPipe`:

.. code-block:: python

    >>> from neuroconv import ConverterPipe
    >>> signal_metadata_key = "signal"
    >>> isosbestic_metadata_key = "isosbestic"
    >>> signal = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="detector_1_excitation_1", metadata_key=signal_metadata_key)
    >>> isosbestic = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="detector_1_excitation_2", metadata_key=isosbestic_metadata_key)

    >>> converter = ConverterPipe(data_interfaces=dict(signal=signal, isosbestic=isosbestic))
    >>> metadata = converter.get_metadata()

    >>> # Every interface names its series ``FiberPhotometryResponseSeries`` by default, so give each
    >>> # one a name of its own before writing them into the same file.
    >>> metadata["FiberPhotometry"][signal_metadata_key]["name"] = "FiberPhotometryResponseSeriesSignal"
    >>> metadata["FiberPhotometry"][isosbestic_metadata_key]["name"] = "FiberPhotometryResponseSeriesIsosbestic"

    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> converter.run_conversion(nwbfile_path=f"{path_to_save_nwbfile}", metadata=metadata, overwrite=True)

NeuroConv aims to automatically add all the metadata annotations that are present in the source format.
It is often the case that crucial information is not available there, such as the anatomical location,
the meaning of the values, or a semantically meaningful description of the data. Follow
:ref:`the fiber photometry how-to <annotate_fiber_photometry_metadata>` for a modality-relevant guide to adding
this extra metadata, which makes the data more useful for future users and for the community as a whole.
Its :ref:`section on templates <how_to_annotate_from_a_template>` starts from scratch, and the
:ref:`reference template <fiber_photometry_metadata_template>` lists every element the metadata accepts.

.. seealso::

    - :doc:`../events/pyphotometry_events` to convert the digital lines carried in the same words.
