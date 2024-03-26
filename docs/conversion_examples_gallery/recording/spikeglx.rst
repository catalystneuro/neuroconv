SpikeGLX
^^^^^^^^

Install NeuroConv with the additional dependencies necessary for reading SpikeGLX data.

.. code-block:: bash

    pip install neuroconv[spikeglx]



SpikeGLXConverter
~~~~~~~~~~~~~~~~~

We can easily convert all data stored in the native SpikeGLX folder structure to NWB using
:py:class:`~neuroconv.converters.SpikeGLXConverterPipe`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.converters import SpikeGLXConverterPipe
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/spikeglx/Noise4Sam_g0"
    >>> converter = SpikeGLXConverterPipe(folder_path=folder_path)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = converter.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = output_folder / "my_spikeglx_session.nwb"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)



Single-stream
~~~~~~~~~~~~~

Defining a 'stream' as a single band on a single NeuroPixels probe, we can convert either an AP or LF SpikeGLX stream to NWB using
:py:class:`~neuroconv.datainterfaces.ecephys.spikeglx.spikeglxdatainterface.SpikeGLXRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import SpikeGLXRecordingInterface
    >>>
    >>> # For this interface we need to pass the location of the ``.bin`` file
    >>> file_path = f"{ECEPHY_DATA_PATH}/spikeglx/Noise4Sam_g0/Noise4Sam_g0_imec0/Noise4Sam_g0_t0.imec0.ap.bin"
    >>> # Change the file_path to the location in your system
    >>> interface = SpikeGLXRecordingInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
