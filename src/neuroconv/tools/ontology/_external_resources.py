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

from ._brain_regions import SUPPORTED_ATLAS_SPECIES, get_brain_region_term
from ._species import get_species_term

__all__ = [
    "OntologyAnnotationMixin",
    "add_brain_region_external_resources",
    "add_species_external_resource",
]


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


def _subject_atlas_species(nwbfile: NWBFile) -> str | None:
    """Canonical species name if the subject has a supported brain atlas (mouse/human), else ``None``."""
    subject = getattr(nwbfile, "subject", None)
    if subject is None:
        return None
    species_term = get_species_term(getattr(subject, "species", None))
    if species_term is None or species_term.canonical_name not in SUPPORTED_ATLAS_SPECIES:
        return None
    return species_term.canonical_name


def _brain_region_mapping_from_metadata(metadata: dict | None) -> dict:
    """Parse ``metadata["BrainRegions"]`` into ``{location string: [(entity_id, entity_uri), ...]}``.

    Each brain area maps to one or more ontology terms, each given as a ``dict`` with an ``id``
    (a CURIE such as ``"MBA:382"`` or ``"UBERON:0003881"``) and a resolvable ``uri``. A single
    ``dict`` or a list of them is accepted, so one area can be annotated with several ontologies
    (e.g. both MBA and UBERON). This representation is ontology-agnostic, so it applies to any
    species, not just mouse.
    """
    if not isinstance(metadata, dict):
        return {}
    raw_mapping = metadata.get("BrainRegions")
    if not isinstance(raw_mapping, dict):
        return {}

    mapping = {}
    for location, value in raw_mapping.items():
        terms = value if isinstance(value, list) else [value]
        entities = []
        for term in terms:
            if not isinstance(term, dict):
                raise TypeError(
                    f"Each metadata['BrainRegions'] term must be a dict with 'id' and 'uri' keys; "
                    f"got {type(term).__name__} for brain area {location!r}."
                )
            entity_id = term.get("id")
            entity_uri = term.get("uri")
            if not entity_id or not entity_uri:
                raise ValueError(
                    f"Each metadata['BrainRegions'] term for brain area {location!r} must define "
                    "both 'id' and 'uri'."
                )
            entities.append((str(entity_id), str(entity_uri)))
        mapping[location] = entities
    return mapping


def _brain_region_annotation_sites(nwbfile: NWBFile) -> list:
    """Collect ``(container, attribute, relative_path, location string)`` tuples to annotate.

    Covers the electrodes table ``location`` column (ecephys), each ``ElectrodeGroup.location``,
    and each ``ImagingPlane.location`` (ophys). Duplicate location strings within the electrodes
    column are collapsed to one reference per column.

    ``container`` is the object HERD records the reference against (the ``location`` column, a
    ``VectorData``, for the electrodes table; the group / plane itself otherwise). ``attribute``
    and ``relative_path`` are how that value is addressed for :meth:`HERD.add_ref` /
    :meth:`HERD.get_key` -- ``None`` / ``""`` for the standalone column, and ``"location"`` for the
    scalar attribute of a group or plane.
    """
    sites = []

    electrodes = nwbfile.electrodes
    if electrodes is not None and "location" in electrodes.colnames:
        location_column = electrodes["location"]
        for location in dict.fromkeys(location_column.data):  # unique, order-preserving
            sites.append((location_column, None, "", location))

    for electrode_group in nwbfile.electrode_groups.values():
        sites.append((electrode_group, "location", "location", electrode_group.location))

    for imaging_plane in nwbfile.imaging_planes.values():
        sites.append((imaging_plane, "location", "location", imaging_plane.location))

    return sites


def _existing_external_resource_refs(herd) -> set:
    """The ``(object_id, key, entity_id)`` references already present in ``herd`` (idempotency)."""
    if len(herd.entities[:]) == 0:
        return set()
    dataframe = herd.to_dataframe()
    return set(zip(dataframe["object_id"].tolist(), dataframe["key"].tolist(), dataframe["entity_id"].tolist()))


def _find_existing_key(herd, container, relative_path: str, key_string: str):
    """Return the ``Key`` already recorded for ``(container, relative_path, key_string)``, or ``None``."""
    try:
        key = herd.get_key(key_string, container=container, relative_path=relative_path)
    except ValueError:
        return None
    if isinstance(key, list):
        return key[0] if key else None
    return key


def add_brain_region_external_resources(nwbfile: NWBFile, metadata: dict | None = None) -> int:
    """
    Annotate anatomical ``location`` fields with brain-region ontology entities via HERD.

    Resolves each ``location`` string on the electrodes table, electrode groups, and imaging planes
    to one or more ontology terms and attaches machine-readable references (stored in-file under
    ``/general/external_resources``). Each location is resolved by:

    1. the ``metadata["BrainRegions"]`` mapping, if it provides an entry (this takes precedence and
       is ontology-agnostic, so it applies to any species and may map one area to several terms,
       e.g. both MBA and UBERON); then
    2. the offline Allen brain-atlas lookup for the subject's species -- the Allen Mouse Brain Atlas
       for *Mus musculus* and the Allen Human Brain Atlas for *Homo sapiens*.

    Locations resolving to neither are left untouched. This is a no-op (returns ``0``) when the
    subject's species has no supported atlas and no metadata mapping is provided.

    Parameters
    ----------
    nwbfile : NWBFile
        The file whose anatomical locations should be annotated. Modified in place.
    metadata : dict, optional
        Conversion metadata. ``metadata["BrainRegions"]`` maps a brain area (location string) to a
        term ``{"id": ..., "uri": ...}`` or a list of such terms.

    Returns
    -------
    int
        The number of external-resource references added.
    """
    custom_mapping = _brain_region_mapping_from_metadata(metadata)
    atlas_species = _subject_atlas_species(nwbfile)
    if not custom_mapping and atlas_species is None:
        return 0

    from hdmf.common import HERD

    herd = nwbfile.external_resources
    is_new_herd = herd is None
    if is_new_herd:
        herd = HERD(type_map=get_type_map())

    already_annotated = _existing_external_resource_refs(herd)
    number_added = 0
    for container, attribute, relative_path, location in _brain_region_annotation_sites(nwbfile):
        if not isinstance(location, str) or location.strip() == "":
            continue

        entities = custom_mapping.get(location)
        if entities is None and atlas_species is not None:
            term = get_brain_region_term(location, species=atlas_species)
            entities = [(term.curie, term.entity_uri)] if term is not None else None
        if not entities:
            continue

        # All terms for a given location share one HERD key; reuse the key object across the
        # location's entities so a single object<->key link carries every ontology reference.
        key = None
        for entity_id, entity_uri in entities:
            if (container.object_id, location, entity_id) in already_annotated:
                continue
            if key is None:
                key = _find_existing_key(herd, container, relative_path, location)
            if key is None:
                herd.add_ref(
                    container=container, attribute=attribute, key=location, entity_id=entity_id, entity_uri=entity_uri
                )
                key = herd.get_key(location, container=container, relative_path=relative_path)
            else:
                herd.add_ref(
                    container=container, attribute=attribute, key=key, entity_id=entity_id, entity_uri=entity_uri
                )
            already_annotated.add((container.object_id, location, entity_id))
            number_added += 1

    if number_added > 0 and is_new_herd:
        nwbfile.external_resources = herd
    return number_added


class OntologyAnnotationMixin:
    """Mixin adding overridable hooks that annotate a written file with ontology references (HERD).

    ``BaseDataInterface`` and ``NWBConverter`` inherit this. Each hook is called once the
    interface/converter data has been added to the file, and delegates to the corresponding
    ``neuroconv.tools.ontology`` function by default. Override a method in a subclass to customize
    or disable a particular annotation (e.g. use a different brain atlas, or turn off species
    annotation).
    """

    def add_species_external_resource(self, nwbfile: NWBFile, metadata: dict | None = None) -> bool:
        """
        Attach a species (NCBITaxon) reference for the subject to ``nwbfile`` (HERD).

        Override to customize. The default implementation delegates to
        :func:`neuroconv.tools.ontology.add_species_external_resource`.

        Parameters
        ----------
        nwbfile : NWBFile
            The populated file to annotate, modified in place.
        metadata : dict, optional
            Conversion metadata (unused by the default implementation; available to overrides).

        Returns
        -------
        bool
            Whether a reference was added.
        """
        return add_species_external_resource(nwbfile)

    def add_brain_region_external_resources(self, nwbfile: NWBFile, metadata: dict | None = None) -> int:
        """
        Attach brain-region ontology references to ``nwbfile`` (HERD). Override to customize.

        The default implementation delegates to
        :func:`neuroconv.tools.ontology.add_brain_region_external_resources`.

        Parameters
        ----------
        nwbfile : NWBFile
            The populated file to annotate, modified in place.
        metadata : dict, optional
            Conversion metadata (see the delegated function for the ``"BrainRegions"`` mapping).

        Returns
        -------
        int
            The number of external-resource references added.
        """
        return add_brain_region_external_resources(nwbfile, metadata=metadata)
