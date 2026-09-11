"""Attach ontology entity references to NWB files via HDMF's HERD.

HERD (HDMF External Resources Data) lets an NWB file carry machine-readable links from its
metadata values to entities in external ontologies. The functions here are the **deterministic**
half of NeuroConv's ontology support: they take terms that are already stated in ``metadata`` and
write the corresponding references into the file. Nothing is guessed -- resolving a free-text
value (a common species name, an atlas acronym) to a term is the job of the ``infer_*`` functions
in this package, which populate the same ``metadata`` blocks these functions read.

The terms sit next to the value they annotate:

- ``metadata["Subject"]["ontology"]["species"]`` -> ``{"id": ..., "uri": ...}`` for ``Subject.species``;
- ``metadata["Subject"]["ontology"]["strain"]`` -> ``{"id": ..., "uri": ...}`` for ``Subject.strain``;
- ``metadata["<modality>"]["ontology"]["brain_regions"]`` -> ``{location string: term-or-list}`` for
  the anatomical ``location`` fields of that modality (``Ecephys`` covers the electrodes table and
  electrode groups, ``Ophys`` the imaging planes, ``FiberPhotometry`` the ``FiberPhotometryTable``).

Each term is an explicit ``{"id": <CURIE>, "uri": <resolvable URI>}`` dict; a list of them annotates
one value with several ontologies (e.g. both MBA and UBERON). This representation is
ontology-agnostic, so it applies to any species.

The reference is stored in-file under ``/general/external_resources``, which requires
``pynwb >= 4.0.0`` (guaranteed by NeuroConv's dependency pin).
"""

from pynwb import NWBFile, get_type_map

__all__ = [
    "add_brain_region_external_resources",
    "add_species_external_resource",
    "add_strain_external_resource",
]

#: Metadata blocks whose ``ontology.brain_regions`` map is consulted for anatomical locations.
_BRAIN_REGION_METADATA_BLOCKS = ("Ecephys", "Ophys", "FiberPhotometry")


def _attribute_already_annotated(herd, container, attribute: str) -> bool:
    """Whether ``herd`` already has an entity for ``container.attribute`` (keeps a call idempotent)."""
    try:
        existing = herd.get_object_entities(container, attribute=attribute)
    except ValueError:
        # Raised when the container is not yet registered in the object table.
        return False
    return not existing.empty


def _ontology_term_entities(value, *, context: str) -> list:
    """Normalize an ``ontology`` metadata term (a dict, or a list of dicts) to ``[(id, uri), ...]``.

    ``context`` names the annotated value in error messages (e.g. ``"Subject species"`` or a brain
    area string).
    """
    terms = value if isinstance(value, list) else [value]
    entities = []
    for term in terms:
        if not isinstance(term, dict):
            raise TypeError(
                f"Each ontology term for {context} must be a dict with 'id' and 'uri' keys; "
                f"got {type(term).__name__}."
            )
        entity_id = term.get("id")
        entity_uri = term.get("uri")
        if not entity_id or not entity_uri:
            raise ValueError(f"The ontology term for {context} must define both 'id' and 'uri'.")
        entities.append((str(entity_id), str(entity_uri)))
    return entities


def _add_subject_attribute_external_resource(nwbfile: NWBFile, metadata: dict | None, *, attribute: str) -> bool:
    """Shared write path for ``add_species_external_resource`` / ``add_strain_external_resource``.

    Reads ``metadata["Subject"]["ontology"][attribute]`` and, when present, adds an
    external-resource reference mapping ``getattr(subject, attribute)`` to it. No-op (``False``)
    when there is no subject, the subject has no value for ``attribute``, or the metadata states no
    term for it. Idempotent: an existing ``external_resources`` HERD is extended in place, and a
    value already annotated for this attribute is not added twice.
    """
    subject = getattr(nwbfile, "subject", None)
    if subject is None:
        return False

    value = getattr(subject, attribute, None)
    if not isinstance(value, str) or value.strip() == "":
        return False

    subject_metadata = (metadata or {}).get("Subject")
    if not isinstance(subject_metadata, dict):
        return False
    term = subject_metadata.get("ontology", {}).get(attribute)
    if term is None:
        return False
    entities = _ontology_term_entities(term, context=f"Subject {attribute}")

    from hdmf.common import HERD

    herd = nwbfile.external_resources
    is_new_herd = herd is None
    if is_new_herd:
        herd = HERD(type_map=get_type_map())
    elif _attribute_already_annotated(herd, subject, attribute=attribute):
        return False

    for entity_id, entity_uri in entities:
        herd.add_ref(
            container=subject,
            attribute=attribute,
            key=value,
            entity_id=entity_id,
            entity_uri=entity_uri,
        )

    # ``external_resources`` is write-once; only assign when we created the HERD, otherwise we
    # have extended the object already linked to the file in place.
    if is_new_herd:
        nwbfile.external_resources = herd
    return True


def add_species_external_resource(nwbfile: NWBFile, metadata: dict | None = None) -> bool:
    """
    Annotate ``nwbfile.subject.species`` with the NCBITaxon term stated in ``metadata`` via HERD.

    Reads ``metadata["Subject"]["ontology"]["species"]`` -- an explicit ``{"id": ..., "uri": ...}``
    term -- and adds an external-resource reference mapping the subject's species value to it,
    stored in-file under ``/general/external_resources``. Nothing is inferred: use
    :func:`neuroconv.tools.ontology.infer_species_ontology_metadata` to populate that term from a
    common name or Latin binomial.

    This is a no-op (returns ``False``) when there is no subject or ``metadata`` states no species
    term. It is idempotent: an existing ``external_resources`` HERD is extended in place rather than
    replaced, and a species already annotated is not added twice.

    Parameters
    ----------
    nwbfile : NWBFile
        The file whose subject species should be annotated. Modified in place.
    metadata : dict, optional
        Conversion metadata. The species term is read from
        ``metadata["Subject"]["ontology"]["species"]``.

    Returns
    -------
    bool
        ``True`` if a reference was added, ``False`` otherwise.
    """
    return _add_subject_attribute_external_resource(nwbfile, metadata, attribute="species")


def add_strain_external_resource(nwbfile: NWBFile, metadata: dict | None = None) -> bool:
    """
    Annotate ``nwbfile.subject.strain`` with the RRID term stated in ``metadata`` via HERD.

    Reads ``metadata["Subject"]["ontology"]["strain"]`` -- an explicit ``{"id": ..., "uri": ...}``
    term -- and adds an external-resource reference mapping the subject's strain value to it,
    stored in-file under ``/general/external_resources``. Nothing is inferred: use
    :func:`neuroconv.tools.ontology.infer_strain_ontology_metadata` to populate that term from an
    informal spelling or canonical designation.

    This is a no-op (returns ``False``) when there is no subject, the subject has no strain set, or
    ``metadata`` states no strain term. It is idempotent: an existing ``external_resources`` HERD is
    extended in place rather than replaced, and a strain already annotated is not added twice.

    Parameters
    ----------
    nwbfile : NWBFile
        The file whose subject strain should be annotated. Modified in place.
    metadata : dict, optional
        Conversion metadata. The strain term is read from
        ``metadata["Subject"]["ontology"]["strain"]``.

    Returns
    -------
    bool
        ``True`` if a reference was added, ``False`` otherwise.
    """
    return _add_subject_attribute_external_resource(nwbfile, metadata, attribute="strain")


def _brain_region_mapping_from_metadata(metadata: dict | None) -> dict:
    """Merge every ``metadata["<modality>"]["ontology"]["brain_regions"]` map into one dict.

    Returns ``{location string: [(entity_id, entity_uri), ...]}``. Each brain area maps to one or
    more ontology terms, each an explicit ``{"id": ..., "uri": ...}`` dict (a single dict or a list
    of them). The maps under :data:`_BRAIN_REGION_METADATA_BLOCKS` are merged; if the same location
    string appears under more than one modality with different terms, the last block wins.
    """
    if not isinstance(metadata, dict):
        return {}

    mapping = {}
    for block_name in _BRAIN_REGION_METADATA_BLOCKS:
        block = metadata.get(block_name)
        if not isinstance(block, dict):
            continue
        raw_mapping = block.get("ontology", {}).get("brain_regions")
        if not isinstance(raw_mapping, dict):
            continue
        for location, value in raw_mapping.items():
            mapping[location] = _ontology_term_entities(value, context=f"brain area {location!r}")
    return mapping


def _brain_region_annotation_sites(nwbfile: NWBFile) -> list:
    """Collect ``(container, attribute, relative_path, location string)`` tuples to annotate.

    Covers the electrodes table ``location`` column (ecephys), each ``ElectrodeGroup.location``,
    each ``ImagingPlane.location`` (ophys), and the ``FiberPhotometryTable`` ``location`` column
    (fiber photometry), if present. Duplicate location strings within a table column are collapsed
    to one reference per column.

    ``container`` is the object HERD records the reference against (the ``location`` column, a
    ``VectorData``, for a table; the group / plane itself otherwise). ``attribute`` and
    ``relative_path`` are how that value is addressed for :meth:`HERD.add_ref` / :meth:`HERD.get_key`
    -- ``None`` / ``""`` for a standalone column, and ``"location"`` for the scalar attribute of a
    group or plane.
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

    # Lazy import: avoids a circular import at module load time (fiber_photometry.py imports from
    # tools.nwb_helpers, which imports from tools.ontology).
    from ..fiber_photometry import get_fiber_photometry_table

    fiber_photometry_table = get_fiber_photometry_table(nwbfile)
    if fiber_photometry_table is not None and "location" in fiber_photometry_table.colnames:
        location_column = fiber_photometry_table["location"]
        for location in dict.fromkeys(location_column.data):  # unique, order-preserving
            sites.append((location_column, None, "", location))

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
    Annotate anatomical ``location`` fields with the brain-region terms stated in ``metadata`` (HERD).

    Reads the ``ontology.brain_regions`` map of every modality block
    (``metadata["Ecephys"]``, ``metadata["Ophys"]``, ``metadata["FiberPhotometry"]``) -- each a
    ``{location string: term-or-list}`` mapping of explicit ``{"id": ..., "uri": ...}`` terms --
    and, for every ``location`` value on the file (the electrodes table, electrode groups, imaging
    planes, and the ``FiberPhotometryTable``) that the map covers, attaches machine-readable
    references stored in-file under ``/general/external_resources``.

    Nothing is inferred: locations the metadata does not name are left untouched. Use
    :func:`neuroconv.tools.ontology.infer_brain_region_ontology_metadata` to populate the map from a
    brain atlas first. This is a no-op (returns ``0``) when no modality block states any term.

    Parameters
    ----------
    nwbfile : NWBFile
        The file whose anatomical locations should be annotated. Modified in place.
    metadata : dict, optional
        Conversion metadata. Brain-region terms are read from
        ``metadata["<modality>"]["ontology"]["brain_regions"]``.

    Returns
    -------
    int
        The number of external-resource references added.
    """
    mapping = _brain_region_mapping_from_metadata(metadata)
    if not mapping:
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

        entities = mapping.get(location)
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
