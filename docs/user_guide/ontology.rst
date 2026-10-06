Ontology Annotation
===================

NeuroConv can attach machine-readable **ontology references** to a written NWB file, so downstream
tools such as the `DANDI Archive <https://dandiarchive.org/>`_ can resolve exactly what a value
means instead of guessing from free text. References are stored **in-file** under
``/general/external_resources`` using HDMF's HERD (External Resources Data), so they travel with the
file. In-file HERD storage requires ``pynwb >= 4.0.0``, which is NeuroConv's minimum supported
version.

Three kinds of value are annotated:

- the subject's **species**, mapped to `NCBITaxon <https://bioregistry.io/registry/ncbitaxon>`_;
- the subject's **strain**, mapped to `RRID <https://bioregistry.io/registry/rrid>`_ (Research
  Resource Identifiers) for common laboratory rodent strains;
- anatomical **brain regions** (``location`` fields), mapped to the
  `Allen Mouse Brain Atlas <https://bioregistry.io/registry/mba>`_ (MBA) for mouse subjects, the
  `Allen Human Brain Atlas <https://bioregistry.io/registry/hba>`_ (HBA) for human subjects, a
  species-agnostic `UBERON <https://bioregistry.io/registry/uberon>`_ vocabulary of common region
  names for every other recognized species (e.g. rat, which has no dedicated Allen atlas), or to
  any ontology you specify in metadata.

Brain-region annotation covers every free-text ``location`` field in the NWB core schema and the
extensions NeuroConv writes:

- the electrodes table ``location`` column and ``ElectrodeGroup.location`` (ecephys);
- ``ImagingPlane.location`` (ophys);
- ``IntracellularElectrode.location`` (icephys);
- ``OptogeneticStimulusSite.location`` (optogenetics);
- the ``FiberPhotometryTable`` ``location`` column (fiber photometry);
- ``ViralVectorInjection.location``, the targeted region of a virus injection (``ndx-ophys-devices``,
  used by both fiber photometry and ``ndx-optogenetics``).

Two steps: infer, then annotate
-------------------------------

Ontology support is deliberately split into two independent halves, both in
:py:mod:`neuroconv.tools.external_resources`:

1. **Inference** — :py:func:`~neuroconv.tools.external_resources.infer_species_external_resources`,
   :py:func:`~neuroconv.tools.external_resources.infer_strain_external_resources` and
   :py:func:`~neuroconv.tools.external_resources.infer_brain_region_external_resources` read a populated
   ``NWBFile``, resolve the free-text values a lab wrote (``"mouse"``, ``"black 6"``, ``"CA1"``) to ontology terms
   and return them as a ``{"ExternalResources": {...}}`` metadata block, **keyed by the value each term
   describes**. They do not modify anything. This step guesses; run it when you want NeuroConv to
   propose terms, then inspect the result and merge it into your metadata.
2. **Annotation** — :py:func:`~neuroconv.tools.external_resources.add_external_resources_to_nwbfile` takes the
   terms already stated in ``metadata`` and writes them into the file as HERD references, running
   the per-domain :py:func:`~neuroconv.tools.external_resources.add_species_external_resource`,
   :py:func:`~neuroconv.tools.external_resources.add_strain_external_resource` and
   :py:func:`~neuroconv.tools.external_resources.add_brain_region_external_resources`. This step is
   deterministic — nothing is inferred, so what lands in the file is exactly what the metadata
   says — and **run_conversion runs it automatically, just before writing**. It is a no-op unless
   the metadata carries an ``ExternalResources`` block.

Because the two are separate, the annotation you write does not have to come from NeuroConv's
inference: you can bring terms from an ontology service or a file you curate once per dataset and
still have a conversion write them, and you always have a record of which terms you gave.

Where the terms live in metadata
--------------------------------

Each term is an explicit ``{"id": <CURIE>, "uri": <resolvable URI>}`` dict. All terms live in one
file-wide ``metadata["ExternalResources"]`` block, with one map per kind of value, each keyed by the exact
string written in the file. HERD links a term to an object through that string, so a key only
takes effect where the file carries the same value:

.. code-block:: python

    metadata["Subject"] = {"subject_id": "sub-01", "species": "Mus musculus", "strain": "C57BL/6J"}

    metadata["ExternalResources"] = {
        "species": {
            "Mus musculus": {"id": "NCBITaxon:10090", "uri": "http://purl.obolibrary.org/obo/NCBITaxon_10090"},
        },
        "strain": {
            "C57BL/6J": {"id": "RRID:IMSR_JAX:000664", "uri": "https://scicrunch.org/resolver/RRID:IMSR_JAX:000664"},
        },
        "brain_regions": {
            "CA1": {"id": "MBA:382", "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382"},
        },
    }

Brain-region terms are keyed by the free-text ``location`` string, regardless of whether that string
labels an electrode, an imaging plane, or a fiber-photometry site -- the same string means the same
place across modalities in a single file. To annotate one value with **several** ontologies, map it
to a list of terms:

.. code-block:: python

    metadata["ExternalResources"]["brain_regions"]["CA1"] = [
        {"id": "MBA:382", "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382"},
        {"id": "UBERON:0003881", "uri": "http://purl.obolibrary.org/obo/UBERON_0003881"},
    ]

The ``ExternalResources`` block is part of the metadata schema: only the ``species`` and ``brain_regions`` maps
are accepted, and every term needs a non-empty ``id`` and ``uri``. A misspelled map name such as
``metadata["ExternalResources"]["brain_region"]`` therefore fails metadata validation instead of silently
annotating nothing.

Species
-------

NWB stores a subject's species in :py:attr:`Subject.species <pynwb.file.Subject.species>` as a
binomial Latin name (e.g. ``"Mus musculus"``) or a taxonomy URL. NeuroConv recognizes a small,
curated, offline table of common neuroscience species
(:py:data:`~neuroconv.tools.external_resources.SPECIES_TERMS`) — no network access, no extra dependencies,
high-precision (it only speaks up when confident; valid-but-uncommon binomials pass silently).

Suggesting a standardized term
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When ``Subject.species`` is a recognized common name (e.g. ``"mouse"``) or a likely typo of a known
binomial (e.g. ``"Homo sapien"``), NeuroConv emits a ``UserWarning`` recommending the canonical
Latin binomial and its NCBITaxon identifier while the metadata is processed in
:py:func:`~neuroconv.tools.nwb_helpers.make_nwbfile_from_metadata`. This never raises and never
blocks a conversion.

.. code-block:: python

    from neuroconv.tools.external_resources import validate_species

    validate_species("mouse")
    # UserWarning: Subject species 'mouse' is a common name. Consider using the Latin binomial
    # 'Mus musculus' (NCBITaxon:10090) for interoperability. See https://bioregistry.io/NCBITaxon:10090

To resolve a value to its canonical term without emitting a warning, use
:py:func:`~neuroconv.tools.external_resources.get_species_term`, which also succeeds on exact canonical
matches:

.. code-block:: python

    from neuroconv.tools.external_resources import get_species_term

    term = get_species_term("rhesus macaque")
    term.canonical_name  # 'Macaca mulatta'
    term.ncbitaxon_id    # 'NCBITaxon:9544'
    term.entity_uri      # 'http://purl.obolibrary.org/obo/NCBITaxon_9544'

Inferring the species term
~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:func:`~neuroconv.tools.external_resources.infer_species_external_resources` resolves ``nwbfile.subject.species``
and returns the term under ``{"ExternalResources": {"species": ...}}``, keyed by the species value exactly as
written (a ``"mouse"`` subject gets a ``"mouse"`` key). It returns ``{}`` when the file has no
subject or the species is not recognized.

.. code-block:: python

    from neuroconv.tools.external_resources import infer_species_external_resources

    infer_species_external_resources(nwbfile)
    # {'ExternalResources': {'species': {'Mus musculus': {
    #     'id': 'NCBITaxon:10090', 'uri': 'http://purl.obolibrary.org/obo/NCBITaxon_10090'}}}}

Writing the NCBITaxon reference into the file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:func:`~neuroconv.tools.external_resources.add_species_external_resource` looks up the subject's species
value in that map and attaches a reference mapping ``Subject.species`` to its NCBITaxon entity.
:py:func:`~neuroconv.tools.external_resources.add_external_resources_to_nwbfile` calls it for you; call it directly
to annotate species only:

.. code-block:: python

    from neuroconv.tools.external_resources import add_species_external_resource

    added = add_species_external_resource(nwbfile, metadata=metadata)  # returns True
    nwbfile.external_resources  # now carries a Mus musculus -> NCBITaxon:10090 reference

The call is a no-op (returns ``False``) when there is no subject or ``metadata`` states no term for
the subject's species value, and it is idempotent: an in-memory ``external_resources`` HERD is
extended in place rather than replaced, and a species that is already annotated is not added twice.

Strain
------

NWB stores a subject's laboratory strain in :py:attr:`Subject.strain <pynwb.file.Subject.strain>`
as free text (e.g. ``"C57BL/6J"``, ``"Long-Evans"``). NeuroConv standardizes it the same way it
standardizes species, backed by a small, curated, offline table of common laboratory rodent strains
(:py:data:`~neuroconv.tools.external_resources.STRAIN_TERMS`).

Suggesting a standardized term
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When ``Subject.strain`` is a recognized informal spelling (e.g. ``"black 6"``) or a likely typo of a
known designation, NeuroConv emits a ``UserWarning`` the same way it does for species, while the
metadata is processed in :py:func:`~neuroconv.tools.nwb_helpers.make_nwbfile_from_metadata`:

.. code-block:: python

    from neuroconv.tools.external_resources import validate_strain

    validate_strain("black 6")
    # UserWarning: Subject strain 'black 6' is an informal spelling. Consider using 'C57BL/6J'
    # (RRID:IMSR_JAX:000664) for interoperability. See https://bioregistry.io/RRID:IMSR_JAX:000664

:py:func:`~neuroconv.tools.external_resources.get_strain_term` resolves a value to its canonical term
(including exact canonical matches) without emitting a warning:

.. code-block:: python

    from neuroconv.tools.external_resources import get_strain_term

    term = get_strain_term("long evans")
    term.canonical_name  # 'Long-Evans'
    term.rrid             # 'RRID:RGD_2308852'

Inferring the strain term
~~~~~~~~~~~~~~~~~~~~~~~~~

:py:func:`~neuroconv.tools.external_resources.infer_strain_external_resources` resolves ``nwbfile.subject.strain``
and returns the term under ``{"ExternalResources": {"strain": ...}}``, keyed by the strain value
exactly as written, the same way species inference does. Only a small curated set of common lab
lines is included in :py:data:`~neuroconv.tools.external_resources.STRAIN_TERMS`; for a strain
outside that table (an in-house line, a less common vendor strain), or to override a curated result,
add its term to ``metadata["ExternalResources"]["strain"]`` yourself. It wins over the inferred one
in the merge:

.. code-block:: python

    from neuroconv.tools.external_resources import infer_strain_external_resources

    infer_strain_external_resources(nwbfile)  # nwbfile.subject.strain == "black 6"
    # {'ExternalResources': {'strain': {'black 6': {
    #     'id': 'RRID:IMSR_JAX:000664', 'uri': 'https://scicrunch.org/resolver/RRID:IMSR_JAX:000664'}}}}

    # An in-house line the curated table does not recognize:
    metadata["ExternalResources"] = {
        "strain": {
            "my in-house line": {"id": "RRID:IMSR_JAX:000664", "uri": "https://scicrunch.org/resolver/RRID:IMSR_JAX:000664"},
        },
    }

Writing the RRID reference into the file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:func:`~neuroconv.tools.external_resources.add_strain_external_resource` looks up the subject's strain
value in that map and attaches a reference mapping ``Subject.strain`` to its RRID entity, the same
way species annotation does.
:py:func:`~neuroconv.tools.external_resources.add_external_resources_to_nwbfile` calls it for you; call it directly
to annotate strain only:

.. code-block:: python

    from neuroconv.tools.external_resources import add_strain_external_resource

    added = add_strain_external_resource(nwbfile, metadata=metadata)  # returns True
    nwbfile.external_resources  # now carries a C57BL/6J -> RRID:IMSR_JAX:000664 reference

The call is a no-op (returns ``False``) when there is no subject, the subject has no strain set, or
``metadata`` states no term for the subject's strain value, and it is idempotent in the same way
species annotation is.

Brain regions
-------------

How locations are resolved
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:func:`~neuroconv.tools.external_resources.infer_brain_region_external_resources` walks a populated file's
``location`` fields and resolves each distinct string against the curated atlas for the subject's
species — the Allen Mouse Brain Atlas for *Mus musculus*, the Allen Human Brain Atlas for
*Homo sapiens*, and a small species-agnostic UBERON vocabulary of common region names
(:py:data:`~neuroconv.tools.external_resources.UBERON_TERMS`) for every other recognized species. A string
matches an exact atlas acronym (case-sensitive, e.g. ``"CA1"``, ``"VISp"``), a canonical structure
name (case-insensitive, e.g. ``"caudoputamen"``), or a common informal name or abbreviation (e.g.
``"hippocampus"``, ``"V1"``).

The lookup is species-specific because the same acronym denotes different structures across atlases
(e.g. ``"MB"`` is the mouse midbrain but the human mammillary body). Strings that do not resolve
(including the ``"unknown"`` placeholder) are simply left out of the map; a subject whose species is
not recognized yields nothing. The UBERON fallback is intentionally small and generic — lab-specific
channel labels (a custom EEG grid's own naming) you add to the map yourself.

.. code-block:: python

    from neuroconv.tools.external_resources import infer_brain_region_external_resources

    # nwbfile already populated: electrodes carry Allen acronyms as their ``location``
    infer_brain_region_external_resources(nwbfile)["ExternalResources"]["brain_regions"]
    #   {"CA1": {"id": "MBA:382", "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382"},
    #    "VISp": {"id": "MBA:385", "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_385"}}

The atlas is chosen from ``nwbfile.subject.species``, so a file without a subject yields ``{}``.

To resolve a single string yourself, use
:py:func:`~neuroconv.tools.external_resources.get_brain_region_term`:

.. code-block:: python

    from neuroconv.tools.external_resources import get_brain_region_term

    term = get_brain_region_term("caudoputamen")  # species defaults to "Mus musculus"
    term.acronym       # 'CP'
    term.curie         # 'MBA:672'
    term.entity_uri    # 'https://purl.brain-bican.org/ontology/mbao/MBA_672'

    get_brain_region_term("CA1", species="Homo sapiens").curie  # 'HBA:12892'
    get_brain_region_term("hippocampus", species="Rattus norvegicus").curie  # 'UBERON:0002421'

Curating the map by hand
~~~~~~~~~~~~~~~~~~~~~~~~~

The ``ExternalResources.brain_regions`` map is ordinary metadata. Add an entry for a string the offline
lookup does not recognize (a lab-specific label, a subregion outside the curated table, a
non-standard spelling, a non-mouse species), or replace one it would produce. Because each term is
an explicit ``id`` and ``uri``, the map generalizes to any ontology and any species:

.. code-block:: python

    metadata["ExternalResources"] = {
        "brain_regions": {
            "my recording site": {
                "id": "MBA:382",
                "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382",
            },
        },
    }

Writing the references into the file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:func:`~neuroconv.tools.external_resources.add_brain_region_external_resources` reads the
``metadata["ExternalResources"]["brain_regions"]`` map and, for each ``location`` value on the file that the
map covers -- whichever modality it belongs to -- attaches the term(s) as HERD references.
:py:func:`~neuroconv.tools.external_resources.add_external_resources_to_nwbfile` calls it for you; call it directly
to annotate brain regions only:

.. code-block:: python

    from neuroconv.tools.external_resources import add_brain_region_external_resources

    number_added = add_brain_region_external_resources(nwbfile, metadata=metadata)

Locations the map does not name are left untouched. The call is idempotent and extends an
in-memory ``external_resources`` HERD in place.

Putting it together
-------------------

Annotation happens at write time, on the file as it is then, so anything added to the in-memory
file after it was created is annotated too. To have NeuroConv propose the terms, build the file once,
run inference on it, merge the result under your metadata, annotate, and write:

.. code-block:: python

    from neuroconv.tools.external_resources import (
        add_external_resources_to_nwbfile,
        infer_brain_region_external_resources,
        infer_species_external_resources,
        infer_strain_external_resources,
    )
    from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile
    from neuroconv.utils import dict_deep_update

    metadata["Subject"] = dict(subject_id="m1", species="Mus musculus", strain="C57BL/6J", sex="M", age="P30D")

    nwbfile = interface.create_nwbfile(metadata=metadata)
    inferred = {}
    for infer in (
        infer_species_external_resources,
        infer_strain_external_resources,
        infer_brain_region_external_resources,
    ):
        inferred = dict_deep_update(inferred, infer(nwbfile))
    # Merge under your metadata, so any term you wrote yourself wins.
    metadata = dict_deep_update(inferred, metadata, append_list=False)
    # ... optionally inspect or edit metadata["ExternalResources"] here ...

    add_external_resources_to_nwbfile(nwbfile, metadata=metadata)
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path="out.nwb", backend="hdf5")

    # out.nwb now carries, under /general/external_resources:
    #   Mus musculus -> NCBITaxon:10090
    #   C57BL/6J     -> RRID:IMSR_JAX:000664
    #   CA1          -> MBA:382
    #   VISp         -> MBA:385

Pass ``append_list=False`` to the merge: by default ``dict_deep_update`` merges lists item by
item, so a value you mapped to several terms would not stay as you wrote it.

``run_conversion`` calls :py:func:`~neuroconv.tools.external_resources.add_external_resources_to_nwbfile` on its
own just before writing, in both write and append mode, for an interface or a converter. So when the
``ExternalResources`` block is already in the metadata you pass, a plain conversion is enough:

.. code-block:: python

    interface.run_conversion(nwbfile_path="out.nwb", metadata=metadata)

To skip it, pass ``add_external_resources=False`` to ``run_conversion``. To leave out a single term,
remove its entry from ``metadata["ExternalResources"]``. To use a different atlas or an external ontology
service, skip ``infer_*`` and write the ``id`` / ``uri`` terms into ``metadata["ExternalResources"]`` yourself.

Annotating an already-written file
-----------------------------------

The annotation functions only need an ``NWBFile`` object and ``metadata``, not a conversion in
progress, so they also work on a file that already exists on disk, including one with no NeuroConv
involvement in how it was originally written. Open it for read/write, run inference (or supply the
``ExternalResources`` metadata yourself) and the annotation functions, then write the changes back:

.. code-block:: python

    from pynwb import NWBHDF5IO
    from neuroconv.tools.external_resources import (
        add_external_resources_to_nwbfile,
        infer_brain_region_external_resources,
        infer_species_external_resources,
    )
    from neuroconv.utils import dict_deep_update

    with NWBHDF5IO("published.nwb", mode="r+") as io:
        nwbfile = io.read()
        metadata = dict_deep_update(
            infer_species_external_resources(nwbfile),
            infer_brain_region_external_resources(nwbfile),
        )
        add_external_resources_to_nwbfile(nwbfile, metadata=metadata)
        io.write(nwbfile)

``run_conversion(..., append_on_disk_nwbfile=True)`` does the same for the file it appends to.

A file that already stores HERD references on disk cannot take new ones: those tables are read back
as fixed-size datasets. Re-running the annotation on such a file adds nothing and does not fail; if the
metadata names a reference the file does not have yet, NeuroConv emits a ``UserWarning`` and leaves
the stored references as they are. Annotate the file when it is first written instead.

Working with an HDMF type configuration
---------------------------------------

NeuroConv never loads a type configuration itself, but it works when you load one, for example
neuro-termsets' ``default_config.yaml`` through ``pynwb.load_type_config``. With a configuration
loaded, HDMF wraps configured fields such as ``Subject.species`` and ``ElectrodeGroup.location`` in a
``TermSetWrapper``; the annotation functions read the plain value behind the wrapper, so the HERD
key is still the string written in the file. Note that the configuration itself validates each
value when it is set and raises for values outside its term set (for example an atlas acronym such
as ``"CA1"`` in a configured ``location`` field), before any NeuroConv code runs.

TermSet files
-------------

The recognized terms live in curated `LinkML <https://linkml.io/>`_ TermSet files shipped with
NeuroConv (one per vocabulary, the same format used by
`HDMF's TermSet <https://hdmf.readthedocs.io/en/stable/tutorials/plot_term_set.html>`_), so the
mappings are transparent and editable.

The informal names NeuroConv accepts (``"hippocampus"``, ``"V1"``, ``"mouse"``, ``"black 6"``) are stored in the
same files as LinkML ``aliases`` on the term they resolve to, so adding one is a YAML edit and needs
no code change:

.. code-block:: yaml

    HIP:
      description: Hippocampal region
      meaning: MBA:1080
      aliases:
        - hippocampus

An alias is matched case-insensitively. An alias may not be shared by two terms of the same file;
NeuroConv raises an error when it loads a term set that does.
