"""Tools for recommending standardized ontology terms for NWB metadata."""

from ._external_resources import add_species_external_resource
from ._species import (
    SPECIES_TERMS,
    SpeciesTerm,
    get_species_suggestion,
    get_species_term,
    validate_species,
)

__all__ = [
    "SPECIES_TERMS",
    "SpeciesTerm",
    "add_species_external_resource",
    "get_species_suggestion",
    "get_species_term",
    "validate_species",
]
