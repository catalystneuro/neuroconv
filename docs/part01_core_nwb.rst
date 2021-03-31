Part 1, Core NWB
================

First, we need to understand what types of data go into NWB. The goal of NWB
is to package all of the data in a particular session into a single file.
This includes the neurophysiology data itself, but also includes other data such
as information about the data acquisition, experiment design, experimental subject,
and behavior of that subject. The NWB core schema defines data containers for
the most common data objects in neurophysiology data. The experiment types NWB
core covers is intracellular electrophysiology (e.g. patch clamping), extracellular
electrophysiology (e.g. Neuropixel probes), and optical physiology (e.g. two-photon imaging).

.. image:: /img/nwb_overview.png

All of these data types and relationships are defined using
`HDMF <https://hdmf-schema-language.readthedocs.io/en/latest/>`_,
a specification language for describing complex structures of data. NWB is faced with the challenge
of supporting a large variety of different experiment types, so the data types and relationships
can get quite complex, so NWB development team supports APIs To help users easily and efficiently read and
write NWB files. These APIs are described in the next section.