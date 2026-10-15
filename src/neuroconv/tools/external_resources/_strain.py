"""Lightweight, offline recommendation of standardized strain terms.

NWB stores ``Subject.strain`` as free text (e.g. ``"C57BL/6J"``, ``"Long-Evans"``). To make files
interoperable and to support downstream external-resource annotation (HERD / RRID), this module
recognizes common laboratory strains and gently suggests the canonical designation and its
RRID (Research Resource Identifier) when a user supplies an informal variant spelling (e.g.
``"long evans"``, ``"wistar rat"``).

This is intentionally a small curated table rather than a full ontology client: it runs offline,
has no extra dependencies, and only emits a suggestion when it is confident there is a better term.
Valid-but-uncurated strains pass silently. The bundled table covers mouse and rat strains; when the
optional ``neuro-termsets`` package is installed, its worm, fly, zebrafish, and transgenic Cre-driver
and reporter mouse lines are merged in.
"""

import warnings
from dataclasses import dataclass

from pynwb import NWBFile

from ._term_sets import _build_alias_table, _unwrapped, load_term_set

__all__ = [
    "STRAIN_TERMS",
    "StrainTerm",
    "get_strain_suggestion",
    "get_strain_term",
    "infer_strain_external_resources",
    "validate_strain",
]


@dataclass(frozen=True)
class StrainTerm:
    """A canonical strain term with its RRID external identifier."""

    canonical_name: str
    rrid: str
    entity_uri: str  # resolvable URI for the RRID entity (usable as a HERD ``entity_uri``)


_STRAIN_TERM_SET = load_term_set("strains.yaml")

# Canonical strain designation -> StrainTerm, from the curated strain TermSet.
STRAIN_TERMS: dict[str, StrainTerm] = {
    info.value: StrainTerm(canonical_name=info.value, rrid=info.curie, entity_uri=info.entity_uri)
    for info in _STRAIN_TERM_SET.values()
}

# Common informal spellings -> canonical strain designation, from the strain TermSet's ``aliases``
# plus each canonical designation itself (so "c57bl/6j" resolves to "C57BL/6J").
# Keys are lower-cased and compared case-insensitively.
_COMMON_NAME_TO_CANONICAL: dict[str, str] = _build_alias_table(_STRAIN_TERM_SET, include_values=True)


def get_strain_suggestion(strain: str) -> tuple[StrainTerm, str] | None:
    """
    Suggest a canonical strain term for a user-provided strain string.

    The lookup is high-precision: it only returns a suggestion when ``strain`` is a recognized
    informal spelling of a known strain designation. An exact match to a known canonical
    designation or an unrecognized (but possibly valid) strain both return ``None`` (nothing to
    suggest). Near misses are not guessed, because real strain designations often differ from each
    other by one or two characters (``"C57BL/6NJ"`` is not ``"C57BL/6N"``).

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

    return None


def get_strain_term(strain: str | None) -> StrainTerm | None:
    """
    Resolve a strain value to its canonical term, including exact canonical matches.

    Unlike :func:`get_strain_suggestion` (which only fires when there is a *better* term to
    recommend), this returns the :class:`StrainTerm` whenever the strain can be recognized at
    all: an exact canonical designation or an informal spelling. It is the lookup
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
    concrete suggestion when ``strain`` is a recognized informal spelling. It
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


def infer_strain_external_resources(nwbfile: NWBFile) -> dict:
    """
    Infer the strain term for the file's subject, as ``{"ExternalResources": {"strain": ...}}``.

    This is the **inference** half of strain annotation: it resolves ``nwbfile.subject.strain`` (an
    informal spelling or a canonical designation) to its RRID term via
    :func:`get_strain_term` and returns an explicit ``{"id": ..., "uri": ...}`` term keyed by that
    value exactly as written (``"long evans"`` stays the key, because HERD links the term to
    ``Subject.strain`` through that string). The deterministic
    :func:`neuroconv.tools.external_resources.add_strain_external_resource` then writes that term into
    the file as a HERD reference.

    Nothing is modified. Merge the result under your metadata so that terms you wrote yourself win::

        metadata = dict_deep_update(infer_strain_external_resources(nwbfile), metadata, append_list=False)

    It does not warn: the :func:`validate_strain` suggestion for an informal value is emitted once,
    when :func:`neuroconv.tools.nwb_helpers.make_nwbfile_from_metadata` processes the metadata.

    Parameters
    ----------
    nwbfile : NWBFile
        The file whose ``subject.strain`` is read.

    Returns
    -------
    dict
        ``{"ExternalResources": {"strain": {strain: term}}}``, or ``{}`` when the file has no subject,
        no strain is set, or the strain is not recognized.
    """
    subject = getattr(nwbfile, "subject", None)
    strain = _unwrapped(getattr(subject, "strain", None))
    term = get_strain_term(strain)
    if term is None:
        return {}
    return {"ExternalResources": {"strain": {strain: {"id": term.rrid, "uri": term.entity_uri}}}}
