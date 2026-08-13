"""Lightweight, offline recommendation of standardized species terms.

NWB stores ``Subject.species`` as a binomial Latin name (or a taxonomy URL). To make
files interoperable and to support downstream external-resource annotation (HERD /
NCBITaxon), this module recognizes common neuroscience species and gently suggests the
canonical Latin binomial and its NCBITaxon identifier when a user supplies a common name
(``"mouse"``) or a likely typo (``"Homo sapien"``).

This is intentionally a small curated table rather than a full ontology client: it runs
offline, has no extra dependencies, and only emits a suggestion when it is confident there
is a better term. Valid-but-uncommon species pass silently.
"""

import difflib
import warnings
from dataclasses import dataclass

from ._term_sets import load_term_set

__all__ = [
    "SPECIES_TERMS",
    "SpeciesTerm",
    "get_species_suggestion",
    "get_species_term",
    "validate_species",
]


@dataclass(frozen=True)
class SpeciesTerm:
    """A canonical species term with its NCBITaxon external identifier."""

    canonical_name: str
    ncbitaxon_id: str
    entity_uri: str  # resolvable URI for the NCBITaxon entity (usable as a HERD ``entity_uri``)


# Canonical Latin binomial -> SpeciesTerm, from the curated species TermSet.
SPECIES_TERMS: dict[str, SpeciesTerm] = {
    info.value: SpeciesTerm(canonical_name=info.value, ncbitaxon_id=info.curie, entity_uri=info.entity_uri)
    for info in load_term_set("species.yaml").values()
}


# Common (English) names -> canonical Latin binomial. Keys are compared case-insensitively.
_COMMON_NAME_TO_CANONICAL: dict[str, str] = {
    "mouse": "Mus musculus",
    "house mouse": "Mus musculus",
    "rat": "Rattus norvegicus",
    "norway rat": "Rattus norvegicus",
    "human": "Homo sapiens",
    "macaque": "Macaca mulatta",
    "rhesus macaque": "Macaca mulatta",
    "rhesus monkey": "Macaca mulatta",
    "cynomolgus macaque": "Macaca fascicularis",
    "crab-eating macaque": "Macaca fascicularis",
    "marmoset": "Callithrix jacchus",
    "common marmoset": "Callithrix jacchus",
    "ferret": "Mustela putorius furo",
    "zebrafish": "Danio rerio",
    "fruit fly": "Drosophila melanogaster",
    "fly": "Drosophila melanogaster",
    "worm": "Caenorhabditis elegans",
    "c. elegans": "Caenorhabditis elegans",
    "chicken": "Gallus gallus",
    "pig": "Sus scrofa",
    "rabbit": "Oryctolagus cuniculus",
    "guinea pig": "Cavia porcellus",
    "cat": "Felis catus",
    "dog": "Canis lupus familiaris",
    "sheep": "Ovis aries",
    "hamster": "Mesocricetus auratus",
    "golden hamster": "Mesocricetus auratus",
    "syrian hamster": "Mesocricetus auratus",
    "opossum": "Monodelphis domestica",
    "zebra finch": "Taeniopygia guttata",
    "axolotl": "Ambystoma mexicanum",
    "goldfish": "Carassius auratus",
    "honeybee": "Apis mellifera",
    "honey bee": "Apis mellifera",
}


def get_species_suggestion(species: str) -> tuple[SpeciesTerm, str] | None:
    """
    Suggest a canonical species term for a user-provided species string.

    The lookup is high-precision: it only returns a suggestion when ``species`` is a
    recognized common name or a close typo of a known Latin binomial. An exact match to a
    known canonical name, an unrecognized (but possibly valid) binomial, or a taxonomy URL
    all return ``None`` (nothing to suggest).

    Parameters
    ----------
    species : str
        The species value as it would be written to ``Subject.species``.

    Returns
    -------
    tuple of (SpeciesTerm, str) or None
        The suggested canonical term and a human-readable reason for the suggestion, or
        ``None`` when no confident suggestion is available.
    """
    if not isinstance(species, str):
        return None

    stripped = species.strip()
    if stripped == "":
        return None

    # Already a canonical Latin binomial we recognize -> nothing to suggest.
    if stripped in SPECIES_TERMS:
        return None

    # A taxonomy URL is already a machine-readable reference -> leave it alone.
    lowered = stripped.lower()
    if lowered.startswith(("http://", "https://")) or lowered.startswith("ncbitaxon:"):
        return None

    # Recognized common (English) name.
    if lowered in _COMMON_NAME_TO_CANONICAL:
        canonical_name = _COMMON_NAME_TO_CANONICAL[lowered]
        reason = f"{species!r} is a common name"
        return SPECIES_TERMS[canonical_name], reason

    # Likely typo of a known binomial (e.g. "Homo sapien" -> "Homo sapiens").
    close_matches = difflib.get_close_matches(stripped, SPECIES_TERMS.keys(), n=1, cutoff=0.85)
    if close_matches:
        canonical_name = close_matches[0]
        reason = f"{species!r} closely matches a known species name"
        return SPECIES_TERMS[canonical_name], reason

    return None


def get_species_term(species: str | None) -> SpeciesTerm | None:
    """
    Resolve a species value to its canonical term, including exact canonical matches.

    Unlike :func:`get_species_suggestion` (which only fires when there is a *better* term to
    recommend), this returns the :class:`SpeciesTerm` whenever the species can be recognized
    at all: an exact canonical binomial, a common name, or a likely typo. It is the lookup
    used to attach an NCBITaxon external-resource reference to an already-valid species value.

    Parameters
    ----------
    species : str or None
        The species value as it would be written to ``Subject.species``.

    Returns
    -------
    SpeciesTerm or None
        The canonical term for a recognized species, or ``None`` when it cannot be resolved.
    """
    if not isinstance(species, str):
        return None

    stripped = species.strip()
    if stripped in SPECIES_TERMS:
        return SPECIES_TERMS[stripped]

    suggestion = get_species_suggestion(species)
    return suggestion[0] if suggestion is not None else None


def validate_species(species: str | None) -> SpeciesTerm | None:
    """
    Warn (non-blocking) when a better standardized species term is available.

    This never raises and never blocks conversion; it only emits a ``UserWarning`` with a
    concrete suggestion when ``species`` is a recognized common name or a likely typo. It
    is safe to call on any metadata value, including ``None``.

    Parameters
    ----------
    species : str or None
        The species value as it would be written to ``Subject.species``.

    Returns
    -------
    SpeciesTerm or None
        The suggested canonical term (also surfaced via the warning), or ``None`` when no
        suggestion was made.
    """
    if species is None:
        return None

    suggestion = get_species_suggestion(species)
    if suggestion is None:
        return None

    term, reason = suggestion
    warnings.warn(
        f"Subject species {reason}. Consider using the Latin binomial "
        f"{term.canonical_name!r} ({term.ncbitaxon_id}) for interoperability. "
        f"See https://bioregistry.io/{term.ncbitaxon_id}",
        UserWarning,
        stacklevel=2,
    )
    return term
