Inscopix GPIO data conversion
-----------------------------

An Inscopix ``.gpio`` file carries a mix of channels: LED-power and focus monitors, general-purpose
inputs, digital lines, and BNC sync/trigger, plus coded inputs such as an odor-concentration line. The
file records no way to tell which channels are continuous signals versus discrete events, so NeuroConv
exposes two interfaces that read the same file independently: one stores channels as ``TimeSeries``, the
other derives discrete events. You can run either or both.

Install NeuroConv with the additional dependencies necessary for reading Inscopix data.

.. code-block:: bash

    pip install "neuroconv[inscopix]"

Channels as TimeSeries
^^^^^^^^^^^^^^^^^^^^^^^

Store the channels as irregular ``TimeSeries`` (one per channel) using
:py:class:`~neuroconv.datainterfaces.ophys.inscopix.inscopixgpiodatainterface.InscopixGpioInterface`.
By default every channel is written (storing a raw trace is always faithful); pass ``exclude_channels``
to drop channels you do not want. To see what a file contains before configuring, use
``InscopixGpioInterface.get_available_channels(file_path)``, which lists each channel's name, sample
count, and value range.

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
explicit: name each channel in ``events_config`` and say how to read it. ``reading`` picks which
value-transitions become events , ``"changes"`` (default, every change), ``"rising"``/``"falling"``
(only where the value increases/decreases), or ``"interval"`` (each increase paired with the next
decrease, giving a duration). ``levels`` optionally cuts a coded line into bands, written as a
categorical column.

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
