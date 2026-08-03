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

The templates in ``templates.npy`` are written as the ``waveform_mean`` column of the units table, but only if
the interface is given ``gain_to_uV``, the microvolts per unit of the data Kilosort was run on. Kilosort records
no scaling of its own and the NWB schema fixes that column to volts, so without a gain there is no honest way to
write it and the conversion warns and writes the units without waveforms. Pass ``waveform_representation="none"``
to ask for spike times only, or ``"sparse_with_electrodes_table"`` to also write the probe geometry from the
sorter folder and link each unit to the electrodes its template was fit on.
