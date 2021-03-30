Part 2, NWB APIs: PyNWB & MatNWB
================================

The development team of NWB develops and supports APIs in Python (PyNWB)
and MATLAB (MatNWB), which guide users in reading and writing NWB files.
The features of these two APIs are very similar to each other, so choose
whichever is more convenient. Note that most of the high-level conversion
tools use PyNWB, but the APIs are interchangeable and there should be no
problem with writing data using MatNWB even if you plan to read it using
PyNWB later (or vice versa). Below is a table of the available tutorials
illustrating the end-to-end conversion of common data types in each imaging
modality:

+-----------------------------------------+-----------------+-----------------+
|                                         | PyNWB           | MatNWB          |
+-----------------------------------------+-----------------+-----------------+
| Reading NWB files                       |                 | `15 min video`_ |
+-----------------------------------------+-----------------+-----------------+
| Writing basics                          |                 |                 |
+-----------------------------------------+-----------------+-----------------+
| Writing extracellular electrophysiology |                 | `46 min video`_ |
+-----------------------------------------+-----------------+-----------------+
| Writing intracellular electrophysiology |                 |                 |
+-----------------------------------------+-----------------+-----------------+
| Writing optical physiology              | `31 min video`_ | `39 min video`_ |
+-----------------------------------------+-----------------+-----------------+
| Advanced write                          |                 | `16 min video`_ |
+-----------------------------------------+-----------------+-----------------+

These tutorials walk you through the most common data types of each of the modalities.
Using the provided APIs and writing your own conversions can be challenging, and we
have provided automated solutions. Even if you are going to use these other tools, it
is important to walk through these so you understand how those tools work and are able
to make any necessary adjustments.

With the tutorials for domain-specific conversion, extensions, advanced I/O,
and the documentation for your proprietary formats, you have all of the tools to
create your own conversion. However, writing a full-fledged conversion script from
the ground up with MatNWB and PyNWB is time-intensive and error-prone. That is why,
in the next section, we will introduce automated conversion tools that work on a
large number of supported proprietary formats.


.. _31 min video: https://www.youtube.com/watch?v=HPjSxBjdFpM&ab_channel=NeurodataWithoutBorders
.. _15 min video: https://www.youtube.com/watch?v=ig_Xv2bTxjs&ab_channel=NeurodataWithoutBorders
.. _46 min video: https://www.youtube.com/watch?v=W8t4_quIl1k&ab_channel=NeurodataWithoutBorders
.. _39 min video: https://www.youtube.com/watch?v=OBidHdocnTc&ab_channel=NeurodataWithoutBorders
.. _16 min video: https://www.youtube.com/watch?v=PIE_F4iVv98&ab_channel=NeurodataWithoutBorders