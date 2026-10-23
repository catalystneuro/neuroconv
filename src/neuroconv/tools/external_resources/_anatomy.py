"""Lightweight, offline recognition of general anatomical structures as UBERON terms.

This is deliberately independent from ``_brain_regions.py``: brain-region annotation targets
``location`` fields (the electrodes table, electrode groups, imaging planes, the
``FiberPhotometryTable``) and is resolved per-species against an Allen atlas. Anatomy annotation
targets a different site -- individual body-part names in an ``ndx-pose`` ``Skeleton.nodes`` array
(pose-estimation keypoints) -- and uses one species-agnostic vocabulary of skeleton parts and
muscles backed by `UBERON <https://bioregistry.io/registry/uberon>`_
(``term_sets/general_anatomy.yaml``), not an atlas selected per species. When the optional
``neuro-termsets`` package is installed, its general-anatomy terms (organs, nerves, limbs, retina,
vibrissa) are merged in.

The lookup is high-precision, same as the other ontology tools here: it recognizes a curated set
of canonical structure names and a handful of common informal spellings, and returns ``None`` for
anything else (e.g. a lab-specific keypoint name like ``"EarL"``) rather than guessing.
"""

from dataclasses import dataclass

from pynwb import NWBFile

from ._term_sets import _build_alias_table, _unwrapped, _ValueMatcher, load_term_set

__all__ = ["ANATOMY_TERMS", "AnatomyTerm", "get_anatomy_term", "infer_anatomy_external_resources"]


@dataclass(frozen=True)
class AnatomyTerm:
    """A general anatomical structure and its UBERON ontology reference."""

    name: str
    curie: str  # entity CURIE, e.g. "UBERON:0002380"
    entity_uri: str  # resolvable entity URI (usable as a HERD ``entity_uri``)


_GENERAL_ANATOMY_TERM_SET = load_term_set("general_anatomy.yaml")

# Canonical structure name -> AnatomyTerm, from the curated general-anatomy TermSet.
ANATOMY_TERMS: dict[str, AnatomyTerm] = {
    info.value: AnatomyTerm(name=info.value, curie=info.curie, entity_uri=info.entity_uri)
    for info in _GENERAL_ANATOMY_TERM_SET.values()
}

# Matches each canonical structure name in any letter case and the common informal names and
# abbreviations from the term set's ``aliases``. Near misses are not matched.
_ANATOMY_MATCHER = _ValueMatcher(
    values=tuple(ANATOMY_TERMS),
    alias_table=_build_alias_table(_GENERAL_ANATOMY_TERM_SET, include_values=True),
    identifier_prefixes=("http://", "https://", "uberon:"),
    alias_reason="is an informal name",
    close_match_reason=None,
)


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
    canonical_name = _ANATOMY_MATCHER.resolve(name)
    return ANATOMY_TERMS[canonical_name] if canonical_name is not None else None


def _skeleton_nodes(nwbfile: NWBFile) -> list:
    """Every ``(skeleton, node name)`` pair on the file, each node name once per ``Skeleton``.

    ``ndx-pose`` ``Skeleton`` objects are found by type wherever they sit (NeuroConv's own
    pose-estimation interfaces write them to ``processing["behavior"]["Skeletons"]``, other tools may
    not), so ``ndx-pose`` does not have to be installed for the rest of the file to work.
    """
    skeletons = [obj for obj in nwbfile.objects.values() if getattr(obj, "neurodata_type", None) == "Skeleton"]
    return [(skeleton, node_name) for skeleton in skeletons for node_name in dict.fromkeys(_unwrapped(skeleton.nodes))]


def infer_anatomy_external_resources(nwbfile: NWBFile, node_structures: dict[str, str] | None = None) -> dict:
    """
    Infer anatomy terms for the file's skeleton node names, as ``{"ExternalResources": {"anatomy": ...}}``.

    This is the **inference** half of anatomy annotation: it walks every ``ndx-pose``
    ``Skeleton.nodes`` entry on ``nwbfile`` (pose-estimation keypoints, e.g. ``"Snout"``,
    ``"Shoulder"``), resolves each distinct name to a UBERON term with :func:`get_anatomy_term`, and
    returns explicit ``{"id": ..., "uri": ...}`` terms keyed by the node name. The deterministic
    :func:`neuroconv.tools.external_resources.add_anatomy_external_resources` then writes those terms
    into the file as HERD references.

    Skeletons usually name keypoints with a side or position (``"ShoulderLeft"``, ``"SpineFront"``),
    which the curated table does not recognize. ``node_structures`` states the structure such a node
    tracks (``{"ShoulderLeft": "Shoulder"}``); the node is then resolved through that structure name,
    and the result is still keyed by the node name as written. Nodes it does not list are looked up
    as they are.

    Nothing is modified. Merge the result under your metadata so that terms you wrote yourself win::

        metadata = dict_deep_update(infer_anatomy_external_resources(nwbfile), metadata, append_list=False)

    Parameters
    ----------
    nwbfile : NWBFile
        A populated file (data already added) whose ``Skeleton`` node names are read.
    node_structures : dict of str to str, optional
        ``{node name: structure name}`` for nodes whose name is not itself a recognized structure.
        Each structure name must resolve with :func:`get_anatomy_term`. Entries for nodes the file
        does not have are ignored.

    Returns
    -------
    dict
        ``{"ExternalResources": {"anatomy": {node name: term}}}``, or ``{}`` when the file has no
        ``Skeleton`` or no node name resolves.

    Raises
    ------
    ValueError
        If a structure name in ``node_structures`` is not recognized.
    """
    node_terms = {}
    for node_name, structure_name in (node_structures or {}).items():
        node_terms[node_name] = get_anatomy_term(structure_name)
        if node_terms[node_name] is None:
            raise ValueError(
                f"node_structures maps node {node_name!r} to {structure_name!r}, which is not a recognized "
                "anatomical structure. Use a name or alias from ANATOMY_TERMS, or state the node's term "
                'in metadata["ExternalResources"]["anatomy"] instead.'
            )

    anatomy = {}
    for node_name in dict.fromkeys(node_name for _, node_name in _skeleton_nodes(nwbfile)):
        term = node_terms[node_name] if node_name in node_terms else get_anatomy_term(node_name)
        if term is not None:
            anatomy[node_name] = {"id": term.curie, "uri": term.entity_uri}

    return {"ExternalResources": {"anatomy": anatomy}} if anatomy else {}
