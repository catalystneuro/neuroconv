Intan analog data conversion
----------------------------

Install NeuroConv with the additional dependencies necessary for reading Intan data.

.. code-block:: bash

    pip install "neuroconv[intan]"

Convert Intan analog channel data (non-amplifier streams) to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.intan.intananaloginterface.IntanAnalogInterface`.

This interface supports analog streams including:

* **RHD2000 auxiliary input channel**: Auxiliary input channels (e.g., accelerometer data)
* **RHD2000 supply voltage channel**: Supply voltage channels
* **USB board ADC input channel**: ADC input channels (analog signals -10V to +10V)
* **DC Amplifier channel**: DC amplifier channels (RHS system only)

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import IntanAnalogInterface
    >>>
    >>> # For this interface we need to pass the location of the .rhd or .rhs file
    >>> file_path = f"{ECEPHY_DATA_PATH}/intan/intan_rhd_test_1.rhd"
    >>>
    >>> # Convert ADC input channels
    >>> interface = IntanAnalogInterface(
    ...     file_path=file_path,
    ...     stream_name="USB board ADC input channel",
    ...     verbose=False
    ... )
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

You can also convert auxiliary input channels (e.g., accelerometer data):

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import IntanAnalogInterface
    >>>
    >>> # For this interface we need to pass the location of the .rhd or .rhs file
    >>> file_path_aux = f"{ECEPHY_DATA_PATH}/intan/intan_fpc_test_231117_052630/info.rhd"
    >>>
    >>> # Convert auxiliary input channels (e.g., accelerometer data)
    >>> interface_aux = IntanAnalogInterface(
    ...     file_path=file_path_aux,
    ...     stream_name="RHD2000 auxiliary input channel",
    ...     verbose=False
    ... )
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata_aux = interface_aux.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata_aux["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path_aux = output_folder / "intan_auxiliary_conversion.nwb"
    >>> interface_aux.run_conversion(nwbfile_path=nwbfile_path_aux, metadata=metadata_aux)

For RHS systems, you can also convert ADC output channels:

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import IntanAnalogInterface
    >>>
    >>> # For this interface we need to pass the location of the .rhs file
    >>> file_path_output = f"{ECEPHY_DATA_PATH}/intan/intan_rhs_test_1.rhs"
    >>>
    >>> # Convert ADC output channels (RHS system)
    >>> interface_output = IntanAnalogInterface(
    ...     file_path=file_path_output,
    ...     stream_name="USB board ADC output channel",
    ...     verbose=False
    ... )
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata_output = interface_output.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata_output["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path_output = output_folder / "intan_adc_output_conversion.nwb"
    >>> interface_output.run_conversion(nwbfile_path=nwbfile_path_output, metadata=metadata_output)
