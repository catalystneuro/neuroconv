Species Ontology
================

NWB stores a subject's species in :py:attr:`Subject.species <pynwb.file.Subject.species>` as a
binomial Latin name (e.g. ``"Mus musculus"``) or a taxonomy URL. Consistent, standardized species
values make files interoperable and allow downstream tools such as the
`DANDI Archive <https://dandiarchive.org/>`_ to resolve the exact organism without guessing.

NeuroConv helps with this in two complementary ways, both applied automatically by
:py:func:`~neuroconv.tools.nwb_helpers.make_nwbfile_from_metadata` (and therefore by every
conversion that builds an NWB file through it):

1. A **non-blocking suggestion** when the species looks like a common name or a typo.
2. A **machine-readable NCBITaxon annotation** attached in-file when the species is recognized.

The lookup is a small, curated, offline table of common neuroscience species
(:py:data:`~neuroconv.tools.ontology.SPECIES_TERMS`). It requires no network access and no extra
dependencies, and it is intentionally high-precision: it only speaks up when it is confident there
is a better term. Valid-but-uncommon binomials pass through silently.

Suggesting a standardized term
------------------------------

When ``Subject.species`` is a recognized common name (e.g. ``"mouse"``) or a likely typo of a known
binomial (e.g. ``"Homo sapien"``), NeuroConv emits a ``UserWarning`` recommending the canonical
Latin binomial and its NCBITaxon identifier. This never raises and never blocks a conversion.

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
-----------------------------------------------

When the species resolves to a recognized term, NeuroConv attaches a machine-readable external
resource reference mapping ``Subject.species`` to its NCBITaxon entity. This is stored **in-file**
under ``/general/external_resources`` using HDMF's HERD (External Resources Data), so the link
travels with the file:

.. code-block:: python

    from neuroconv.tools.ontology import add_species_external_resource

    # nwbfile.subject.species == "Mus musculus"
    added = add_species_external_resource(nwbfile)  # returns True
    nwbfile.external_resources  # now carries a Mus musculus -> NCBITaxon:10090 reference

The call is a no-op (returns ``False``) when there is no subject or the species is not recognized,
and it is idempotent: an existing ``external_resources`` HERD is extended in place rather than
replaced, and a species that is already annotated is not added twice.

.. note::

    In-file HERD storage requires ``pynwb >= 4.0.0``, which is NeuroConv's minimum supported
    version.
