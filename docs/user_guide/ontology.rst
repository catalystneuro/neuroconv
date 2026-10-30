Ontology Annotation
===================

NeuroConv can attach machine-readable **ontology references** to a written NWB file, so downstream
tools such as the `DANDI Archive <https://dandiarchive.org/>`_ can resolve exactly what a value
means instead of guessing from free text. References are stored **in-file** under
``/general/external_resources`` using HDMF's HERD (External Resources Data), so they travel with the
file. In-file HERD storage requires ``pynwb >= 4.0.0``, which is NeuroConv's minimum supported
version.

You state the terms in metadata and NeuroConv writes them. NeuroConv does not look terms up or guess
them from free text, so what lands in the file is exactly what the metadata says.

These values can be annotated:

- the subject's **species** (:py:attr:`Subject.species <pynwb.file.Subject.species>`), usually with
  an `NCBITaxon <https://bioregistry.io/registry/ncbitaxon>`_ term;
- the subject's **strain** (:py:attr:`Subject.strain <pynwb.file.Subject.strain>`), usually with an
  `RRID <https://bioregistry.io/registry/rrid>`_;
- **anatomical structures**, such as brain areas, other tissues, and body parts, usually with a term from the
  `Allen Mouse Brain Atlas <https://bioregistry.io/registry/mba>`_ (MBA), the
  `Allen Human Brain Atlas <https://bioregistry.io/registry/hba>`_ (HBA) or
  `UBERON <https://bioregistry.io/registry/uberon>`_;
- the names in the file's **experimenter** list
  (:py:attr:`NWBFile.experimenter <pynwb.file.NWBFile.experimenter>`), each with its
  `ORCID <https://bioregistry.io/registry/orcid>`_ iD.

Anatomical-structure annotation covers every free-text ``location`` field in the NWB core schema and the
extensions NeuroConv writes, and the node names of pose-estimation skeletons:

- the electrodes table ``location`` column and ``ElectrodeGroup.location`` (ecephys);
- ``ImagingPlane.location`` (ophys);
- ``IntracellularElectrode.location`` (icephys);
- ``OptogeneticStimulusSite.location`` (optogenetics);
- the ``FiberPhotometryTable`` ``location`` column (fiber photometry);
- ``ViralVectorInjection.location``, the targeted region of a virus injection (``ndx-ophys-devices``,
  used by both fiber photometry and ``ndx-optogenetics``);
- ``Skeleton.nodes``, the keypoints of an ``ndx-pose`` skeleton (pose estimation).

Where the terms live in metadata
--------------------------------

Each term is an explicit ``{"id": <CURIE>, "uri": <resolvable URI>}`` dict. All terms live in one
file-wide ``metadata["ExternalResources"]`` block, with one map per kind of value, each keyed by the exact
string written in the file. HERD links a term to an object through that string, so a key only
takes effect where the file carries the same value:

.. code-block:: python

    metadata["Subject"] = {"subject_id": "sub-01", "species": "Mus musculus"}

    metadata["ExternalResources"] = {
        "species": {
            "Mus musculus": {"id": "NCBITaxon:10090", "uri": "http://purl.obolibrary.org/obo/NCBITaxon_10090"},
        },
        "anatomical_structures": {
            "CA1": {"id": "MBA:382", "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382"},
        },
    }

Anatomical-structure terms are keyed by the free-text string, whether that string labels an electrode, an
imaging plane, a fiber-photometry site, or a skeleton node: the same string means the same structure
across modalities in a single file. To annotate one value with **several** ontologies, map it to a list
of terms:

.. code-block:: python

    metadata["ExternalResources"]["anatomical_structures"]["CA1"] = [
        {"id": "MBA:382", "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382"},
        {"id": "UBERON:0003881", "uri": "http://purl.obolibrary.org/obo/UBERON_0003881"},
    ]

The ``ExternalResources`` block is part of the metadata schema: only the ``species``, ``strain``,
``anatomical_structures`` and ``experimenter`` maps are accepted, and every term needs a non-empty
``id`` and ``uri``. A misspelled map name such as ``metadata["ExternalResources"]["anatomical_structure"]``
therefore fails metadata validation instead of silently annotating nothing.

Finding a term
~~~~~~~~~~~~~~

Look up the ``id`` and ``uri`` in the ontology itself, for example on the
`Ontology Lookup Service <https://www.ebi.ac.uk/ols4/>`_ (NCBITaxon, UBERON) or the
`Bioregistry <https://bioregistry.io/>`_, which also gives the URI pattern of each prefix (MBA, HBA).
Use the most specific term that is true for your data, and use the atlas that matches your subject's
species: the same acronym can name different structures in different atlases (``MB`` is the mouse
midbrain but the human mammillary body).

Strain
~~~~~~

Annotate ``Subject.strain`` with the RRID of the exact colony, which names the vendor: C57BL/6N from
Charles River (``RRID:IMSR_CRL:027``) and from Taconic (``RRID:IMSR_TAC:b6``) have different RRIDs.

.. code-block:: python

    metadata["Subject"]["strain"] = "C57BL/6J"

    metadata["ExternalResources"]["strain"] = {
        "C57BL/6J": {"id": "RRID:IMSR_JAX:000664", "uri": "https://scicrunch.org/resolver/RRID:IMSR_JAX:000664"},
    }

The RRID of a mouse strain from a repository such as JAX or MMRRC appears on the strain's page there, and
``https://scicrunch.org/resolver/<RRID>`` resolves any RRID.

Pose-estimation body parts
~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``anatomical_structures`` map also annotates the node names of every ``ndx-pose`` ``Skeleton`` on the
file, wherever the skeleton sits. Keypoint names are often lab conventions (``"EarL"``,
``"ShoulderLeft"``), so map each name you want annotated to the structure it marks, and leave out names
that have no matching term, such as keypoints on a lever or a headstage:

.. code-block:: python

    metadata["ExternalResources"]["anatomical_structures"] = {
        "Snout": {"id": "UBERON:0006333", "uri": "http://purl.obolibrary.org/obo/UBERON_0006333"},
        "ShoulderLeft": {"id": "UBERON:0001467", "uri": "http://purl.obolibrary.org/obo/UBERON_0001467"},
    }

Experimenters
~~~~~~~~~~~~~

Annotate each name in ``NWBFile.experimenter`` with that person's ORCID iD. Each name is annotated on its
own, so a name without an iD is left out:

.. code-block:: python

    metadata["NWBFile"]["experimenter"] = ["Carberry, Josiah", "Doe, Jane"]

    metadata["ExternalResources"]["experimenter"] = {
        "Carberry, Josiah": {"id": "orcid:0000-0002-1825-0097", "uri": "https://orcid.org/0000-0002-1825-0097"},
    }

The `ORCID search <https://orcid.org/orcid-search/search>`_ gives the iD of a person, and
``https://orcid.org/<iD>`` resolves it.

Writing the references
----------------------

``run_conversion`` calls :py:func:`~neuroconv.tools.external_resources.add_external_resources_to_nwbfile`
just before writing, in both write and append mode, for an interface or a converter. When the
``ExternalResources`` block is in the metadata you pass, a plain conversion is enough:

.. code-block:: python

    interface.run_conversion(nwbfile_path="out.nwb", metadata=metadata)

    # out.nwb now carries, under /general/external_resources:
    #   Mus musculus -> NCBITaxon:10090
    #   CA1          -> MBA:382

Annotation happens at write time, on the file as it is then, so anything added to the in-memory file
after it was created is annotated too. When you build the file with ``create_nwbfile`` and write it
yourself, call the function right before writing:

.. code-block:: python

    from neuroconv.tools.external_resources import add_external_resources_to_nwbfile
    from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile

    nwbfile = interface.create_nwbfile(metadata=metadata)
    add_external_resources_to_nwbfile(nwbfile, metadata=metadata)  # returns the number of references added
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path="out.nwb", backend="hdf5")

Values the metadata does not name are left untouched. The call is a no-op when the metadata has no
``ExternalResources`` block, and it is idempotent: an in-memory ``external_resources`` HERD is extended
in place, and references already in it are not added again. To skip annotation, leave the
``ExternalResources`` block out of the metadata; to leave out a single term, remove its entry.

Annotating an already-written file
-----------------------------------

:py:func:`~neuroconv.tools.external_resources.add_external_resources_to_nwbfile` only needs an
``NWBFile`` object and ``metadata``, not a conversion in progress, so it also works on a file that
already exists on disk, including one written without NeuroConv. Open it for read/write, annotate,
and write the changes back:

.. code-block:: python

    from pynwb import NWBHDF5IO
    from neuroconv.tools.external_resources import add_external_resources_to_nwbfile

    metadata = {
        "ExternalResources": {
            "species": {
                "Mus musculus": {"id": "NCBITaxon:10090", "uri": "http://purl.obolibrary.org/obo/NCBITaxon_10090"},
            },
        },
    }

    with NWBHDF5IO("published.nwb", mode="r+") as io:
        nwbfile = io.read()
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
``TermSetWrapper``; NeuroConv reads the plain value behind the wrapper, so the HERD key is still the
string written in the file. The configuration itself validates each value when it is set and raises
for values outside its term set (for example an atlas acronym such as ``"CA1"`` in a configured
``location`` field), before any NeuroConv code runs.
