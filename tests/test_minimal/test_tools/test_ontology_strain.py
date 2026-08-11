"""Tests for the offline strain term recommendation tools."""

import pytest

from neuroconv.tools.ontology import (
    STRAIN_TERMS,
    StrainTerm,
    get_strain_suggestion,
    get_strain_term,
    validate_strain,
)


class TestStrainTermsTable:
    def test_entries_are_strain_terms_with_rrids(self):
        for canonical_name, term in STRAIN_TERMS.items():
            assert isinstance(term, StrainTerm)
            assert term.canonical_name == canonical_name
            assert term.rrid.startswith("RRID:")

    def test_entity_uri_is_derived_from_rrid(self):
        term = STRAIN_TERMS["Long-Evans"]
        assert term.rrid == "RRID:RGD_2308852"
        assert term.entity_uri == "https://scicrunch.org/resolver/RRID:RGD_2308852"


class TestGetStrainSuggestion:
    @pytest.mark.parametrize(
        "strain",
        [
            "C57BL/6J",  # exact canonical name
            "https://scicrunch.org/resolver/RRID:IMSR_JAX:000664",  # resolvable URL
            "RRID:IMSR_JAX:000664",  # CURIE
            "Octodon degus strain X",  # unrecognized, not in table
            "",  # empty
            None,  # not a string
            42,  # not a string
        ],
    )
    def test_returns_none_when_nothing_to_suggest(self, strain):
        assert get_strain_suggestion(strain) is None

    def test_informal_spelling_suggestion(self):
        suggestion = get_strain_suggestion("black 6")
        assert suggestion is not None
        term, reason = suggestion
        assert term.canonical_name == "C57BL/6J"
        assert term.rrid == "RRID:IMSR_JAX:000664"
        assert "informal spelling" in reason

    def test_informal_spelling_is_case_insensitive_and_stripped(self):
        term, _ = get_strain_suggestion("  Long Evans  ")
        assert term.canonical_name == "Long-Evans"

    def test_typo_suggestion(self):
        suggestion = get_strain_suggestion("Sprague Dawly")
        assert suggestion is not None
        term, reason = suggestion
        assert term.canonical_name == "Sprague Dawley"
        assert "closely matches" in reason


class TestGetStrainTerm:
    def test_exact_canonical_name_resolves(self):
        term = get_strain_term("Long-Evans")
        assert term.canonical_name == "Long-Evans"
        assert term.rrid == "RRID:RGD_2308852"

    def test_informal_spelling_resolves(self):
        term = get_strain_term("long evans")
        assert term.canonical_name == "Long-Evans"

    def test_typo_resolves(self):
        term = get_strain_term("Sprague Dawly")
        assert term.canonical_name == "Sprague Dawley"

    @pytest.mark.parametrize("strain", ["Octodon degus strain X", "", None, 42])
    def test_unrecognized_returns_none(self, strain):
        assert get_strain_term(strain) is None


class TestValidateStrain:
    def test_no_warning_for_canonical_name(self, recwarn):
        result = validate_strain("Long-Evans")
        assert result is None
        assert len(recwarn) == 0

    def test_no_warning_for_none(self, recwarn):
        assert validate_strain(None) is None
        assert len(recwarn) == 0

    def test_no_warning_for_unrecognized_strain(self, recwarn):
        assert validate_strain("Octodon degus strain X") is None
        assert len(recwarn) == 0

    def test_warns_and_returns_term_for_informal_spelling(self):
        with pytest.warns(UserWarning, match="C57BL/6J"):
            term = validate_strain("black 6")
        assert term.canonical_name == "C57BL/6J"
        assert term.rrid == "RRID:IMSR_JAX:000664"

    def test_warning_message_points_to_bioregistry(self):
        with pytest.warns(UserWarning, match="bioregistry.io/RRID:RGD_2308852"):
            validate_strain("long evans")
