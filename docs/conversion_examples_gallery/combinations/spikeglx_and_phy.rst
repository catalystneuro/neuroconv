SpikeGLX & Phy
--------------

A common workflow is to record electrophysiology data and then extract spiking units. The following is an example of
how to combine electrophysiology recordings and spike sorting data in the same conversion. For this specific example
were are combining a SpikeGLX recording with Phy sorting results using the
:py:class:`~neuroconv.datainterfaces.ecephys.spikeglx.spikeglxdatainterface.SpikeGLXRecordingInterface` and
:py:class:`~.neuroconv.datainterfaces.ecephys.phy.phydatainterface.PhySortingInterface` classes.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv import ConverterPipe
    >>> from neuroconv.datainterfaces import SpikeGLXRecordingInterface, PhySortingInterface
    >>>
    >>> # For this interface we need to pass the location of the ``.bin`` file. Change the file_path to the location in your system
    >>> file_path = f"{ECEPHY_DATA_PATH}/spikeglx/Noise4Sam_g0/Noise4Sam_g0_imec0/Noise4Sam_g0_t0.imec0.ap.bin"
    >>> interface_spikeglx = SpikeGLXRecordingInterface(file_path=file_path, verbose=False)
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/phy/phy_example_0"  # Change the folder_path to the location of the data in your system
    >>> interface_phy = PhySortingInterface(folder_path=folder_path, verbose=False)
    >>>
    >>>  # Now that we have defined the two interfaces we pass them to the ConverterPipe which will coordinate the
    >>>  # concurrent conversion of the data
    >>> converter = ConverterPipe(data_interfaces=[interface_spikeglx, interface_phy], verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = converter.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> nwbfile = converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)
