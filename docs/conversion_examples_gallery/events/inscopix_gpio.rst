Inscopix GPIO data conversion
-----------------------------

An Inscopix ``.gpio`` file carries two kinds of auxiliary signal: the analog/monitor channels
(``GPIO-1..4``, the LED monitors, ``e-focus``) and the digital/coded channels (the ``Digital`` lines,
the ``BNC`` sync/trigger, and coded inputs such as an odor-concentration line). NeuroConv exposes these
through two interfaces that read the same file independently, so you can convert either or both.

Install NeuroConv with the additional dependencies necessary for reading Inscopix data.

.. code-block:: bash

    pip install "neuroconv[inscopix]"

Analog and monitor channels
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Store the analog/monitor channels as irregular ``TimeSeries`` (one per channel) using
:py:class:`~neuroconv.datainterfaces.ophys.inscopix.inscopixgpiodatainterface.InscopixGpioInterface`.

.. code-block:: python

    >>> from neuroconv.datainterfaces import InscopixGpioInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "analog_datasets" / "inscopix" / "gpio" / "odor_concentration_stimulus.gpio"
    >>> interface = InscopixGpioInterface(file_path=file_path, verbose=False)
    >>>
    >>> # session_start_time is read from the file; add subject information (required for DANDI upload)
    >>> metadata = interface.get_metadata()
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

Digital and coded channels as events
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Derive discrete events from the digital and coded channels with
:py:class:`~neuroconv.datainterfaces.events.inscopix_gpio_events.inscopixgpioeventsdatainterface.InscopixGpioEventsInterface`,
which writes each channel as a ``pynwb.event.EventsTable`` into ``nwbfile.events``. Selection is
explicit: name each channel in ``events_config`` and say how to read it. A digital line is edge-detected
(``reading`` is ``"rising"``, ``"falling"``, or ``"interval"``); a coded analog line is cut into bands
at ``levels`` and carries the band index as a categorical column.

.. code-block:: python

    >>> from neuroconv.datainterfaces import InscopixGpioEventsInterface
    >>>
    >>> events_config = {
    ...     "BNC Sync Output": {"reading": "rising"},                       # frame-clock pulses
    ...     "GPIO-2": {"levels": [136, 152, 192], "field": "concentration"},  # odor concentration code
    ... }
    >>> interface = InscopixGpioEventsInterface(file_path=file_path, events_config=events_config, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = output_folder / "inscopix_gpio_events.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

.. seealso::

    Other Inscopix data interfaces:

    - :doc:`../imaging/inscopix` to convert Inscopix imaging movies.
    - :doc:`../segmentation/inscopix` to convert Inscopix segmentation output.
