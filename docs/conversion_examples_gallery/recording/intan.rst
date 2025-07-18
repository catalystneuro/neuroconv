Intan Amplifier Data Conversion
------------------------------

This guide covers the conversion of Intan amplifier data, which contains the primary neural recordings from the RHD2000 or RHS2000 amplifier channels.
If your data includes other streams like analog inputs, auxiliary inputs, or DC amplifiers, please see the :doc:`IntanAnalogInterface <intan_analog>` guide.

Install NeuroConv with the additional dependencies necessary for reading Intan data.

.. code-block:: bash

    pip install "neuroconv[intan]"

Convert Intan data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.intan.intandatainterface.IntanRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import IntanRecordingInterface
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/intan/intan_rhd_test_1.rhd" # This can also be .rhs
    >>> interface = IntanRecordingInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

.. note::
    If your Intan data contains non-amplifier analog streams (e.g., auxiliary inputs, ADC inputs, DC amplifiers),
    use the :doc:`IntanAnalogInterface <intan_analog>` instead.
