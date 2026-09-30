EthoVision data conversion
--------------------------

Install NeuroConv with the dependencies needed for Noldus EthoVision XT exports.

.. code-block:: bash

    pip install "neuroconv[ethovision]"

EthoVision exports raw data as an Excel workbook or as a ``.txt`` text file with a delimiter chosen
at export time, and NeuroConv reads both. The delimiter of a text export is detected automatically
or can be passed as ``delimiter``. The EthoVision data is organized by Track: one subject
in one arena during one recording run (what EthoVision calls a trial).
:py:class:`~neuroconv.datainterfaces.behavior.ethovision.ethovisiontrackinterface.EthoVisionTrackInterface`
converts one Track at a time, selected with ``arena_name`` and ``subject_name``. Use
:meth:`~neuroconv.datainterfaces.behavior.ethovision.ethovisiontrackinterface.EthoVisionTrackInterface.get_available_tracks`
to list the valid pairs in a file.

Convert one Track
~~~~~~~~~~~~~~~~~

.. code-block:: python

    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import EthoVisionTrackInterface

    >>> file_path = BEHAVIOR_DATA_PATH / "ethovision" / "excel" / "single_arena_single_subject" / "track_and_manual_scoring" / "two_c57.xlsx"

    >>> # A workbook can hold many Tracks, so pick one by its arena and subject.
    >>> interface = EthoVisionTrackInterface(file_path=file_path, arena_name="Arena 1", subject_name="Subject 1")

    >>> metadata = interface.get_metadata()

    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("Asia/Tokyo"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)

    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="U")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata, overwrite=True)

The selected Track is written to the ``behavior`` processing module: ``X center`` and ``Y center`` as one
:py:class:`~pynwb.behavior.SpatialSeries`, and every other column except ``Trial time`` and ``Recording time``
as one :py:class:`~pynwb.base.TimeSeries` each.

Convert Manual Scoring
~~~~~~~~~~~~~~~~~~~~~~

An Excel workbook can also hold a ``Manual Scoring-<arena>`` sheet with the behaviors scored by hand in that
arena, with or without the Track sheets beside it.
:py:class:`~neuroconv.datainterfaces.behavior.ethovision.ethovisionmanualscoringinterface.EthoVisionManualScoringInterface`
converts one subject's rows of that sheet, selected with ``arena_name`` and ``subject_name`` like a Track. Use
:meth:`~neuroconv.datainterfaces.behavior.ethovision.ethovisionmanualscoringinterface.EthoVisionManualScoringInterface.get_available_scorings`
to list the valid pairs in a file.

.. code-block:: python

    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import EthoVisionManualScoringInterface

    >>> file_path = BEHAVIOR_DATA_PATH / "ethovision" / "excel" / "single_arena_single_subject" / "track_and_manual_scoring" / "two_c57.xlsx"

    >>> # A Manual Scoring sheet can hold several subjects, so pick one by its arena and subject.
    >>> interface = EthoVisionManualScoringInterface(file_path=file_path, arena_name="Arena 1", subject_name="Subject 1")

    >>> metadata = interface.get_metadata()

    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("Asia/Tokyo"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)

    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="U")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata, overwrite=True)

The selected subject's rows are written as one :py:class:`~pynwb.event.EventsTable`, with each ``state start``
and ``state stop`` pair as one row with a duration. The scored behaviors are catalogued in an ``ndx-ethogram``
``Ethogram``, and the closed state bouts are written to an ``EthogramBouts`` table, both in the ``behavior``
processing module.

NeuroConv aims to automatically add all the metadata annotations that are present in the source format.
It is often the case that crucial information is not available there, such as what a scored behavior means,
since a Manual Scoring sheet carries only each behavior's label.
Follow :ref:`the events how-to <annotate_events_metadata>` for a modality-relevant guide to adding this
extra metadata, which makes the data more useful for future users and for the community as a whole.

Not supported yet
~~~~~~~~~~~~~~~~~
The following workflows are not supported yet:

- Exports from EthoVision releases before XT (EthoVision 3.1 and earlier), which use a different text format.
- EthoVision's native files, such as ``.trk`` track files and the ``.evxt`` experiment; export the raw data first.
- Statistics and other analysis-output exports; only raw data exports are read.
- Exports that were opened and re-saved in a spreadsheet program; convert the file EthoVision wrote.
- The ``Hardware`` and ``Trial Control`` sheets.
- Manual Scoring from a text log; only the Manual Scoring sheet of an Excel workbook is read.
- Several recording runs of one subject combined into one NWB file.

Please reach out if you have any of those or any other workflow that we are not covering yet. You can
`open an issue <https://github.com/catalystneuro/neuroconv/issues>`_ with a sample file and a description
of your use case and we will be happy to help you convert your data and/or add support for your workflow.
