Ontology Annotation
===================

NeuroConv can attach machine-readable **ontology references** to a written NWB file, so downstream
tools such as the `DANDI Archive <https://dandiarchive.org/>`_ can resolve exactly what a value
means instead of guessing from free text. References are stored **in-file** under
``/general/external_resources`` using HDMF's HERD (External Resources Data), so they travel with the
file. In-file HERD storage requires ``pynwb >= 4.0.0``, which is NeuroConv's minimum supported
version.

Two kinds of value are annotated:

- the subject's **species**, mapped to `NCBITaxon <https://bioregistry.io/registry/ncbitaxon>`_;
- anatomical **brain regions** (``location`` fields), mapped to the
  `Allen Mouse Brain Atlas <https://bioregistry.io/registry/mba>`_ (MBA) for mouse subjects, the
  `Allen Human Brain Atlas <https://bioregistry.io/registry/hba>`_ (HBA) for human subjects, a
  species-agnostic `UBERON <https://bioregistry.io/registry/uberon>`_ vocabulary of common region
  names for every other recognized species (e.g. rat, which has no dedicated Allen atlas), or to
  any ontology you specify in metadata.

Brain-region annotation covers every ``location`` field NeuroConv knows about: the electrodes table
``location`` column and ``ElectrodeGroup.location`` (ecephys), ``ImagingPlane.location`` (ophys), and
the ``FiberPhotometryTable`` ``location`` column (fiber photometry).

Two steps: infer, then annotate
-------------------------------

Ontology support is deliberately split into two independent halves, both in
:py:mod:`neuroconv.tools.ontology`:

1. **Inference** — :py:func:`~neuroconv.tools.ontology.infer_species_ontology_metadata` and
   :py:func:`~neuroconv.tools.ontology.infer_brain_region_ontology_metadata` take the free-text
   values a lab wrote (``"mouse"``, ``"CA1"``) and resolve them to ontology terms, writing each
   term into ``metadata`` **next to the value it describes**. This step guesses; run it when you
   want NeuroConv to propose terms, then inspect and edit the result.
2. **Annotation** — :py:func:`~neuroconv.tools.ontology.add_species_external_resource` and
   :py:func:`~neuroconv.tools.ontology.add_brain_region_external_resources` take the terms already
   stated in ``metadata`` and write them into the file as HERD references. This step is
   deterministic — nothing is inferred, so what lands in the file is exactly what the metadata
   says — and **a conversion runs it automatically**. It is a no-op unless the metadata carries an
   ``ontology`` block.

Because the two are separate, the annotation you write does not have to come from NeuroConv's
inference: you can bring terms from an ontology service or a file you curate once per dataset and
still have a conversion write them, and you always have a record of which terms you gave.

Where the terms live in metadata
--------------------------------

Each term is an explicit ``{"id": <CURIE>, "uri": <resolvable URI>}`` dict, placed in an
``ontology`` sub-block of the metadata block that already holds the value:

.. code-block:: python

    metadata["Subject"] = {
        "subject_id": "sub-01",
        "species": "Mus musculus",
        "ontology": {
            "species": {"id": "NCBITaxon:10090", "uri": "http://purl.obolibrary.org/obo/NCBITaxon_10090"},
        },
    }

    metadata["Ecephys"]["ontology"] = {
        "brain_regions": {
            "CA1": {"id": "MBA:382", "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382"},
        },
    }

Brain-region terms are keyed by the free-text ``location`` string and live under the modality block
whose objects carry that location: ``metadata["Ecephys"]["ontology"]["brain_regions"]`` (electrodes
table and electrode groups), ``metadata["Ophys"]["ontology"]["brain_regions"]`` (imaging planes),
and ``metadata["FiberPhotometry"]["ontology"]["brain_regions"]`` (the ``FiberPhotometryTable``). To
annotate one value with **several** ontologies, map it to a list of terms:

.. code-block:: python

    metadata["Ecephys"]["ontology"]["brain_regions"]["CA1"] = [
        {"id": "MBA:382", "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382"},
        {"id": "UBERON:0003881", "uri": "http://purl.obolibrary.org/obo/UBERON_0003881"},
    ]

Species
-------

NWB stores a subject's species in :py:attr:`Subject.species <pynwb.file.Subject.species>` as a
binomial Latin name (e.g. ``"Mus musculus"``) or a taxonomy URL. NeuroConv recognizes a small,
curated, offline table of common neuroscience species
(:py:data:`~neuroconv.tools.ontology.SPECIES_TERMS`) — no network access, no extra dependencies,
high-precision (it only speaks up when confident; valid-but-uncommon binomials pass silently).

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

To resolve a value to its canonical term without emitting a warning, use
:py:func:`~neuroconv.tools.ontology.get_species_term`, which also succeeds on exact canonical
matches:

.. code-block:: python

    from neuroconv.tools.ontology import get_species_term

    term = get_species_term("rhesus macaque")
    term.canonical_name  # 'Macaca mulatta'
    term.ncbitaxon_id    # 'NCBITaxon:9544'
    term.entity_uri      # 'http://purl.obolibrary.org/obo/NCBITaxon_9544'

Inferring the species term into metadata
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:func:`~neuroconv.tools.ontology.infer_species_ontology_metadata` resolves
``metadata["Subject"]["species"]`` and writes the term under
``metadata["Subject"]["ontology"]["species"]``. It never overwrites a term you put there yourself.

.. code-block:: python

    from neuroconv.tools.ontology import infer_species_ontology_metadata

    metadata["Subject"] = dict(subject_id="m1", species="Mus musculus", sex="M", age="P30D")
    infer_species_ontology_metadata(metadata)
    metadata["Subject"]["ontology"]["species"]
    # {'id': 'NCBITaxon:10090', 'uri': 'http://purl.obolibrary.org/obo/NCBITaxon_10090'}

Writing the NCBITaxon reference into the file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:func:`~neuroconv.tools.ontology.add_species_external_resource` reads that term and attaches a
reference mapping ``Subject.species`` to its NCBITaxon entity. A conversion calls it for you; call
it directly to annotate an already-populated in-memory file:

.. code-block:: python

    from neuroconv.tools.ontology import add_species_external_resource

    added = add_species_external_resource(nwbfile, metadata=metadata)  # returns True
    nwbfile.external_resources  # now carries a Mus musculus -> NCBITaxon:10090 reference

The call is a no-op (returns ``False``) when there is no subject or ``metadata`` states no species
term, and it is idempotent: an existing ``external_resources`` HERD is extended in place rather than
replaced, and a species that is already annotated is not added twice.

Brain regions
-------------

How locations are resolved
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:func:`~neuroconv.tools.ontology.infer_brain_region_ontology_metadata` walks a populated file's
``location`` fields and resolves each distinct string against the curated atlas for the subject's
species — the Allen Mouse Brain Atlas for *Mus musculus*, the Allen Human Brain Atlas for
*Homo sapiens*, and a small species-agnostic UBERON vocabulary of common region names
(:py:data:`~neuroconv.tools.ontology.UBERON_TERMS`) for every other recognized species. A string
matches an exact atlas acronym (case-sensitive, e.g. ``"CA1"``, ``"VISp"``), a canonical structure
name (case-insensitive, e.g. ``"caudoputamen"``), or a common informal name or abbreviation (e.g.
``"hippocampus"``, ``"V1"``).

The lookup is species-specific because the same acronym denotes different structures across atlases
(e.g. ``"MB"`` is the mouse midbrain but the human mammillary body). Strings that do not resolve
(including the ``"unknown"`` placeholder) are simply left out of the map; a subject whose species is
not recognized yields nothing. The UBERON fallback is intentionally small and generic — lab-specific
channel labels (a custom EEG grid's own naming) you add to the map yourself.

.. code-block:: python

    from neuroconv.tools.ontology import infer_brain_region_ontology_metadata

    # nwbfile already populated: electrodes carry Allen acronyms as their ``location``
    infer_brain_region_ontology_metadata(nwbfile, metadata)
    metadata["Ecephys"]["ontology"]["brain_regions"]
    #   {"CA1": {"id": "MBA:382", "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382"},
    #    "VISp": {"id": "MBA:385", "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_385"}}

To resolve a single string yourself, use
:py:func:`~neuroconv.tools.ontology.get_brain_region_term`:

.. code-block:: python

    from neuroconv.tools.ontology import get_brain_region_term

    term = get_brain_region_term("caudoputamen")  # species defaults to "Mus musculus"
    term.acronym       # 'CP'
    term.curie         # 'MBA:672'
    term.entity_uri    # 'https://purl.brain-bican.org/ontology/mbao/MBA_672'

    get_brain_region_term("CA1", species="Homo sapiens").curie  # 'HBA:12892'
    get_brain_region_term("hippocampus", species="Rattus norvegicus").curie  # 'UBERON:0002421'

Curating the map by hand
~~~~~~~~~~~~~~~~~~~~~~~~~

The ``ontology.brain_regions`` map is ordinary metadata. Add an entry for a string the offline
lookup does not recognize (a lab-specific label, a subregion outside the curated table, a
non-standard spelling, a non-mouse species), or overwrite one it produced. Because each term is an
explicit ``id`` and ``uri``, the map generalizes to any ontology and any species:

.. code-block:: python

    metadata["Ecephys"]["ontology"] = {
        "brain_regions": {
            "my recording site": {
                "id": "MBA:382",
                "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382",
            },
        },
    }

Writing the references into the file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:func:`~neuroconv.tools.ontology.add_brain_region_external_resources` reads the
``ontology.brain_regions`` map of every modality block and, for each ``location`` value on the file
that the map covers, attaches the term(s) as HERD references. A conversion calls it for you:

.. code-block:: python

    from neuroconv.tools.ontology import add_brain_region_external_resources

    number_added = add_brain_region_external_resources(nwbfile, metadata=metadata)

Locations the map does not name are left untouched. The call is idempotent and extends an existing
``external_resources`` HERD in place.

Putting it together
-------------------

A conversion writes whatever the metadata's ``ontology`` blocks state. To have NeuroConv fill those
blocks in, run inference on the assembled file first, inspect the result, then convert:

.. code-block:: python

    from neuroconv.tools.ontology import (
        infer_species_ontology_metadata,
        infer_brain_region_ontology_metadata,
    )

    metadata["Subject"] = dict(subject_id="m1", species="Mus musculus", sex="M", age="P30D")

    # Assemble the file once so inference can see the electrode locations, ...
    staging_nwbfile = interface.create_nwbfile(metadata=metadata)
    infer_species_ontology_metadata(metadata)
    infer_brain_region_ontology_metadata(staging_nwbfile, metadata)
    # ... optionally edit metadata["Ecephys"]["ontology"]["brain_regions"] here, ...

    # ... then convert: create_nwbfile / run_conversion write the stated terms as HERD references.
    interface.run_conversion(nwbfile_path="out.nwb", metadata=metadata)

    # out.nwb now carries, under /general/external_resources:
    #   Mus musculus -> NCBITaxon:10090
    #   CA1          -> MBA:382
    #   VISp         -> MBA:385

To disable an annotation, simply do not populate its ``ontology`` block (or delete it from the
metadata before converting). To use a different atlas or an external ontology service, skip
``infer_*`` and write the ``id`` / ``uri`` terms into the ``ontology`` blocks yourself.

TermSet files
-------------

The recognized terms live in curated `LinkML <https://linkml.io/>`_ TermSet files shipped with
NeuroConv (one per vocabulary, the same format used by
`HDMF's TermSet <https://hdmf.readthedocs.io/en/stable/tutorials/plot_term_set.html>`_), so the
mappings are transparent and editable.
