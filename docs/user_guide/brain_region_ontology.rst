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

Each distinct ``location`` string is resolved in two steps:

1. **Metadata mapping (takes precedence).** If ``metadata["BrainRegions"]`` provides an entry for
   the exact location string, those terms are used. The mapping is ontology-agnostic (each term is
   an explicit ``id`` and ``uri``), so it applies to **any** species and can attach more than one
   term to a region. This is how you annotate a region the offline lookup does not recognize, or
   override one it does.
2. **Offline lookup (mouse only).** Otherwise, for a mouse subject, NeuroConv consults a small
   curated table of common mouse brain structures, matching an exact Allen acronym (case-sensitive,
   e.g. ``"CA1"``, ``"VISp"``), a canonical structure name (case-insensitive, e.g.
   ``"caudoputamen"``), or a common informal name or abbreviation (e.g. ``"hippocampus"``, ``"V1"``).

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
table, a non-standard spelling, or a non-mouse species), map it under ``metadata["BrainRegions"]``.
Each brain area (the key) maps to an ontology term given as a dict with an ``id`` and a resolvable
``uri``. Because the term is explicit rather than MBA-specific, this mapping generalizes to any
ontology and any species:

.. code-block:: python

    metadata["BrainRegions"] = {
        "my recording site": {
            "id": "MBA:382",
            "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382",
        },
    }

    interface.run_conversion(nwbfile_path="out.nwb", metadata=metadata)

To annotate one brain area with **several** ontologies (e.g. both the Allen atlas and UBERON), map
it to a list of terms:

.. code-block:: python

    metadata["BrainRegions"] = {
        "CA1": [
            {"id": "MBA:382", "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382"},
            {"id": "UBERON:0003881", "uri": "http://purl.obolibrary.org/obo/UBERON_0003881"},
        ],
    }

The metadata mapping takes precedence over the offline lookup, so you can also use it to override a
string the mouse lookup would otherwise resolve differently.

Customizing the annotation
--------------------------

Both ontology annotations are overridable methods provided by ``OntologyAnnotationMixin``, which
``BaseDataInterface`` and ``NWBConverter`` inherit:

- ``add_brain_region_external_resources(nwbfile, metadata=None)`` — anatomical locations (this page)
- ``add_species_external_resource(nwbfile, metadata=None)`` — the subject species (see
  :doc:`species_ontology`)

Each runs at write time, once the interface/converter data has been added to the file. Override one
in your interface or converter subclass to change or disable that annotation — for example to use a
different atlas, annotate additional objects, or turn it off:

.. code-block:: python

    class MyConverter(NWBConverter):
        def add_brain_region_external_resources(self, nwbfile, metadata=None):
            return 0  # disable brain-region annotation

    # or extend the default behavior:
    class MyOtherConverter(NWBConverter):
        def add_brain_region_external_resources(self, nwbfile, metadata=None):
            number_added = super().add_brain_region_external_resources(nwbfile, metadata=metadata)
            # ... attach additional references here ...
            return number_added

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
