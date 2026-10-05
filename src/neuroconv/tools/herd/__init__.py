"""Tools for recommending standardized ontology terms for NWB metadata and writing them as HERD.

Two layers, deliberately separate:

- **inference** -- ``infer_species_herd_metadata`` / ``infer_brain_region_herd_metadata``
  (and the ``get_*_term`` primitives they use) read a populated ``NWBFile``, resolve its free-text
  values to ontology terms and return them as a ``{"HERD": {...}}`` metadata block, keyed by the
  value they describe. This step guesses; run it when you want NeuroConv to propose terms, and merge
  the result under your metadata with ``dict_deep_update(inferred, metadata, append_list=False)``.
- **annotation** -- ``add_herd_annotations_to_nwbfile`` (which runs the per-domain
  ``add_species_external_resource`` / ``add_brain_region_external_resources``) takes the terms
  already stated in ``metadata`` and writes them into the file as HERD references. This step is
  deterministic, and ``run_conversion`` runs it automatically just before writing.
"""

from ._brain_regions import (
    HBA_TERMS,
    MBA_TERMS,
    UBERON_TERMS,
    BrainRegionTerm,
    get_brain_region_term,
    infer_brain_region_herd_metadata,
)
from ._external_resources import (
    add_brain_region_external_resources,
    add_herd_annotations_to_nwbfile,
    add_species_external_resource,
)
from ._species import (
    SPECIES_TERMS,
    SpeciesTerm,
    get_species_suggestion,
    get_species_term,
    infer_species_herd_metadata,
    validate_species,
)

__all__ = [
    "HBA_TERMS",
    "MBA_TERMS",
    "UBERON_TERMS",
    "SPECIES_TERMS",
    "BrainRegionTerm",
    "SpeciesTerm",
    "add_brain_region_external_resources",
    "add_herd_annotations_to_nwbfile",
    "add_species_external_resource",
    "get_brain_region_term",
    "get_species_suggestion",
    "get_species_term",
    "infer_brain_region_herd_metadata",
    "infer_species_herd_metadata",
    "validate_species",
]
