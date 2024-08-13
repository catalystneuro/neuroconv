.. _adding_trials:

Adding Trials to NWB Files
==========================

NWB allows you to store information about time intervals in a structured way. These structure are often used to store
information about trials, epochs, or other time intervals in the data.
You can add time intervals to an NWBFile object before writing it using PyNWB.
Here is an example of how to add trials to an NWBFile object.
Here is how you would add trials to an NWB file:

.. code-block:: python

    # you can add custom columns to the trials table
    nwbfile.add_trials_column(name="trial_type", description="the type of trial")

    nwbfile.add_trial(start_time=0.0, stop_time=1.0, trial_type="go")
    nwbfile.add_trial(start_time=1.0, stop_time=2.0, trial_type="nogo")

You can also add epochs or other types of time intervals to an NWB File. See
`PyNWB Annotating Time Intervals <https://pynwb.readthedocs.io/en/stable/tutorials/general/plot_timeintervals.html>`_
for more information.

Once this information is added, you can write the NWB file to disk.

.. code-block:: python

    from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile

    configure_and_write_nwbfile(nwbfile, save_path="path/to/destination.nwb", backend="hdf5")

.. note::

    NWB generally recommends storing the full continuous stream of data in the NWB file, and then adding trials or
    epochs as time intervals. Trial-aligning the data is then done on-the-fly when reading the file. This allows for
    more flexibility in the analysis of the data.
