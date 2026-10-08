"""Attach ontology entity references to NWB files via HDMF's HERD.

HERD (HDMF External Resources Data) lets an NWB file carry machine-readable links from its
metadata values to entities in external ontologies. The functions here are the **deterministic**
half of NeuroConv's ontology support: they take terms that are already stated in ``metadata`` and
write the corresponding references into the file. Nothing is guessed -- resolving a free-text
value (a common species name, an atlas acronym) to a term is the job of the ``infer_*`` functions
in this package, which populate the same ``metadata`` blocks these functions read.

The terms live in one file-wide ``metadata["ExternalResources"]`` block, each map keyed by the exact value
string it annotates (HERD links a term to an object through that string):

- ``metadata["ExternalResources"]["species"]`` -> ``{species string: term-or-list}`` for ``Subject.species``;
- ``metadata["ExternalResources"]["brain_regions"]`` -> ``{location string: term-or-list}`` for every
  anatomical ``location`` field on the file (the electrodes table and electrode groups, imaging
  planes, intracellular electrodes, optogenetic stimulus sites, viral vector injections, and the
  ``FiberPhotometryTable``), regardless of which modality it belongs to.

Each term is an explicit ``{"id": <CURIE>, "uri": <resolvable URI>}`` dict; a list of them annotates
one value with several ontologies (e.g. both MBA and UBERON). This representation is
ontology-agnostic, so it applies to any species.

The reference is stored in-file under ``/general/external_resources``, which requires
``pynwb >= 4.0.0`` (guaranteed by NeuroConv's dependency pin).
"""

import warnings

from pynwb import NWBFile, get_type_map

from ._brain_regions import _location_containers
from ._term_sets import _unwrapped

__all__ = [
    "add_brain_region_external_resources",
    "add_external_resources_to_nwbfile",
    "add_species_external_resource",
]


def _get_or_create_herd(nwbfile: NWBFile) -> tuple:
    """Return ``(herd, is_new)``: the file's HERD, or a new one when it has none.

    HERD resolves each annotated object through its type map. A file read from disk needs the reading
    IO's type map (it knows the namespaces loaded with the file, extensions included), and a HERD read
    back from a file otherwise only has hdmf-common's, which cannot resolve any NWB type. A file built in
    memory uses pynwb's.
    """
    from hdmf.common import HERD

    read_io = nwbfile.get_read_io()
    type_map = read_io.manager.type_map if read_io is not None else get_type_map()

    herd = nwbfile.external_resources
    if herd is None:
        return HERD(type_map=type_map), True
    herd.type_map = type_map
    return herd, False


def _herd_is_read_only(herd) -> bool:
    """Whether ``herd`` was read from disk, where its tables are fixed-size datasets that cannot grow."""
    return not isinstance(herd.keys.data, list)


def _warn_read_only_herd(number_of_references: int) -> None:
    warnings.warn(
        f"The file already stores external resources (HERD) on disk, which cannot be extended, so "
        f"{number_of_references} new reference(s) from metadata['ExternalResources'] were not added. Annotate the file "
        "when it is first written instead.",
        UserWarning,
        stacklevel=3,
    )


def _species_already_annotated(herd, subject) -> bool:
    """Whether ``herd`` already has a species entity for ``subject`` (keeps the call idempotent)."""
    try:
        existing = herd.get_object_entities(subject, attribute="species")
    except ValueError:
        # Raised when the subject is not yet registered in the object table.
        return False
    return not existing.empty


def _ontology_term_entities(value, *, context: str) -> list:
    """Normalize an ``ExternalResources`` metadata term (a dict, or a list of dicts) to ``[(id, uri), ...]``.

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


def add_species_external_resource(nwbfile: NWBFile, metadata: dict | None = None) -> bool:
    """
    Annotate ``nwbfile.subject.species`` with the NCBITaxon term stated in ``metadata`` via HERD.

    Looks up the subject's species value in ``metadata["ExternalResources"]["species"]`` -- a
    ``{species string: term-or-list}`` map of explicit ``{"id": ..., "uri": ...}`` terms -- and adds
    an external-resource reference mapping that value to its term(s), stored in-file under
    ``/general/external_resources``. Nothing is inferred: use
    :func:`neuroconv.tools.external_resources.infer_species_external_resources` to propose that term from a
    common name or Latin binomial.

    This is a no-op (returns ``False``) when there is no subject or ``metadata`` states no term for
    the subject's species value. It is idempotent: an existing ``external_resources`` HERD is extended in place rather than
    replaced, and a species already annotated is not added twice.

    Parameters
    ----------
    nwbfile : NWBFile
        The file whose subject species should be annotated. Modified in place.
    metadata : dict, optional
        Conversion metadata. The species term is read from
        ``metadata["ExternalResources"]["species"][<Subject.species>]``.

    Returns
    -------
    bool
        ``True`` if a reference was added, ``False`` otherwise.
    """
    subject = getattr(nwbfile, "subject", None)
    if subject is None:
        return False

    species = _unwrapped(subject.species)
    if not isinstance(species, str) or species.strip() == "":
        return False

    species_mapping = (metadata or {}).get("ExternalResources", {}).get("species")
    if not isinstance(species_mapping, dict) or species_mapping.get(species) is None:
        return False
    entities = _ontology_term_entities(species_mapping[species], context=f"Subject species {species!r}")

    herd, is_new_herd = _get_or_create_herd(nwbfile)
    if not is_new_herd and _species_already_annotated(herd, subject):
        return False
    if not is_new_herd and _herd_is_read_only(herd):
        _warn_read_only_herd(len(entities))
        return False

    for entity_id, entity_uri in entities:
        herd.add_ref(
            container=subject,
            attribute="species",
            key=species,
            entity_id=entity_id,
            entity_uri=entity_uri,
        )

    # ``external_resources`` is write-once; only assign when we created the HERD, otherwise we
    # have extended the object already linked to the file in place.
    if is_new_herd:
        nwbfile.external_resources = herd
    return True


def _brain_region_mapping_from_metadata(metadata: dict | None) -> dict:
    """Normalize ``metadata["ExternalResources"]["brain_regions"]`` to ``{location: [(id, uri), ...]}``.

    Each brain area maps to one or more ontology terms, each an explicit ``{"id": ..., "uri": ...}``
    dict (a single dict or a list of them).
    """
    if not isinstance(metadata, dict):
        return {}

    raw_mapping = metadata.get("ExternalResources", {}).get("brain_regions")
    if not isinstance(raw_mapping, dict):
        return {}

    return {
        location: _ontology_term_entities(value, context=f"brain area {location!r}")
        for location, value in raw_mapping.items()
    }


def _brain_region_annotation_sites(nwbfile: NWBFile) -> list:
    """Collect ``(container, attribute, relative_path, location string)`` tuples to annotate.

    Covers the electrodes table ``location`` column (ecephys) and the ``FiberPhotometryTable``
    ``location`` column (fiber photometry), if present, plus every object with a scalar ``location``
    attribute (electrode groups, imaging planes, intracellular electrodes, optogenetic stimulus
    sites, and viral vector injections). Duplicate location strings within a table column are
    collapsed to one reference per column.

    ``container`` is the object HERD records the reference against (the ``location`` column, a
    ``VectorData``, for a table; the object itself otherwise). ``attribute`` and ``relative_path``
    are how that value is addressed for :meth:`HERD.add_ref` / :meth:`HERD.get_key` -- ``None`` /
    ``""`` for a standalone column, and ``"location"`` for a scalar attribute.
    """
    sites = []

    electrodes = nwbfile.electrodes
    if electrodes is not None and "location" in electrodes.colnames:
        location_column = electrodes["location"]
        for location in dict.fromkeys(_unwrapped(location_column.data)):  # unique, order-preserving
            sites.append((location_column, None, "", location))

    for container in _location_containers(nwbfile):
        sites.append((container, "location", "location", _unwrapped(container.location)))

    # Lazy import: avoids a circular import at module load time (fiber_photometry.py imports from
    # tools.nwb_helpers, which imports from tools.external_resources).
    from ..fiber_photometry import get_fiber_photometry_table

    fiber_photometry_table = get_fiber_photometry_table(nwbfile)
    if fiber_photometry_table is not None and "location" in fiber_photometry_table.colnames:
        location_column = fiber_photometry_table["location"]
        for location in dict.fromkeys(_unwrapped(location_column.data)):  # unique, order-preserving
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

    Reads ``metadata["ExternalResources"]["brain_regions"]`` -- a ``{location string: term-or-list}`` mapping
    of explicit ``{"id": ..., "uri": ...}`` terms -- and, for every ``location`` value on the file
    (the electrodes table, electrode groups, imaging planes, intracellular electrodes, optogenetic
    stimulus sites, viral vector injections, and the ``FiberPhotometryTable``) that the map covers, attaches machine-readable references stored in-file under
    ``/general/external_resources``.

    Nothing is inferred: locations the metadata does not name are left untouched. Use
    :func:`neuroconv.tools.external_resources.infer_brain_region_external_resources` to propose the map from a
    brain atlas first. This is a no-op (returns ``0``) when ``metadata`` states no term.

    Parameters
    ----------
    nwbfile : NWBFile
        The file whose anatomical locations should be annotated. Modified in place.
    metadata : dict, optional
        Conversion metadata. Brain-region terms are read from
        ``metadata["ExternalResources"]["brain_regions"]``.

    Returns
    -------
    int
        The number of external-resource references added.
    """
    mapping = _brain_region_mapping_from_metadata(metadata)
    if not mapping:
        return 0

    herd, is_new_herd = _get_or_create_herd(nwbfile)

    already_annotated = _existing_external_resource_refs(herd)
    pending = []  # (container, attribute, relative_path, location, [(entity_id, entity_uri), ...])
    for container, attribute, relative_path, location in _brain_region_annotation_sites(nwbfile):
        if not isinstance(location, str) or location.strip() == "":
            continue
        new_entities = [
            (entity_id, entity_uri)
            for entity_id, entity_uri in mapping.get(location, [])
            if (container.object_id, location, entity_id) not in already_annotated
        ]
        if new_entities:
            pending.append((container, attribute, relative_path, location, new_entities))

    if pending and not is_new_herd and _herd_is_read_only(herd):
        _warn_read_only_herd(sum(len(entities) for *_, entities in pending))
        return 0

    number_added = 0
    for container, attribute, relative_path, location, entities in pending:
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


def add_external_resources_to_nwbfile(nwbfile: NWBFile, metadata: dict | None = None) -> int:
    """
    Write every term stated in ``metadata["ExternalResources"]`` into the file as HERD references.

    This is the single entry point for the **annotation** half: it runs each per-domain writer
    (:func:`add_species_external_resource`, :func:`add_brain_region_external_resources`) on the file
    as it is now. ``run_conversion`` calls it just before writing, so objects added to an in-memory
    file after it was created are annotated too. Call it yourself right before writing when you build
    the file with ``create_nwbfile`` and write it with ``configure_and_write_nwbfile``.

    Nothing is inferred, and it is a no-op (returns ``0``) when ``metadata`` carries no ``ExternalResources`` block.
    It is idempotent: references already in the file are not added again.

    Parameters
    ----------
    nwbfile : NWBFile
        The file to annotate. Modified in place.
    metadata : dict, optional
        Conversion metadata. Terms are read from ``metadata["ExternalResources"]``.

    Returns
    -------
    int
        The number of external-resource references added.
    """
    number_added = int(add_species_external_resource(nwbfile, metadata=metadata))
    number_added += add_brain_region_external_resources(nwbfile, metadata=metadata)
    return number_added
