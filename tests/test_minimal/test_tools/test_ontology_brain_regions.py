"""Tests for the offline Allen brain-atlas (mouse MBA / human HBA) region lookup."""

import pytest

from neuroconv.tools.ontology import (
    HBA_TERMS,
    MBA_TERMS,
    BrainRegionTerm,
    get_brain_region_term,
)


class TestAtlasTermTables:
    @pytest.mark.parametrize("terms, prefix", [(MBA_TERMS, "MBA"), (HBA_TERMS, "HBA")])
    def test_tables_are_populated(self, terms, prefix):
        assert len(terms) > 50

    @pytest.mark.parametrize("terms, prefix", [(MBA_TERMS, "MBA"), (HBA_TERMS, "HBA")])
    def test_entries_are_self_consistent(self, terms, prefix):
        for acronym, term in terms.items():
            assert isinstance(term, BrainRegionTerm)
            assert term.acronym == acronym
            assert term.name
            assert term.curie.startswith(f"{prefix}:")

    def test_mouse_curie_and_uri(self):
        term = MBA_TERMS["CA1"]
        assert term.curie == "MBA:382"
        assert term.entity_uri == "https://purl.brain-bican.org/ontology/mbao/MBA_382"

    def test_human_curie_and_uri(self):
        term = HBA_TERMS["CA1"]
        assert term.curie == "HBA:12892"
        assert term.entity_uri == "https://purl.brain-bican.org/ontology/hbao/HBA_12892"

    @pytest.mark.parametrize("terms", [MBA_TERMS, HBA_TERMS])
    def test_curies_are_unique_within_an_atlas(self, terms):
        curies = [term.curie for term in terms.values()]
        assert len(curies) == len(set(curies))


class TestGetBrainRegionTermMouse:
    @pytest.mark.parametrize(
        "location, expected_acronym",
        [
            ("CA1", "CA1"),  # exact acronym
            ("VISp", "VISp"),  # case-specific acronym
            ("SSp-bfd", "SSp-bfd"),  # acronym with a hyphen
            ("Field CA1", "CA1"),  # canonical name
            ("caudoputamen", "CP"),  # canonical name, case-insensitive
            ("Nucleus accumbens", "ACB"),
            ("hippocampus", "HIP"),  # informal alias
            ("V1", "VISp"),  # abbreviation alias
            ("barrel cortex", "SSp-bfd"),
            ("locus coeruleus", "LC"),  # alternate spelling alias
        ],
    )
    def test_recognized_locations(self, location, expected_acronym):
        term = get_brain_region_term(location)  # default species is mouse
        assert term is not None
        assert term.acronym == expected_acronym
        assert term.curie.startswith("MBA:")

    def test_whitespace_is_stripped(self):
        assert get_brain_region_term("  CA1  ").acronym == "CA1"

    @pytest.mark.parametrize("location", ["", "   ", "not a region", "ca1", "visp"])
    def test_unrecognized_locations_return_none(self, location):
        # Note: acronym matching is case-sensitive, so lowercase "ca1"/"visp" are not recognized.
        assert get_brain_region_term(location) is None

    @pytest.mark.parametrize("location", [None, 382, ["CA1"]])
    def test_non_string_returns_none(self, location):
        assert get_brain_region_term(location) is None


class TestGetBrainRegionTermHuman:
    @pytest.mark.parametrize(
        "location, expected_curie",
        [
            ("CA1", "HBA:12892"),  # same acronym as mouse, different atlas/id
            ("cerebral cortex", "HBA:4008"),  # canonical name
            ("Precuneus", "HBA:4118"),  # canonical name, case-insensitive
            ("hippocampus", "HBA:4249"),  # alias -> hippocampal formation
            ("caudate", "HBA:4278"),  # alias
            ("nucleus accumbens", "HBA:4290"),
        ],
    )
    def test_recognized_human_locations(self, location, expected_curie):
        term = get_brain_region_term(location, species="Homo sapiens")
        assert term is not None
        assert term.curie == expected_curie

    def test_same_acronym_resolves_per_species(self):
        # "MB" is the mouse midbrain but the human mammillary body.
        assert get_brain_region_term("MB", species="Mus musculus").curie == "MBA:313"
        assert get_brain_region_term("MB", species="Homo sapiens").curie == "HBA:12909"

    def test_common_name_species_is_accepted(self):
        assert get_brain_region_term("cerebral cortex", species="human").curie == "HBA:4008"

    @pytest.mark.parametrize("species", ["Rattus norvegicus", "Danio rerio", None])
    def test_species_without_atlas_returns_none(self, species):
        assert get_brain_region_term("CA1", species=species) is None
