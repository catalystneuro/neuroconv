spikeGLX & Phy
^^^^^^^^^^^^^^

A common workflow is to record electrophysiological data and then extract spiking units from the stream. The following is an
example of how to combine electrophysiological recordings and spike sorting data in the same conversion.

Note that for this specific example were using :py:class:`~neuroconv.datainterfaces.ecephys.spikeglxrecordingingerface.SpikeGLXRecordingInterface` as a recorder
and :py:class:`~.neuroconv.datainterfaces.ecephys.phy.phydatainterface.PhySortingInterface` as a sorter but any
of the other examples in our conversion gallery can be combined in this way.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import SpikeGLXRecordingInterface
    >>> from neuroconv.datainterfaces import PhySortingInterface
    >>> from neuroconv import NWBConverter
    >>>
    >>> # For this interface we need to pass the location of the ``.bin`` file
    >>> file_path = f"{ECEPHY_DATA_PATH}/spikeglx/Noise4Sam_g0/Noise4Sam_g0_imec0/Noise4Sam_g0_t0.imec0.ap.bin"
    >>> # Change the file_path to the location in your system
    >>> interface_spikeglx = SpikeGLXRecordingInterface(file_path=file_path, verbose=False)
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/phy/phy_example_0"
    >>> # Change the folder_path to the location of the data in your system
    >>> interface_phy = PhySortingInterface(folder_path=folder_path, verbose=False)
    >>>
    >>>  # Now that we have defined the two interfaces we pass them to the NWBConverter which will coordinate the
    >>>  # concurrent conversion of the data
    >>> converter = NWBConverter(data_interfaces=[interface_spikeglx, interface_phy], verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = converter.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> tzinfo = tz.gettz("US/Pacific")
    >>> session_start_time = datetime.fromisoformat(metadata["NWBFile"]["session_start_time"])
    >>> session_start_time = session_start_time.replace(tzinfo=tzinfo).isoformat()
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"test.nwb"
    >>> nwbfile = converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)
