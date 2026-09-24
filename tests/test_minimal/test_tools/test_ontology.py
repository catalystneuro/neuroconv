"""Tests for neuroconv.tools.ontology: term resolution, metadata inference, and HERD annotation."""

import sys
from datetime import datetime

import pytest
from dateutil.tz import tzutc
from pynwb import NWBFile
from pynwb.file import Subject

from neuroconv.tools.ontology import (
    HBA_TERMS,
    MBA_TERMS,
    SPECIES_TERMS,
    BrainRegionTerm,
    SpeciesTerm,
    add_brain_region_external_resources,
    add_species_external_resource,
    get_brain_region_term,
    get_species_suggestion,
    get_species_term,
    infer_brain_region_ontology_metadata,
    infer_species_ontology_metadata,
    validate_species,
)

MOUSE_SPECIES_TERM = {"id": "NCBITaxon:10090", "uri": "http://purl.obolibrary.org/obo/NCBITaxon_10090"}


def _make_nwbfile(species="Mus musculus", with_subject=True) -> NWBFile:
    nwbfile = NWBFile(
        session_description="d",
        identifier="id",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )
    if with_subject:
        nwbfile.subject = Subject(subject_id="s1", species=species)
    return nwbfile


def _add_electrodes(nwbfile: NWBFile, locations) -> None:
    device = nwbfile.create_device(name="probe")
    group = nwbfile.create_electrode_group(name="group0", description="d", location="unknown", device=device)
    for index, location in enumerate(locations):
        nwbfile.add_electrode(location=location, group=group, id=index)


def _optical_channel():
    from pynwb.ophys import OpticalChannel

    return OpticalChannel(name="channel0", description="d", emission_lambda=500.0)


def _add_icephys_ogen_and_injection(nwbfile: NWBFile, icephys_location, ogen_location, injection_location) -> None:
    """Add an intracellular electrode, an optogenetic stimulus site, and a viral vector injection.

    The injection sits inside the ``FiberPhotometry`` lab metadata, where NeuroConv's fiber-photometry
    tool puts it.
    """
    ndx_ophys_devices = pytest.importorskip("ndx_ophys_devices")
    ndx_fiber_photometry = pytest.importorskip("ndx_fiber_photometry")
    from pynwb.ogen import OptogeneticStimulusSite

    device = nwbfile.create_device(name="rig")
    nwbfile.create_icephys_electrode(name="electrode0", description="d", device=device, location=icephys_location)
    nwbfile.add_ogen_site(
        OptogeneticStimulusSite(
            name="site0", device=device, description="d", excitation_lambda=473.0, location=ogen_location
        )
    )

    viral_vector = ndx_ophys_devices.ViralVector(
        name="virus0", construct_name="AAV", description="d", manufacturer="m", titer_in_vg_per_ml=1e12
    )
    injection = ndx_ophys_devices.ViralVectorInjection(
        name="injection0",
        location=injection_location,
        hemisphere="left",
        reference="Bregma",
        ap_in_mm=1.0,
        ml_in_mm=1.0,
        dv_in_mm=1.0,
        volume_in_uL=0.5,
        viral_vector=viral_vector,
    )
    indicator = ndx_ophys_devices.Indicator(name="indicator0", label="GCaMP", description="d", manufacturer="m")
    nwbfile.add_lab_meta_data(
        ndx_fiber_photometry.FiberPhotometry(
            name="fiber_photometry",
            fiber_photometry_table=ndx_fiber_photometry.FiberPhotometryTable(
                name="fiber_photometry_table", description="d"
            ),
            fiber_photometry_viruses=ndx_fiber_photometry.FiberPhotometryViruses(viral_vectors=[viral_vector]),
            fiber_photometry_virus_injections=ndx_fiber_photometry.FiberPhotometryVirusInjections(
                viral_vector_injections=[injection]
            ),
            fiber_photometry_indicators=ndx_fiber_photometry.FiberPhotometryIndicators(indicators=[indicator]),
        )
    )


def _brain_regions_metadata(mapping: dict) -> dict:
    """A metadata dict carrying a file-wide ``ontology.brain_regions`` map."""
    return {"ontology": {"brain_regions": mapping}}


# ---------------------------------------------------------------------------
# Optional upstream term sets (neuro-termsets)
# ---------------------------------------------------------------------------


class TestUpstreamTermSets:
    """``neuro-termsets`` is not installed in this environment (and not yet on PyPI), so these tests
    fake the package via ``sys.modules`` rather than requiring it."""

    def setup_method(self):
        from neuroconv.tools.ontology._term_sets import load_term_set, load_upstream_term_set

        load_term_set.cache_clear()
        load_upstream_term_set.cache_clear()

    teardown_method = setup_method

    def test_absent_package_is_a_noop(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "neuro_termsets", None)  # makes ``import neuro_termsets`` fail

        from neuroconv.tools.ontology._term_sets import load_term_set, load_upstream_term_set

        assert load_upstream_term_set("species.yaml") is None
        assert load_term_set("species.yaml")["Mus musculus"].curie == "NCBITaxon:10090"

    def test_brain_region_term_sets_are_never_looked_up_upstream(self, monkeypatch):
        # neuro-termsets keys its brain-region files by full name, not acronym, so merging them
        # would corrupt the acronym-keyed atlases.
        requested = []

        class _RecordingNeuroTermsets:
            @staticmethod
            def get_termset_path(name):
                requested.append(name)
                raise FileNotFoundError(name)

        monkeypatch.setitem(sys.modules, "neuro_termsets", _RecordingNeuroTermsets())

        from neuroconv.tools.ontology._term_sets import load_upstream_term_set

        for file_name in ["mouse_brain_atlas.yaml", "human_brain_atlas.yaml", "uberon_common_regions.yaml"]:
            assert load_upstream_term_set(file_name) is None
        assert requested == []

    def test_mapped_names_exist_in_the_installed_neuro_termsets(self):
        neuro_termsets = pytest.importorskip("neuro_termsets")

        from neuroconv.tools.ontology._term_sets import _UPSTREAM_TERM_SET_NAMES

        available = neuro_termsets.get_available_termsets()
        for bundled_name, upstream_name in _UPSTREAM_TERM_SET_NAMES.items():
            assert upstream_name in available, f"{bundled_name} maps to {upstream_name!r}, not in {available}"

    def test_real_neuro_termsets_species_merge_keeps_bundled_terms_and_aliases(self):
        pytest.importorskip("neuro_termsets")

        from neuroconv.tools.ontology._term_sets import load_term_set, load_upstream_term_set

        assert load_upstream_term_set("species.yaml") is not None  # the mapped name really resolves
        merged = load_term_set("species.yaml")
        assert merged["Mus musculus"].curie == "NCBITaxon:10090"
        assert "mouse" in merged["Mus musculus"].aliases  # ours survive an upstream entry without aliases
        assert "Xenopus laevis" in merged  # bundled-only values are kept

    def test_unmapped_file_name_returns_none(self):
        from neuroconv.tools.ontology._term_sets import load_upstream_term_set

        assert load_upstream_term_set("not_a_bundled_file.yaml") is None

    def test_upstream_terms_are_preferred_and_merged(self, monkeypatch, tmp_path):
        upstream_yaml = tmp_path / "upstream_species.yaml"
        upstream_yaml.write_text(
            "prefixes:\n"
            "  NCBITaxon: http://purl.obolibrary.org/obo/NCBITaxon_\n"
            "enums:\n"
            "  Species:\n"
            "    permissible_values:\n"
            "      Mus musculus:\n"
            "        meaning: NCBITaxon:10090\n"
            "        description: upstream mouse\n"
            "      Rattus norvegicus:\n"
            "        meaning: NCBITaxon:10116\n"
            "        description: upstream rat\n"
        )

        class _FakeNeuroTermsets:
            @staticmethod
            def get_termset_path(name):
                assert name == "subject_species_ncbitaxon_termset.yaml"
                return str(upstream_yaml)

        monkeypatch.setitem(sys.modules, "neuro_termsets", _FakeNeuroTermsets())

        from neuroconv.tools.ontology._term_sets import load_term_set, load_upstream_term_set

        upstream = load_upstream_term_set("species.yaml")
        assert upstream["Mus musculus"].description == "upstream mouse"
        assert "Rattus norvegicus" in upstream

        merged = load_term_set("species.yaml")
        assert merged["Mus musculus"].description == "upstream mouse"  # upstream wins on overlap
        assert "Homo sapiens" in merged  # bundled-only values are kept
        assert "mouse" in merged["Mus musculus"].aliases  # upstream has no aliases: ours are not dropped

    def test_aliases_of_both_sources_are_combined(self, monkeypatch, tmp_path):
        upstream_yaml = tmp_path / "ncbitaxon.yaml"
        upstream_yaml.write_text(
            "prefixes:\n"
            "  NCBITaxon: http://purl.obolibrary.org/obo/NCBITaxon_\n"
            "enums:\n"
            "  Species:\n"
            "    permissible_values:\n"
            "      Mus musculus:\n"
            "        meaning: NCBITaxon:10090\n"
            "        aliases:\n"
            "          - murine\n"
            "          - mouse\n"
        )

        class _FakeNeuroTermsets:
            @staticmethod
            def get_termset_path(name):
                return str(upstream_yaml)

        monkeypatch.setitem(sys.modules, "neuro_termsets", _FakeNeuroTermsets())

        from neuroconv.tools.ontology._term_sets import load_term_set

        aliases = load_term_set("species.yaml")["Mus musculus"].aliases
        assert "murine" in aliases and "house mouse" in aliases
        assert aliases.count("mouse") == 1  # a name both sources list appears once

    def test_upstream_failure_falls_back_to_bundled(self, monkeypatch):
        class _BrokenNeuroTermsets:
            @staticmethod
            def get_termset_path(name):
                raise FileNotFoundError("term set renamed upstream")

        monkeypatch.setitem(sys.modules, "neuro_termsets", _BrokenNeuroTermsets())

        from neuroconv.tools.ontology._term_sets import load_term_set, load_upstream_term_set

        assert load_upstream_term_set("species.yaml") is None
        assert load_term_set("species.yaml")["Mus musculus"].curie == "NCBITaxon:10090"


# ---------------------------------------------------------------------------
# Aliases live in the term set files
# ---------------------------------------------------------------------------

TERM_SET_FILES = ["species.yaml", "mouse_brain_atlas.yaml", "human_brain_atlas.yaml", "uberon_common_regions.yaml"]


class TestTermSetAliases:
    def test_aliases_are_parsed_into_term_info(self):
        from neuroconv.tools.ontology._term_sets import load_term_set

        assert "mouse" in load_term_set("species.yaml")["Mus musculus"].aliases
        assert load_term_set("mouse_brain_atlas.yaml")["HIP"].aliases == ("hippocampus",)

    def test_term_without_aliases_has_an_empty_tuple(self):
        from neuroconv.tools.ontology._term_sets import load_term_set

        assert load_term_set("mouse_brain_atlas.yaml")["TH"].aliases == ()

    @pytest.mark.parametrize("file_name", TERM_SET_FILES)
    def test_no_alias_is_shared_between_terms(self, file_name):
        from neuroconv.tools.ontology._term_sets import load_term_set

        owner = {}
        for term in load_term_set(file_name).values():
            for alias in term.aliases:
                assert owner.setdefault(alias.lower(), term.value) == term.value, alias

    @pytest.mark.parametrize(
        "location, species, expected_curie",
        [
            ("brainstem", "Mus musculus", "MBA:343"),
            ("lateral entorhinal cortex", "Mus musculus", "MBA:918"),
            ("Area CA1", "Mus musculus", "MBA:382"),
            ("insular cortex", "Homo sapiens", "HBA:4268"),
            ("isocortex", "Rattus norvegicus", "UBERON:0001950"),
        ],
    )
    def test_brain_region_aliases_resolve(self, location, species, expected_curie):
        assert get_brain_region_term(location, species=species).curie == expected_curie

    @pytest.mark.parametrize(
        "name, expected_species",
        [
            ("mice", "Mus musculus"),
            ("African clawed frog", "Xenopus laevis"),
            ("domestic ferret", "Mustela putorius furo"),
            ("swine", "Sus scrofa"),
        ],
    )
    def test_species_aliases_resolve(self, name, expected_species):
        assert get_species_term(name).canonical_name == expected_species

    def test_atlas_rejects_an_alias_already_used_by_another_term(self, monkeypatch):
        from neuroconv.tools.ontology import _brain_regions
        from neuroconv.tools.ontology._term_sets import TermInfo

        fake_term_set = {
            "A": TermInfo("A", "X:1", "https://example.org/1", "first", ("shared",)),
            "B": TermInfo("B", "X:2", "https://example.org/2", "second", ("shared",)),
        }
        monkeypatch.setattr(_brain_regions, "load_term_set", lambda file_name: fake_term_set)
        with pytest.raises(ValueError, match="already used"):
            _brain_regions._build_atlas("unused.yaml")


# ---------------------------------------------------------------------------
# Species term resolution
# ---------------------------------------------------------------------------


class TestSpeciesTerms:
    def test_table_entries_are_self_consistent(self):
        for canonical_name, term in SPECIES_TERMS.items():
            assert isinstance(term, SpeciesTerm)
            assert term.canonical_name == canonical_name
            assert term.ncbitaxon_id.startswith("NCBITaxon:")

    def test_entity_uri_is_derived_from_ncbitaxon_id(self):
        term = SPECIES_TERMS["Mus musculus"]
        assert term.ncbitaxon_id == "NCBITaxon:10090"
        assert term.entity_uri == "http://purl.obolibrary.org/obo/NCBITaxon_10090"

    def test_exact_canonical_name_resolves(self):
        term = get_species_term("Mus musculus")
        assert term.canonical_name == "Mus musculus"
        assert term.ncbitaxon_id == "NCBITaxon:10090"

    def test_common_name_suggestion(self):
        suggestion = get_species_suggestion("mouse")
        term, reason = suggestion
        assert term.canonical_name == "Mus musculus"
        assert "common name" in reason
        # get_species_term resolves the same way, without emitting a suggestion.
        assert get_species_term("mouse").canonical_name == "Mus musculus"

    def test_common_name_is_case_insensitive_and_stripped(self):
        term, _ = get_species_suggestion("  Rhesus Macaque  ")
        assert term.canonical_name == "Macaca mulatta"

    def test_typo_suggestion(self):
        suggestion = get_species_suggestion("Homo sapien")
        term, reason = suggestion
        assert term.canonical_name == "Homo sapiens"
        assert "closely matches" in reason

    @pytest.mark.parametrize(
        "species",
        ["Octodon degus", "", None, 42],  # valid-but-uncommon binomial, empty, non-string
    )
    def test_unrecognized_returns_none(self, species):
        assert get_species_suggestion(species) is None
        assert get_species_term(species) is None

    def test_validate_species_no_warning_for_canonical_name(self, recwarn):
        assert validate_species("Mus musculus") is None
        assert len(recwarn) == 0

    def test_validate_species_warns_and_returns_term_for_common_name(self):
        with pytest.warns(UserWarning, match="Mus musculus"):
            term = validate_species("mouse")
        assert term.canonical_name == "Mus musculus"

    def test_validate_species_warning_points_to_bioregistry(self):
        with pytest.warns(UserWarning, match="bioregistry.io/NCBITaxon:9606"):
            validate_species("human")


# ---------------------------------------------------------------------------
# Brain-region term resolution
# ---------------------------------------------------------------------------


class TestBrainRegionTerms:
    @pytest.mark.parametrize("terms, prefix", [(MBA_TERMS, "MBA"), (HBA_TERMS, "HBA")])
    def test_atlas_tables_are_self_consistent(self, terms, prefix):
        assert len(terms) > 50
        curies = []
        for acronym, term in terms.items():
            assert isinstance(term, BrainRegionTerm)
            assert term.acronym == acronym
            assert term.curie.startswith(f"{prefix}:")
            curies.append(term.curie)
        assert len(curies) == len(set(curies))  # unique within the atlas

    @pytest.mark.parametrize(
        "location, expected_acronym",
        [
            ("CA1", "CA1"),  # exact acronym
            ("SSp-bfd", "SSp-bfd"),  # acronym with a hyphen
            ("caudoputamen", "CP"),  # canonical name, case-insensitive
            ("hippocampus", "HIP"),  # informal alias
            ("V1", "VISp"),  # abbreviation alias
        ],
    )
    def test_mouse_lookup(self, location, expected_acronym):
        term = get_brain_region_term(location)  # default species is mouse
        assert term.acronym == expected_acronym
        assert term.curie.startswith("MBA:")

    @pytest.mark.parametrize("location", ["not a region", "ca1", None, 382])  # case-sensitive, non-string
    def test_mouse_unrecognized_returns_none(self, location):
        assert get_brain_region_term(location) is None

    @pytest.mark.parametrize(
        "location, expected_curie",
        [
            ("CA1", "HBA:12892"),  # same acronym as mouse, different atlas/id
            ("cerebral cortex", "HBA:4008"),  # canonical name
            ("hippocampus", "HBA:4249"),  # alias
        ],
    )
    def test_human_lookup(self, location, expected_curie):
        assert get_brain_region_term(location, species="Homo sapiens").curie == expected_curie

    def test_same_acronym_resolves_per_species(self):
        # "MB" is the mouse midbrain but the human mammillary body.
        assert get_brain_region_term("MB", species="Mus musculus").curie == "MBA:313"
        assert get_brain_region_term("MB", species="Homo sapiens").curie == "HBA:12909"

    def test_common_species_name_is_accepted(self):
        assert get_brain_region_term("cerebral cortex", species="human").curie == "HBA:4008"

    def test_uberon_fallback_for_species_without_dedicated_atlas(self):
        # Rat has no dedicated Allen atlas; common region names still resolve via the
        # species-agnostic UBERON fallback vocabulary.
        term = get_brain_region_term("hippocampus", species="Rattus norvegicus")
        assert term.curie == "UBERON:0002421"
        # Mouse-specific acronyms are not in the generic fallback vocabulary.
        assert get_brain_region_term("CA1", species="Rattus norvegicus") is None

    def test_unrecognized_species_returns_none(self):
        assert get_brain_region_term("CA1", species=None) is None
        assert get_brain_region_term("CA1", species="not a species") is None


# ---------------------------------------------------------------------------
# Species ontology inference (metadata -> metadata)
# ---------------------------------------------------------------------------


class TestInferSpeciesOntologyMetadata:
    def test_recognized_species_writes_term(self):
        metadata = {"Subject": {"species": "Mus musculus"}}
        infer_species_ontology_metadata(metadata)
        assert metadata["ontology"]["species"] == {"Mus musculus": MOUSE_SPECIES_TERM}
        assert "ontology" not in metadata["Subject"]

    def test_common_name_is_resolved_and_warns(self):
        metadata = {"Subject": {"species": "mouse"}}
        with pytest.warns(UserWarning, match="Mus musculus"):
            infer_species_ontology_metadata(metadata)
        # Keyed by the value as written: HERD links the term to Subject.species through that string.
        assert metadata["ontology"]["species"] == {"mouse": MOUSE_SPECIES_TERM}

    def test_unrecognized_species_leaves_metadata_untouched(self):
        metadata = {"Subject": {"species": "Octodon degus"}}
        infer_species_ontology_metadata(metadata)
        assert "ontology" not in metadata

    def test_existing_user_term_is_not_overwritten(self):
        curated = {"id": "NCBITaxon:99999", "uri": "https://example.org/custom"}
        metadata = {"Subject": {"species": "Mus musculus"}, "ontology": {"species": {"Mus musculus": curated}}}
        infer_species_ontology_metadata(metadata)
        assert metadata["ontology"]["species"] == {"Mus musculus": curated}

    def test_other_ontology_entries_are_kept(self):
        brain_regions = {"CA1": {"id": "MBA:382", "uri": "https://example.org/MBA_382"}}
        metadata = {"Subject": {"species": "Mus musculus"}, "ontology": {"brain_regions": brain_regions}}
        infer_species_ontology_metadata(metadata)
        assert metadata["ontology"]["brain_regions"] == brain_regions
        assert metadata["ontology"]["species"] == {"Mus musculus": MOUSE_SPECIES_TERM}

    def test_no_subject_block_is_a_noop(self):
        metadata = {"NWBFile": {}}
        assert infer_species_ontology_metadata(metadata) is metadata


# ---------------------------------------------------------------------------
# Brain-region ontology inference (file + metadata -> metadata)
# ---------------------------------------------------------------------------


class TestInferBrainRegionOntologyMetadata:
    def test_electrode_locations_are_resolved(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        _add_electrodes(nwbfile, ["CA1", "VISp", "unknown"])
        metadata = {}

        infer_brain_region_ontology_metadata(nwbfile, metadata)
        brain_regions = metadata["ontology"]["brain_regions"]
        assert brain_regions["CA1"] == {"id": "MBA:382", "uri": MBA_TERMS["CA1"].entity_uri}
        assert brain_regions["VISp"]["id"] == "MBA:385"
        assert "unknown" not in brain_regions  # unresolved locations are skipped

    def test_species_selects_the_atlas(self):
        nwbfile = _make_nwbfile(species="Homo sapiens")
        _add_electrodes(nwbfile, ["CA1"])
        metadata = {}

        infer_brain_region_ontology_metadata(nwbfile, metadata)
        assert metadata["ontology"]["brain_regions"]["CA1"]["id"] == "HBA:12892"

    def test_icephys_ogen_and_virus_injection_locations_are_resolved(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        _add_icephys_ogen_and_injection(nwbfile, icephys_location="CA1", ogen_location="VISp", injection_location="VTA")
        metadata = {}

        infer_brain_region_ontology_metadata(nwbfile, metadata)
        brain_regions = metadata["ontology"]["brain_regions"]
        assert {location: term["id"] for location, term in brain_regions.items()} == {
            "CA1": "MBA:382",
            "VISp": "MBA:385",
            "VTA": "MBA:749",
        }

    def test_imaging_plane_locations_are_resolved(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        device = nwbfile.create_device(name="scope")
        nwbfile.create_imaging_plane(
            name="plane0",
            optical_channel=_optical_channel(),
            description="d",
            device=device,
            excitation_lambda=600.0,
            indicator="GCaMP",
            location="SSp",
            imaging_rate=30.0,
        )
        metadata = {}

        infer_brain_region_ontology_metadata(nwbfile, metadata)
        assert metadata["ontology"]["brain_regions"]["SSp"]["id"] == "MBA:322"

    def test_locations_shared_across_modalities_resolve_once(self):
        # The same location string across two modalities is one entry in the flat map.
        nwbfile = _make_nwbfile(species="Mus musculus")
        _add_electrodes(nwbfile, ["CA1"])
        device = nwbfile.create_device(name="scope")
        nwbfile.create_imaging_plane(
            name="plane0",
            optical_channel=_optical_channel(),
            description="d",
            device=device,
            excitation_lambda=600.0,
            indicator="GCaMP",
            location="CA1",
            imaging_rate=30.0,
        )
        metadata = {}

        infer_brain_region_ontology_metadata(nwbfile, metadata)
        assert metadata["ontology"]["brain_regions"].keys() == {"CA1"}

    def test_unrecognized_species_is_a_noop(self):
        nwbfile = _make_nwbfile(species="Octodon degus")
        _add_electrodes(nwbfile, ["CA1"])
        metadata = {}
        infer_brain_region_ontology_metadata(nwbfile, metadata)
        assert metadata == {}

    def test_existing_user_term_is_not_overwritten(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        _add_electrodes(nwbfile, ["CA1"])
        curated = {"id": "MBA:999", "uri": "https://example.org/custom"}
        metadata = _brain_regions_metadata({"CA1": curated})

        infer_brain_region_ontology_metadata(nwbfile, metadata)
        assert metadata["ontology"]["brain_regions"]["CA1"] == curated


# ---------------------------------------------------------------------------
# Species HERD annotation (metadata -> file)
# ---------------------------------------------------------------------------


class TestSpeciesExternalResource:
    @pytest.mark.parametrize(
        "kwargs, metadata",
        [
            (dict(with_subject=False), {"ontology": {"species": {"Mus musculus": MOUSE_SPECIES_TERM}}}),
            (dict(), None),  # no metadata
            (dict(), {"Subject": {"species": "Mus musculus"}}),  # metadata but no ontology term
            (dict(), {"ontology": {"species": {"mouse": MOUSE_SPECIES_TERM}}}),  # term for another value
        ],
    )
    def test_noop_cases(self, kwargs, metadata):
        nwbfile = _make_nwbfile(**kwargs)
        assert add_species_external_resource(nwbfile, metadata=metadata) is False
        assert nwbfile.external_resources is None

    def test_species_term_from_metadata_is_annotated(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        metadata = {"ontology": {"species": {"Mus musculus": MOUSE_SPECIES_TERM}}}
        assert add_species_external_resource(nwbfile, metadata=metadata) is True

        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["Mus musculus"]
        assert dataframe["entity_id"].tolist() == ["NCBITaxon:10090"]

        objects = nwbfile.external_resources.objects.to_dataframe()
        assert objects["object_id"].tolist() == [nwbfile.subject.object_id]
        assert objects["relative_path"].tolist() == ["species"]

    def test_idempotent(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        metadata = {"ontology": {"species": {"Mus musculus": MOUSE_SPECIES_TERM}}}
        assert add_species_external_resource(nwbfile, metadata=metadata) is True
        assert add_species_external_resource(nwbfile, metadata=metadata) is False
        assert len(nwbfile.external_resources.entities[:]) == 1

    def test_extends_existing_herd_in_place(self):
        from hdmf.common import HERD
        from pynwb import get_type_map

        nwbfile = _make_nwbfile(species="Mus musculus")
        herd = HERD(type_map=get_type_map())
        herd.add_ref(
            container=nwbfile.subject,
            attribute="subject_id",
            key="s1",
            entity_id="EXAMPLE:1",
            entity_uri="https://example.org/1",
        )
        nwbfile.external_resources = herd

        metadata = {"ontology": {"species": {"Mus musculus": MOUSE_SPECIES_TERM}}}
        assert add_species_external_resource(nwbfile, metadata=metadata) is True
        assert nwbfile.external_resources is herd  # extended in place, not replaced
        assert len(herd.entities[:]) == 2


# ---------------------------------------------------------------------------
# Brain-region HERD annotation (metadata -> file)
# ---------------------------------------------------------------------------


class TestBrainRegionExternalResources:
    def test_noop_without_metadata(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1"])
        assert add_brain_region_external_resources(nwbfile) == 0
        assert nwbfile.external_resources is None

    def test_noop_when_metadata_covers_no_present_location(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1", "VISp", "unknown"])
        metadata = _brain_regions_metadata({"some other area": {"id": "MBA:1", "uri": "https://example.org/1"}})
        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 0
        assert nwbfile.external_resources is None

    def test_electrodes_groups_and_imaging_planes_are_annotated(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1", "CA1", "VISp", "unknown"])  # duplicates collapse to one ref
        device = nwbfile.create_device(name="scope")
        nwbfile.create_electrode_group(name="g0", description="d", location="MOp", device=device)
        nwbfile.create_imaging_plane(
            name="plane0",
            optical_channel=_optical_channel(),
            description="d",
            device=device,
            excitation_lambda=600.0,
            indicator="GCaMP",
            location="SSp",
            imaging_rate=30.0,
        )
        metadata = _brain_regions_metadata(
            {
                "CA1": {"id": "MBA:382", "uri": "https://example.org/MBA_382"},
                "VISp": {"id": "MBA:385", "uri": "https://example.org/MBA_385"},
                "MOp": {"id": "MBA:985", "uri": "https://example.org/MBA_985"},
                "SSp": {"id": "MBA:322", "uri": "https://example.org/MBA_322"},
            }
        )

        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 4
        dataframe = nwbfile.external_resources.to_dataframe()
        by_key = dict(zip(dataframe["key"], dataframe["entity_id"]))
        assert by_key == {"CA1": "MBA:382", "VISp": "MBA:385", "MOp": "MBA:985", "SSp": "MBA:322"}

        # HERD records the electrodes reference against the ``location`` column, not the table.
        objects = nwbfile.external_resources.objects.to_dataframe()
        assert nwbfile.electrodes["location"].object_id in objects["object_id"].tolist()

    def test_icephys_ogen_and_virus_injection_locations_are_annotated(self, tmp_path):
        from pynwb import NWBHDF5IO

        nwbfile = _make_nwbfile()
        _add_icephys_ogen_and_injection(nwbfile, icephys_location="CA1", ogen_location="VISp", injection_location="VTA")
        metadata = _brain_regions_metadata(
            {
                "CA1": {"id": "MBA:382", "uri": "https://example.org/MBA_382"},
                "VISp": {"id": "MBA:385", "uri": "https://example.org/MBA_385"},
                "VTA": {"id": "MBA:749", "uri": "https://example.org/MBA_749"},
            }
        )

        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 3

        path = tmp_path / "locations.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(path, "r") as io:
            dataframe = io.read().external_resources.to_dataframe()
        rows = set(zip(dataframe["object_type"], dataframe["relative_path"], dataframe["key"], dataframe["entity_id"]))
        assert rows == {
            ("IntracellularElectrode", "location", "CA1", "MBA:382"),
            ("OptogeneticStimulusSite", "location", "VISp", "MBA:385"),
            ("ViralVectorInjection", "location", "VTA", "MBA:749"),
        }

    def test_fiber_photometry_table_location_is_annotated(self):
        from neuroconv.tools.fiber_photometry import get_fiber_photometry_table
        from neuroconv.tools.testing.mock_interfaces import MockFiberPhotometryInterface

        interface = MockFiberPhotometryInterface()
        metadata = interface.get_metadata()
        metadata["Subject"] = dict(subject_id="m1", species="Mus musculus", sex="M", age="P30D")
        metadata["DeviceModels"] = dict(
            optical_fiber_model=dict(
                type="OpticalFiberModel", name="optical_fiber_model", manufacturer="m", numerical_aperture=0.48
            ),
            excitation_source_model=dict(
                type="ExcitationSourceModel",
                name="excitation_source_model",
                manufacturer="m",
                source_type="LED",
                excitation_mode="one-photon",
            ),
            photodetector_model=dict(
                type="PhotodetectorModel", name="photodetector_model", manufacturer="m", detector_type="photodiode"
            ),
        )
        metadata["Devices"] = dict(
            optical_fiber=dict(
                type="OpticalFiber",
                name="optical_fiber",
                device_model_metadata_key="optical_fiber_model",
                fiber_insertion=dict(depth_in_mm=1.0),
            ),
            excitation_source=dict(
                type="ExcitationSource", name="excitation_source", device_model_metadata_key="excitation_source_model"
            ),
            photodetector=dict(
                type="Photodetector", name="photodetector", device_model_metadata_key="photodetector_model"
            ),
        )
        fiber_photometry_metadata = metadata["FiberPhotometry"]
        fiber_photometry_metadata["FiberPhotometryIndicators"] = dict(indicator=dict(name="indicator", label="GCaMP6s"))
        fiber_photometry_metadata["FiberPhotometryTable"] = dict(
            name="fiber_photometry_table",
            description="d",
            rows=dict(
                row0=dict(
                    location="CA1",
                    excitation_wavelength_in_nm=470.0,
                    emission_wavelength_in_nm=525.0,
                    indicator_metadata_key="indicator",
                    optical_fiber_metadata_key="optical_fiber",
                    excitation_source_metadata_key="excitation_source",
                    photodetector_metadata_key="photodetector",
                )
            ),
        )
        metadata["ontology"] = dict(brain_regions={"CA1": {"id": "MBA:382", "uri": "https://example.org/MBA_382"}})
        series_metadata = fiber_photometry_metadata[interface.metadata_key]
        series_metadata["fiber_photometry_table_region"] = ["row0"]
        series_metadata["fiber_photometry_table_region_description"] = "d"

        nwbfile = interface.create_nwbfile(metadata=metadata)

        dataframe = nwbfile.external_resources.to_dataframe()
        by_key = dict(zip(dataframe["key"], dataframe["entity_id"]))
        assert by_key["CA1"] == "MBA:382"
        objects = nwbfile.external_resources.objects.to_dataframe()
        location_column = get_fiber_photometry_table(nwbfile)["location"]
        assert location_column.object_id in objects["object_id"].tolist()

    def test_maps_one_area_to_multiple_ontology_terms(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1"])
        metadata = _brain_regions_metadata(
            {
                "CA1": [
                    {"id": "MBA:382", "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382"},
                    {"id": "UBERON:0003881", "uri": "http://purl.obolibrary.org/obo/UBERON_0003881"},
                ]
            }
        )

        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 2
        dataframe = nwbfile.external_resources.to_dataframe()
        assert sorted(dataframe["entity_id"].tolist()) == ["MBA:382", "UBERON:0003881"]

    def test_annotation_is_species_agnostic(self):
        # The writer never looks at the subject; a rat file is annotated from metadata alone.
        nwbfile = _make_nwbfile(species="Rattus norvegicus")
        _add_electrodes(nwbfile, ["my region", "CA1"])
        metadata = _brain_regions_metadata(
            {"my region": {"id": "UBERON:0002436", "uri": "http://purl.obolibrary.org/obo/UBERON_0002436"}}
        )

        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 1
        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["my region"]

    @pytest.mark.parametrize(
        "bad_value",
        ["MBA:382", {"id": "MBA:382"}, {"uri": "https://example.org/1"}, {"id": "", "uri": ""}],
    )
    def test_malformed_metadata_term_raises(self, bad_value):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["area"])
        metadata = _brain_regions_metadata({"area": bad_value})
        with pytest.raises((TypeError, ValueError)):
            add_brain_region_external_resources(nwbfile, metadata=metadata)

    def test_idempotent(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1", "VISp"])
        metadata = _brain_regions_metadata(
            {
                "CA1": {"id": "MBA:382", "uri": "https://example.org/MBA_382"},
                "VISp": {"id": "MBA:385", "uri": "https://example.org/MBA_385"},
            }
        )
        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 2
        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 0
        assert len(nwbfile.external_resources.entities[:]) == 2

    def test_extends_existing_herd_in_place(self):
        from hdmf.common import HERD
        from pynwb import get_type_map

        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1"])
        herd = HERD(type_map=get_type_map())
        herd.add_ref(
            container=nwbfile.subject,
            attribute="subject_id",
            key="s1",
            entity_id="EXAMPLE:1",
            entity_uri="https://example.org/1",
        )
        nwbfile.external_resources = herd

        metadata = _brain_regions_metadata({"CA1": {"id": "MBA:382", "uri": "https://example.org/MBA_382"}})
        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 1
        assert nwbfile.external_resources is herd  # extended in place, not replaced
        assert len(herd.entities[:]) == 2

    def test_shared_location_term_applies_across_modalities(self, recwarn):
        # One flat ontology.brain_regions map: a location string means the same place regardless
        # of which modality's site carries it, so one term annotates both without any conflict.
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1"])
        device = nwbfile.create_device(name="scope")
        nwbfile.create_imaging_plane(
            name="plane0",
            optical_channel=_optical_channel(),
            description="d",
            device=device,
            excitation_lambda=600.0,
            indicator="GCaMP",
            location="CA1",
            imaging_rate=30.0,
        )
        metadata = _brain_regions_metadata({"CA1": {"id": "MBA:382", "uri": "https://example.org/MBA_382"}})

        number_added = add_brain_region_external_resources(nwbfile, metadata=metadata)

        assert number_added == 2  # the electrodes column and the imaging plane
        dataframe = nwbfile.external_resources.to_dataframe()
        assert set(dataframe["entity_id"].tolist()) == {"MBA:382"}
        assert len(recwarn) == 0


# ---------------------------------------------------------------------------
# Conversion pipeline: infer -> create_nwbfile writes the stated terms
# ---------------------------------------------------------------------------


class TestConversionPipelineAnnotation:
    def _mouse_recording_interface(self, brain_areas):
        from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

        interface = MockRecordingInterface(num_channels=len(brain_areas), durations=(0.1,))
        interface.recording_extractor.set_property("brain_area", list(brain_areas))
        return interface

    def _mouse_metadata(self, interface):
        metadata = interface.get_metadata()
        metadata["Subject"] = dict(subject_id="m1", species="Mus musculus", sex="M", age="P30D")
        return metadata

    def test_plain_metadata_writes_no_external_resources(self):
        interface = self._mouse_recording_interface(["CA1", "VISp"])
        nwbfile = interface.create_nwbfile(metadata=self._mouse_metadata(interface))
        assert nwbfile.external_resources is None

    def test_inferred_terms_are_written_through_create_nwbfile(self):
        interface = self._mouse_recording_interface(["CA1", "VISp"])
        metadata = self._mouse_metadata(interface)

        # Inference needs the populated file to see the electrode locations.
        staging_nwbfile = interface.create_nwbfile(metadata=metadata)
        infer_species_ontology_metadata(metadata)
        infer_brain_region_ontology_metadata(staging_nwbfile, metadata)

        nwbfile = interface.create_nwbfile(metadata=metadata)
        entity_ids = set(nwbfile.external_resources.to_dataframe()["entity_id"].tolist())
        assert "NCBITaxon:10090" in entity_ids
        assert {"MBA:382", "MBA:385"}.issubset(entity_ids)

    def test_references_round_trip_through_file(self, tmp_path):
        from pynwb import NWBHDF5IO

        interface = self._mouse_recording_interface(["CA1", "VISp"])
        metadata = self._mouse_metadata(interface)
        staging_nwbfile = interface.create_nwbfile(metadata=metadata)
        infer_species_ontology_metadata(metadata)
        infer_brain_region_ontology_metadata(staging_nwbfile, metadata)
        nwbfile = interface.create_nwbfile(metadata=metadata)

        path = tmp_path / "ontology_herd.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(path, "r") as io:
            read_nwbfile = io.read()
            entity_ids = set(read_nwbfile.external_resources.to_dataframe()["entity_id"].tolist())

        assert {"NCBITaxon:10090", "MBA:382", "MBA:385"}.issubset(entity_ids)


# ---------------------------------------------------------------------------
# Compatibility with an HDMF type configuration (neuro-termsets' default config)
# ---------------------------------------------------------------------------


@pytest.fixture
def neuro_termsets_type_config():
    """Load neuro-termsets' ``default_config.yaml`` into pynwb for one test, then unload it.

    With the config loaded, HDMF wraps ``Subject.species`` and ``ElectrodeGroup.location`` in a
    ``TermSetWrapper`` and validates them against neuro-termsets' term sets. Skipped when
    ``linkml-runtime`` (needed by HDMF's ``TermSet``) or neuro-termsets is not installed.
    """
    pytest.importorskip("linkml_runtime")
    neuro_termsets = pytest.importorskip("neuro_termsets")
    import os

    import pynwb

    pynwb.load_type_config(config_path=os.path.join(os.path.dirname(neuro_termsets.__file__), "default_config.yaml"))
    try:
        yield
    finally:
        pynwb.unload_type_config()


@pytest.mark.usefixtures("neuro_termsets_type_config")
class TestTypeConfigCompatibility:
    # With the config loaded, locations must be keys of neuro-termsets' UBERON term set.
    UBERON_CA1 = "CA1 field of hippocampus"
    UBERON_CA1_TERM = {"id": "UBERON:0003881", "uri": "http://purl.obolibrary.org/obo/UBERON_0003881"}

    def _make_wrapped_nwbfile(self) -> NWBFile:
        from hdmf.term_set import TermSetWrapper

        nwbfile = _make_nwbfile(species="Mus musculus")
        device = nwbfile.create_device(name="probe")
        nwbfile.create_electrode_group(name="group0", description="d", location=self.UBERON_CA1, device=device)
        assert isinstance(nwbfile.subject.species, TermSetWrapper)
        assert isinstance(nwbfile.electrode_groups["group0"].location, TermSetWrapper)
        return nwbfile

    def test_wrapped_values_are_annotated_with_plain_keys(self, tmp_path):
        from pynwb import NWBHDF5IO

        nwbfile = self._make_wrapped_nwbfile()
        metadata = {
            "ontology": {
                "species": {"Mus musculus": MOUSE_SPECIES_TERM},
                "brain_regions": {self.UBERON_CA1: self.UBERON_CA1_TERM},
            }
        }

        assert add_species_external_resource(nwbfile, metadata=metadata) is True
        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 1
        # Idempotent on wrapped values too.
        assert add_species_external_resource(nwbfile, metadata=metadata) is False
        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 0

        # Before the fix, the wrapper object itself became the HERD key and the write failed.
        path = tmp_path / "wrapped.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(path, "r") as io:
            dataframe = io.read().external_resources.to_dataframe()
        rows = set(zip(dataframe["object_type"], dataframe["key"], dataframe["entity_id"]))
        assert rows == {
            ("Subject", "Mus musculus", "NCBITaxon:10090"),
            ("ElectrodeGroup", self.UBERON_CA1, "UBERON:0003881"),
        }

    def test_inference_reads_wrapped_values(self):
        nwbfile = self._make_wrapped_nwbfile()
        # The electrodes table column is not in the config, so it can carry an atlas acronym; the
        # atlas is still chosen from the wrapped Subject.species.
        nwbfile.add_electrode(location="CA1", group=nwbfile.electrode_groups["group0"], id=0)
        metadata = {"Subject": {"species": "Mus musculus"}}

        infer_species_ontology_metadata(metadata)
        infer_brain_region_ontology_metadata(nwbfile, metadata)

        assert metadata["ontology"]["species"] == {"Mus musculus": MOUSE_SPECIES_TERM}
        assert metadata["ontology"]["brain_regions"]["CA1"]["id"] == "MBA:382"
