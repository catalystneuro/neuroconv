"""Tests for the offline species term recommendation tools."""

import pytest

from neuroconv.tools.ontology import (
    SPECIES_TERMS,
    SpeciesTerm,
    get_species_suggestion,
    get_species_term,
    validate_species,
)


class TestSpeciesTermsTable:
    def test_entries_are_species_terms_with_ncbitaxon_ids(self):
        for canonical_name, term in SPECIES_TERMS.items():
            assert isinstance(term, SpeciesTerm)
            assert term.canonical_name == canonical_name
            assert term.ncbitaxon_id.startswith("NCBITaxon:")

    def test_entity_uri_is_derived_from_ncbitaxon_id(self):
        term = SPECIES_TERMS["Mus musculus"]
        assert term.ncbitaxon_id == "NCBITaxon:10090"
        assert term.entity_uri == "http://purl.obolibrary.org/obo/NCBITaxon_10090"


class TestGetSpeciesSuggestion:
    @pytest.mark.parametrize(
        "species",
        [
            "Mus musculus",  # exact canonical name
            "http://purl.obolibrary.org/obo/NCBITaxon_10090",  # taxonomy URL
            "NCBITaxon:10090",  # CURIE
            "Octodon degus",  # valid but uncommon binomial, not in table
            "",  # empty
            None,  # not a string
            42,  # not a string
        ],
    )
    def test_returns_none_when_nothing_to_suggest(self, species):
        assert get_species_suggestion(species) is None

    def test_common_name_suggestion(self):
        suggestion = get_species_suggestion("mouse")
        assert suggestion is not None
        term, reason = suggestion
        assert term.canonical_name == "Mus musculus"
        assert term.ncbitaxon_id == "NCBITaxon:10090"
        assert "common name" in reason

    def test_common_name_is_case_insensitive_and_stripped(self):
        term, _ = get_species_suggestion("  Rhesus Macaque  ")
        assert term.canonical_name == "Macaca mulatta"

    def test_typo_suggestion(self):
        suggestion = get_species_suggestion("Homo sapien")
        assert suggestion is not None
        term, reason = suggestion
        assert term.canonical_name == "Homo sapiens"
        assert "closely matches" in reason


class TestGetSpeciesTerm:
    def test_exact_canonical_name_resolves(self):
        term = get_species_term("Mus musculus")
        assert term.canonical_name == "Mus musculus"
        assert term.ncbitaxon_id == "NCBITaxon:10090"

    def test_common_name_resolves(self):
        term = get_species_term("mouse")
        assert term.canonical_name == "Mus musculus"

    def test_typo_resolves(self):
        term = get_species_term("Homo sapien")
        assert term.canonical_name == "Homo sapiens"

    @pytest.mark.parametrize("species", ["Octodon degus", "", None, 42])
    def test_unrecognized_returns_none(self, species):
        assert get_species_term(species) is None


class TestValidateSpecies:
    def test_no_warning_for_canonical_name(self, recwarn):
        result = validate_species("Mus musculus")
        assert result is None
        assert len(recwarn) == 0

    def test_no_warning_for_none(self, recwarn):
        assert validate_species(None) is None
        assert len(recwarn) == 0

    def test_no_warning_for_unknown_binomial(self, recwarn):
        assert validate_species("Octodon degus") is None
        assert len(recwarn) == 0

    def test_warns_and_returns_term_for_common_name(self):
        with pytest.warns(UserWarning, match="Mus musculus"):
            term = validate_species("mouse")
        assert term.canonical_name == "Mus musculus"
        assert term.ncbitaxon_id == "NCBITaxon:10090"

    def test_warning_message_points_to_bioregistry(self):
        with pytest.warns(UserWarning, match="bioregistry.io/NCBITaxon:9606"):
            validate_species("human")
