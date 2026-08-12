"""Lightweight, offline recognition of general anatomical structures as UBERON terms.

This is deliberately independent from ``_brain_regions.py``: brain-region annotation targets
``location`` fields (the electrodes table, electrode groups, imaging planes, the
``FiberPhotometryTable``) and is resolved per-species against an Allen atlas. Anatomy annotation
targets a different site -- individual body-part names in an ``ndx-pose`` ``Skeleton.nodes`` array
(pose-estimation keypoints) -- and uses one species-agnostic vocabulary of skeleton parts and
muscles backed by `UBERON <https://bioregistry.io/registry/uberon>`_
(``term_sets/general_anatomy.yaml``), not an atlas selected per species.

The lookup is high-precision, same as the other ontology tools here: it recognizes a curated set
of canonical structure names and a handful of common informal spellings, and returns ``None`` for
anything else (e.g. a lab-specific keypoint name like ``"EarL"``) rather than guessing.
"""

from dataclasses import dataclass

from ._term_sets import load_term_set

__all__ = ["ANATOMY_TERMS", "AnatomyTerm", "get_anatomy_term"]


@dataclass(frozen=True)
class AnatomyTerm:
    """A general anatomical structure and its UBERON ontology reference."""

    name: str
    curie: str  # entity CURIE, e.g. "UBERON:0002380"
    entity_uri: str  # resolvable entity URI (usable as a HERD ``entity_uri``)


# Canonical structure name -> AnatomyTerm, from the curated general-anatomy TermSet.
ANATOMY_TERMS: dict[str, AnatomyTerm] = {
    info.value: AnatomyTerm(name=info.value, curie=info.curie, entity_uri=info.entity_uri)
    for info in load_term_set("general_anatomy.yaml").values()
}

_LOWER_TO_CANONICAL: dict[str, str] = {name.lower(): name for name in ANATOMY_TERMS}

# Common informal names and abbreviations -> canonical structure name. Compared case-insensitively.
_ALIAS_TO_CANONICAL: dict[str, str] = {
    "nose": "Snout",
    "muzzle": "Snout",
    "pinna": "Ear",
    "external ear": "Ear",
    "forepaw": "Hand",
    "fore paw": "Hand",
    "manus": "Hand",
    "hindpaw": "Foot",
    "hind paw": "Foot",
    "pes": "Foot",
    "carpus": "Wrist",
    "tarsus": "Ankle",
    "tarsal region": "Ankle",
    "tailbase": "Tail",
    "tail base": "Tail",
    "arm": "Upper arm",
    "vertebral column": "Spine",
    "backbone": "Spine",
    "trapezius": "Trapezius muscle",
    "masseter": "Masseter muscle",
    "scm": "Sternocleidomastoid",
}


def get_anatomy_term(name: str | None) -> AnatomyTerm | None:
    """
    Resolve a free-text anatomical structure name to a UBERON term.

    The lookup is case-insensitive and high-precision: it matches an exact canonical structure
    name (e.g. ``"Trapezius muscle"``) or a small set of common informal names and abbreviations
    (e.g. ``"nose"``, ``"forepaw"``, ``"trapezius"``). Anything it does not recognize -- including
    lab-specific keypoint names with laterality markers (e.g. ``"EarL"``) -- returns ``None``.

    Parameters
    ----------
    name : str or None
        The anatomical structure name (e.g. an ``ndx-pose`` ``Skeleton`` node name).

    Returns
    -------
    AnatomyTerm or None
        The recognized term, or ``None`` when the string cannot be resolved.
    """
    if not isinstance(name, str):
        return None
    stripped = name.strip()
    if stripped == "":
        return None
    lowered = stripped.lower()
    canonical_name = _LOWER_TO_CANONICAL.get(lowered) or _ALIAS_TO_CANONICAL.get(lowered)
    return ANATOMY_TERMS.get(canonical_name) if canonical_name is not None else None
