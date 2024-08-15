.. _adding_trials:

Adding Trials to NWB Files
==========================

NWB allows you to store information about timing information in a structured way.
These structures are often used to store information about trials, epochs, or other time intervals in the data.
Here is how to add trials to an NWBFile object:

.. code-block:: python

    # you can add custom columns to the trials table
    nwbfile.add_trials_column(name="trial_type", description="the type of trial")

    nwbfile.add_trial(start_time=0.0, stop_time=1.0, trial_type="go")
    nwbfile.add_trial(start_time=1.0, stop_time=2.0, trial_type="nogo")

You can also add epochs or other types of time intervals to an NWB File. See
`PyNWB Annotating Time Intervals <https://pynwb.readthedocs.io/en/stable/tutorials/general/plot_timeintervals.html>`_
for more information.

Once this information is added, you can write the NWB file to disk:

.. code-block:: python

    from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile

    configure_and_write_nwbfile(
        nwbfile, save_path="path/to/destination.nwb", backend="hdf5"
    )

This will write the NWB file to disk with the added trials information, and optimize the storage settings of large
datasets for cloud compute.
