"""Attach ontology entity references to NWB files via HDMF's HERD.

HERD (HDMF External Resources Data) lets an NWB file carry machine-readable links from its
metadata values to entities in external ontologies. NeuroConv uses it to annotate values it
can recognize -- ``Subject.species`` -> NCBITaxon, ``Subject.strain`` -> RRID, anatomical
``location`` fields (the electrodes table, electrode groups, imaging planes, and the
``FiberPhotometryTable``) -> the Allen Mouse or Human Brain Atlas (or a species-agnostic UBERON
vocabulary for any other recognized species), and ``ndx-pose`` ``Skeleton`` node names -> a
species-agnostic UBERON vocabulary of skeleton parts and muscles -- so downstream tools (e.g. the
DANDI archive) can resolve the term without guessing.

The reference is stored in-file under ``/general/external_resources``, which requires
``pynwb >= 4.0.0`` (guaranteed by NeuroConv's dependency pin).
"""

from pynwb import NWBFile, get_type_map

from ._anatomy import get_anatomy_term
from ._brain_regions import get_brain_region_term
from ._species import get_species_term
from ._strain import get_strain_term

__all__ = [
    "OntologyAnnotationMixin",
    "add_anatomy_external_resources",
    "add_brain_region_external_resources",
    "add_species_external_resource",
    "add_strain_external_resource",
]


def _attribute_already_annotated(herd, container, attribute: str) -> bool:
    """Whether ``herd`` already has an entity for ``container.attribute`` (keeps a call idempotent)."""
    try:
        existing = herd.get_object_entities(container, attribute=attribute)
    except ValueError:
        # Raised when the container is not yet registered in the object table.
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
    elif _attribute_already_annotated(herd, subject, attribute="species"):
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


def _strain_mapping_from_metadata(metadata: dict | None) -> dict:
    """Parse ``metadata["Strain"]`` into ``{strain string: [(entity_id, entity_uri), ...]}``.

    Maps a strain string (as it appears on ``Subject.strain``) to one or more ontology terms, each
    given as a ``dict`` with an ``id`` (a CURIE such as ``"RRID:IMSR_JAX:000664"``) and a resolvable
    ``uri``. A single ``dict`` or a list of them is accepted. This is how you annotate a strain the
    curated :data:`~neuroconv.tools.ontology.STRAIN_TERMS` table does not recognize (e.g. an
    in-house line), or override one it does.
    """
    return _id_uri_mapping_from_metadata(metadata, metadata_key="Strain", item_label="strain")


def add_strain_external_resource(nwbfile: NWBFile, metadata: dict | None = None) -> bool:
    """
    Annotate ``nwbfile.subject.strain`` with an RRID entity via HERD.

    Adds an external-resource reference mapping the subject's strain (a laboratory rodent strain
    designation) to its RRID identifier, stored in-file under ``/general/external_resources``. The
    strain is resolved by:

    1. the ``metadata["Strain"]`` mapping, if it provides an entry for the exact strain string
       (this takes precedence and is ontology-agnostic, so it may map the strain to several
       terms); then
    2. the curated :data:`~neuroconv.tools.ontology.STRAIN_TERMS` offline lookup.

    This is a no-op (returns ``False``) when there is no subject, the subject has no strain set,
    or the strain resolves through neither.

    Parameters
    ----------
    nwbfile : NWBFile
        The file whose subject strain should be annotated. Modified in place.
    metadata : dict, optional
        Conversion metadata. ``metadata["Strain"]`` maps the strain string to a term
        ``{"id": ..., "uri": ...}`` or a list of such terms.

    Returns
    -------
    bool
        ``True`` if at least one reference was added, ``False`` otherwise.
    """
    subject = getattr(nwbfile, "subject", None)
    if subject is None:
        return False

    strain = getattr(subject, "strain", None)
    if not isinstance(strain, str) or strain.strip() == "":
        return False

    custom_mapping = _strain_mapping_from_metadata(metadata)
    entities = custom_mapping.get(strain)
    if entities is None:
        term = get_strain_term(strain)
        entities = [(term.rrid, term.entity_uri)] if term is not None else None
    if not entities:
        return False

    from hdmf.common import HERD

    herd = nwbfile.external_resources
    is_new_herd = herd is None
    if is_new_herd:
        herd = HERD(type_map=get_type_map())

    already_annotated = _existing_external_resource_refs(herd)
    number_added = 0
    # All terms for the strain share one HERD key; reuse the key object across entities so a
    # single object<->key link carries every ontology reference.
    key = None
    for entity_id, entity_uri in entities:
        if (subject.object_id, strain, entity_id) in already_annotated:
            continue
        if key is None:
            key = _find_existing_key(herd, subject, "strain", strain)
        if key is None:
            herd.add_ref(container=subject, attribute="strain", key=strain, entity_id=entity_id, entity_uri=entity_uri)
            key = herd.get_key(strain, container=subject, relative_path="strain")
        else:
            herd.add_ref(container=subject, attribute="strain", key=key, entity_id=entity_id, entity_uri=entity_uri)
        number_added += 1

    if number_added > 0 and is_new_herd:
        nwbfile.external_resources = herd
    return number_added > 0


def _subject_atlas_species(nwbfile: NWBFile) -> str | None:
    """Canonical species name if the subject is recognized, else ``None``.

    Every recognized species resolves brain regions: mouse and human against their dedicated
    Allen atlas, any other recognized species (e.g. rat) against the UBERON fallback vocabulary
    (see :func:`neuroconv.tools.ontology.get_brain_region_term`).
    """
    subject = getattr(nwbfile, "subject", None)
    if subject is None:
        return None
    species_term = get_species_term(getattr(subject, "species", None))
    return species_term.canonical_name if species_term is not None else None


def _id_uri_mapping_from_metadata(metadata: dict | None, *, metadata_key: str, item_label: str) -> dict:
    """Parse ``metadata[metadata_key]`` into ``{value string: [(entity_id, entity_uri), ...]}``.

    Shared by the ``"BrainRegions"`` and ``"Strain"`` metadata overrides: each maps a value string
    (a location or a strain designation) to one or more ontology terms, each given as a ``dict``
    with an ``id`` (a CURIE) and a resolvable ``uri``. A single ``dict`` or a list of them is
    accepted, so one value can be annotated with several ontologies. This representation is
    ontology-agnostic and species-agnostic.

    Parameters
    ----------
    metadata : dict, optional
        Conversion metadata.
    metadata_key : str
        The top-level metadata key holding the mapping (``"BrainRegions"`` or ``"Strain"``).
    item_label : str
        Human-readable noun for the mapped value, used only in error messages (e.g. ``"brain
        area"`` or ``"strain"``).
    """
    if not isinstance(metadata, dict):
        return {}
    raw_mapping = metadata.get(metadata_key)
    if not isinstance(raw_mapping, dict):
        return {}

    mapping = {}
    for value, term_value in raw_mapping.items():
        terms = term_value if isinstance(term_value, list) else [term_value]
        entities = []
        for term in terms:
            if not isinstance(term, dict):
                raise TypeError(
                    f"Each metadata[{metadata_key!r}] term must be a dict with 'id' and 'uri' keys; "
                    f"got {type(term).__name__} for {item_label} {value!r}."
                )
            entity_id = term.get("id")
            entity_uri = term.get("uri")
            if not entity_id or not entity_uri:
                raise ValueError(
                    f"Each metadata[{metadata_key!r}] term for {item_label} {value!r} must define "
                    "both 'id' and 'uri'."
                )
            entities.append((str(entity_id), str(entity_uri)))
        mapping[value] = entities
    return mapping


def _brain_region_mapping_from_metadata(metadata: dict | None) -> dict:
    """Parse ``metadata["BrainRegions"]`` into ``{location string: [(entity_id, entity_uri), ...]}``.

    Each brain area maps to one or more ontology terms, each given as a ``dict`` with an ``id``
    (a CURIE such as ``"MBA:382"`` or ``"UBERON:0003881"``) and a resolvable ``uri``. A single
    ``dict`` or a list of them is accepted, so one area can be annotated with several ontologies
    (e.g. both MBA and UBERON). This representation is ontology-agnostic, so it applies to any
    species, not just mouse.
    """
    return _id_uri_mapping_from_metadata(metadata, metadata_key="BrainRegions", item_label="brain area")


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
    Annotate anatomical ``location`` fields with brain-region ontology entities via HERD.

    Resolves each ``location`` string on the electrodes table, electrode groups, imaging planes, and
    the ``FiberPhotometryTable`` (if present) to one or more ontology terms and attaches
    machine-readable references (stored in-file under ``/general/external_resources``). Each
    location is resolved by:

    1. the ``metadata["BrainRegions"]`` mapping, if it provides an entry (this takes precedence and
       is ontology-agnostic, so it applies to any species and may map one area to several terms,
       e.g. both MBA and UBERON); then
    2. the offline brain-atlas lookup for the subject's species -- the Allen Mouse Brain Atlas for
       *Mus musculus*, the Allen Human Brain Atlas for *Homo sapiens*, and a species-agnostic
       UBERON-backed vocabulary of common region names for every other recognized species.

    Locations resolving to neither are left untouched. This is a no-op (returns ``0``) when the
    subject's species is not recognized and no metadata mapping is provided.

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


def _anatomy_mapping_from_metadata(metadata: dict | None) -> dict:
    """Parse ``metadata["Anatomy"]`` into ``{structure name: [(entity_id, entity_uri), ...]}``.

    Same ontology-agnostic shape as ``metadata["BrainRegions"]``/``metadata["Strain"]``: each
    structure name maps to one or more ontology terms, each a ``dict`` with an ``id`` and a
    resolvable ``uri``. This is how you annotate a structure the curated
    :data:`~neuroconv.tools.ontology.ANATOMY_TERMS` table does not recognize (e.g. a lab-specific
    keypoint name with a laterality marker like ``"EarL"``), or override one it does.
    """
    return _id_uri_mapping_from_metadata(metadata, metadata_key="Anatomy", item_label="anatomical structure")


def _anatomy_annotation_sites(nwbfile: NWBFile) -> list:
    """Collect ``(container, attribute, relative_path, node name)`` tuples to annotate.

    Covers every ``ndx-pose`` ``Skeleton.nodes`` entry in ``nwbfile.processing["behavior"]["Skeletons"]``
    (the container path NeuroConv's own pose-estimation interfaces write to), if present. Unlike
    the brain-region sites, ``nodes`` is a plain array attribute of the ``Skeleton`` itself (not a
    separate ``VectorData`` column), so the ``Skeleton`` is the HERD container and ``"nodes"`` is
    both the attribute and the relative path.
    """
    sites = []
    behavior_module = nwbfile.processing.get("behavior")
    if behavior_module is None:
        return sites
    skeletons_container = behavior_module.data_interfaces.get("Skeletons")
    if skeletons_container is None:
        return sites
    for skeleton in skeletons_container.skeletons.values():
        for node_name in dict.fromkeys(skeleton.nodes):  # unique, order-preserving
            sites.append((skeleton, "nodes", "nodes", node_name))
    return sites


def add_anatomy_external_resources(nwbfile: NWBFile, metadata: dict | None = None) -> int:
    """
    Annotate ``ndx-pose`` ``Skeleton`` node names with general-anatomy ontology entities via HERD.

    Resolves each distinct node name in every ``Skeleton.nodes`` array (pose-estimation keypoints,
    e.g. ``"Snout"``, ``"Shoulder"``) to one or more ontology terms and attaches machine-readable
    references (stored in-file under ``/general/external_resources``). Each name is resolved by:

    1. the ``metadata["Anatomy"]`` mapping, if it provides an entry (this takes precedence and is
       ontology-agnostic, so it may map one structure to several terms); then
    2. the curated :data:`~neuroconv.tools.ontology.ANATOMY_TERMS` offline lookup of skeleton parts
       and muscles, backed by UBERON.

    Names resolving to neither are left untouched. This is a no-op (returns ``0``) when the file
    has no ``Skeleton`` and no metadata mapping is provided.

    Parameters
    ----------
    nwbfile : NWBFile
        The file whose skeleton node names should be annotated. Modified in place.
    metadata : dict, optional
        Conversion metadata. ``metadata["Anatomy"]`` maps a node name to a term
        ``{"id": ..., "uri": ...}`` or a list of such terms.

    Returns
    -------
    int
        The number of external-resource references added.
    """
    custom_mapping = _anatomy_mapping_from_metadata(metadata)
    sites = _anatomy_annotation_sites(nwbfile)
    if not custom_mapping and not sites:
        return 0

    from hdmf.common import HERD

    herd = nwbfile.external_resources
    is_new_herd = herd is None
    if is_new_herd:
        herd = HERD(type_map=get_type_map())

    already_annotated = _existing_external_resource_refs(herd)
    number_added = 0
    for container, attribute, relative_path, node_name in sites:
        if not isinstance(node_name, str) or node_name.strip() == "":
            continue

        entities = custom_mapping.get(node_name)
        if entities is None:
            term = get_anatomy_term(node_name)
            entities = [(term.curie, term.entity_uri)] if term is not None else None
        if not entities:
            continue

        # All terms for a given node name share one HERD key; reuse the key object across the
        # name's entities so a single object<->key link carries every ontology reference.
        key = None
        for entity_id, entity_uri in entities:
            if (container.object_id, node_name, entity_id) in already_annotated:
                continue
            if key is None:
                key = _find_existing_key(herd, container, relative_path, node_name)
            if key is None:
                herd.add_ref(
                    container=container,
                    attribute=attribute,
                    key=node_name,
                    entity_id=entity_id,
                    entity_uri=entity_uri,
                )
                key = herd.get_key(node_name, container=container, relative_path=relative_path)
            else:
                herd.add_ref(
                    container=container, attribute=attribute, key=key, entity_id=entity_id, entity_uri=entity_uri
                )
            already_annotated.add((container.object_id, node_name, entity_id))
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

    def add_strain_external_resource(self, nwbfile: NWBFile, metadata: dict | None = None) -> bool:
        """
        Attach a strain (RRID) reference for the subject to ``nwbfile`` (HERD).

        Override to customize. The default implementation delegates to
        :func:`neuroconv.tools.ontology.add_strain_external_resource`.

        Parameters
        ----------
        nwbfile : NWBFile
            The populated file to annotate, modified in place.
        metadata : dict, optional
            Conversion metadata (see the delegated function for the ``"Strain"`` mapping).

        Returns
        -------
        bool
            Whether a reference was added.
        """
        return add_strain_external_resource(nwbfile, metadata=metadata)

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

    def add_anatomy_external_resources(self, nwbfile: NWBFile, metadata: dict | None = None) -> int:
        """
        Attach general-anatomy ontology references to ``nwbfile`` (HERD). Override to customize.

        The default implementation delegates to
        :func:`neuroconv.tools.ontology.add_anatomy_external_resources`.

        Parameters
        ----------
        nwbfile : NWBFile
            The populated file to annotate, modified in place.
        metadata : dict, optional
            Conversion metadata (see the delegated function for the ``"Anatomy"`` mapping).

        Returns
        -------
        int
            The number of external-resource references added.
        """
        return add_anatomy_external_resources(nwbfile, metadata=metadata)
