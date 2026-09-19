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

from pynwb import NWBFile

from ._term_sets import load_term_set

__all__ = ["ANATOMY_TERMS", "AnatomyTerm", "get_anatomy_term", "infer_anatomy_ontology_metadata"]


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


def _skeleton_node_names(nwbfile: NWBFile) -> list:
    """Every distinct ``ndx-pose`` ``Skeleton.nodes`` entry on the file, or ``[]`` if there is none.

    Reads ``nwbfile.processing["behavior"]["Skeletons"]``, the container path NeuroConv's own
    pose-estimation interfaces write to.
    """
    behavior_module = nwbfile.processing.get("behavior")
    if behavior_module is None:
        return []
    skeletons_container = behavior_module.data_interfaces.get("Skeletons")
    if skeletons_container is None:
        return []
    names: dict = {}
    for skeleton in skeletons_container.skeletons.values():
        names.update(dict.fromkeys(str(node_name) for node_name in skeleton.nodes))
    return list(names)


def infer_anatomy_ontology_metadata(nwbfile: NWBFile, metadata: dict) -> dict:
    """
    Fill ``metadata["PoseEstimation"]["ontology"]["anatomy"]`` from the file's skeleton node names.

    This is the **inference** half of anatomy annotation: it walks every ``ndx-pose``
    ``Skeleton.nodes`` entry on ``nwbfile`` (pose-estimation keypoints, e.g. ``"Snout"``,
    ``"Shoulder"``), resolves each distinct name to a UBERON term with :func:`get_anatomy_term`, and
    writes explicit ``{"id": ..., "uri": ...}`` terms under
    ``metadata["PoseEstimation"]["ontology"]["anatomy"]``. The deterministic
    :func:`neuroconv.tools.ontology.add_anatomy_external_resources` then writes those terms into the
    file as HERD references.

    The metadata is modified in place (and also returned). A name that does not resolve, or one
    already present in the map (a user-curated term is never overwritten), is left as is. This is a
    no-op when the file has no ``Skeleton`` or nothing resolves.

    Parameters
    ----------
    nwbfile : NWBFile
        A populated file (data already added) whose ``Skeleton`` node names are read.
    metadata : dict
        Conversion metadata. Terms are written under
        ``metadata["PoseEstimation"]["ontology"]["anatomy"]``.

    Returns
    -------
    dict
        The same ``metadata`` object, for chaining.
    """
    if not isinstance(metadata, dict):
        return metadata

    existing = metadata.get("PoseEstimation", {}).get("ontology", {}).get("anatomy", {})
    resolved = {}
    for node_name in _skeleton_node_names(nwbfile):
        if node_name in existing:
            continue
        term = get_anatomy_term(node_name)
        if term is not None:
            resolved[node_name] = {"id": term.curie, "uri": term.entity_uri}

    if resolved:
        anatomy = metadata.setdefault("PoseEstimation", {}).setdefault("ontology", {}).setdefault("anatomy", {})
        anatomy.update(resolved)

    return metadata
