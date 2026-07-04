"""Tests for the offline Allen Mouse Brain Atlas brain-region lookup."""

import pytest

from neuroconv.tools.ontology import (
    MBA_TERMS,
    BrainRegionTerm,
    get_brain_region_term,
)


class TestMBATermsTable:
    def test_table_is_populated(self):
        assert len(MBA_TERMS) > 50

    def test_entries_are_self_consistent(self):
        for acronym, term in MBA_TERMS.items():
            assert isinstance(term, BrainRegionTerm)
            assert term.acronym == acronym
            assert isinstance(term.mba_id, int)
            assert term.name

    def test_curie_and_uri_derive_from_id(self):
        term = MBA_TERMS["CA1"]
        assert term.mba_id == 382
        assert term.curie == "MBA:382"
        assert term.entity_uri == "https://purl.brain-bican.org/ontology/mbao/MBA_382"

    def test_ids_are_unique(self):
        ids = [term.mba_id for term in MBA_TERMS.values()]
        assert len(ids) == len(set(ids))


class TestGetBrainRegionTerm:
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
        term = get_brain_region_term(location)
        assert term is not None
        assert term.acronym == expected_acronym

    def test_whitespace_is_stripped(self):
        assert get_brain_region_term("  CA1  ").acronym == "CA1"

    @pytest.mark.parametrize("location", ["", "   ", "not a region", "ca1", "visp"])
    def test_unrecognized_locations_return_none(self, location):
        # Note: acronym matching is case-sensitive, so lowercase "ca1"/"visp" are not recognized.
        assert get_brain_region_term(location) is None

    @pytest.mark.parametrize("location", [None, 382, ["CA1"]])
    def test_non_string_returns_none(self, location):
        assert get_brain_region_term(location) is None
