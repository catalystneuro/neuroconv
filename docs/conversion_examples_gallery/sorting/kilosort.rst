KiloSort data conversion
------------------------

Install NeuroConv with the additional dependencies necessary for reading kilosort data.

.. code-block:: bash

    pip install "neuroconv[kilosort]"

Convert KiloSort data to NWB using
:py:class:`~neuroconv.datainterfaces.ecephys.kilosort.kilosortdatainterface.KiloSortSortingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>>
    >>> from neuroconv.datainterfaces import KiloSortSortingInterface
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/phy/phy_example_0"
    >>> # Change the folder_path to the location of the data in your system
    >>> interface = KiloSortSortingInterface(folder_path=folder_path, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

Writing the templates
~~~~~~~~~~~~~~~~~~~~~

The templates in ``templates.npy`` are written as the ``waveform_mean`` column of the units table. Kilosort
records no scaling of its own and the NWB schema fixes that column's unit to volts, so the interface needs
``gain_to_uV``, the microvolts per unit of the data Kilosort was run on. Without it there is nothing to convert
the templates with, and writing them unconverted would label the sorter's own units as volts, so the conversion
warns and writes the units without waveforms. This is a limitation of the schema rather than of the format: the
fixed unit is being relaxed to a default, after which the templates will be writable in their native units and
the gain will only be needed to state them in volts.

``waveform_representation`` chooses what a folder converted on its own produces:

* ``"dense"``, the default. The channel axis spans every channel Kilosort sorted, in ``channel_map.npy`` order
  and the same for every unit, and is exactly zero on the channels a unit's template was not fit on, so the
  footprint stays readable as the non-zero columns. Nothing states which electrodes those channels are, because
  a Phy folder cannot say.
* ``"sparse_with_electrodes_table"``. An electrodes table is written from ``channel_positions.npy`` and
  ``channel_shanks.npy``, and each unit's waveform is narrowed to the electrodes its template was fit on. This
  is the only way the probe geometry reaches the file, at the cost of inventing a ``Device`` and an
  ``ElectrodeGroup`` that the folder does not describe, which is why it is not the default.
* ``"none"``. No waveforms, and nothing is read from ``templates.npy`` at all. This is how a conversion asks for
  spike times only, rather than asking for it by leaving out the gain, and it is the one setting that does not
  warn about a missing one.

When the raw recording is available, prefer linking the units to its real electrodes over inventing a probe
here. :py:class:`~neuroconv.converters.SortedRecordingConverter` does that, and
``KiloSortSortingInterface.get_unit_ids_to_channel_ids`` derives the mapping it needs straight from the
templates, so it does not have to be written by hand; see :ref:`deriving_mapping_from_kilosort`. The supplied
electrodes then decide the layout, and ``waveform_representation`` only decides whether the waveforms are
written at all.
