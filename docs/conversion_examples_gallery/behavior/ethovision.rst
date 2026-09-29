EthoVision data conversion
--------------------------

Install NeuroConv with the dependencies needed for Noldus EthoVision XT exports.

.. code-block:: bash

    pip install "neuroconv[ethovision]"

EthoVision exports raw data as an Excel workbook or as a ``.txt`` text file with a delimiter chosen
at export time, and NeuroConv reads both. The delimiter of a text export is detected automatically
or can be passed as ``delimiter``. The EthoVision data is organized by Track: one subject
in one arena during one recording run (what EthoVision calls a trial).
:py:class:`~neuroconv.datainterfaces.behavior.ethovision.ethovisiondatainterface.EthoVisionDataInterface`
converts one Track at a time, selected with ``arena_name`` and ``subject_name``. Use
:meth:`~neuroconv.datainterfaces.behavior.ethovision.ethovisiondatainterface.EthoVisionDataInterface.get_available_tracks`
to list the valid pairs in a file.

Convert one Track
~~~~~~~~~~~~~~~~~

.. code-block:: python

    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import EthoVisionDataInterface

    >>> file_path = BEHAVIOR_DATA_PATH / "ethovision" / "excel" / "single_arena_single_subject" / "track_and_manual_scoring" / "two_c57.xlsx"

    >>> # A workbook can hold many Tracks, so pick one by its arena and subject.
    >>> interface = EthoVisionDataInterface(file_path=file_path, arena_name="Arena 1", subject_name="Subject 1")

    >>> metadata = interface.get_metadata()

    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("Asia/Tokyo"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)

    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="U")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata, overwrite=True)

The selected Track, and the selected subject's rows of the arena's Manual Scoring sheet (Excel
only), are written to the ``behavior`` processing module as follows:

.. list-table::
    :header-rows: 1
    :widths: 45 55

    * - EthoVision source
      - NWB representation
    * - ``X center`` and ``Y center``
      - One :py:class:`~pynwb.behavior.SpatialSeries`
    * - Every other Track column except ``Trial time`` and ``Recording time``
      - One :py:class:`~pynwb.base.TimeSeries` per column
    * - Manual Scoring ``Behavior`` labels
      - One `Ethogram <https://github.com/catalystneuro/ndx-ethogram#ethogram>`_
    * - Manual Scoring rows
      - One :py:class:`~pynwb.event.EventsTable`
    * - A Manual Scoring ``state start`` and the next ``state stop`` for the same subject and behavior
      - One row in `EthogramBouts <https://github.com/catalystneuro/ndx-ethogram#ethogrambouts>`_

A ``point event`` or ``state start`` without a matching stop remains in the events table only.

The Manual Scoring export holds behavior names and times but not what each behavior means, so the
``Ethogram`` entries are written without definitions or categories. To fully annotate the events see
 :ref:`the events how-to <annotate_events_metadata>`.

Not supported yet
~~~~~~~~~~~~~~~~~
The following workflows are not supported yet:

- Exports from EthoVision releases before XT (EthoVision 3.1 and earlier), which use a different text format.
- EthoVision's native files, such as ``.trk`` track files and the ``.evxt`` experiment; export the raw data first.
- Statistics and other analysis-output exports; only raw data exports are read.
- Exports that were opened and re-saved in a spreadsheet program; convert the file EthoVision wrote.
- The ``Hardware`` and ``Trial Control`` sheets.
- Manual Scoring logs exported as text; only the Manual Scoring sheet of an Excel workbook is read.
- Several recording runs of one subject combined into one NWB file.

Please reach out if you have any of those or any other workflow that we are not covering yet. You can
`open an issue <https://github.com/catalystneuro/neuroconv/issues>`_ with a sample file and a description
of your use case and we will be happy to help you convert your data and/or add support for your workflow.
