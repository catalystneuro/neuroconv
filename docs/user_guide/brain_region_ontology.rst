Brain Region Ontology
=====================

Anatomical locations are stored in NWB as free-text strings: the ``location`` column of the
electrodes table (ecephys), ``ElectrodeGroup.location``, and ``ImagingPlane.location`` (ophys).
For a **mouse** subject, NeuroConv can attach a machine-readable
`Allen Mouse Brain Atlas <https://bioregistry.io/registry/mba>`_ (MBA) reference to each of these
locations, so downstream tools (e.g. the `DANDI Archive <https://dandiarchive.org/>`_) can resolve
the exact brain structure instead of guessing from an acronym.

This runs automatically at write time (once the electrodes table and imaging planes have been
populated) whenever the subject's species resolves to *Mus musculus*. It is gated on species
because the MBA vocabulary is mouse-specific; non-mouse subjects are left untouched. See also
:doc:`species_ontology` for how the species itself is standardized and annotated.

How locations are resolved
--------------------------

Each distinct ``location`` string is resolved to an MBA term in two steps:

1. **Metadata mapping (takes precedence).** If ``metadata["BrainRegions"]`` provides an entry for
   the exact location string, that mapping is used. This is how you annotate a region the offline
   lookup does not recognize, or override one it does.
2. **Offline lookup.** Otherwise NeuroConv consults a small curated table of common mouse brain
   structures, matching an exact Allen acronym (case-sensitive, e.g. ``"CA1"``, ``"VISp"``), a
   canonical structure name (case-insensitive, e.g. ``"caudoputamen"``), or a common informal name
   or abbreviation (e.g. ``"hippocampus"``, ``"V1"``).

Locations that resolve to neither (including the ``"unknown"`` placeholder) are left unannotated.

Automatic annotation
---------------------

No configuration is required for recognized regions. Given a mouse recording whose electrodes carry
Allen acronyms as their ``location`` (for a SpikeInterface recording, this is the ``brain_area``
property), a conversion writes an NCBITaxon reference for the species and an MBA reference for each
recognized region:

.. code-block:: python

    # recording.set_property("brain_area", ["CA1", "CA1", "VISp"]) upstream
    metadata["Subject"] = dict(subject_id="m1", species="Mus musculus", sex="M", age="P30D")

    nwbfile = interface.create_nwbfile(metadata=metadata)
    nwbfile.external_resources.to_dataframe()[["key", "entity_id", "entity_uri"]]
    #   key     entity_id   entity_uri
    #   CA1     MBA:382     https://purl.brain-bican.org/ontology/mbao/MBA_382
    #   VISp    MBA:385     https://purl.brain-bican.org/ontology/mbao/MBA_385

Defining the mapping in metadata
--------------------------------

When a location string is not recognized (a lab-specific label, a subregion outside the curated
table, or a non-standard spelling), map it to an MBA identifier under ``metadata["BrainRegions"]``.
The value may be a CURIE (``"MBA:382"``), a bare numeric id (``"382"``), the full MBA URI, or a
dict with an ``mba_id`` key and optional ``acronym`` / ``name``:

.. code-block:: python

    metadata["BrainRegions"] = {
        "my recording site": "MBA:382",              # CURIE
        "area X": {"mba_id": 385, "name": "V1"},     # explicit id with a label
    }

    interface.run_conversion(nwbfile_path="out.nwb", metadata=metadata)

You can also use the mapping to override the offline lookup for a string it would otherwise resolve
differently, since the metadata mapping takes precedence.

Using the lookup directly
-------------------------

The resolution and annotation functions are available in :py:mod:`neuroconv.tools.ontology`:

.. code-block:: python

    from neuroconv.tools.ontology import get_brain_region_term, add_brain_region_external_resources

    term = get_brain_region_term("caudoputamen")
    term.acronym       # 'CP'
    term.curie         # 'MBA:672'
    term.entity_uri    # 'https://purl.brain-bican.org/ontology/mbao/MBA_672'

    # Annotate an already-populated in-memory NWBFile (no-op unless the subject is a mouse):
    number_added = add_brain_region_external_resources(nwbfile, metadata=metadata)

.. note::

    In-file HERD storage requires ``pynwb >= 4.0.0``, which is NeuroConv's minimum supported
    version.
