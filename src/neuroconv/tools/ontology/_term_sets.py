"""Read the curated ontology term sets shipped with NeuroConv.

Each controlled vocabulary (species, mouse brain atlas, human brain atlas) is stored as a
`LinkML <https://linkml.io/>`_ TermSet YAML file under ``term_sets/`` -- the same format used by
HDMF's :class:`~hdmf.term_set.TermSet` (https://hdmf.readthedocs.io/en/stable/tutorials/plot_term_set.html).
These files are the source of truth mapping each permissible value to an ontology entity.

The format is small and stable, so NeuroConv reads it directly with PyYAML rather than taking a
dependency on ``linkml-runtime``; the files remain valid TermSets and can be loaded with
``hdmf.term_set.TermSet(term_schema_path=...)`` by anyone who wants to.

Bundled terms can be opportunistically extended by the community-maintained
`neuro-termsets <https://github.com/NeurodataWithoutBorders/neuro-termsets>`_ project, when it is
installed -- see :func:`load_upstream_term_set`. This is a soft, optional upgrade, not a
dependency: NeuroConv works exactly as it does today when ``neuro-termsets`` is absent.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

_TERM_SET_DIRECTORY = Path(__file__).parent / "term_sets"

# Bundled TermSet file name -> the equivalent term set name in the optional `neuro-termsets`
# package (queried via `neuro_termsets.get_termset_path(name)`). `neuro-termsets` is pre-production
# and these names are provisional; review this mapping as that project's layout stabilizes.
_UPSTREAM_TERM_SET_NAMES: dict[str, str] = {
    "species.yaml": "ncbitaxon",
    "uberon_common_regions.yaml": "uberon",
    "mouse_brain_atlas.yaml": "mba",
    "human_brain_atlas.yaml": "hba",
}


@dataclass(frozen=True)
class TermInfo:
    """One permissible value of a TermSet and its resolved ontology entity."""

    value: str  # the permissible value (e.g. "Mus musculus" or "CA1")
    curie: str  # the entity CURIE from the term's ``meaning`` (e.g. "NCBITaxon:10090")
    entity_uri: str  # the resolvable entity URI (the CURIE expanded via the schema ``prefixes``)
    description: str


def _parse_term_set_schema(schema: dict) -> dict[str, TermInfo]:
    """Parse an already-loaded LinkML TermSet schema into a ``{permissible value: TermInfo}`` mapping."""
    prefixes = schema.get("prefixes", {})
    # A NeuroConv TermSet defines a single enumeration of permissible values.
    (enumeration,) = schema["enums"].values()

    term_set = {}
    for value, term in enumeration["permissible_values"].items():
        curie = term["meaning"]
        prefix, local_identifier = curie.split(":", 1)
        entity_uri = prefixes[prefix] + local_identifier
        term_set[value] = TermInfo(
            value=value, curie=curie, entity_uri=entity_uri, description=term.get("description", "")
        )
    return term_set


def _load_term_set_file(path: Path) -> dict[str, TermInfo]:
    with open(path, encoding="utf-8") as file:
        schema = yaml.safe_load(file)
    return _parse_term_set_schema(schema)


@lru_cache(maxsize=None)
def load_upstream_term_set(file_name: str) -> dict[str, TermInfo] | None:
    """
    Best-effort lookup of a bundled term set's equivalent from the optional ``neuro-termsets`` package.

    `neuro-termsets <https://github.com/NeurodataWithoutBorders/neuro-termsets>`_ aims to be a
    shared, ontology-backed term set source for the NWB ecosystem, curated closer to the source
    ontologies than NeuroConv's own bundled snapshot. It is **not** a NeuroConv dependency: it is
    pre-production and not yet published to PyPI, so this is a purely opportunistic upgrade. Every
    failure mode -- the package is not installed, it doesn't recognize the requested term set name,
    or its file no longer parses as a TermSet -- is treated the same way: "unavailable", so callers
    fall back to the bundled file.

    Parameters
    ----------
    file_name : str
        The bundled TermSet file name whose upstream equivalent should be loaded (e.g.
        ``"species.yaml"``). Only file names listed in ``_UPSTREAM_TERM_SET_NAMES`` are looked up.

    Returns
    -------
    dict of str to TermInfo, or None
        The upstream term set, or ``None`` when it is unavailable for any reason.
    """
    upstream_name = _UPSTREAM_TERM_SET_NAMES.get(file_name)
    if upstream_name is None:
        return None

    try:
        import neuro_termsets

        path = neuro_termsets.get_termset_path(upstream_name)
        return _load_term_set_file(Path(path))
    except Exception:
        # `neuro-termsets` is pre-production: any failure here (not installed, a renamed or
        # restructured term set, a schema this version can no longer parse) just means "no
        # upstream term set available right now", not a NeuroConv error.
        return None


@lru_cache(maxsize=None)
def load_term_set(file_name: str) -> dict[str, TermInfo]:
    """
    Load a LinkML TermSet YAML file into a ``{permissible value: TermInfo}`` mapping.

    Reads NeuroConv's own bundled copy under ``term_sets/`` first. When the optional
    `neuro-termsets <https://github.com/NeurodataWithoutBorders/neuro-termsets>`_ package is
    installed and has a term set for ``file_name``, its terms are merged in on top -- preferred
    over the bundled ones for any value both define, and adding any value only it defines. Nothing
    changes when that package is absent, which is the default today.

    Parameters
    ----------
    file_name : str
        The TermSet file name under ``neuroconv/tools/ontology/term_sets`` (e.g. ``"species.yaml"``).

    Returns
    -------
    dict of str to TermInfo
        The permissible values, each with its CURIE and expanded entity URI.
    """
    term_set = _load_term_set_file(_TERM_SET_DIRECTORY / file_name)

    upstream_term_set = load_upstream_term_set(file_name)
    if upstream_term_set:
        term_set = {**term_set, **upstream_term_set}

    return term_set
