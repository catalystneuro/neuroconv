Ontology Annotation
===================

NeuroConv can attach machine-readable **ontology references** to a written NWB file, so downstream
tools such as the `DANDI Archive <https://dandiarchive.org/>`_ can resolve exactly what a value
means instead of guessing from free text. References are stored **in-file** under
``/general/external_resources`` using HDMF's HERD (External Resources Data), so they travel with the
file.

Two kinds of value are annotated automatically by a conversion:

- the subject's **species**, mapped to `NCBITaxon <https://bioregistry.io/registry/ncbitaxon>`_;
- anatomical **brain regions** (``location`` fields), mapped for mouse subjects to the
  `Allen Mouse Brain Atlas <https://bioregistry.io/registry/mba>`_ (MBA), or to any ontology you
  specify in metadata.

Both annotations are applied at write time by the overridable
:py:class:`~neuroconv.tools.ontology.OntologyAnnotationMixin`, which ``BaseDataInterface`` and
``NWBConverter`` inherit (see `Customizing the annotation`_ below). In-file HERD storage requires
``pynwb >= 4.0.0``, which is NeuroConv's minimum supported version.

Species
-------

NWB stores a subject's species in :py:attr:`Subject.species <pynwb.file.Subject.species>` as a
binomial Latin name (e.g. ``"Mus musculus"``) or a taxonomy URL. NeuroConv helps standardize it in
two complementary ways, backed by a small, curated, offline table of common neuroscience species
(:py:data:`~neuroconv.tools.ontology.SPECIES_TERMS`). The table needs no network access and no extra
dependencies, and it is high-precision: it only speaks up when confident, and valid-but-uncommon
binomials pass through silently.

Suggesting a standardized term
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When ``Subject.species`` is a recognized common name (e.g. ``"mouse"``) or a likely typo of a known
binomial (e.g. ``"Homo sapien"``), NeuroConv emits a ``UserWarning`` recommending the canonical
Latin binomial and its NCBITaxon identifier while the metadata is processed in
:py:func:`~neuroconv.tools.nwb_helpers.make_nwbfile_from_metadata`. This never raises and never
blocks a conversion.

.. code-block:: python

    from neuroconv.tools.ontology import validate_species

    validate_species("mouse")
    # UserWarning: Subject species 'mouse' is a common name. Consider using the Latin binomial
    # 'Mus musculus' (NCBITaxon:10090) for interoperability. See https://bioregistry.io/NCBITaxon:10090

    validate_species("Homo sapien")
    # UserWarning: Subject species 'Homo sapien' closely matches a known species name. Consider using
    # the Latin binomial 'Homo sapiens' (NCBITaxon:9606) for interoperability. ...

    validate_species("Mus musculus")  # already canonical -> no warning, returns the term
    validate_species("Octodon degus")  # valid but not in the table -> no warning, returns None

To resolve a value to its canonical term without emitting a warning, use
:py:func:`~neuroconv.tools.ontology.get_species_term`, which also succeeds on exact canonical
matches:

.. code-block:: python

    from neuroconv.tools.ontology import get_species_term

    term = get_species_term("rhesus macaque")
    term.canonical_name  # 'Macaca mulatta'
    term.ncbitaxon_id    # 'NCBITaxon:9544'
    term.entity_uri      # 'http://purl.obolibrary.org/obo/NCBITaxon_9544'

Annotating the file with an NCBITaxon reference
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When the species resolves to a recognized term, NeuroConv attaches a reference mapping
``Subject.species`` to its NCBITaxon entity:

.. code-block:: python

    from neuroconv.tools.ontology import add_species_external_resource

    # nwbfile.subject.species == "Mus musculus"
    added = add_species_external_resource(nwbfile)  # returns True
    nwbfile.external_resources  # now carries a Mus musculus -> NCBITaxon:10090 reference

The call is a no-op (returns ``False``) when there is no subject or the species is not recognized,
and it is idempotent: an existing ``external_resources`` HERD is extended in place rather than
replaced, and a species that is already annotated is not added twice.

Brain regions
-------------

Anatomical locations are stored in NWB as free-text strings: the ``location`` column of the
electrodes table (ecephys), ``ElectrodeGroup.location``, and ``ImagingPlane.location`` (ophys). For
a **mouse** subject, NeuroConv can attach an MBA reference to each of these, so downstream tools can
resolve the exact structure instead of guessing from an acronym. This runs at write time, once the
electrodes table and imaging planes have been populated.

How locations are resolved
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
The offline lookup is gated on species because the MBA vocabulary is mouse-specific; a non-mouse
subject is annotated only through the metadata mapping.

Automatic annotation
~~~~~~~~~~~~~~~~~~~~~~

No configuration is required for recognized regions. Given a mouse recording whose electrodes carry
Allen acronyms as their ``location`` (for a SpikeInterface recording, this is the ``brain_area``
property), a conversion writes an NCBITaxon reference for the species and an MBA reference for each
recognized region:

.. code-block:: python

    # recording.set_property("brain_area", ["CA1", "CA1", "VISp"]) upstream
    metadata["Subject"] = dict(subject_id="m1", species="Mus musculus", sex="M", age="P30D")

    nwbfile = interface.create_nwbfile(metadata=metadata)
    nwbfile.external_resources.to_dataframe()[["key", "entity_id", "entity_uri"]]
    #   key             entity_id         entity_uri
    #   Mus musculus    NCBITaxon:10090   http://purl.obolibrary.org/obo/NCBITaxon_10090
    #   CA1             MBA:382           https://purl.brain-bican.org/ontology/mbao/MBA_382
    #   VISp            MBA:385           https://purl.brain-bican.org/ontology/mbao/MBA_385

Defining the mapping in metadata
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

Both annotations are overridable methods provided by
:py:class:`~neuroconv.tools.ontology.OntologyAnnotationMixin`, which ``BaseDataInterface`` and
``NWBConverter`` inherit:

- ``add_species_external_resource(nwbfile, metadata=None)`` — the subject species;
- ``add_brain_region_external_resources(nwbfile, metadata=None)`` — anatomical locations.

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

Using the lookups directly
--------------------------

The resolution and annotation functions are available in :py:mod:`neuroconv.tools.ontology`:

.. code-block:: python

    from neuroconv.tools.ontology import get_brain_region_term, add_brain_region_external_resources

    term = get_brain_region_term("caudoputamen")
    term.acronym       # 'CP'
    term.curie         # 'MBA:672'
    term.entity_uri    # 'https://purl.brain-bican.org/ontology/mbao/MBA_672'

    # Annotate an already-populated in-memory NWBFile (no-op unless the subject is a mouse):
    number_added = add_brain_region_external_resources(nwbfile, metadata=metadata)
