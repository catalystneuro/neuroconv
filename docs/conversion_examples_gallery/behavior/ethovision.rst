EthoVision data conversion
--------------------------

Install NeuroConv with the dependencies needed for Noldus EthoVision XT exports.

.. code-block:: bash

    pip install "neuroconv[ethovision]"

EthoVision exports the same Track model as Excel, CSV, or TXT. One Track is one subject's
sampled data in one arena. :py:class:`~neuroconv.datainterfaces.behavior.ethovision.ethovisiondatainterface.EthoVisionDataInterface`
reads exactly one Track from any of those containers.

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

``arena_name`` and ``subject_name`` identify the Track by its semantic arena-subject pair rather
than by an Excel worksheet name. They are optional when the source contains exactly one Track,
because that identity is unambiguous, but required when an Excel workbook contains several Tracks.
Use :meth:`~neuroconv.datainterfaces.behavior.ethovision.ethovisiondatainterface.EthoVisionDataInterface.get_available_tracks`
to discover the valid pairs.

The selected Track is mapped to NWB as follows:

.. list-table::
    :header-rows: 1
    :widths: 45 55

    * - EthoVision source
      - NWB representation
    * - ``X center`` and ``Y center``
      - One :py:class:`~pynwb.behavior.SpatialSeries`
    * - Every other Track channel
      - One :py:class:`~pynwb.base.TimeSeries` per channel
    * - Manual Scoring behavior labels
      - One `Ethogram <https://github.com/catalystneuro/ndx-ethogram#ethogram>`_
    * - Manual Scoring occurrences
      - One :py:class:`~pynwb.event.EventsTable`
    * - Matching ``state start`` and ``state stop`` rows
      - One row in `EthogramBouts <https://github.com/catalystneuro/ndx-ethogram#ethogrambouts>`_

A ``point event`` or ``state start`` without a matching stop remains in the events table only.

NeuroConv preserves the behavior labels and occurrences present in the Manual Scoring export.
Descriptions, categories, and the experimental meaning of those behaviors may not be present in the
source. Follow :ref:`the events how-to <annotate_events_metadata>` to add that context to the event
and ethogram metadata before conversion.

Combine same-session Tracks
~~~~~~~~~~~~~~~~~~~~~~~~~~~

An Excel workbook can contain several arenas and subjects from one acquisition trial. NeuroConv
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

When same-arena subject interfaces are composed, their subject-filtered Manual Scoring rows
contribute to one arena-level ``Ethogram``, ``EventsTable``, and ``EthogramBouts`` table. The
occurrence tables distinguish subjects with their ``subject`` columns.

Subjects recorded together in one arena normally belong in the same NWB file. Separate arenas
should remain separate unless the experiment establishes that they are one session.

CSV and TXT contain one Track per file rather than several worksheets. Construct one interface per
file and pass those interfaces through the same ``ConverterPipe`` pattern. The explicit file list
records that the separate exports belong to the same session.
