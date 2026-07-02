"""Attach ontology entity references to NWB files via HDMF's HERD.

HERD (HDMF External Resources Data) lets an NWB file carry machine-readable links from its
metadata values to entities in external ontologies. NeuroConv uses it to annotate values it
can recognize -- currently ``Subject.species`` -> NCBITaxon -- so downstream tools (e.g. the
DANDI archive) can resolve the term without guessing.

The reference is stored in-file under ``/general/external_resources``, which requires
``pynwb >= 4.0.0`` (guaranteed by NeuroConv's dependency pin).
"""

from pynwb import NWBFile, get_type_map

from ._species import get_species_term

__all__ = ["add_species_external_resource"]


def _species_already_annotated(herd, subject) -> bool:
    """Whether ``herd`` already has a species entity for ``subject`` (keeps the call idempotent)."""
    try:
        existing = herd.get_object_entities(subject, attribute="species")
    except ValueError:
        # Raised when the subject is not yet registered in the object table.
        return False
    return not existing.empty


def add_species_external_resource(nwbfile: NWBFile) -> bool:
    """
    Annotate ``nwbfile.subject.species`` with its NCBITaxon entity via HERD.

    Adds an external-resource reference mapping the subject's species (a Latin binomial) to its
    NCBITaxon identifier, stored in-file under ``/general/external_resources``. This is a no-op
    (returns ``False``) when there is no subject or the species is not recognized.

    Parameters
    ----------
    nwbfile : NWBFile
        The file whose subject species should be annotated. Modified in place.

    Returns
    -------
    bool
        ``True`` if a reference was added, ``False`` otherwise.
    """
    subject = getattr(nwbfile, "subject", None)
    if subject is None:
        return False

    species = subject.species
    term = get_species_term(species)
    if term is None:
        return False

    from hdmf.common import HERD

    herd = nwbfile.external_resources
    is_new_herd = herd is None
    if is_new_herd:
        herd = HERD(type_map=get_type_map())
    elif _species_already_annotated(herd, subject):
        return False

    herd.add_ref(
        container=subject,
        attribute="species",
        key=species,
        entity_id=term.ncbitaxon_id,
        entity_uri=term.entity_uri,
    )

    # ``external_resources`` is write-once; only assign when we created the HERD, otherwise we
    # have extended the object already linked to the file in place.
    if is_new_herd:
        nwbfile.external_resources = herd
    return True
