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

import warnings
from dataclasses import dataclass

from pynwb import NWBFile

from ._term_sets import _build_alias_table, _unwrapped, _ValueMatcher, load_term_set

__all__ = [
    "SPECIES_TERMS",
    "SpeciesTerm",
    "get_species_suggestion",
    "get_species_term",
    "infer_species_external_resources",
    "validate_species",
]


@dataclass(frozen=True)
class SpeciesTerm:
    """A canonical species term with its NCBITaxon external identifier."""

    canonical_name: str
    ncbitaxon_id: str
    entity_uri: str  # resolvable URI for the NCBITaxon entity (usable as a HERD ``entity_uri``)


_SPECIES_TERM_SET = load_term_set("species.yaml")

# Canonical Latin binomial -> SpeciesTerm, from the curated species TermSet.
SPECIES_TERMS: dict[str, SpeciesTerm] = {
    info.value: SpeciesTerm(canonical_name=info.value, ncbitaxon_id=info.curie, entity_uri=info.entity_uri)
    for info in _SPECIES_TERM_SET.values()
}

# Matches common (English) names from the species TermSet's ``aliases`` and likely typos of a
# Latin binomial (e.g. "Homo sapien" -> "Homo sapiens").
_SPECIES_MATCHER = _ValueMatcher(
    values=tuple(SPECIES_TERMS),
    alias_table=_build_alias_table(_SPECIES_TERM_SET, include_values=False),
    identifier_prefixes=("http://", "https://", "ncbitaxon:"),
    alias_reason="is a common name",
    close_match_reason="closely matches a known species name",
)


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
    suggestion = _SPECIES_MATCHER.suggest(species)
    if suggestion is None:
        return None
    canonical_name, reason = suggestion
    return SPECIES_TERMS[canonical_name], reason


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
    canonical_name = _SPECIES_MATCHER.resolve(species)
    return SPECIES_TERMS[canonical_name] if canonical_name is not None else None


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


def infer_species_external_resources(nwbfile: NWBFile) -> dict:
    """
    Infer the species term for the file's subject, as ``{"ExternalResources": {"species": ...}}``.

    This is the **inference** half of species annotation: it resolves ``nwbfile.subject.species`` (a
    common name, a likely typo, or a Latin binomial) to its NCBITaxon term via
    :func:`get_species_term` and returns an explicit ``{"id": ..., "uri": ...}`` term keyed by that
    value exactly as written (``"mouse"`` stays the key, because HERD links the term to
    ``Subject.species`` through that string). The deterministic
    :func:`neuroconv.tools.external_resources.add_species_external_resource` then writes that term into the file
    as a HERD reference.

    Nothing is modified. Merge the result under your metadata so that terms you wrote yourself win::

        metadata = dict_deep_update(infer_species_external_resources(nwbfile), metadata, append_list=False)

    It does not warn: the :func:`validate_species` suggestion for an informal value is emitted once,
    when :func:`neuroconv.tools.nwb_helpers.make_nwbfile_from_metadata` processes the metadata.

    Parameters
    ----------
    nwbfile : NWBFile
        The file whose ``subject.species`` is read.

    Returns
    -------
    dict
        ``{"ExternalResources": {"species": {species: term}}}``, or ``{}`` when the file has no subject or the
        species is not recognized.
    """
    subject = getattr(nwbfile, "subject", None)
    species = _unwrapped(getattr(subject, "species", None))
    term = get_species_term(species)
    if term is None:
        return {}
    return {"ExternalResources": {"species": {species: {"id": term.ncbitaxon_id, "uri": term.entity_uri}}}}
