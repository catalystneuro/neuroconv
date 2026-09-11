"""Tools for recommending standardized ontology terms for NWB metadata and writing them as HERD.

Two layers, deliberately separate:

- **inference** -- ``infer_species_ontology_metadata`` / ``infer_strain_ontology_metadata`` /
  ``infer_brain_region_ontology_metadata`` / ``infer_anatomy_ontology_metadata`` (and the
  ``get_*_term`` primitives they use) resolve free-text values to ontology terms and write those
  terms into ``metadata`` next to the value they describe. This step guesses; run it when you want
  NeuroConv to propose terms.
- **annotation** -- ``add_species_external_resource`` / ``add_strain_external_resource`` /
  ``add_brain_region_external_resources`` / ``add_anatomy_external_resources`` take the terms
  already stated in ``metadata`` and write them into the file as HERD references. This step is
  deterministic and is what a conversion runs automatically.
"""

from ._anatomy import (
    ANATOMY_TERMS,
    AnatomyTerm,
    get_anatomy_term,
    infer_anatomy_ontology_metadata,
)
from ._brain_regions import (
    HBA_TERMS,
    MBA_TERMS,
    UBERON_TERMS,
    BrainRegionTerm,
    get_brain_region_term,
    infer_brain_region_ontology_metadata,
)
from ._external_resources import (
    add_anatomy_external_resources,
    add_brain_region_external_resources,
    add_species_external_resource,
    add_strain_external_resource,
)
from ._species import (
    SPECIES_TERMS,
    SpeciesTerm,
    get_species_suggestion,
    get_species_term,
    infer_species_ontology_metadata,
    validate_species,
)
from ._strain import (
    STRAIN_TERMS,
    StrainTerm,
    get_strain_suggestion,
    get_strain_term,
    infer_strain_ontology_metadata,
    validate_strain,
)

__all__ = [
    "ANATOMY_TERMS",
    "HBA_TERMS",
    "MBA_TERMS",
    "UBERON_TERMS",
    "SPECIES_TERMS",
    "STRAIN_TERMS",
    "AnatomyTerm",
    "BrainRegionTerm",
    "SpeciesTerm",
    "StrainTerm",
    "add_anatomy_external_resources",
    "add_brain_region_external_resources",
    "add_species_external_resource",
    "add_strain_external_resource",
    "get_anatomy_term",
    "get_brain_region_term",
    "get_species_suggestion",
    "get_species_term",
    "get_strain_suggestion",
    "get_strain_term",
    "infer_anatomy_ontology_metadata",
    "infer_brain_region_ontology_metadata",
    "infer_species_ontology_metadata",
    "infer_strain_ontology_metadata",
    "validate_species",
    "validate_strain",
]
