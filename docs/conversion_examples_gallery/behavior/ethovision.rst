EthoVision data conversion
--------------------------

Install NeuroConv with the dependencies needed for Noldus EthoVision XT exports.

.. code-block:: bash

    pip install "neuroconv[ethovision]"

EthoVision exports raw data as an Excel workbook or as a ``.txt`` text file with a delimiter chosen
at export time, and NeuroConv reads both. The delimiter of a text export is detected automatically
or can be passed as ``delimiter``. As a convenience, text exports renamed to ``.csv`` or ``.tsv``
are read the same way and no delimiter is necessary. The EthoVision data is organized by Track: one subject
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

Tracks written to the same file share one ``Ethogram``, ``EventsTable``, and ``EthogramBouts``; see
:ref:`Combine same-session Tracks <ethovision_combine_tracks>`.

A ``point event`` or ``state start`` without a matching stop remains in the events table only.

The Manual Scoring export holds behavior names and times but not what each behavior means, so the
``Ethogram`` entries are written without definitions or categories. To fully annotate the events see
 :ref:`the events how-to <annotate_events_metadata>`.

.. _ethovision_combine_tracks:

Combine same-session Tracks
~~~~~~~~~~~~~~~~~~~~~~~~~~~

An Excel workbook can contain several arenas and subjects from one recording run. NeuroConv
does not automatically decide which Tracks belong in the same NWB file. Discover the complete
Track identities, select one arena, and compose its Tracks explicitly:

.. code-block:: python

    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv import ConverterPipe
    >>> from neuroconv.datainterfaces import EthoVisionDataInterface

    >>> file_path = BEHAVIOR_DATA_PATH / "ethovision" / "excel" / "single_arena_multiple_subjects" / "hardware_and_trial_control" / "two_subjects_missing_samples.xlsx"
    >>> available_tracks = EthoVisionDataInterface.get_available_tracks(file_path=file_path)
    >>> available_tracks
    [{'arena_name': 'Rat Arena 1a', 'subject_name': 'Subject 1'}, {'arena_name': 'Rat Arena 1a', 'subject_name': 'Subject 2'}]
    >>> arena_name = "Rat Arena 1a"
    >>> subject_1_interface = EthoVisionDataInterface(file_path=file_path, arena_name=arena_name, subject_name="Subject 1")
    >>> subject_2_interface = EthoVisionDataInterface(file_path=file_path, arena_name=arena_name, subject_name="Subject 2")
    >>> converter = ConverterPipe(data_interfaces=[subject_1_interface, subject_2_interface])

    >>> metadata = converter.get_metadata()
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("Asia/Tokyo"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)

    >>> converter.run_conversion(
    ...     nwbfile_path=path_to_save_nwbfile,
    ...     metadata=metadata,
    ...     overwrite=True,
    ... )

Each interface adds only its own subject's Manual Scoring rows, and the ``subject`` and ``arena``
columns identify the Track each row came from.

Subjects recorded together in one arena normally belong in the same NWB file. Separate arenas
should remain separate unless the experiment establishes that they are one session.

CSV and TXT contain one Track per file rather than several worksheets. Construct one interface per
file and pass those interfaces through the same ``ConverterPipe`` pattern. The explicit file list
records that the separate exports belong to the same session.
