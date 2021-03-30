Part 1, Core NWB
================

First, we need to understand what types of data go into NWB.
The NWB core schema defines data containers for the most common data objects in
neurophysiology data. The experiment types NWB core covers is intracellular
electrophysiology (e.g. patch clamping), extracellular electrophysiology
(e.g. Neuropixel probes), and optical physiology (e.g. two-photon imaging).

The goal of NWB is to package all of the data in a particular session into a single file.
This includes the neurophysiology data itself, but also includes other data such
as information about the data acquisition, experiment design, experimental subject,
and behavior of that subject. Neurophysiology data is rapidly evolving,
and it would be impossible for NWB core to handle all possible neurodata types.
For this, we have an extensions library, which allows users to create and share
additions to the NWB core which describe new data objects. Read more about extensions
`here <https://pynwb.readthedocs.io/en/stable/tutorials/general/extensions.html#tutorial-extending-nwb>`_.

.. image:: ../img/nwb_overview.png