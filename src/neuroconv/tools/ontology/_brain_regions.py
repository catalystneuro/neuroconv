"""Lightweight, offline recognition of brain regions as ontology terms.

NWB stores an anatomical location as a free-text string (e.g. the ``location`` column of the
electrodes table, ``ElectrodeGroup.location``, or ``ImagingPlane.location``). The Allen brain
atlases provide standard controlled vocabularies of brain structures per species: the Allen Mouse
Brain Atlas (``MBA``) for mouse and the Allen Human Brain Atlas (``HBA``) for human. Recognizing a
location string as an atlas term lets NeuroConv attach a machine-readable reference (``MBA:<id>`` /
``HBA:<id>``) so downstream tools can resolve the exact structure.

The lookup is species-specific because the same acronym denotes different structures across atlases
(e.g. ``MB`` is the mouse midbrain but the human mammillary body). The terms live in the curated
TermSet files ``term_sets/mouse_brain_atlas.yaml`` and ``term_sets/human_brain_atlas.yaml``
(identifiers taken from the Allen structure graphs, registered in the Bioregistry under the ``MBA``
https://bioregistry.io/registry/mba and ``HBA`` https://bioregistry.io/registry/hba prefixes).

Any other recognized species (no dedicated Allen atlas -- e.g. rat) falls back to a small,
species-agnostic vocabulary of common region names backed by
`UBERON <https://bioregistry.io/registry/uberon>`_ (``term_sets/uberon_common_regions.yaml``),
cross-species anatomy ontology's closest equivalent to the Allen atlases' curated common-name
aliases. This module adds the offline resolution of a free-text location string to one of these
terms.
"""

from dataclasses import dataclass

from pynwb import NWBFile

from ._species import get_species_term
from ._term_sets import load_term_set

__all__ = [
    "HBA_TERMS",
    "MBA_TERMS",
    "UBERON_TERMS",
    "SUPPORTED_ATLAS_SPECIES",
    "BrainRegionTerm",
    "get_brain_region_term",
    "infer_brain_region_ontology_metadata",
]


@dataclass(frozen=True)
class BrainRegionTerm:
    """An Allen brain-atlas structure and its ontology reference."""

    acronym: str
    name: str
    curie: str  # entity CURIE, e.g. "MBA:382"
    entity_uri: str  # resolvable entity URI (usable as a HERD ``entity_uri``)


# Common informal names and abbreviations -> Allen acronym, per atlas. Compared case-insensitively.
_MBA_ALIAS_TO_ACRONYM: dict[str, str] = {
    "hippocampus": "HIP",
    "entorhinal cortex": "ENT",
    "primary visual cortex": "VISp",
    "v1": "VISp",
    "primary motor cortex": "MOp",
    "m1": "MOp",
    "primary somatosensory cortex": "SSp",
    "s1": "SSp",
    "barrel cortex": "SSp-bfd",
    "neocortex": "Isocortex",
    "dorsal striatum": "CP",
    "locus coeruleus": "LC",
    "substantia nigra pars compacta": "SNc",
    "substantia nigra pars reticulata": "SNr",
    "periaqueductal grey": "PAG",
}

_HBA_ALIAS_TO_ACRONYM: dict[str, str] = {
    "hippocampus": "HiF",
    "caudate": "Cd",
    "midbrain": "MES",
    "medulla": "MY",
    "medulla oblongata": "MY",
    "cingulate cortex": "CgG",
    "locus coeruleus": "LC",
}

# Species-agnostic fallback (any recognized species without a dedicated Allen atlas, e.g. rat).
_UBERON_ALIAS_TO_ACRONYM: dict[str, str] = {
    "v1": "V1",
    "v2": "V2",
    "m1": "M1",
    "m2": "M2",
    "s1": "S1",
}


@dataclass(frozen=True)
class _BrainAtlas:
    """A curated, offline lookup of one species' brain-atlas terms."""

    terms: dict[str, BrainRegionTerm]  # acronym -> term
    name_to_acronym: dict[str, str]  # lower-cased canonical name -> acronym
    alias_to_acronym: dict[str, str]  # lower-cased informal name -> acronym

    def resolve(self, location: str) -> BrainRegionTerm | None:
        """Resolve a location string to a term via exact acronym, canonical name, or alias."""
        stripped = location.strip()
        if stripped == "":
            return None
        # Exact acronym (case-sensitive: acronyms like "VISp"/"CgG" are case-specific).
        if stripped in self.terms:
            return self.terms[stripped]
        lowered = stripped.lower()
        acronym = self.name_to_acronym.get(lowered) or self.alias_to_acronym.get(lowered)
        return self.terms.get(acronym) if acronym is not None else None


def _build_atlas(term_set_file: str, alias_to_acronym: dict) -> _BrainAtlas:
    terms = {
        info.value: BrainRegionTerm(
            acronym=info.value, name=info.description, curie=info.curie, entity_uri=info.entity_uri
        )
        for info in load_term_set(term_set_file).values()
    }
    name_to_acronym = {term.name.lower(): term.acronym for term in terms.values()}
    return _BrainAtlas(terms=terms, name_to_acronym=name_to_acronym, alias_to_acronym=alias_to_acronym)


_MBA_ATLAS = _build_atlas("mouse_brain_atlas.yaml", _MBA_ALIAS_TO_ACRONYM)
_HBA_ATLAS = _build_atlas("human_brain_atlas.yaml", _HBA_ALIAS_TO_ACRONYM)
_UBERON_ATLAS = _build_atlas("uberon_common_regions.yaml", _UBERON_ALIAS_TO_ACRONYM)

# Canonical species binomial -> its dedicated Allen brain atlas. Any other recognized species
# (e.g. rat) falls back to the species-agnostic _UBERON_ATLAS -- see _atlas_for_species.
_SPECIES_TO_ATLAS: dict[str, _BrainAtlas] = {
    "Mus musculus": _MBA_ATLAS,
    "Homo sapiens": _HBA_ATLAS,
}

#: Canonical species names with a dedicated (non-fallback) Allen brain atlas. Every other
#: recognized species still resolves brain regions, via the UBERON fallback vocabulary.
SUPPORTED_ATLAS_SPECIES: frozenset = frozenset(_SPECIES_TO_ATLAS)

#: Acronym -> :class:`BrainRegionTerm` for the Allen Mouse Brain Atlas.
MBA_TERMS: dict[str, BrainRegionTerm] = _MBA_ATLAS.terms
#: Acronym -> :class:`BrainRegionTerm` for the Allen Human Brain Atlas.
HBA_TERMS: dict[str, BrainRegionTerm] = _HBA_ATLAS.terms
#: Acronym -> :class:`BrainRegionTerm` for the species-agnostic UBERON fallback vocabulary.
UBERON_TERMS: dict[str, BrainRegionTerm] = _UBERON_ATLAS.terms


def _atlas_for_species(species: str | None) -> _BrainAtlas | None:
    """Return the brain atlas for a species value (resolving common names), or ``None``.

    A species with a dedicated Allen atlas (mouse, human) uses it; any other recognized species
    falls back to the species-agnostic UBERON vocabulary; an unrecognized species returns ``None``.
    """
    species_term = get_species_term(species)
    if species_term is None:
        return None
    return _SPECIES_TO_ATLAS.get(species_term.canonical_name, _UBERON_ATLAS)


def get_brain_region_term(location: str, species: str = "Mus musculus") -> BrainRegionTerm | None:
    """
    Resolve a free-text location string to a brain-region ontology term for a species.

    The lookup is high-precision: it matches an exact atlas acronym (case-sensitive, e.g.
    ``"CA1"``), a canonical structure name (case-insensitive, e.g. ``"caudoputamen"``), or a small
    set of common informal names and abbreviations (e.g. ``"hippocampus"``, ``"V1"``). Anything it
    does not recognize returns ``None``.

    The atlas is chosen from ``species``: ``"Mus musculus"`` (default) uses the Allen Mouse Brain
    Atlas and ``"Homo sapiens"`` the Allen Human Brain Atlas. Any other recognized species (e.g.
    ``"Rattus norvegicus"``) falls back to a small, species-agnostic vocabulary of common region
    names backed by UBERON. Common names (e.g. ``"mouse"``, ``"human"``, ``"rat"``) are accepted.
    An unrecognized species returns ``None``.

    Parameters
    ----------
    location : str
        The anatomical location string as written to an NWB ``location`` field.
    species : str, default: "Mus musculus"
        The subject species selecting which atlas to resolve against.

    Returns
    -------
    BrainRegionTerm or None
        The recognized atlas term, or ``None`` when the string cannot be resolved.
    """
    if not isinstance(location, str):
        return None
    atlas = _atlas_for_species(species)
    if atlas is None:
        return None
    return atlas.resolve(location)


def _modality_locations(nwbfile: NWBFile) -> dict:
    """``{metadata block name: [unique location strings]}`` for every anatomical site on the file.

    The electrodes table ``location`` column and every ``ElectrodeGroup.location`` fall under
    ``"Ecephys"``; every ``ImagingPlane.location`` under ``"Ophys"``; the ``FiberPhotometryTable``
    ``location`` column under ``"FiberPhotometry"``.
    """
    locations: dict[str, dict] = {"Ecephys": {}, "Ophys": {}, "FiberPhotometry": {}}

    electrodes = nwbfile.electrodes
    if electrodes is not None and "location" in electrodes.colnames:
        locations["Ecephys"].update(dict.fromkeys(str(value) for value in electrodes["location"].data))
    for electrode_group in nwbfile.electrode_groups.values():
        locations["Ecephys"].setdefault(electrode_group.location)

    for imaging_plane in nwbfile.imaging_planes.values():
        locations["Ophys"].setdefault(imaging_plane.location)

    # Lazy import: fiber_photometry.py imports (transitively) from tools.ontology.
    from ..fiber_photometry import get_fiber_photometry_table

    fiber_photometry_table = get_fiber_photometry_table(nwbfile)
    if fiber_photometry_table is not None and "location" in fiber_photometry_table.colnames:
        locations["FiberPhotometry"].update(
            dict.fromkeys(str(value) for value in fiber_photometry_table["location"].data)
        )

    return {block: list(values) for block, values in locations.items() if values}


def infer_brain_region_ontology_metadata(nwbfile: NWBFile, metadata: dict) -> dict:
    """
    Fill ``metadata["<modality>"]["ontology"]["brain_regions"]`` from the file's ``location`` fields.

    This is the **inference** half of brain-region annotation: it walks every anatomical
    ``location`` on ``nwbfile`` (the electrodes table, electrode groups, imaging planes, and the
    ``FiberPhotometryTable``), resolves each distinct string to a brain-atlas term with
    :func:`get_brain_region_term` -- choosing the atlas from the subject's species (Allen Mouse or
    Human Brain Atlas, or the species-agnostic UBERON fallback) -- and writes explicit
    ``{"id": ..., "uri": ...}`` terms under the ``ontology.brain_regions`` map of the modality block
    the location belongs to. The deterministic
    :func:`neuroconv.tools.ontology.add_brain_region_external_resources` then writes those terms
    into the file as HERD references.

    The metadata is modified in place (and also returned). A location that does not resolve, or one
    already present in the map (a user-curated term is never overwritten), is left as is. This is a
    no-op when the subject's species is not recognized or nothing resolves.

    Parameters
    ----------
    nwbfile : NWBFile
        A populated file (data already added) whose ``location`` fields are read.
    metadata : dict
        Conversion metadata. Terms are written under
        ``metadata["<modality>"]["ontology"]["brain_regions"]``.

    Returns
    -------
    dict
        The same ``metadata`` object, for chaining.
    """
    if not isinstance(metadata, dict):
        return metadata

    subject = getattr(nwbfile, "subject", None)
    species = getattr(subject, "species", None)
    if species is None:
        subject_metadata = metadata.get("Subject")
        species = subject_metadata.get("species") if isinstance(subject_metadata, dict) else None

    for block_name, block_locations in _modality_locations(nwbfile).items():
        existing = metadata.get(block_name, {}).get("ontology", {}).get("brain_regions", {})
        resolved = {}
        for location in block_locations:
            if not isinstance(location, str) or location.strip() == "" or location in existing:
                continue
            term = get_brain_region_term(location, species=species)
            if term is not None:
                resolved[location] = {"id": term.curie, "uri": term.entity_uri}
        if resolved:
            brain_regions = (
                metadata.setdefault(block_name, {}).setdefault("ontology", {}).setdefault("brain_regions", {})
            )
            brain_regions.update(resolved)

    return metadata
