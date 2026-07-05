"""Lightweight, offline recognition of brain regions as Allen brain-atlas terms.

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
https://bioregistry.io/registry/mba and ``HBA`` https://bioregistry.io/registry/hba prefixes). This
module adds the offline resolution of a free-text location string to one of those terms.
"""

from dataclasses import dataclass

from ._species import get_species_term
from ._term_sets import load_term_set

__all__ = [
    "HBA_TERMS",
    "MBA_TERMS",
    "SUPPORTED_ATLAS_SPECIES",
    "BrainRegionTerm",
    "get_brain_region_term",
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

# Canonical species binomial -> its brain atlas.
_SPECIES_TO_ATLAS: dict[str, _BrainAtlas] = {
    "Mus musculus": _MBA_ATLAS,
    "Homo sapiens": _HBA_ATLAS,
}

#: Canonical species names for which an offline brain-atlas lookup is available.
SUPPORTED_ATLAS_SPECIES: frozenset = frozenset(_SPECIES_TO_ATLAS)

#: Acronym -> :class:`BrainRegionTerm` for the Allen Mouse Brain Atlas.
MBA_TERMS: dict[str, BrainRegionTerm] = _MBA_ATLAS.terms
#: Acronym -> :class:`BrainRegionTerm` for the Allen Human Brain Atlas.
HBA_TERMS: dict[str, BrainRegionTerm] = _HBA_ATLAS.terms


def _atlas_for_species(species: str | None) -> _BrainAtlas | None:
    """Return the brain atlas for a species value (resolving common names), or ``None``."""
    species_term = get_species_term(species)
    canonical_name = species_term.canonical_name if species_term is not None else species
    return _SPECIES_TO_ATLAS.get(canonical_name)


def get_brain_region_term(location: str, species: str = "Mus musculus") -> BrainRegionTerm | None:
    """
    Resolve a free-text location string to an Allen brain-atlas term for a species.

    The lookup is high-precision: it matches an exact Allen acronym (case-sensitive, e.g.
    ``"CA1"``), a canonical structure name (case-insensitive, e.g. ``"caudoputamen"``), or a small
    set of common informal names and abbreviations (e.g. ``"hippocampus"``, ``"V1"``). Anything it
    does not recognize returns ``None``.

    The atlas is chosen from ``species``: ``"Mus musculus"`` (default) uses the Allen Mouse Brain
    Atlas and ``"Homo sapiens"`` the Allen Human Brain Atlas. Common names (e.g. ``"mouse"``,
    ``"human"``) are accepted. A species without a supported atlas returns ``None``.

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
