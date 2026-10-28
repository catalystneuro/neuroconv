"""Attach ontology entity references to NWB files via HDMF's HERD.

HERD (HDMF External Resources Data) lets an NWB file carry machine-readable links from its
metadata values to entities in external ontologies. :func:`add_external_resources_to_nwbfile` takes
the terms stated in ``metadata`` and writes the corresponding references into the file. Nothing is
guessed: a value without a term in ``metadata`` is left untouched.

The terms live in one file-wide ``metadata["ExternalResources"]`` block, each map keyed by the exact value
string it annotates (HERD links a term to an object through that string):

- ``metadata["ExternalResources"]["species"]`` -> ``{species string: term-or-list}`` for ``Subject.species``;
- ``metadata["ExternalResources"]["strain"]`` -> ``{strain string: term-or-list}`` for ``Subject.strain``;
- ``metadata["ExternalResources"]["brain_regions"]`` -> ``{location string: term-or-list}`` for every
  anatomical ``location`` field on the file (the electrodes table and electrode groups, imaging
  planes, intracellular electrodes, optogenetic stimulus sites, viral vector injections, and the
  ``FiberPhotometryTable``), regardless of which modality it belongs to.

Each term is an explicit ``{"id": <CURIE>, "uri": <resolvable URI>}`` dict; a list of them annotates
one value with several ontologies (e.g. both MBA and UBERON). This representation is
ontology-agnostic, so it applies to any species.

Each map has a target finder in ``_TARGET_FINDERS`` that lists the objects on the file carrying its
values. Supporting a new kind of value takes a finder and a property in the ``ExternalResources``
block of the base metadata schema.

The reference is stored in-file under ``/general/external_resources``, which requires
``pynwb >= 4.0.0`` (guaranteed by NeuroConv's dependency pin).
"""

import warnings
from functools import partial

from hdmf.term_set import TermSetWrapper
from pynwb import NWBFile, get_type_map

__all__ = ["add_external_resources_to_nwbfile"]


def _unwrapped(value):
    """The plain value behind an HDMF ``TermSetWrapper``, or ``value`` itself.

    With a type configuration loaded (``pynwb.load_type_config``, e.g. neuro-termsets'
    ``default_config.yaml``), HDMF wraps configured fields such as ``Subject.species`` and
    ``ElectrodeGroup.location`` in a ``TermSetWrapper``. The wrapper does not compare or convert like
    the string it holds, so every value read from a file goes through this first.
    """
    return value.value if isinstance(value, TermSetWrapper) else value


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


def _ontology_term_entities(value, *, context: str) -> list:
    """Normalize an ``ExternalResources`` metadata term (a dict, or a list of dicts) to ``[(id, uri), ...]``.

    ``context`` names the annotated value in error messages (e.g. ``"species 'Mus musculus'"``).
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


def _subject_attribute_targets(nwbfile: NWBFile, attribute: str) -> list:
    """The subject's ``attribute`` as a ``(container, attribute, relative_path, value)`` target."""
    subject = getattr(nwbfile, "subject", None)
    if subject is None:
        return []
    return [(subject, attribute, attribute, _unwrapped(getattr(subject, attribute, None)))]


def _location_containers(nwbfile: NWBFile) -> list:
    """Every object on the file that carries a scalar ``location`` attribute naming a brain region.

    Covers ``ElectrodeGroup`` (ecephys), ``ImagingPlane`` (ophys), ``IntracellularElectrode``
    (icephys), ``OptogeneticStimulusSite`` (ogen), and every ``ndx-ophys-devices``
    ``ViralVectorInjection``, whose ``location`` is the targeted region. Injections are found by type
    wherever they sit (the fiber-photometry and optogenetics containers both hold them), so no
    extension has to be installed for the rest to work. Objects whose ``location`` is unset are
    skipped.
    """
    containers = [
        *nwbfile.electrode_groups.values(),
        *nwbfile.imaging_planes.values(),
        *nwbfile.icephys_electrodes.values(),
        *nwbfile.ogen_sites.values(),
        *(obj for obj in nwbfile.objects.values() if getattr(obj, "neurodata_type", None) == "ViralVectorInjection"),
    ]
    return [container for container in containers if _unwrapped(getattr(container, "location", None)) is not None]


def _brain_region_targets(nwbfile: NWBFile) -> list:
    """Collect ``(container, attribute, relative_path, location string)`` targets for brain regions.

    Covers the electrodes table ``location`` column (ecephys) and the ``FiberPhotometryTable``
    ``location`` column (fiber photometry), if present, plus every object with a scalar ``location``
    attribute (electrode groups, imaging planes, intracellular electrodes, optogenetic stimulus
    sites, and viral vector injections). Duplicate location strings within a table column are
    collapsed to one target per column.
    """
    targets = []

    electrodes = nwbfile.electrodes
    if electrodes is not None and "location" in electrodes.colnames:
        location_column = electrodes["location"]
        for location in dict.fromkeys(_unwrapped(location_column.data)):  # unique, order-preserving
            targets.append((location_column, None, "", location))

    for container in _location_containers(nwbfile):
        targets.append((container, "location", "location", _unwrapped(container.location)))

    # Lazy import: avoids a circular import at module load time (fiber_photometry.py imports from
    # tools.nwb_helpers, which imports from tools.external_resources).
    from ..fiber_photometry import get_fiber_photometry_table

    fiber_photometry_table = get_fiber_photometry_table(nwbfile)
    if fiber_photometry_table is not None and "location" in fiber_photometry_table.colnames:
        location_column = fiber_photometry_table["location"]
        for location in dict.fromkeys(_unwrapped(location_column.data)):  # unique, order-preserving
            targets.append((location_column, None, "", location))

    return targets


# One finder per map of ``metadata["ExternalResources"]``. A finder returns the
# ``(container, attribute, relative_path, value)`` targets on the file: ``container`` is the object HERD
# records the reference against (the column, a ``VectorData``, for a table value; the object itself
# otherwise), and ``attribute`` / ``relative_path`` are how the value is addressed for
# :meth:`HERD.add_ref` / :meth:`HERD.get_key` (``None`` / ``""`` for a standalone column).
_TARGET_FINDERS = {
    "species": partial(_subject_attribute_targets, attribute="species"),
    "strain": partial(_subject_attribute_targets, attribute="strain"),
    "brain_regions": _brain_region_targets,
}


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


def add_external_resources_to_nwbfile(nwbfile: NWBFile, metadata: dict | None = None) -> int:
    """
    Write every term stated in ``metadata["ExternalResources"]`` into the file as HERD references.

    For each map of the block (``species``, ``strain``, ``brain_regions``), every value on the file that the map
    covers gets a reference to its term(s), stored in-file under ``/general/external_resources``.
    ``run_conversion`` calls this just before writing, so objects added to an in-memory file after it
    was created are annotated too. Call it yourself right before writing when you build the file with
    ``create_nwbfile`` and write it with ``configure_and_write_nwbfile``.

    Nothing is inferred, and it is a no-op (returns ``0``) when ``metadata`` carries no ``ExternalResources``
    block. It is idempotent: an existing ``external_resources`` HERD is extended in place, and
    references already in it are not added again. A HERD read back from disk cannot grow, so new
    references for such a file are skipped with a warning.

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
    block = (metadata or {}).get("ExternalResources")
    if not isinstance(block, dict):
        return 0

    # (container, attribute, relative_path, value, [(entity_id, entity_uri), ...]) for every covered value
    covered_targets = []
    for map_name, find_targets in _TARGET_FINDERS.items():
        term_map = block.get(map_name)
        if not isinstance(term_map, dict) or not term_map:
            continue
        for container, attribute, relative_path, value in find_targets(nwbfile):
            if not isinstance(value, str) or value.strip() == "" or term_map.get(value) is None:
                continue
            entities = _ontology_term_entities(term_map[value], context=f"{map_name} {value!r}")
            covered_targets.append((container, attribute, relative_path, value, entities))
    if not covered_targets:
        return 0

    herd, is_new_herd = _get_or_create_herd(nwbfile)

    already_annotated = _existing_external_resource_refs(herd)
    pending = []
    for container, attribute, relative_path, value, entities in covered_targets:
        new_entities = [
            (entity_id, entity_uri)
            for entity_id, entity_uri in entities
            if (container.object_id, value, entity_id) not in already_annotated
        ]
        if new_entities:
            pending.append((container, attribute, relative_path, value, new_entities))

    if pending and not is_new_herd and _herd_is_read_only(herd):
        _warn_read_only_herd(sum(len(entities) for *_, entities in pending))
        return 0

    number_added = 0
    for container, attribute, relative_path, value, entities in pending:
        # All terms for a given value share one HERD key; reuse the key object across the value's
        # entities so a single object<->key link carries every ontology reference.
        key = None
        for entity_id, entity_uri in entities:
            if (container.object_id, value, entity_id) in already_annotated:
                continue
            if key is None:
                key = _find_existing_key(herd, container, relative_path, value)
            if key is None:
                herd.add_ref(
                    container=container, attribute=attribute, key=value, entity_id=entity_id, entity_uri=entity_uri
                )
                key = herd.get_key(value, container=container, relative_path=relative_path)
            else:
                herd.add_ref(
                    container=container, attribute=attribute, key=key, entity_id=entity_id, entity_uri=entity_uri
                )
            already_annotated.add((container.object_id, value, entity_id))
            number_added += 1

    # ``external_resources`` is write-once; only assign when we created the HERD, otherwise we
    # have extended the object already linked to the file in place.
    if number_added > 0 and is_new_herd:
        nwbfile.external_resources = herd
    return number_added
