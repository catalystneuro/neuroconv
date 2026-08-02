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
which writes each derived event type as a ``pynwb.event.EventsTable`` into ``nwbfile.events``. Selection
is explicit: name each channel in ``detection_configuration`` and give it a list of detection specs, one
per event type you want from it. **Start from the inventory**, since the file itself says nothing about
what a channel is: ``InscopixGpioEventsInterface.get_available_channels(file_path)`` reports each
channel's sample count and value set, which is what tells you whether a channel is a two-valued line, a
graded stimulus level, or flat for the whole session, and it is where the cut points below come from. A
spec's ``detection`` picks which transitions become events:
``"high_period"``/``"low_period"`` (a durative reading pairing each edge with the next opposite edge,
giving a duration), ``"rising"``/``"falling"`` (only the up/down transitions, as point events), or
``"value_change"`` (a point event at every transition).

Every spec also carries a ``signal_conditioning`` saying how its channel becomes a two-valued line. A
channel that is already two-valued takes ``{"binarize": "midpoint"}``, whose cut falls strictly between
its levels whatever they are, so a ``0``/``1`` line and a line at 48 and 64 both read correctly without
you knowing either. A graded channel takes ``{"binarize": c}`` naming where to cut, and the value set
from the inventory is what tells you where the meaningful boundaries are. To keep several levels of one
channel apart, cut it once per boundary and give each spec its own ``event_name``, as below: each cut
becomes a durative event type with real start and stop times, and the level the channel occupies at any
instant is how many of them are open, so nothing is lost.

.. code-block:: python

    >>> from neuroconv.datainterfaces import InscopixGpioEventsInterface
    >>>
    >>> detection_configuration = {
    ...     # A 0/1 frame clock: the derived cut lands between its two levels.
    ...     "BNC Sync Output": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising"}],
    ...     # An odor-concentration stimulus, cut at two boundaries worth telling apart.
    ...     "GPIO-2": [
    ...         {"signal_conditioning": {"binarize": 136}, "detection": "high_period", "event_name": "odor_low"},
    ...         {"signal_conditioning": {"binarize": 192}, "detection": "high_period", "event_name": "odor_high"},
    ...     ],
    ... }
    >>> interface = InscopixGpioEventsInterface(
    ...     file_path=file_path, detection_configuration=detection_configuration, verbose=False
    ... )
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
