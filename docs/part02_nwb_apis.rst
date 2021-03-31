Part 2, NWB APIs: PyNWB & MatNWB
================================

The development team of NWB develops and supports APIs in Python
(`PyNWB <https://pynwb.readthedocs.io/en/stable/>`_)
and MATLAB (`MatNWB <https://github.com/NeurodataWithoutBorders/matnwb>`_),
which guide users in reading and writing NWB files.
The features of these two APIs are very similar to each other, so choose
whichever is more convenient. Note that most of the high-level conversion
tools use PyNWB, but the APIs are interchangeable and there should be no
problem with writing data using MatNWB even if you plan to read it using
PyNWB later (or vice versa). Below is a table of the available tutorials
illustrating the end-to-end conversion of common data types in each imaging
modality:

.. list-table::
    :header-rows: 1

    * -
      - PyNWB
      - MatNWB
    * - Reading NWB files
      - `Jupyter notebook <https://github.com/NeurodataWithoutBorders/nwb_tutorial/blob/master/HCK09/pynwb_read_demo.ipynb>`_
      - `15 min video`_

        `MATLAB Live Script`_
    * - Writing extracellular electrophysiology
      - `23 min video`_

        `Jupyter notebook <https://github.com/NeurodataWithoutBorders/nwb_tutorial/blob/master/HCK08/ecephys_tutorial.ipynb>`_
      - `46 min video`_

        `Written tutorial <https://neurodatawithoutborders.github.io/matnwb/tutorials/html/ecephys.html>`_
    * - Writing intracellular electrophysiology
      - `Jupyter notebook <https://github.com/NeurodataWithoutBorders/nwb_tutorial/blob/master/HCK08/ICEphys_basic_hck8.ipynb>`_
      - `Written tutorial <https://neurodatawithoutborders.github.io/matnwb/tutorials/html/icephys.html>`_
    * - Writing optical physiology
      - `31 min video`_

        `Jupyter notebook <https://github.com/NeurodataWithoutBorders/nwb_tutorial/blob/master/HCK08/ophys_tutorial.ipynb>`_
      - `39 min video`_

        `Written tutorial <https://neurodatawithoutborders.github.io/matnwb/tutorials/html/ophys.html>`_
    * - Advanced write
      - `26 min video <https://www.youtube.com/watch?v=wduZHfNOaNg&ab_channel=NeurodataWithoutBorders>`_
      - `16 min video <https://www.youtube.com/watch?v=PIE_F4iVv98&ab_channel=NeurodataWithoutBorders>`_

        `Written tutorial <https://neurodatawithoutborders.github.io/matnwb/tutorials/html/dataPipe.html>`_

These tutorials walk you through the most common data types of each of the modalities.
With the tutorials for domain-specific conversion, extensions, advanced I/O,
and the documentation for your proprietary formats, you have all of the tools to
create your own conversion. However, writing a full-fledged conversion script from
the ground up with MatNWB and PyNWB is time-intensive, error-prone, and requires
detailed knowledge of the source format. That is why, in the next section, we
will introduce automated conversion tools that work on a large number of supported proprietary formats.


.. _31 min video: https://www.youtube.com/watch?v=HPjSxBjdFpM&ab_channel=NeurodataWithoutBorders
.. _15 min video: https://www.youtube.com/watch?v=ig_Xv2bTxjs&ab_channel=NeurodataWithoutBorders
.. _46 min video: https://www.youtube.com/watch?v=W8t4_quIl1k&ab_channel=NeurodataWithoutBorders
.. _39 min video: https://www.youtube.com/watch?v=OBidHdocnTc&ab_channel=NeurodataWithoutBorders
.. _16 min video: https://www.youtube.com/watch?v=PIE_F4iVv98&ab_channel=NeurodataWithoutBorders
.. _MATLAB Live Script: https://github.com/NeurodataWithoutBorders/nwb_tutorial/blob/master/HCK09/matnwb_read_demo.mlx?raw=true
.. _23 min video: https://www.youtube.com/watch?v=rlywed3ar-s&ab_channel=NeurodataWithoutBorders