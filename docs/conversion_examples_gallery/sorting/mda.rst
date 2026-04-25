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


Linking units to their contact through peak channel
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When the original recording is available, NWB allows each unit in the
units table to be linked to the electrode it fires on through a
``DynamicTableRegion`` on ``units.electrodes`` (see
:ref:`linking_sorted_data`). A common way to build this linkage is to assign each unit to
the single electrode where its spikes are largest, that unit's "peak channel."

When MountainSort is run with peak-channel tracking enabled,
``firings.mda`` records this peak channel for each unit. However, the
value is stored as a 1-indexed position into the subset of
acquisition-system channels that were passed to the sorter, so it
cannot be used directly to identify an electrode.

Neuroconv builds the linkage in terms of stable identifiers instead:
the channel IDs of the recording and the unit IDs of the sorting, both
provided through SpikeInterface. The missing piece is the bridge
between the positional index in ``firings.mda`` and the recording's
channel IDs, namely the ordered list of channel IDs that was passed to
the sorter when the algorithm was run.

When this information is available, ``SortedRecordingConverter`` can be
used as follows:

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
    peak_channel_indices = sorting_interface.sorting_extractor.get_property("mda_peak_channel")

    unit_ids_to_channel_ids = {}
    for unit_id, peak_channel_index in zip(unit_ids, peak_channel_indices):
        # MountainSort stores peak channels as 1-indexed positions; subtract 1 for 0-indexed list access
        position_in_sorter_input = int(peak_channel_index) - 1
        peak_channel_id = sorter_input_channel_ids[position_in_sorter_input]
        unit_ids_to_channel_ids[unit_id] = [peak_channel_id]

    converter = SortedRecordingConverter(
        recording_interface=recording_interface,
        sorting_interface=sorting_interface,
        unit_ids_to_channel_ids=unit_ids_to_channel_ids,
    )
    nwbfile = converter.create_nwbfile()

If either piece is missing, the peak-channel value remains on the units
table as a plain integer column named ``mda_peak_channel`` and the
formal electrode linkage is simply skipped.
