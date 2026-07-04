"""Attach ontology entity references to NWB files via HDMF's HERD.

HERD (HDMF External Resources Data) lets an NWB file carry machine-readable links from its
metadata values to entities in external ontologies. NeuroConv uses it to annotate values it
can recognize -- ``Subject.species`` -> NCBITaxon, and (for mice) anatomical ``location``
fields -> Allen Mouse Brain Atlas -- so downstream tools (e.g. the DANDI archive) can resolve
the term without guessing.

The reference is stored in-file under ``/general/external_resources``, which requires
``pynwb >= 4.0.0`` (guaranteed by NeuroConv's dependency pin).
"""

from pynwb import NWBFile, get_type_map

from ._brain_regions import brain_region_term_from_identifier, get_brain_region_term
from ._species import get_species_term

__all__ = ["add_brain_region_external_resources", "add_species_external_resource"]


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


def _subject_is_mouse(nwbfile: NWBFile) -> bool:
    """Whether the file's subject resolves to ``Mus musculus`` (via the species ontology)."""
    subject = getattr(nwbfile, "subject", None)
    if subject is None:
        return False
    species_term = get_species_term(subject.species)
    return species_term is not None and species_term.canonical_name == "Mus musculus"


def _brain_region_mapping_from_metadata(metadata: dict | None) -> dict:
    """Parse ``metadata["BrainRegions"]`` into a ``{location string: BrainRegionTerm}`` mapping.

    The metadata value maps a location string to an Allen Mouse Brain Atlas identifier, given
    either as a bare id / CURIE / URI string (``"MBA:382"``) or as a dict with an ``mba_id``
    (or ``id`` / ``curie``) key and optional ``acronym`` / ``name``.
    """
    if not isinstance(metadata, dict):
        return {}
    raw_mapping = metadata.get("BrainRegions")
    if not isinstance(raw_mapping, dict):
        return {}

    mapping = {}
    for location, value in raw_mapping.items():
        if isinstance(value, dict):
            identifier = value.get("mba_id", value.get("id", value.get("curie")))
            if identifier is None:
                continue
            term = brain_region_term_from_identifier(
                identifier, acronym=value.get("acronym", ""), name=value.get("name", "")
            )
        else:
            term = brain_region_term_from_identifier(value)
        mapping[location] = term
    return mapping


def _brain_region_annotation_sites(nwbfile: NWBFile) -> list:
    """Collect ``(container, attribute, reference_object, location string)`` tuples to annotate.

    Covers the electrodes table ``location`` column (ecephys), each ``ElectrodeGroup.location``,
    and each ``ImagingPlane.location`` (ophys). Duplicate location strings within the electrodes
    column are collapsed to one reference per column.

    ``reference_object`` is the object whose ``object_id`` HERD records for the reference: the
    ``location`` column (a ``VectorData``) for the electrodes table, and the container itself for
    the scalar ``location`` attribute of an electrode group or imaging plane. It is used to detect
    references that already exist (idempotency).
    """
    sites = []

    electrodes = nwbfile.electrodes
    if electrodes is not None and "location" in electrodes.colnames:
        location_column = electrodes["location"]
        for location in dict.fromkeys(location_column.data):  # unique, order-preserving
            sites.append((electrodes, "location", location_column, location))

    for electrode_group in nwbfile.electrode_groups.values():
        sites.append((electrode_group, "location", electrode_group, electrode_group.location))

    for imaging_plane in nwbfile.imaging_planes.values():
        sites.append((imaging_plane, "location", imaging_plane, imaging_plane.location))

    return sites


def _existing_object_key_pairs(herd) -> set:
    """The ``(object_id, key)`` pairs already present in ``herd`` (for idempotency)."""
    if len(herd.entities[:]) == 0:
        return set()
    dataframe = herd.to_dataframe()
    return set(zip(dataframe["object_id"].tolist(), dataframe["key"].tolist()))


def add_brain_region_external_resources(nwbfile: NWBFile, metadata: dict | None = None) -> int:
    """
    Annotate anatomical ``location`` fields with Allen Mouse Brain Atlas entities via HERD.

    For a mouse subject, resolves each ``location`` string on the electrodes table, electrode
    groups, and imaging planes to an Allen Mouse Brain Atlas (MBA) term and attaches a
    machine-readable reference (stored in-file under ``/general/external_resources``). Each
    location is resolved first against the ``metadata["BrainRegions"]`` mapping (if provided) and
    then against the offline lookup of common structures, so unrecognized regions can be annotated
    by defining the mapping in metadata.

    This is a no-op (returns ``0``) when the subject is not a mouse or no location is recognized.

    Parameters
    ----------
    nwbfile : NWBFile
        The file whose anatomical locations should be annotated. Modified in place.
    metadata : dict, optional
        Conversion metadata. ``metadata["BrainRegions"]`` may map a location string to an MBA
        identifier (a CURIE / bare id / URI, or a dict with an ``mba_id`` key and optional
        ``acronym`` / ``name``). This mapping takes precedence over the offline lookup.

    Returns
    -------
    int
        The number of external-resource references added.
    """
    if not _subject_is_mouse(nwbfile):
        return 0

    custom_mapping = _brain_region_mapping_from_metadata(metadata)
    sites = _brain_region_annotation_sites(nwbfile)

    from hdmf.common import HERD

    herd = nwbfile.external_resources
    is_new_herd = herd is None
    if is_new_herd:
        herd = HERD(type_map=get_type_map())

    already_annotated = _existing_object_key_pairs(herd)
    number_added = 0
    for container, attribute, reference_object, location in sites:
        if not isinstance(location, str) or location.strip() == "":
            continue
        term = custom_mapping.get(location) or get_brain_region_term(location)
        if term is None:
            continue

        object_key_pair = (reference_object.object_id, location)
        if object_key_pair in already_annotated:
            continue

        herd.add_ref(
            container=container,
            attribute=attribute,
            key=location,
            entity_id=term.curie,
            entity_uri=term.entity_uri,
        )
        already_annotated.add(object_key_pair)
        number_added += 1

    if number_added > 0 and is_new_herd:
        nwbfile.external_resources = herd
    return number_added
