.. _adding_trials:

Adding Trials to NWB Files
==========================

NWB allows you to store information about timing information in a structured way.
These structures are often used to store information about trials, epochs, or other time intervals in the data.

Creating an NWBFile Object
---------------------------

To add trials, you first need an :py:class:`~pynwb.file.NWBFile` object. The recommended approach is to use the
:py:meth:`~neuroconv.basedatainterface.BaseDataInterface.create_nwbfile` method from any data interface or data converter.
This method creates an in-memory :py:class:`~pynwb.file.NWBFile` object with the interface's data already added to it, which you can
then modify before writing to disk.

.. code-block:: python

    from neuroconv.datainterfaces import YourDataInterface

    # Initialize your data interface with the path to your data
    interface = YourDataInterface(file_path="path/to/your/data")

    # Create an NWBFile object with the interface's data
    nwbfile = interface.create_nwbfile()

Adding Trials to the NWBFile
-----------------------------

Once you have an :py:class:`~pynwb.file.NWBFile` object, you can add trials to it:

.. code-block:: python

    # you can add custom columns to the trials table
    nwbfile.add_trials_column(name="trial_type", description="the type of trial")

    nwbfile.add_trial(start_time=0.0, stop_time=1.0, trial_type="go")
    nwbfile.add_trial(start_time=1.0, stop_time=2.0, trial_type="nogo")

You can also add epochs or other types of time intervals to an NWB File. See
`PyNWB Annotating Time Intervals <https://pynwb.readthedocs.io/en/stable/tutorials/general/plot_timeintervals.html>`_
for more information.

Writing the NWBFile to Disk
----------------------------

Once this information is added, you can write the :py:class:`~pynwb.file.NWBFile` to disk:

.. code-block:: python

    from neuroconv.tools import configure_and_write_nwbfile

    configure_and_write_nwbfile(
        nwbfile, nwbfile_path="path/to/destination.nwb", backend="hdf5"
    )

This will write the NWB file to disk with the added trials information, and optimize the storage settings of large
datasets for cloud compute.
