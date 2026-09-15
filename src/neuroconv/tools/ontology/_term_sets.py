"""Read the curated ontology term sets shipped with NeuroConv.

Each controlled vocabulary (species, mouse brain atlas, human brain atlas) is stored as a
`LinkML <https://linkml.io/>`_ TermSet YAML file under ``term_sets/`` -- the same format used by
HDMF's :class:`~hdmf.term_set.TermSet` (https://hdmf.readthedocs.io/en/stable/tutorials/plot_term_set.html).
These files are the source of truth mapping each permissible value to an ontology entity.

The format is small and stable, so NeuroConv reads it directly with PyYAML rather than taking a
dependency on ``linkml-runtime``; the files remain valid TermSets and can be loaded with
``hdmf.term_set.TermSet(term_schema_path=...)`` by anyone who wants to.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

_TERM_SET_DIRECTORY = Path(__file__).parent / "term_sets"


@dataclass(frozen=True)
class TermInfo:
    """One permissible value of a TermSet and its resolved ontology entity."""

    value: str  # the permissible value (e.g. "Mus musculus" or "CA1")
    curie: str  # the entity CURIE from the term's ``meaning`` (e.g. "NCBITaxon:10090")
    entity_uri: str  # the resolvable entity URI (the CURIE expanded via the schema ``prefixes``)
    description: str


@lru_cache(maxsize=None)
def load_term_set(file_name: str) -> dict[str, TermInfo]:
    """
    Load a LinkML TermSet YAML file into a ``{permissible value: TermInfo}`` mapping.

    Parameters
    ----------
    file_name : str
        The TermSet file name under ``neuroconv/tools/ontology/term_sets`` (e.g. ``"species.yaml"``).

    Returns
    -------
    dict of str to TermInfo
        The permissible values, each with its CURIE and expanded entity URI.
    """
    with open(_TERM_SET_DIRECTORY / file_name, encoding="utf-8") as file:
        schema = yaml.safe_load(file)

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
