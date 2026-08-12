Ontology Annotation
===================

NeuroConv can attach machine-readable **ontology references** to a written NWB file, so downstream
tools such as the `DANDI Archive <https://dandiarchive.org/>`_ can resolve exactly what a value
means instead of guessing from free text. References are stored **in-file** under
``/general/external_resources`` using HDMF's HERD (External Resources Data), so they travel with the
file.

Four kinds of value are annotated automatically by a conversion:

- the subject's **species**, mapped to `NCBITaxon <https://bioregistry.io/registry/ncbitaxon>`_;
- the subject's **strain**, mapped to `RRID <https://bioregistry.io/registry/rrid>`_ (Research
  Resource Identifiers) for common laboratory rodent strains;
- anatomical **brain regions** (``location`` fields), mapped to the
  `Allen Mouse Brain Atlas <https://bioregistry.io/registry/mba>`_ (MBA) for mouse subjects, the
  `Allen Human Brain Atlas <https://bioregistry.io/registry/hba>`_ (HBA) for human subjects, a
  species-agnostic `UBERON <https://bioregistry.io/registry/uberon>`_ vocabulary of common region
  names for every other recognized species (e.g. rat, which has no dedicated Allen atlas), or to
  any ontology you specify in metadata;
- **general anatomy** -- skeleton parts and muscles named as ``ndx-pose`` ``Skeleton`` nodes
  (pose-estimation keypoints, e.g. ``"Snout"``, ``"Shoulder"``) -- mapped to a species-agnostic
  UBERON vocabulary. This is independent of brain-region annotation: it targets pose-estimation
  keypoints, not ``location`` fields, and does not vary per species or atlas.

Brain-region annotation covers every ``location`` field NeuroConv knows about: the electrodes table
``location`` column and ``ElectrodeGroup.location`` (ecephys), ``ImagingPlane.location`` (ophys), and
the ``FiberPhotometryTable`` ``location`` column (fiber photometry).

The recognized terms live in curated `LinkML <https://linkml.io/>`_ TermSet files shipped with
NeuroConv (one per vocabulary, the same format used by
`HDMF's TermSet <https://hdmf.readthedocs.io/en/stable/tutorials/plot_term_set.html>`_), so the
mappings are transparent and editable.

All four annotations are applied at write time by the overridable
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

Strain
------

NWB stores a subject's laboratory strain in :py:attr:`Subject.strain <pynwb.file.Subject.strain>`
as free text (e.g. ``"C57BL/6J"``, ``"Long-Evans"``). NeuroConv standardizes it the same way it
standardizes species, backed by a small, curated, offline table of common laboratory rodent
strains (:py:data:`~neuroconv.tools.ontology.STRAIN_TERMS`):

.. code-block:: python

    from neuroconv.tools.ontology import validate_strain, get_strain_term, add_strain_external_resource

    validate_strain("black 6")
    # UserWarning: Subject strain 'black 6' is an informal spelling. Consider using 'C57BL/6J'
    # (RRID:IMSR_JAX:000664) for interoperability. See https://bioregistry.io/RRID:IMSR_JAX:000664

    term = get_strain_term("long evans")
    term.canonical_name  # 'Long-Evans'
    term.rrid             # 'RRID:RGD_2308852'

    # nwbfile.subject.strain == "Long-Evans"
    added = add_strain_external_resource(nwbfile)  # returns True

The call is a no-op (returns ``False``) when there is no subject, the subject has no strain set,
or the strain resolves through neither the metadata mapping below nor the curated table, and it is
idempotent in the same way species annotation is.

Only a small curated set of common lab lines is included in :py:data:`~neuroconv.tools.ontology.STRAIN_TERMS`.
For a strain outside that table (an in-house line, a less common vendor strain), or to override a
curated result, map it under ``metadata["Strain"]`` -- the same ontology-agnostic pattern
``metadata["BrainRegions"]`` uses for brain regions. Each key is the exact strain string as it
appears on ``Subject.strain``, mapped to a term ``{"id": ..., "uri": ...}`` (or a list of terms, to
attach more than one ontology reference):

.. code-block:: python

    metadata["Strain"] = {
        "my in-house line": {
            "id": "RRID:IMSR_JAX:000664",
            "uri": "https://scicrunch.org/resolver/RRID:IMSR_JAX:000664",
        },
    }

    interface.run_conversion(nwbfile_path="out.nwb", metadata=metadata)

The metadata mapping takes precedence over the curated table, so it can also override a strain the
table would otherwise resolve differently.

Brain regions
-------------

Anatomical locations are stored in NWB as free-text strings: the ``location`` column of the
electrodes table (ecephys), ``ElectrodeGroup.location``, ``ImagingPlane.location`` (ophys), and the
``FiberPhotometryTable`` ``location`` column (fiber photometry). For any subject whose species is
recognized, NeuroConv can attach an ontology reference to each of these, so downstream tools can
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
2. **Offline lookup (per species).** Otherwise NeuroConv consults the curated atlas for the
   subject's species -- the Allen Mouse Brain Atlas for *Mus musculus*, the Allen Human Brain
   Atlas for *Homo sapiens*, and a small species-agnostic UBERON vocabulary of common region names
   (:py:data:`~neuroconv.tools.ontology.UBERON_TERMS`) for every other recognized species -- matching
   an exact atlas acronym (case-sensitive, e.g. ``"CA1"``, ``"VISp"``), a canonical structure name
   (case-insensitive, e.g. ``"caudoputamen"``), or a common informal name or abbreviation (e.g.
   ``"hippocampus"``, ``"V1"``).

Locations that resolve to neither (including the ``"unknown"`` placeholder) are left unannotated.
The lookup is species-specific because the same acronym denotes different structures across atlases
(e.g. ``"MB"`` is the mouse midbrain but the human mammillary body); a subject whose species is not
recognized at all is annotated only through the metadata mapping. The UBERON fallback is
intentionally small and generic -- lab-specific channel labels (e.g. a custom EEG grid's own
naming) still belong in the metadata mapping.

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

General anatomy
----------------

``ndx-pose`` stores a pose-estimation skeleton's body-part names as free text in
``Skeleton.nodes`` (e.g. ``"Snout"``, ``"Shoulder"``, ``"Tail"``). NeuroConv can attach a UBERON
reference to each recognized node name, so downstream tools can resolve the exact anatomical
structure a keypoint tracks. This is independent of brain-region annotation above: it never looks
at ``location`` fields, and the vocabulary (:py:data:`~neuroconv.tools.ontology.ANATOMY_TERMS`,
~28 curated skeleton parts and muscles) is species-agnostic -- there is no per-species atlas
selection.

.. code-block:: python

    from neuroconv.tools.ontology import get_anatomy_term, add_anatomy_external_resources

    term = get_anatomy_term("trapezius muscle")
    term.curie        # 'UBERON:0002380'
    term.entity_uri   # 'http://purl.obolibrary.org/obo/UBERON_0002380'

    # skeleton.nodes == ["Snout", "Shoulder", "EarL"] on an nwbfile.processing["behavior"]["Skeletons"] entry
    number_added = add_anatomy_external_resources(nwbfile)  # annotates "Snout" and "Shoulder"; "EarL" is left alone

Like brain regions, an unrecognized node name (e.g. a lab-specific keypoint with a laterality
marker such as ``"EarL"``) can be mapped explicitly under ``metadata["Anatomy"]``, using the same
``{"id": ..., "uri": ...}`` (or list-of-terms) shape and the same override-takes-precedence rule:

.. code-block:: python

    metadata["Anatomy"] = {
        "EarL": {"id": "UBERON:0001691", "uri": "http://purl.obolibrary.org/obo/UBERON_0001691"},
    }

Customizing the annotation
--------------------------

All four annotations are overridable methods provided by
:py:class:`~neuroconv.tools.ontology.OntologyAnnotationMixin`, which ``BaseDataInterface`` and
``NWBConverter`` inherit:

- ``add_species_external_resource(nwbfile, metadata=None)`` — the subject species;
- ``add_strain_external_resource(nwbfile, metadata=None)`` — the subject strain;
- ``add_brain_region_external_resources(nwbfile, metadata=None)`` — anatomical locations;
- ``add_anatomy_external_resources(nwbfile, metadata=None)`` — pose-estimation skeleton nodes.

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

    term = get_brain_region_term("caudoputamen")  # species defaults to "Mus musculus"
    term.acronym       # 'CP'
    term.curie         # 'MBA:672'
    term.entity_uri    # 'https://purl.brain-bican.org/ontology/mbao/MBA_672'

    get_brain_region_term("CA1", species="Homo sapiens").curie  # 'HBA:12892'
    get_brain_region_term("hippocampus", species="Rattus norvegicus").curie  # 'UBERON:0002421'

    # Annotate an already-populated in-memory NWBFile (no-op unless the subject's species is recognized):
    number_added = add_brain_region_external_resources(nwbfile, metadata=metadata)
