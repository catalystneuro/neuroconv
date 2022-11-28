spikeGLX data conversion
------------------------

Install NeuroConv with the additional dependencies necessary for reading SpikeGLX data.

.. code-block:: bash

    pip install neuroconv[spikeglx]

Convert SpikeGLX data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.spikeglx.spikeglxdatainterface.SpikeGLXRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import SpikeGLXRecordingInterface, SpikeGLXLFPInterface
    >>>
    >>> # Pass the location of the ``ap.bin`` file.
    >>> file_path = f"{ECEPHY_DATA_PATH}/spikeglx/Noise4Sam_g0/Noise4Sam_g0_imec0/Noise4Sam_g0_t0.imec0.ap.bin"
    >>> interface_spikeglx_ap = SpikeGLXRecordingInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Pass the location of the ``ap.bin`` file.
    >>> file_path = f"{ECEPHY_DATA_PATH}/spikeglx/Noise4Sam_g0/Noise4Sam_g0_imec0/Noise4Sam_g0_t0.imec0.lf.bin"
    >>> interface_spikeglx_lf = SpikeGLXLFPInterface(file_path=file_path, verbose=False)
    >>>
    >>>  # Now that we have defined the two interfaces we pass them to the ConverterPipe which will coordinate the
    >>>  # concurrent conversion of the data
    >>> converter = ConverterPipe(data_interfaces=[interface_spikeglx_ap, interface_spikeglx_lf], verbose=False)
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
