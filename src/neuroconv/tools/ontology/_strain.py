"""Lightweight, offline recommendation of standardized strain terms.

NWB stores ``Subject.strain`` as free text (e.g. ``"C57BL/6J"``, ``"Long-Evans"``). To make files
interoperable and to support downstream external-resource annotation (HERD / RRID), this module
recognizes common laboratory rodent strains and gently suggests the canonical designation and its
RRID (Research Resource Identifier) when a user supplies an informal variant spelling (e.g.
``"black 6"``, ``"Long Evans"``).

This is intentionally a small curated table rather than a full ontology client: it runs offline,
has no extra dependencies, and only emits a suggestion when it is confident there is a better term.
Valid-but-uncurated strains pass silently.
"""

import difflib
import warnings
from dataclasses import dataclass

from ._term_sets import load_term_set

__all__ = [
    "STRAIN_TERMS",
    "StrainTerm",
    "get_strain_suggestion",
    "get_strain_term",
    "validate_strain",
]


@dataclass(frozen=True)
class StrainTerm:
    """A canonical strain term with its RRID external identifier."""

    canonical_name: str
    rrid: str
    entity_uri: str  # resolvable URI for the RRID entity (usable as a HERD ``entity_uri``)


# Canonical strain designation -> StrainTerm, from the curated strain TermSet.
STRAIN_TERMS: dict[str, StrainTerm] = {
    info.value: StrainTerm(canonical_name=info.value, rrid=info.curie, entity_uri=info.entity_uri)
    for info in load_term_set("strains.yaml").values()
}


# Common informal spellings -> canonical strain designation. Keys are compared case-insensitively.
_COMMON_NAME_TO_CANONICAL: dict[str, str] = {
    "c57bl/6": "C57BL/6J",
    "c57bl6": "C57BL/6J",
    "black 6": "C57BL/6J",
    "b6": "C57BL/6J",
    "c57bl/6n": "C57BL/6N",
    "balb/c": "BALB/cJ",
    "balbc": "BALB/cJ",
    "129s1": "129S1/SvImJ",
    "129 s1": "129S1/SvImJ",
    "long evans": "Long-Evans",
    "long-evans rat": "Long-Evans",
    "sprague-dawley": "Sprague Dawley",
    "sprague dawley rat": "Sprague Dawley",
    "wistar rat": "Wistar",
}


def get_strain_suggestion(strain: str) -> tuple[StrainTerm, str] | None:
    """
    Suggest a canonical strain term for a user-provided strain string.

    The lookup is high-precision: it only returns a suggestion when ``strain`` is a recognized
    informal spelling or a close typo of a known strain designation. An exact match to a known
    canonical designation or an unrecognized (but possibly valid) strain both return ``None``
    (nothing to suggest).

    Parameters
    ----------
    strain : str
        The strain value as it would be written to ``Subject.strain``.

    Returns
    -------
    tuple of (StrainTerm, str) or None
        The suggested canonical term and a human-readable reason for the suggestion, or ``None``
        when no confident suggestion is available.
    """
    if not isinstance(strain, str):
        return None

    stripped = strain.strip()
    if stripped == "":
        return None

    # Already a canonical designation we recognize -> nothing to suggest.
    if stripped in STRAIN_TERMS:
        return None

    lowered = stripped.lower()
    if lowered.startswith(("http://", "https://")) or lowered.startswith("rrid:"):
        return None

    # Recognized informal spelling.
    if lowered in _COMMON_NAME_TO_CANONICAL:
        canonical_name = _COMMON_NAME_TO_CANONICAL[lowered]
        reason = f"{strain!r} is an informal spelling"
        return STRAIN_TERMS[canonical_name], reason

    # Likely typo of a known designation (e.g. "C57BL/6j" -> "C57BL/6J").
    close_matches = difflib.get_close_matches(stripped, STRAIN_TERMS.keys(), n=1, cutoff=0.85)
    if close_matches:
        canonical_name = close_matches[0]
        reason = f"{strain!r} closely matches a known strain designation"
        return STRAIN_TERMS[canonical_name], reason

    return None


def get_strain_term(strain: str | None) -> StrainTerm | None:
    """
    Resolve a strain value to its canonical term, including exact canonical matches.

    Unlike :func:`get_strain_suggestion` (which only fires when there is a *better* term to
    recommend), this returns the :class:`StrainTerm` whenever the strain can be recognized at
    all: an exact canonical designation, an informal spelling, or a likely typo. It is the lookup
    used to attach an RRID external-resource reference to an already-valid strain value.

    Parameters
    ----------
    strain : str or None
        The strain value as it would be written to ``Subject.strain``.

    Returns
    -------
    StrainTerm or None
        The canonical term for a recognized strain, or ``None`` when it cannot be resolved.
    """
    if not isinstance(strain, str):
        return None

    stripped = strain.strip()
    if stripped in STRAIN_TERMS:
        return STRAIN_TERMS[stripped]

    suggestion = get_strain_suggestion(strain)
    return suggestion[0] if suggestion is not None else None


def validate_strain(strain: str | None) -> StrainTerm | None:
    """
    Warn (non-blocking) when a better standardized strain term is available.

    This never raises and never blocks conversion; it only emits a ``UserWarning`` with a
    concrete suggestion when ``strain`` is a recognized informal spelling or a likely typo. It
    is safe to call on any metadata value, including ``None``.

    Parameters
    ----------
    strain : str or None
        The strain value as it would be written to ``Subject.strain``.

    Returns
    -------
    StrainTerm or None
        The suggested canonical term (also surfaced via the warning), or ``None`` when no
        suggestion was made.
    """
    if strain is None:
        return None

    suggestion = get_strain_suggestion(strain)
    if suggestion is None:
        return None

    term, reason = suggestion
    warnings.warn(
        f"Subject strain {reason}. Consider using {term.canonical_name!r} ({term.rrid}) "
        f"for interoperability. See https://bioregistry.io/{term.rrid}",
        UserWarning,
        stacklevel=2,
    )
    return term
