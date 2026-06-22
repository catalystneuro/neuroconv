Neurophotometrics (NPM) Events data conversion
----------------------------------------------

NPM stores discrete events in a raw, two-column stimuli CSV: the first column holds the event onset
time (in the recording's raw time base) and the second column holds the event type label (e.g.
``whitenoise``, ``pinknoise``). This interface reads that file, splits the rows by unique type
label, and writes each label as its own ``ndx_events.Events`` object.

Install NeuroConv with the additional dependencies necessary for reading NPM event data.

.. code-block:: bash

    pip install "neuroconv[npm_events]"

Convert NPM event data to NWB using
:py:class:`~neuroconv.datainterfaces.behavior.npm_events.npmeventsdatainterface.NPMEventsInterface`.

The raw onset times are scaled to seconds by ``time_unit`` but otherwise remain in the recording's
raw time base; use ``interface.set_aligned_starting_time(...)`` to express them relative to the
recording start. NPM recordings carry no embedded recording-start timestamp, so
``session_start_time`` must be supplied explicitly in the metadata.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import NPMEventsInterface

    >>> folder_path = f"{OPHYS_DATA_PATH}/fiber_photometry_datasets/NPM/sampleData_NPM_4"

    >>> interface = NPMEventsInterface(folder_path=folder_path, verbose=False)
    >>> metadata = interface.get_metadata()
    >>> # NPM recordings have no embedded start time, so it must be set explicitly.
    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)
