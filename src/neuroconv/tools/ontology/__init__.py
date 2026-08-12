"""Tools for recommending standardized ontology terms for NWB metadata."""

from ._brain_regions import (
    HBA_TERMS,
    MBA_TERMS,
    UBERON_TERMS,
    BrainRegionTerm,
    get_brain_region_term,
)
from ._external_resources import (
    OntologyAnnotationMixin,
    add_brain_region_external_resources,
    add_species_external_resource,
    add_strain_external_resource,
)
from ._species import (
    SPECIES_TERMS,
    SpeciesTerm,
    get_species_suggestion,
    get_species_term,
    validate_species,
)
from ._strain import (
    STRAIN_TERMS,
    StrainTerm,
    get_strain_suggestion,
    get_strain_term,
    validate_strain,
)

__all__ = [
    "HBA_TERMS",
    "MBA_TERMS",
    "UBERON_TERMS",
    "SPECIES_TERMS",
    "STRAIN_TERMS",
    "BrainRegionTerm",
    "OntologyAnnotationMixin",
    "SpeciesTerm",
    "StrainTerm",
    "add_brain_region_external_resources",
    "add_species_external_resource",
    "add_strain_external_resource",
    "get_brain_region_term",
    "get_species_suggestion",
    "get_species_term",
    "get_strain_suggestion",
    "get_strain_term",
    "validate_species",
    "validate_strain",
]
