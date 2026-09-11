"""Tests for neuroconv.tools.ontology: term resolution, metadata inference, and HERD annotation."""

from datetime import datetime

import pytest
from dateutil.tz import tzutc
from pynwb import NWBFile
from pynwb.file import Subject

from neuroconv.tools.ontology import (
    ANATOMY_TERMS,
    HBA_TERMS,
    MBA_TERMS,
    SPECIES_TERMS,
    STRAIN_TERMS,
    AnatomyTerm,
    BrainRegionTerm,
    SpeciesTerm,
    StrainTerm,
    add_anatomy_external_resources,
    add_brain_region_external_resources,
    add_species_external_resource,
    add_strain_external_resource,
    get_anatomy_term,
    get_brain_region_term,
    get_species_suggestion,
    get_species_term,
    get_strain_suggestion,
    get_strain_term,
    infer_anatomy_ontology_metadata,
    infer_brain_region_ontology_metadata,
    infer_species_ontology_metadata,
    infer_strain_ontology_metadata,
    validate_species,
    validate_strain,
)

MOUSE_SPECIES_TERM = {"id": "NCBITaxon:10090", "uri": "http://purl.obolibrary.org/obo/NCBITaxon_10090"}
LONG_EVANS_STRAIN_TERM = {"id": "RRID:RGD_2308852", "uri": "https://scicrunch.org/resolver/RRID:RGD_2308852"}


def _make_nwbfile(species="Mus musculus", strain=None, with_subject=True) -> NWBFile:
    nwbfile = NWBFile(
        session_description="d",
        identifier="id",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )
    if with_subject:
        nwbfile.subject = Subject(subject_id="s1", species=species, strain=strain)
    return nwbfile


def _add_electrodes(nwbfile: NWBFile, locations) -> None:
    device = nwbfile.create_device(name="probe")
    group = nwbfile.create_electrode_group(name="group0", description="d", location="unknown", device=device)
    for index, location in enumerate(locations):
        nwbfile.add_electrode(location=location, group=group, id=index)


def _add_skeleton(nwbfile: NWBFile, node_names, name="skeleton0"):
    import ndx_pose

    skeleton = ndx_pose.Skeleton(name=name, nodes=list(node_names), edges=None)
    behavior_module = nwbfile.processing.get("behavior") or nwbfile.create_processing_module(
        name="behavior", description="d"
    )
    if "Skeletons" not in behavior_module.data_interfaces:
        behavior_module.add(ndx_pose.Skeletons(skeletons=[skeleton]))
    else:
        behavior_module["Skeletons"].add_skeletons(skeleton)
    return skeleton


def _optical_channel():
    from pynwb.ophys import OpticalChannel

    return OpticalChannel(name="channel0", description="d", emission_lambda=500.0)


def _ecephys_brain_regions(mapping: dict) -> dict:
    """A metadata dict carrying an ``Ecephys.ontology.brain_regions`` map."""
    return {"Ecephys": {"ontology": {"brain_regions": mapping}}}


def _pose_estimation_anatomy(mapping: dict) -> dict:
    """A metadata dict carrying a ``PoseEstimation.ontology.anatomy`` map."""
    return {"PoseEstimation": {"ontology": {"anatomy": mapping}}}


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
# Strain term resolution
# ---------------------------------------------------------------------------


class TestStrainTerms:
    def test_table_entries_are_self_consistent(self):
        for canonical_name, term in STRAIN_TERMS.items():
            assert isinstance(term, StrainTerm)
            assert term.canonical_name == canonical_name
            assert term.rrid.startswith("RRID:")

    def test_entity_uri_is_derived_from_rrid(self):
        term = STRAIN_TERMS["Long-Evans"]
        assert term.rrid == "RRID:RGD_2308852"
        assert term.entity_uri == "https://scicrunch.org/resolver/RRID:RGD_2308852"

    def test_exact_canonical_name_resolves(self):
        term = get_strain_term("Long-Evans")
        assert term.canonical_name == "Long-Evans"
        assert term.rrid == "RRID:RGD_2308852"

    def test_informal_spelling_suggestion(self):
        suggestion = get_strain_suggestion("black 6")
        term, reason = suggestion
        assert term.canonical_name == "C57BL/6J"
        assert "informal spelling" in reason
        assert get_strain_term("black 6").canonical_name == "C57BL/6J"

    def test_informal_spelling_is_case_insensitive_and_stripped(self):
        term, _ = get_strain_suggestion("  Long Evans  ")
        assert term.canonical_name == "Long-Evans"

    def test_typo_suggestion(self):
        suggestion = get_strain_suggestion("Sprague Dawly")
        term, reason = suggestion
        assert term.canonical_name == "Sprague Dawley"
        assert "closely matches" in reason

    @pytest.mark.parametrize("strain", ["Octodon degus strain X", "", None, 42])
    def test_unrecognized_returns_none(self, strain):
        assert get_strain_suggestion(strain) is None
        assert get_strain_term(strain) is None

    def test_validate_strain_no_warning_for_canonical_name(self, recwarn):
        assert validate_strain("Long-Evans") is None
        assert len(recwarn) == 0

    def test_validate_strain_warns_and_returns_term_for_informal_spelling(self):
        with pytest.warns(UserWarning, match="C57BL/6J"):
            term = validate_strain("black 6")
        assert term.canonical_name == "C57BL/6J"

    def test_validate_strain_warning_points_to_bioregistry(self):
        with pytest.warns(UserWarning, match="bioregistry.io/RRID:RGD_2308852"):
            validate_strain("long evans")


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
# General-anatomy term resolution
# ---------------------------------------------------------------------------


class TestAnatomyTerms:
    def test_table_entries_are_self_consistent(self):
        for canonical_name, term in ANATOMY_TERMS.items():
            assert isinstance(term, AnatomyTerm)
            assert term.name == canonical_name
            assert term.curie.startswith("UBERON:")

    def test_exact_canonical_name_resolves(self):
        term = get_anatomy_term("Trapezius muscle")
        assert term.name == "Trapezius muscle"
        assert term.curie == "UBERON:0002380"
        assert term.entity_uri == "http://purl.obolibrary.org/obo/UBERON_0002380"

    def test_case_insensitive_match(self):
        assert get_anatomy_term("snout").name == "Snout"
        assert get_anatomy_term("SNOUT").name == "Snout"

    @pytest.mark.parametrize(
        "alias, expected_canonical",
        [
            ("nose", "Snout"),
            ("forepaw", "Hand"),
            ("hindpaw", "Foot"),
            ("carpus", "Wrist"),
            ("trapezius", "Trapezius muscle"),
        ],
    )
    def test_informal_alias_resolves(self, alias, expected_canonical):
        assert get_anatomy_term(alias).name == expected_canonical

    @pytest.mark.parametrize("name", ["EarL", "ear_l", "not a structure", "", None, 42])
    def test_unrecognized_returns_none(self, name):
        # Lab-specific keypoint names with laterality markers are not recognized -- high precision
        # over guessing.
        assert get_anatomy_term(name) is None


# ---------------------------------------------------------------------------
# Species ontology inference (metadata -> metadata)
# ---------------------------------------------------------------------------


class TestInferSpeciesOntologyMetadata:
    def test_recognized_species_writes_term(self):
        metadata = {"Subject": {"species": "Mus musculus"}}
        infer_species_ontology_metadata(metadata)
        assert metadata["Subject"]["ontology"]["species"] == MOUSE_SPECIES_TERM

    def test_common_name_is_resolved_and_warns(self):
        metadata = {"Subject": {"species": "mouse"}}
        with pytest.warns(UserWarning, match="Mus musculus"):
            infer_species_ontology_metadata(metadata)
        assert metadata["Subject"]["ontology"]["species"] == MOUSE_SPECIES_TERM

    def test_unrecognized_species_leaves_metadata_untouched(self):
        metadata = {"Subject": {"species": "Octodon degus"}}
        infer_species_ontology_metadata(metadata)
        assert metadata["Subject"].get("ontology", {}).get("species") is None

    def test_existing_user_term_is_not_overwritten(self):
        curated = {"id": "NCBITaxon:99999", "uri": "https://example.org/custom"}
        metadata = {"Subject": {"species": "Mus musculus", "ontology": {"species": curated}}}
        infer_species_ontology_metadata(metadata)
        assert metadata["Subject"]["ontology"]["species"] == curated

    def test_no_subject_block_is_a_noop(self):
        metadata = {"NWBFile": {}}
        assert infer_species_ontology_metadata(metadata) is metadata


# ---------------------------------------------------------------------------
# Strain ontology inference (metadata -> metadata)
# ---------------------------------------------------------------------------


class TestInferStrainOntologyMetadata:
    def test_recognized_strain_writes_term(self):
        metadata = {"Subject": {"strain": "Long-Evans"}}
        infer_strain_ontology_metadata(metadata)
        assert metadata["Subject"]["ontology"]["strain"] == LONG_EVANS_STRAIN_TERM

    def test_informal_spelling_is_resolved_and_warns(self):
        metadata = {"Subject": {"strain": "black 6"}}
        with pytest.warns(UserWarning, match="C57BL/6J"):
            infer_strain_ontology_metadata(metadata)
        assert metadata["Subject"]["ontology"]["strain"]["id"] == "RRID:IMSR_JAX:000664"

    def test_unrecognized_strain_leaves_metadata_untouched(self):
        metadata = {"Subject": {"strain": "my in-house line"}}
        infer_strain_ontology_metadata(metadata)
        assert metadata["Subject"].get("ontology", {}).get("strain") is None

    def test_existing_user_term_is_not_overwritten(self):
        curated = {"id": "RRID:EXAMPLE:1", "uri": "https://example.org/1"}
        metadata = {"Subject": {"strain": "Long-Evans", "ontology": {"strain": curated}}}
        infer_strain_ontology_metadata(metadata)
        assert metadata["Subject"]["ontology"]["strain"] == curated

    def test_no_subject_block_is_a_noop(self):
        metadata = {"NWBFile": {}}
        assert infer_strain_ontology_metadata(metadata) is metadata


# ---------------------------------------------------------------------------
# Brain-region ontology inference (file + metadata -> metadata)
# ---------------------------------------------------------------------------


class TestInferBrainRegionOntologyMetadata:
    def test_electrode_locations_are_resolved_under_ecephys(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        _add_electrodes(nwbfile, ["CA1", "VISp", "unknown"])
        metadata = {}

        infer_brain_region_ontology_metadata(nwbfile, metadata)
        brain_regions = metadata["Ecephys"]["ontology"]["brain_regions"]
        assert brain_regions["CA1"] == {"id": "MBA:382", "uri": MBA_TERMS["CA1"].entity_uri}
        assert brain_regions["VISp"]["id"] == "MBA:385"
        assert "unknown" not in brain_regions  # unresolved locations are skipped

    def test_species_selects_the_atlas(self):
        nwbfile = _make_nwbfile(species="Homo sapiens")
        _add_electrodes(nwbfile, ["CA1"])
        metadata = {}

        infer_brain_region_ontology_metadata(nwbfile, metadata)
        assert metadata["Ecephys"]["ontology"]["brain_regions"]["CA1"]["id"] == "HBA:12892"

    def test_imaging_plane_locations_are_resolved_under_ophys(self):
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
        assert metadata["Ophys"]["ontology"]["brain_regions"]["SSp"]["id"] == "MBA:322"

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
        metadata = _ecephys_brain_regions({"CA1": curated})

        infer_brain_region_ontology_metadata(nwbfile, metadata)
        assert metadata["Ecephys"]["ontology"]["brain_regions"]["CA1"] == curated


# ---------------------------------------------------------------------------
# Anatomy ontology inference (file + metadata -> metadata)
# ---------------------------------------------------------------------------


class TestInferAnatomyOntologyMetadata:
    def test_skeleton_node_names_are_resolved(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout", "Shoulder", "EarL"])
        metadata = {}

        infer_anatomy_ontology_metadata(nwbfile, metadata)
        anatomy = metadata["PoseEstimation"]["ontology"]["anatomy"]
        assert anatomy["Snout"]["id"] == get_anatomy_term("Snout").curie
        assert anatomy["Shoulder"]["id"] == get_anatomy_term("Shoulder").curie
        assert "EarL" not in anatomy  # unresolved (lab-specific, laterality marker) is skipped

    def test_no_skeleton_is_a_noop(self):
        nwbfile = _make_nwbfile()
        metadata = {}
        infer_anatomy_ontology_metadata(nwbfile, metadata)
        assert metadata == {}

    def test_existing_user_term_is_not_overwritten(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout"])
        curated = {"id": "UBERON:9999999", "uri": "https://example.org/custom"}
        metadata = _pose_estimation_anatomy({"Snout": curated})

        infer_anatomy_ontology_metadata(nwbfile, metadata)
        assert metadata["PoseEstimation"]["ontology"]["anatomy"]["Snout"] == curated


# ---------------------------------------------------------------------------
# Species HERD annotation (metadata -> file)
# ---------------------------------------------------------------------------


class TestSpeciesExternalResource:
    @pytest.mark.parametrize(
        "kwargs, metadata",
        [
            (dict(with_subject=False), {"Subject": {"ontology": {"species": MOUSE_SPECIES_TERM}}}),
            (dict(), None),  # no metadata
            (dict(), {"Subject": {"species": "Mus musculus"}}),  # metadata but no ontology term
        ],
    )
    def test_noop_cases(self, kwargs, metadata):
        nwbfile = _make_nwbfile(**kwargs)
        assert add_species_external_resource(nwbfile, metadata=metadata) is False
        assert nwbfile.external_resources is None

    def test_species_term_from_metadata_is_annotated(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        metadata = {"Subject": {"species": "Mus musculus", "ontology": {"species": MOUSE_SPECIES_TERM}}}
        assert add_species_external_resource(nwbfile, metadata=metadata) is True

        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["Mus musculus"]
        assert dataframe["entity_id"].tolist() == ["NCBITaxon:10090"]

        objects = nwbfile.external_resources.objects.to_dataframe()
        assert objects["object_id"].tolist() == [nwbfile.subject.object_id]
        assert objects["relative_path"].tolist() == ["species"]

    def test_idempotent(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        metadata = {"Subject": {"ontology": {"species": MOUSE_SPECIES_TERM}}}
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

        metadata = {"Subject": {"ontology": {"species": MOUSE_SPECIES_TERM}}}
        assert add_species_external_resource(nwbfile, metadata=metadata) is True
        assert nwbfile.external_resources is herd  # extended in place, not replaced
        assert len(herd.entities[:]) == 2


# ---------------------------------------------------------------------------
# Strain HERD annotation (metadata -> file)
# ---------------------------------------------------------------------------


class TestStrainExternalResource:
    @pytest.mark.parametrize(
        "kwargs, metadata",
        [
            (dict(with_subject=False), {"Subject": {"ontology": {"strain": LONG_EVANS_STRAIN_TERM}}}),
            (dict(strain="Long-Evans"), None),  # no metadata
            (dict(strain="Long-Evans"), {"Subject": {"strain": "Long-Evans"}}),  # metadata but no ontology term
            (dict(strain=None), {"Subject": {"strain": None, "ontology": {"strain": LONG_EVANS_STRAIN_TERM}}}),
        ],
    )
    def test_noop_cases(self, kwargs, metadata):
        nwbfile = _make_nwbfile(**kwargs)
        assert add_strain_external_resource(nwbfile, metadata=metadata) is False
        assert nwbfile.external_resources is None

    def test_strain_term_from_metadata_is_annotated(self):
        nwbfile = _make_nwbfile(strain="Long-Evans")
        metadata = {"Subject": {"strain": "Long-Evans", "ontology": {"strain": LONG_EVANS_STRAIN_TERM}}}
        assert add_strain_external_resource(nwbfile, metadata=metadata) is True

        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["Long-Evans"]
        assert dataframe["entity_id"].tolist() == ["RRID:RGD_2308852"]

        objects = nwbfile.external_resources.objects.to_dataframe()
        assert objects["object_id"].tolist() == [nwbfile.subject.object_id]
        assert objects["relative_path"].tolist() == ["strain"]

    def test_idempotent(self):
        nwbfile = _make_nwbfile(strain="Long-Evans")
        metadata = {"Subject": {"ontology": {"strain": LONG_EVANS_STRAIN_TERM}}}
        assert add_strain_external_resource(nwbfile, metadata=metadata) is True
        assert add_strain_external_resource(nwbfile, metadata=metadata) is False
        assert len(nwbfile.external_resources.entities[:]) == 1

    def test_extends_existing_herd_in_place(self):
        from hdmf.common import HERD
        from pynwb import get_type_map

        nwbfile = _make_nwbfile(strain="Long-Evans")
        herd = HERD(type_map=get_type_map())
        herd.add_ref(
            container=nwbfile.subject,
            attribute="subject_id",
            key="s1",
            entity_id="EXAMPLE:1",
            entity_uri="https://example.org/1",
        )
        nwbfile.external_resources = herd

        metadata = {"Subject": {"ontology": {"strain": LONG_EVANS_STRAIN_TERM}}}
        assert add_strain_external_resource(nwbfile, metadata=metadata) is True
        assert nwbfile.external_resources is herd  # extended in place, not replaced
        assert len(herd.entities[:]) == 2

    def test_maps_strain_to_multiple_ontology_terms(self):
        nwbfile = _make_nwbfile(strain="Long-Evans")
        metadata = {
            "Subject": {
                "ontology": {
                    "strain": [
                        LONG_EVANS_STRAIN_TERM,
                        {"id": "RRID:EXAMPLE:3", "uri": "https://example.org/3"},
                    ]
                }
            }
        }

        assert add_strain_external_resource(nwbfile, metadata=metadata) is True
        dataframe = nwbfile.external_resources.to_dataframe()
        assert sorted(dataframe["entity_id"].tolist()) == ["RRID:EXAMPLE:3", "RRID:RGD_2308852"]

    @pytest.mark.parametrize(
        "bad_value",
        ["RRID:EXAMPLE:1", {"id": "RRID:EXAMPLE:1"}, {"uri": "https://example.org/1"}, {"id": "", "uri": ""}],
    )
    def test_malformed_metadata_term_raises(self, bad_value):
        nwbfile = _make_nwbfile(strain="a strain")
        metadata = {"Subject": {"ontology": {"strain": bad_value}}}
        with pytest.raises((TypeError, ValueError)):
            add_strain_external_resource(nwbfile, metadata=metadata)


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
        metadata = _ecephys_brain_regions({"some other area": {"id": "MBA:1", "uri": "https://example.org/1"}})
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
        metadata = {
            "Ecephys": {
                "ontology": {
                    "brain_regions": {
                        "CA1": {"id": "MBA:382", "uri": "https://example.org/MBA_382"},
                        "VISp": {"id": "MBA:385", "uri": "https://example.org/MBA_385"},
                        "MOp": {"id": "MBA:985", "uri": "https://example.org/MBA_985"},
                    }
                }
            },
            "Ophys": {"ontology": {"brain_regions": {"SSp": {"id": "MBA:322", "uri": "https://example.org/MBA_322"}}}},
        }

        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 4
        dataframe = nwbfile.external_resources.to_dataframe()
        by_key = dict(zip(dataframe["key"], dataframe["entity_id"]))
        assert by_key == {"CA1": "MBA:382", "VISp": "MBA:385", "MOp": "MBA:985", "SSp": "MBA:322"}

        # HERD records the electrodes reference against the ``location`` column, not the table.
        objects = nwbfile.external_resources.objects.to_dataframe()
        assert nwbfile.electrodes["location"].object_id in objects["object_id"].tolist()

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
        fiber_photometry_metadata["ontology"] = dict(
            brain_regions={"CA1": {"id": "MBA:382", "uri": "https://example.org/MBA_382"}}
        )
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
        metadata = _ecephys_brain_regions(
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
        metadata = _ecephys_brain_regions(
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
        metadata = _ecephys_brain_regions({"area": bad_value})
        with pytest.raises((TypeError, ValueError)):
            add_brain_region_external_resources(nwbfile, metadata=metadata)

    def test_idempotent(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1", "VISp"])
        metadata = _ecephys_brain_regions(
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

        metadata = _ecephys_brain_regions({"CA1": {"id": "MBA:382", "uri": "https://example.org/MBA_382"}})
        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 1
        assert nwbfile.external_resources is herd  # extended in place, not replaced
        assert len(herd.entities[:]) == 2


# ---------------------------------------------------------------------------
# General-anatomy HERD annotation (metadata -> file)
# ---------------------------------------------------------------------------


class TestAnatomyExternalResources:
    def test_noop_without_metadata(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout"])
        assert add_anatomy_external_resources(nwbfile) == 0
        assert nwbfile.external_resources is None

    def test_noop_when_metadata_covers_no_present_node(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout", "EarL"])
        metadata = _pose_estimation_anatomy({"some other node": {"id": "UBERON:1", "uri": "https://example.org/1"}})
        assert add_anatomy_external_resources(nwbfile, metadata=metadata) == 0
        assert nwbfile.external_resources is None

    def test_skeleton_nodes_are_annotated(self):
        nwbfile = _make_nwbfile()
        skeleton = _add_skeleton(nwbfile, ["Snout", "Snout", "EarL", "Shoulder"])  # duplicates collapse
        metadata = _pose_estimation_anatomy(
            {
                "Snout": {"id": "UBERON:0006333", "uri": "https://example.org/UBERON_0006333"},
                "Shoulder": {"id": "UBERON:0001467", "uri": "https://example.org/UBERON_0001467"},
            }
        )

        assert add_anatomy_external_resources(nwbfile, metadata=metadata) == 2
        dataframe = nwbfile.external_resources.to_dataframe()
        by_key = dict(zip(dataframe["key"], dataframe["entity_id"]))
        assert by_key == {"Snout": "UBERON:0006333", "Shoulder": "UBERON:0001467"}

        # HERD records the reference against the Skeleton itself (nodes is a plain array
        # attribute, not a separate VectorData column); both keys share that one object row.
        objects = nwbfile.external_resources.objects.to_dataframe()
        assert objects["object_id"].tolist() == [skeleton.object_id]
        assert objects["relative_path"].tolist() == ["nodes"]

    def test_multiple_skeletons_are_all_annotated(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout"], name="skeleton_rat1")
        _add_skeleton(nwbfile, ["Tail"], name="skeleton_rat2")
        metadata = _pose_estimation_anatomy(
            {
                "Snout": {"id": "UBERON:0006333", "uri": "https://example.org/UBERON_0006333"},
                "Tail": {"id": "UBERON:0002415", "uri": "https://example.org/UBERON_0002415"},
            }
        )

        assert add_anatomy_external_resources(nwbfile, metadata=metadata) == 2
        dataframe = nwbfile.external_resources.to_dataframe()
        assert sorted(dataframe["key"].tolist()) == ["Snout", "Tail"]

    def test_maps_one_node_to_multiple_ontology_terms(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout"])
        metadata = _pose_estimation_anatomy(
            {
                "Snout": [
                    {"id": "UBERON:0006333", "uri": "http://purl.obolibrary.org/obo/UBERON_0006333"},
                    {"id": "EXAMPLE:1", "uri": "https://example.org/1"},
                ]
            }
        )

        assert add_anatomy_external_resources(nwbfile, metadata=metadata) == 2
        dataframe = nwbfile.external_resources.to_dataframe()
        assert sorted(dataframe["entity_id"].tolist()) == ["EXAMPLE:1", "UBERON:0006333"]

    @pytest.mark.parametrize(
        "bad_value",
        ["UBERON:0006333", {"id": "UBERON:0006333"}, {"uri": "https://example.org/1"}, {"id": "", "uri": ""}],
    )
    def test_malformed_metadata_term_raises(self, bad_value):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout"])
        metadata = _pose_estimation_anatomy({"Snout": bad_value})
        with pytest.raises((TypeError, ValueError)):
            add_anatomy_external_resources(nwbfile, metadata=metadata)

    def test_idempotent(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout", "Tail"])
        metadata = _pose_estimation_anatomy(
            {
                "Snout": {"id": "UBERON:0006333", "uri": "https://example.org/UBERON_0006333"},
                "Tail": {"id": "UBERON:0002415", "uri": "https://example.org/UBERON_0002415"},
            }
        )
        assert add_anatomy_external_resources(nwbfile, metadata=metadata) == 2
        assert add_anatomy_external_resources(nwbfile, metadata=metadata) == 0
        assert len(nwbfile.external_resources.entities[:]) == 2

    def test_extends_existing_herd_in_place(self):
        from hdmf.common import HERD
        from pynwb import get_type_map

        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout"])
        herd = HERD(type_map=get_type_map())
        herd.add_ref(
            container=nwbfile.subject,
            attribute="subject_id",
            key="s1",
            entity_id="EXAMPLE:1",
            entity_uri="https://example.org/1",
        )
        nwbfile.external_resources = herd

        metadata = _pose_estimation_anatomy({"Snout": {"id": "UBERON:0006333", "uri": "https://example.org/UBERON_0006333"}})
        assert add_anatomy_external_resources(nwbfile, metadata=metadata) == 1
        assert nwbfile.external_resources is herd  # extended in place, not replaced
        assert len(herd.entities[:]) == 2


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
        metadata["Subject"] = dict(subject_id="m1", species="Mus musculus", strain="C57BL/6J", sex="M", age="P30D")
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
        infer_strain_ontology_metadata(metadata)
        infer_brain_region_ontology_metadata(staging_nwbfile, metadata)

        nwbfile = interface.create_nwbfile(metadata=metadata)
        entity_ids = set(nwbfile.external_resources.to_dataframe()["entity_id"].tolist())
        # Species (NCBITaxon), strain (RRID), and brain-region (MBA) references are all written.
        assert "NCBITaxon:10090" in entity_ids
        assert "RRID:IMSR_JAX:000664" in entity_ids
        assert {"MBA:382", "MBA:385"}.issubset(entity_ids)

    def test_references_round_trip_through_file(self, tmp_path):
        from pynwb import NWBHDF5IO

        interface = self._mouse_recording_interface(["CA1", "VISp"])
        metadata = self._mouse_metadata(interface)
        staging_nwbfile = interface.create_nwbfile(metadata=metadata)
        infer_species_ontology_metadata(metadata)
        infer_strain_ontology_metadata(metadata)
        infer_brain_region_ontology_metadata(staging_nwbfile, metadata)
        nwbfile = interface.create_nwbfile(metadata=metadata)

        path = tmp_path / "ontology_herd.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(path, "r") as io:
            read_nwbfile = io.read()
            entity_ids = set(read_nwbfile.external_resources.to_dataframe()["entity_id"].tolist())

        assert {"NCBITaxon:10090", "RRID:IMSR_JAX:000664", "MBA:382", "MBA:385"}.issubset(entity_ids)

    def test_inferred_anatomy_terms_are_written_through_create_nwbfile(self):
        from neuroconv.tools.testing.mock_interfaces import MockPoseEstimationInterface

        interface = MockPoseEstimationInterface(num_nodes=3)  # nodes: head, neck, left_shoulder
        metadata = interface.get_metadata()
        metadata["Subject"] = dict(subject_id="m1", species="Mus musculus", sex="M", age="P30D")

        # Inference needs the populated file to see the skeleton node names.
        staging_nwbfile = interface.create_nwbfile(metadata=metadata)
        infer_species_ontology_metadata(metadata)
        infer_anatomy_ontology_metadata(staging_nwbfile, metadata)

        nwbfile = interface.create_nwbfile(metadata=metadata)
        entity_ids = set(nwbfile.external_resources.to_dataframe()["entity_id"].tolist())
        assert "NCBITaxon:10090" in entity_ids
        assert {"UBERON:0000033", "UBERON:0000974"}.issubset(entity_ids)  # head, neck
