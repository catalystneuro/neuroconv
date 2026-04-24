MountainSort MDA sorting data conversion
----------------------------------------

Install NeuroConv with the additional dependencies necessary for reading MountainSort MDA sorting data.

.. code-block:: bash

    pip install "neuroconv[mda]"

Convert MountainSort ``firings.mda`` sorting output to NWB using
:py:class:`~neuroconv.datainterfaces.ecephys.mda.mdadatainterface.MdaSortingInterface`.

The MDA sorting format (MountainSort v4 and earlier) stores, per spike event,
the primary channel, sample time, and unit label. See the
`MountainSort firings.mda specification
<https://mountainsort.readthedocs.io/en/latest/first_sort.html#format-of-the-firings-mda>`_
for details. This interface reads ``firings.mda`` files produced by
``ml_ms4alg`` (MountainSort v4 standalone) or MountainLab-js pipelines.
SpikeInterface-wrapped MountainSort workflows produce ``firings.npz``
instead and are not served by this interface.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>>
    >>> from neuroconv.datainterfaces import MdaSortingInterface
    >>>
    >>> interface = MdaSortingInterface(file_path=mda_firings_path, sampling_frequency=mda_sampling_frequency, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


Linking units to electrodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``MdaSortingInterface`` surfaces the peak channel from row 0 of
``firings.mda`` as an ``mda_peak_channel`` property on the units table.
The value is a 1-indexed integer position into the sorter's input channel
subset — not a channel ID, and not a row index into the NWB electrodes
table. If MountainSort was run without peak-channel tracking (row 0 all
zeros), the column is not added.

When the original recording that was sorted is available through a
``RecordingInterface``, this column can be lifted into a formal
``DynamicTableRegion`` linkage on ``units.electrodes`` by pairing with
:py:class:`~neuroconv.converters.SortedRecordingConverter` (see the
:ref:`linking_sorted_data` how-to for general electrode linkage
background). Two conditions must be met:

- The original recording that MountainSort was run on is available through
  a ``RecordingInterface``.
- You know the ordered list of channel IDs that was passed to the sorter.
  This is lab knowledge; it is not stored in ``firings.mda``. For
  SpikeGadgets workflows it can be read from the ``.trodesconf`` file's
  ``<SpikeNTrode>`` blocks. For manual extraction pipelines it is wherever
  the channel selection was specified (a Python script, a config file, lab
  notes).

``SortedRecordingConverter`` then maps each channel ID to its
electrodes-table row automatically once the recording interface is given
to it.

.. code-block:: python

    from neuroconv.converters import SortedRecordingConverter
    from neuroconv.datainterfaces import IntanRecordingInterface, MdaSortingInterface

    recording_interface = IntanRecordingInterface(file_path="path/to/intan.rhd")
    sorting_interface = MdaSortingInterface(
        file_path="path/to/firings.mda", sampling_frequency=30_000,
    )

    # The recording channel IDs corresponding to the channel indices that were
    # passed to MountainSort, in the same order. When you ran MountainSort, you
    # selected a subset of the recording's channels (e.g. indices [60, 61, 62, 63])
    # and handed their data to the sorter; the IDs of those channels, in that order,
    # go here. Parse from your pipeline config (e.g. .trodesconf for SpikeGadgets)
    # or from the extraction script that built raw.mda.
    sorter_input_channel_ids = ["A-060", "A-061", "A-062", "A-063"]

    unit_ids = sorting_interface.sorting_extractor.get_unit_ids()
    peak_indices = sorting_interface.sorting_extractor.get_property("mda_peak_channel")

    unit_ids_to_channel_ids = {
        str(unit_id): [sorter_input_channel_ids[int(peak_index) - 1]]
        for unit_id, peak_index in zip(unit_ids, peak_indices)
    }

    converter = SortedRecordingConverter(
        recording_interface=recording_interface,
        sorting_interface=sorting_interface,
        unit_ids_to_channel_ids=unit_ids_to_channel_ids,
    )
    nwbfile = converter.create_nwbfile()

If the original recording or the ordered list of sorted channels is not
available, leave ``mda_peak_channel`` as a raw integer hint and skip
``SortedRecordingConverter``.
