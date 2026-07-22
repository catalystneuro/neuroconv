Neurophotometrics (NPM) Events data conversion
----------------------------------------------

:py:class:`~neuroconv.datainterfaces.events.npm_events.npmeventsdatainterface.NPMEventsInterface`
converts discrete events from Neurophotometrics (NPM) recordings. NPM stores its events in a raw,
headerless two-column stimuli CSV: the first column holds the event onset time (in the recording's
raw time base) and the second column holds the event type label (e.g. ``whitenoise``, ``pinknoise``,
a boolean ``True``/``False`` annotation, or a numeric code). Each distinct label is split out and
written as its own ``pynwb.event.EventsTable`` (onset timestamps) into ``nwbfile.events``. The raw
onset times are scaled to seconds by ``time_unit``.

How the event types map onto tables -- one table per type by default, or several types merged into a
single table -- is driven entirely by the editable events metadata. See :ref:`annotate_events_metadata`
for the full metadata format.

NPM events need only NeuroConv's core dependencies, but the ``npm_events`` extra is available for a
consistent install command.

.. code-block:: bash

    pip install "neuroconv[npm_events]"

NPM recordings carry no embedded recording-start timestamp, so ``session_start_time`` must be
supplied explicitly in the metadata.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo

    >>> import pandas as pd

    >>> from neuroconv.datainterfaces import NPMEventsInterface

    >>> # NPM events are a headerless two-column CSV: onset time (seconds) + event-type label. Here we
    >>> # write a small example event file with two event types ("stim" and "noise").
    >>> file_path = output_folder / "npm_events.csv"
    >>> pd.DataFrame([[1.0, "stim"], [2.0, "noise"], [3.0, "stim"]]).to_csv(file_path, index=False, header=False)

    >>> interface = NPMEventsInterface(file_path=file_path, verbose=False)
    >>> metadata = interface.get_metadata()
    >>> # NPM recordings have no embedded start time, so it must be set explicitly.
    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

.. seealso::

    - :doc:`csv_events` for the general-purpose CSV events reader this interface is built on.
