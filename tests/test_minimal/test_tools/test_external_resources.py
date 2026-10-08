"""Tests for neuroconv.tools.external_resources: term resolution, metadata inference, and HERD annotation."""

import sys
from datetime import datetime
from pathlib import Path

import pytest
from dateutil.tz import tzutc
from jsonschema import ValidationError
from pynwb import NWBFile
from pynwb.file import Subject

from neuroconv.tools.external_resources import (
    HBA_TERMS,
    MBA_TERMS,
    add_brain_region_external_resources,
    add_external_resources_to_nwbfile,
    add_species_external_resource,
    get_brain_region_term,
    get_species_suggestion,
    get_species_term,
    infer_brain_region_external_resources,
    infer_species_external_resources,
    validate_species,
)
from neuroconv.utils import dict_deep_update, load_dict_from_file
from neuroconv.utils.json_schema import validate_metadata

MOUSE_SPECIES_TERM = {"id": "NCBITaxon:10090", "uri": "http://purl.obolibrary.org/obo/NCBITaxon_10090"}
CA1_TERM = {"id": "MBA:382", "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382"}


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


def _add_imaging_plane(nwbfile: NWBFile, location) -> None:
    from pynwb.ophys import OpticalChannel

    device = nwbfile.create_device(name="scope")
    nwbfile.create_imaging_plane(
        name="plane0",
        optical_channel=OpticalChannel(name="channel0", description="d", emission_lambda=500.0),
        description="d",
        device=device,
        excitation_lambda=600.0,
        indicator="GCaMP",
        location=location,
        imaging_rate=30.0,
    )


def _add_icephys_and_ogen(nwbfile: NWBFile, icephys_location, ogen_location) -> None:
    """Add an intracellular electrode and an optogenetic stimulus site (core NWB types)."""
    from pynwb.ogen import OptogeneticStimulusSite

    device = nwbfile.create_device(name="rig")
    nwbfile.create_icephys_electrode(name="electrode0", description="d", device=device, location=icephys_location)
    nwbfile.add_ogen_site(
        OptogeneticStimulusSite(
            name="site0", device=device, description="d", excitation_lambda=473.0, location=ogen_location
        )
    )


def _brain_regions_metadata(mapping: dict) -> dict:
    """A metadata dict carrying a file-wide ``ExternalResources.brain_regions`` map."""
    return {"ExternalResources": {"brain_regions": mapping}}


def _infer_external_resources(nwbfile: NWBFile) -> dict:
    """Both inferences for ``nwbfile``, combined into one ``{"ExternalResources": {...}}`` block."""
    return dict_deep_update(infer_species_external_resources(nwbfile), infer_brain_region_external_resources(nwbfile))


# ---------------------------------------------------------------------------
# Optional upstream term sets (neuro-termsets)
# ---------------------------------------------------------------------------


class TestUpstreamTermSets:
    """``neuro-termsets`` is not installed in this environment (and not yet on PyPI), so these tests
    fake the package via ``sys.modules`` rather than requiring it."""

    def setup_method(self):
        from neuroconv.tools.external_resources._term_sets import load_term_set, load_upstream_term_set

        load_term_set.cache_clear()
        load_upstream_term_set.cache_clear()

    teardown_method = setup_method

    @pytest.mark.parametrize("broken", [False, True], ids=["not_installed", "lookup_fails"])
    def test_unavailable_package_falls_back_to_bundled(self, monkeypatch, broken):
        class _BrokenNeuroTermsets:
            @staticmethod
            def get_termset_path(name):
                raise FileNotFoundError("term set renamed upstream")

        # ``None`` in ``sys.modules`` makes ``import neuro_termsets`` fail.
        monkeypatch.setitem(sys.modules, "neuro_termsets", _BrokenNeuroTermsets() if broken else None)

        from neuroconv.tools.external_resources._term_sets import load_term_set, load_upstream_term_set

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

        from neuroconv.tools.external_resources._term_sets import load_upstream_term_set

        for file_name in ["mouse_brain_atlas.yaml", "human_brain_atlas.yaml", "uberon_common_regions.yaml"]:
            assert load_upstream_term_set(file_name) is None
        assert requested == []

    def test_real_neuro_termsets_species_merge_keeps_bundled_terms_and_aliases(self):
        pytest.importorskip("neuro_termsets")

        from neuroconv.tools.external_resources._term_sets import (
            _UPSTREAM_TERM_SET_NAMES,
            load_term_set,
            load_upstream_term_set,
        )

        for bundled_name in _UPSTREAM_TERM_SET_NAMES:
            assert load_upstream_term_set(bundled_name) is not None, bundled_name  # the mapped name resolves
        merged = load_term_set("species.yaml")
        assert merged["Mus musculus"].curie == "NCBITaxon:10090"
        assert "mouse" in merged["Mus musculus"].aliases  # ours survive an upstream entry without aliases
        assert "Xenopus laevis" in merged  # bundled-only values are kept

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
            "        aliases:\n"
            "          - murine\n"
            "          - mouse\n"
            "      Rattus norvegicus:\n"
            "        meaning: NCBITaxon:10116\n"
            "        description: upstream rat\n",
            encoding="utf-8",
        )

        class _FakeNeuroTermsets:
            @staticmethod
            def get_termset_path(name):
                assert name == "subject_species_ncbitaxon_termset.yaml"
                return str(upstream_yaml)

        monkeypatch.setitem(sys.modules, "neuro_termsets", _FakeNeuroTermsets())

        from neuroconv.tools.external_resources._term_sets import load_term_set, load_upstream_term_set

        upstream = load_upstream_term_set("species.yaml")
        assert upstream["Mus musculus"].description == "upstream mouse"
        assert "Rattus norvegicus" in upstream

        merged = load_term_set("species.yaml")
        assert merged["Mus musculus"].description == "upstream mouse"  # upstream wins on overlap
        assert "Homo sapiens" in merged  # bundled-only values are kept
        aliases = merged["Mus musculus"].aliases
        assert "murine" in aliases and "house mouse" in aliases  # the aliases of both sources are combined
        assert aliases.count("mouse") == 1  # a name both sources list appears once


# ---------------------------------------------------------------------------
# Species term resolution
# ---------------------------------------------------------------------------


class TestSpeciesTerms:
    def test_canonical_name_resolves_without_a_suggestion(self):
        assert get_species_term("Mus musculus").ncbitaxon_id == "NCBITaxon:10090"
        assert get_species_suggestion("Mus musculus") is None

    @pytest.mark.parametrize(
        "species, expected_species, reason",
        [
            ("  Rhesus Macaque  ", "Macaca mulatta", "common name"),  # case-insensitive and stripped
            ("Homo sapien", "Homo sapiens", "closely matches"),
        ],
    )
    def test_common_names_and_typos_are_suggested(self, species, expected_species, reason):
        term, suggestion_reason = get_species_suggestion(species)
        assert term.canonical_name == expected_species
        assert reason in suggestion_reason
        assert get_species_term(species) == term

    @pytest.mark.parametrize(
        "species",
        ["Octodon degus", "", None, 42],  # valid-but-uncommon binomial, empty, non-string
    )
    def test_unrecognized_returns_none(self, species):
        assert get_species_suggestion(species) is None
        assert get_species_term(species) is None

    def test_validate_species_warns_for_common_name(self):
        with pytest.warns(UserWarning, match="'Mus musculus'.*bioregistry.io/NCBITaxon:10090"):
            term = validate_species("mouse")
        assert term.canonical_name == "Mus musculus"


# ---------------------------------------------------------------------------
# Brain-region term resolution
# ---------------------------------------------------------------------------


class TestBrainRegionTerms:
    @pytest.mark.parametrize("terms, prefix", [(MBA_TERMS, "MBA"), (HBA_TERMS, "HBA")])
    def test_atlas_curies_are_unique_and_prefixed(self, terms, prefix):
        curies = [term.curie for term in terms.values()]
        assert all(curie.startswith(f"{prefix}:") for curie in curies)
        assert len(curies) == len(set(curies))

    def test_atlas_rejects_an_alias_already_used_by_another_term(self, monkeypatch):
        # The bundled term sets go through this check when the module is imported.
        from neuroconv.tools.external_resources import _brain_regions
        from neuroconv.tools.external_resources._term_sets import TermInfo

        fake_term_set = {
            "A": TermInfo("A", "X:1", "https://example.org/1", "first", ("shared",)),
            "B": TermInfo("B", "X:2", "https://example.org/2", "second", ("shared",)),
        }
        monkeypatch.setattr(_brain_regions, "load_term_set", lambda file_name: fake_term_set)
        with pytest.raises(ValueError, match="already used"):
            _brain_regions._build_atlas("unused.yaml")

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
# Species inference (file -> ExternalResources metadata)
# ---------------------------------------------------------------------------


class TestInferSpeciesExternalResources:
    def test_recognized_species_returns_term(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        assert infer_species_external_resources(nwbfile) == {
            "ExternalResources": {"species": {"Mus musculus": MOUSE_SPECIES_TERM}}
        }

    def test_common_name_is_the_key(self):
        nwbfile = _make_nwbfile(species="mouse")
        with pytest.warns(UserWarning):
            inferred = infer_species_external_resources(nwbfile)
        # Keyed by the value as written: HERD links the term to Subject.species through that string.
        assert inferred == {"ExternalResources": {"species": {"mouse": MOUSE_SPECIES_TERM}}}

    @pytest.mark.parametrize("kwargs", [dict(species="Octodon degus"), dict(with_subject=False)])
    def test_unrecognized_species_or_no_subject_returns_empty(self, kwargs):
        assert infer_species_external_resources(_make_nwbfile(**kwargs)) == {}


# ---------------------------------------------------------------------------
# Brain-region inference (file -> ExternalResources metadata)
# ---------------------------------------------------------------------------


class TestInferBrainRegionExternalResources:
    def test_locations_of_every_modality_are_resolved(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        _add_electrodes(nwbfile, ["CA1", "unknown"])  # the electrode group's location is "unknown" too
        _add_icephys_and_ogen(nwbfile, icephys_location="VISp", ogen_location="MOp")
        _add_imaging_plane(nwbfile, location="SSp")

        brain_regions = infer_brain_region_external_resources(nwbfile)["ExternalResources"]["brain_regions"]
        assert brain_regions["CA1"] == CA1_TERM
        # "unknown" does not resolve and is skipped.
        assert {location: term["id"] for location, term in brain_regions.items()} == {
            "CA1": "MBA:382",
            "VISp": "MBA:385",
            "MOp": "MBA:985",
            "SSp": "MBA:322",
        }

    def test_species_selects_the_atlas(self):
        nwbfile = _make_nwbfile(species="Homo sapiens")
        _add_electrodes(nwbfile, ["CA1"])

        assert (
            infer_brain_region_external_resources(nwbfile)["ExternalResources"]["brain_regions"]["CA1"]["id"]
            == "HBA:12892"
        )

    @pytest.mark.parametrize("kwargs", [dict(species="Octodon degus"), dict(with_subject=False)])
    def test_unrecognized_species_or_no_subject_returns_empty(self, kwargs):
        nwbfile = _make_nwbfile(**kwargs)
        _add_electrodes(nwbfile, ["CA1"])
        assert infer_brain_region_external_resources(nwbfile) == {}


class TestMergeInferredExternalResources:
    """The documented merge, ``dict_deep_update(inferred, metadata, append_list=False)``."""

    def test_user_terms_win_and_inferred_terms_fill_the_rest(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        _add_electrodes(nwbfile, ["CA1", "VISp"])
        # A list of terms the user wrote is kept whole, not merged item by item with the inferred term.
        curated = [
            {"id": "MBA:999", "uri": "https://example.org/custom"},
            {"id": "UBERON:0003881", "uri": "http://purl.obolibrary.org/obo/UBERON_0003881"},
        ]
        metadata = _brain_regions_metadata({"CA1": curated})

        merged = dict_deep_update(_infer_external_resources(nwbfile), metadata, append_list=False)
        assert merged["ExternalResources"]["brain_regions"]["CA1"] == curated
        assert merged["ExternalResources"]["brain_regions"]["VISp"]["id"] == "MBA:385"
        assert merged["ExternalResources"]["species"] == {"Mus musculus": MOUSE_SPECIES_TERM}


# ---------------------------------------------------------------------------
# Species HERD annotation (metadata -> file)
# ---------------------------------------------------------------------------


class TestSpeciesExternalResource:
    @pytest.mark.parametrize(
        "kwargs, metadata",
        [
            (dict(with_subject=False), {"ExternalResources": {"species": {"Mus musculus": MOUSE_SPECIES_TERM}}}),
            (dict(), None),  # no metadata
            (dict(), {"Subject": {"species": "Mus musculus"}}),  # metadata but no ontology term
            (dict(), {"ExternalResources": {"species": {"mouse": MOUSE_SPECIES_TERM}}}),  # term for another value
        ],
    )
    def test_noop_cases(self, kwargs, metadata):
        nwbfile = _make_nwbfile(**kwargs)
        assert add_species_external_resource(nwbfile, metadata=metadata) is False
        assert nwbfile.external_resources is None

    def test_species_term_from_metadata_is_annotated(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        metadata = {"ExternalResources": {"species": {"Mus musculus": MOUSE_SPECIES_TERM}}}
        assert add_species_external_resource(nwbfile, metadata=metadata) is True

        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["Mus musculus"]
        assert dataframe["entity_id"].tolist() == ["NCBITaxon:10090"]

        objects = nwbfile.external_resources.objects.to_dataframe()
        assert objects["object_id"].tolist() == [nwbfile.subject.object_id]
        assert objects["relative_path"].tolist() == ["species"]


# ---------------------------------------------------------------------------
# Brain-region HERD annotation (metadata -> file)
# ---------------------------------------------------------------------------


class TestBrainRegionExternalResources:
    @pytest.mark.parametrize(
        "metadata",
        [None, _brain_regions_metadata({"some other area": {"id": "MBA:1", "uri": "https://example.org/1"}})],
        ids=["no_metadata", "no_present_location"],
    )
    def test_noop_cases(self, metadata):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1"])
        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 0
        assert nwbfile.external_resources is None

    def test_every_core_location_field_is_annotated(self, tmp_path):
        from pynwb import NWBHDF5IO

        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1", "CA1", "unknown"])  # duplicates collapse to one reference
        nwbfile.create_electrode_group(name="g0", description="d", location="MOp", device=nwbfile.devices["probe"])
        _add_imaging_plane(nwbfile, location="SSp")
        _add_icephys_and_ogen(nwbfile, icephys_location="CA1", ogen_location="VISp")
        metadata = _brain_regions_metadata(
            {
                "CA1": {"id": "MBA:382", "uri": "https://example.org/MBA_382"},
                "VISp": {"id": "MBA:385", "uri": "https://example.org/MBA_385"},
                "MOp": {"id": "MBA:985", "uri": "https://example.org/MBA_985"},
                "SSp": {"id": "MBA:322", "uri": "https://example.org/MBA_322"},
            }
        )

        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 5
        # HERD records the electrodes reference against the ``location`` column, not the table.
        objects = nwbfile.external_resources.objects.to_dataframe()
        assert nwbfile.electrodes["location"].object_id in objects["object_id"].tolist()

        path = tmp_path / "locations.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(path, "r") as io:
            dataframe = io.read().external_resources.to_dataframe()
        assert set(zip(dataframe["object_type"], dataframe["key"], dataframe["entity_id"])) == {
            ("VectorData", "CA1", "MBA:382"),
            ("IntracellularElectrode", "CA1", "MBA:382"),
            ("ElectrodeGroup", "MOp", "MBA:985"),
            ("ImagingPlane", "SSp", "MBA:322"),
            ("OptogeneticStimulusSite", "VISp", "MBA:385"),
        }

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


# ---------------------------------------------------------------------------
# The ExternalResources block of the base metadata schema
# ---------------------------------------------------------------------------


class TestExternalResourcesMetadataSchema:
    BRAIN_REGION_TERM = {"id": "MBA:382", "uri": "https://example.org/MBA_382"}

    @pytest.fixture(scope="class")
    def base_metadata_schema(self):
        import neuroconv

        return load_dict_from_file(Path(neuroconv.__file__).parent / "schemas" / "base_metadata_schema.json")

    def _validate(self, block, schema):
        nwbfile_metadata = {"session_start_time": datetime(2020, 1, 1, tzinfo=tzutc())}
        validate_metadata(metadata={"NWBFile": nwbfile_metadata, "ExternalResources": block}, schema=schema)

    @pytest.mark.parametrize(
        "block",
        [
            {},
            {"species": {"Mus musculus": MOUSE_SPECIES_TERM}},
            {"brain_regions": {"CA1": [BRAIN_REGION_TERM, {"id": "UBERON:0003881", "uri": "https://example.org/U"}]}},
            {"brain_regions": {"CA1": {**BRAIN_REGION_TERM, "label": "Field CA1"}}},  # extra keys are allowed
        ],
        ids=["empty", "species", "list_of_terms", "term_with_label"],
    )
    def test_valid_blocks_pass(self, block, base_metadata_schema):
        self._validate(block, base_metadata_schema)

    @pytest.mark.parametrize(
        "block",
        [
            {"brain_region": {"CA1": BRAIN_REGION_TERM}},  # typo in the map name
            {"brain_regions": {"CA1": {"id": "MBA:382", "url": "https://example.org/MBA_382"}}},  # misspelled uri
            {"brain_regions": {"CA1": {"id": "", "uri": "https://example.org/MBA_382"}}},  # empty id
            {"brain_regions": {"CA1": "MBA:382"}},  # a bare CURIE, not a term
            {"brain_regions": {"CA1": []}},  # empty list
        ],
        ids=["unknown_map", "misspelled_uri", "empty_id", "bare_string", "empty_list"],
    )
    def test_invalid_blocks_raise(self, block, base_metadata_schema):
        with pytest.raises(ValidationError) as error:
            self._validate(block, base_metadata_schema)
        assert error.value.absolute_path[0] == "ExternalResources"

    def test_interface_schema_rejects_unknown_map(self):
        # Interfaces build their schema on the base one, so the typo is caught before any data is written.
        from neuroconv.tools.testing.mock_interfaces import MockIcephysInterface

        interface = MockIcephysInterface(num_sweeps=1, sweep_duration=0.01)
        metadata = interface.get_metadata()
        metadata["ExternalResources"] = {"brain_region": {"CA1": self.BRAIN_REGION_TERM}}
        with pytest.raises(ValidationError, match="brain_region"):
            interface.validate_metadata(metadata=metadata)


# ---------------------------------------------------------------------------
# Annotation at write time: add_external_resources_to_nwbfile and run_conversion
# ---------------------------------------------------------------------------


class TestAddExternalResourcesToNWBFile:
    def test_runs_every_domain_and_counts_references(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        _add_electrodes(nwbfile, ["CA1"])
        metadata = {
            "ExternalResources": {"species": {"Mus musculus": MOUSE_SPECIES_TERM}, "brain_regions": {"CA1": CA1_TERM}}
        }

        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 2
        entity_ids = set(nwbfile.external_resources.to_dataframe()["entity_id"])
        assert entity_ids == {"NCBITaxon:10090", "MBA:382"}
        # Idempotent.
        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 0

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

        metadata = {"ExternalResources": {"species": {"Mus musculus": MOUSE_SPECIES_TERM}}}
        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 1
        assert nwbfile.external_resources is herd  # extended in place, not replaced
        assert len(herd.entities[:]) == 2

    @pytest.mark.parametrize("metadata", [None, {}, {"Subject": {"species": "Mus musculus"}}])
    def test_no_block_is_a_noop(self, metadata):
        nwbfile = _make_nwbfile(species="Mus musculus")
        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 0
        assert nwbfile.external_resources is None


def _written_references(path) -> set:
    """``(object_type, key, entity_id)`` for every HERD reference in the file at ``path``."""
    from pynwb import NWBHDF5IO

    with NWBHDF5IO(path, "r") as io:
        herd = io.read().external_resources
        if herd is None:
            return set()
        dataframe = herd.to_dataframe()
    return set(zip(dataframe["object_type"], dataframe["key"], dataframe["entity_id"]))


MOUSE_REFERENCE = ("Subject", "Mus musculus", "NCBITaxon:10090")
CA1_ELECTRODE_REFERENCE = ("IntracellularElectrode", "CA1", "MBA:382")


class TestConversionPipelineAnnotation:
    # The icephys mock needs only core NWB, so these run in the minimal test environment.
    def _mouse_icephys_interface(self, location="CA1", herd=None):
        from neuroconv.tools.testing.mock_interfaces import MockIcephysInterface

        interface = MockIcephysInterface(num_sweeps=1, sweep_duration=0.01)
        metadata = interface.get_metadata()
        metadata["Subject"] = dict(subject_id="m1", species="Mus musculus", sex="M", age="P30D")
        metadata["Icephys"]["IntracellularElectrodes"]["mock"]["location"] = location
        if herd is not None:
            metadata["ExternalResources"] = herd
        return interface, metadata

    def test_create_nwbfile_does_not_annotate(self):
        # Annotation happens at write time, so create_nwbfile leaves the file as the interfaces built it.
        interface, metadata = self._mouse_icephys_interface(herd={"species": {"Mus musculus": MOUSE_SPECIES_TERM}})
        assert interface.create_nwbfile(metadata=metadata).external_resources is None

    @pytest.mark.parametrize("converter", [False, True], ids=["interface", "converter"])
    def test_run_conversion_writes_references(self, tmp_path, converter):
        from neuroconv import ConverterPipe

        interface, metadata = self._mouse_icephys_interface(
            herd={"species": {"Mus musculus": MOUSE_SPECIES_TERM}, "brain_regions": {"CA1": CA1_TERM}}
        )
        runner = ConverterPipe(data_interfaces={"icephys": interface}) if converter else interface
        path = tmp_path / "run_conversion.nwb"
        runner.run_conversion(nwbfile_path=path, metadata=metadata)
        assert _written_references(path) == {MOUSE_REFERENCE, CA1_ELECTRODE_REFERENCE}

    def test_run_conversion_annotates_objects_added_to_an_in_memory_file(self, tmp_path):
        # Objects added to the in-memory file before run_conversion are annotated too.
        from pynwb.ogen import OptogeneticStimulusSite

        from neuroconv.tools.nwb_helpers import make_nwbfile_from_metadata

        interface, metadata = self._mouse_icephys_interface(
            herd={"brain_regions": {"CA1": CA1_TERM, "VISp": {"id": "MBA:385", "uri": "https://example.org/MBA_385"}}}
        )
        nwbfile = make_nwbfile_from_metadata(metadata=metadata)
        device = nwbfile.create_device(name="laser")
        nwbfile.add_ogen_site(
            OptogeneticStimulusSite(
                name="site0", device=device, description="d", excitation_lambda=473.0, location="VISp"
            )
        )

        path = tmp_path / "in_memory.nwb"
        interface.run_conversion(nwbfile_path=path, nwbfile=nwbfile, metadata=metadata)
        assert _written_references(path) == {CA1_ELECTRODE_REFERENCE, ("OptogeneticStimulusSite", "VISp", "MBA:385")}


class TestAppendModeAnnotation:
    """``run_conversion(append_on_disk_nwbfile=True)`` annotates the file read back from disk."""

    FULL_EXTERNAL_RESOURCES = {"species": {"Mus musculus": MOUSE_SPECIES_TERM}, "brain_regions": {"CA1": CA1_TERM}}

    def _write_icephys_file(self, path, herd=None):
        interface, metadata = TestConversionPipelineAnnotation()._mouse_icephys_interface(herd=herd)
        interface.run_conversion(nwbfile_path=path, metadata=metadata)

    def _append_time_series(self, path, herd, converter=False):
        from neuroconv import ConverterPipe
        from neuroconv.tools.testing.mock_interfaces import MockTimeSeriesInterface

        interface = MockTimeSeriesInterface()
        metadata = interface.get_metadata()
        metadata["ExternalResources"] = herd
        runner = ConverterPipe(data_interfaces={"time_series": interface}) if converter else interface
        runner.run_conversion(nwbfile_path=path, metadata=metadata, append_on_disk_nwbfile=True)

    @pytest.mark.parametrize("converter", [False, True], ids=["interface", "converter"])
    def test_file_without_herd_is_annotated(self, tmp_path, converter):
        path = tmp_path / "append.nwb"
        self._write_icephys_file(path)
        self._append_time_series(path, herd=self.FULL_EXTERNAL_RESOURCES, converter=converter)
        assert _written_references(path) == {MOUSE_REFERENCE, CA1_ELECTRODE_REFERENCE}

    def test_already_annotated_file_is_left_as_is(self, tmp_path):
        path = tmp_path / "append.nwb"
        self._write_icephys_file(path, herd=self.FULL_EXTERNAL_RESOURCES)
        self._append_time_series(path, herd=self.FULL_EXTERNAL_RESOURCES)
        assert _written_references(path) == {MOUSE_REFERENCE, CA1_ELECTRODE_REFERENCE}

    def test_new_references_on_a_stored_herd_warn_and_the_append_still_writes(self, tmp_path):
        from pynwb import NWBHDF5IO

        path = tmp_path / "append.nwb"
        self._write_icephys_file(path, herd={"species": {"Mus musculus": MOUSE_SPECIES_TERM}})
        with pytest.warns(UserWarning, match="cannot be extended"):
            self._append_time_series(path, herd=self.FULL_EXTERNAL_RESOURCES)

        assert _written_references(path) == {MOUSE_REFERENCE}
        with NWBHDF5IO(path, "r") as io:
            assert "TimeSeries" in io.read().acquisition


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
            "ExternalResources": {
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

        inferred = _infer_external_resources(nwbfile)

        assert inferred["ExternalResources"]["species"] == {"Mus musculus": MOUSE_SPECIES_TERM}
        assert inferred["ExternalResources"]["brain_regions"]["CA1"]["id"] == "MBA:382"
