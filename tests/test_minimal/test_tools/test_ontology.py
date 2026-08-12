"""Tests for neuroconv.tools.ontology: species/brain-region term resolution and HERD annotation."""

from datetime import datetime

import pytest
from dateutil.tz import tzutc
from pynwb import NWBFile
from pynwb.file import Subject

from neuroconv.tools.ontology import (
    HBA_TERMS,
    MBA_TERMS,
    SPECIES_TERMS,
    STRAIN_TERMS,
    BrainRegionTerm,
    SpeciesTerm,
    StrainTerm,
    add_brain_region_external_resources,
    add_species_external_resource,
    add_strain_external_resource,
    get_brain_region_term,
    get_species_suggestion,
    get_species_term,
    get_strain_suggestion,
    get_strain_term,
    validate_species,
    validate_strain,
)


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


def _optical_channel():
    from pynwb.ophys import OpticalChannel

    return OpticalChannel(name="channel0", description="d", emission_lambda=500.0)


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
# Species HERD annotation
# ---------------------------------------------------------------------------


class TestSpeciesExternalResource:
    @pytest.mark.parametrize("kwargs", [dict(with_subject=False), dict(species=None), dict(species="Octodon degus")])
    def test_noop_cases(self, kwargs):
        nwbfile = _make_nwbfile(**kwargs)
        assert add_species_external_resource(nwbfile) is False
        assert nwbfile.external_resources is None

    def test_recognized_species_is_annotated(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        assert add_species_external_resource(nwbfile) is True

        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["Mus musculus"]
        assert dataframe["entity_id"].tolist() == ["NCBITaxon:10090"]

        objects = nwbfile.external_resources.objects.to_dataframe()
        assert objects["object_id"].tolist() == [nwbfile.subject.object_id]
        assert objects["relative_path"].tolist() == ["species"]

    def test_idempotent(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        assert add_species_external_resource(nwbfile) is True
        assert add_species_external_resource(nwbfile) is False
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

        assert add_species_external_resource(nwbfile) is True
        assert nwbfile.external_resources is herd  # extended in place, not replaced
        assert len(herd.entities[:]) == 2


# ---------------------------------------------------------------------------
# Strain HERD annotation
# ---------------------------------------------------------------------------


class TestStrainExternalResource:
    @pytest.mark.parametrize(
        "kwargs", [dict(with_subject=False), dict(strain=None), dict(strain="a custom in-house line")]
    )
    def test_noop_cases(self, kwargs):
        nwbfile = _make_nwbfile(**kwargs)
        assert add_strain_external_resource(nwbfile) is False
        assert nwbfile.external_resources is None

    def test_recognized_strain_is_annotated(self):
        nwbfile = _make_nwbfile(strain="Long-Evans")
        assert add_strain_external_resource(nwbfile) is True

        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["Long-Evans"]
        assert dataframe["entity_id"].tolist() == ["RRID:RGD_2308852"]

        objects = nwbfile.external_resources.objects.to_dataframe()
        assert objects["object_id"].tolist() == [nwbfile.subject.object_id]
        assert objects["relative_path"].tolist() == ["strain"]

    def test_idempotent(self):
        nwbfile = _make_nwbfile(strain="Long-Evans")
        assert add_strain_external_resource(nwbfile) is True
        assert add_strain_external_resource(nwbfile) is False
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

        assert add_strain_external_resource(nwbfile) is True
        assert nwbfile.external_resources is herd  # extended in place, not replaced
        assert len(herd.entities[:]) == 2

    def test_metadata_mapping_annotates_unrecognized_and_takes_precedence(self):
        nwbfile = _make_nwbfile(strain="Long-Evans")
        metadata = {
            "Strain": {
                # Overrides the curated result (RRID:RGD_2308852) with an explicit term.
                "Long-Evans": {"id": "RRID:EXAMPLE:2", "uri": "https://example.org/2"},
            }
        }
        assert add_strain_external_resource(nwbfile, metadata=metadata) is True
        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["entity_id"].tolist() == ["RRID:EXAMPLE:2"]

    def test_maps_strain_to_multiple_ontology_terms(self):
        nwbfile = _make_nwbfile(strain="Long-Evans")
        metadata = {
            "Strain": {
                "Long-Evans": [
                    {"id": "RRID:RGD_2308852", "uri": "https://scicrunch.org/resolver/RRID:RGD_2308852"},
                    {"id": "RRID:EXAMPLE:3", "uri": "https://example.org/3"},
                ]
            }
        }

        assert add_strain_external_resource(nwbfile, metadata=metadata) is True
        dataframe = nwbfile.external_resources.to_dataframe()
        assert sorted(dataframe["entity_id"].tolist()) == ["RRID:EXAMPLE:3", "RRID:RGD_2308852"]

    def test_metadata_mapping_without_matching_entry_falls_back_to_offline_lookup(self):
        nwbfile = _make_nwbfile(strain="Long-Evans")
        metadata = {"Strain": {"a different strain": {"id": "RRID:EXAMPLE:4", "uri": "https://example.org/4"}}}

        assert add_strain_external_resource(nwbfile, metadata=metadata) is True
        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["entity_id"].tolist() == ["RRID:RGD_2308852"]

    @pytest.mark.parametrize(
        "bad_value",
        ["RRID:EXAMPLE:1", {"id": "RRID:EXAMPLE:1"}, {"uri": "https://example.org/1"}, {"id": "", "uri": ""}],
    )
    def test_malformed_metadata_term_raises(self, bad_value):
        nwbfile = _make_nwbfile(strain="a strain")
        metadata = {"Strain": {"a strain": bad_value}}
        with pytest.raises((TypeError, ValueError)):
            add_strain_external_resource(nwbfile, metadata=metadata)


# ---------------------------------------------------------------------------
# Brain-region HERD annotation
# ---------------------------------------------------------------------------


class TestBrainRegionExternalResources:
    def test_noop_when_no_subject(self):
        nwbfile = _make_nwbfile(with_subject=False)
        _add_electrodes(nwbfile, ["CA1"])
        assert add_brain_region_external_resources(nwbfile) == 0
        assert nwbfile.external_resources is None

    def test_noop_when_nothing_recognized(self):
        nwbfile = _make_nwbfile(species="Rattus norvegicus")  # no dedicated atlas
        _add_electrodes(nwbfile, ["CA1", "VISp", "unknown"])  # mouse-only acronyms
        assert add_brain_region_external_resources(nwbfile) == 0
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

        assert add_brain_region_external_resources(nwbfile) == 4
        dataframe = nwbfile.external_resources.to_dataframe()
        by_key = dict(zip(dataframe["key"], dataframe["entity_id"]))
        assert by_key == {"CA1": "MBA:382", "VISp": "MBA:385", "MOp": "MBA:985", "SSp": "MBA:322"}

        # HERD records the electrodes reference against the ``location`` column, not the table.
        objects = nwbfile.external_resources.objects.to_dataframe()
        assert nwbfile.electrodes["location"].object_id in objects["object_id"].tolist()

    def test_human_locations_are_annotated_with_hba(self):
        nwbfile = _make_nwbfile(species="Homo sapiens")
        _add_electrodes(nwbfile, ["CA1", "unknown"])

        assert add_brain_region_external_resources(nwbfile) == 1
        dataframe = nwbfile.external_resources.to_dataframe()
        # Same "CA1" acronym resolves to the human atlas id, not the mouse one.
        assert dataframe["entity_id"].tolist() == ["HBA:12892"]

    def test_uberon_fallback_is_used_for_species_without_a_dedicated_atlas(self):
        nwbfile = _make_nwbfile(species="Rattus norvegicus")
        _add_electrodes(nwbfile, ["hippocampus"])
        assert add_brain_region_external_resources(nwbfile) == 1
        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["entity_id"].tolist() == ["UBERON:0002421"]

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

    def test_metadata_mapping_annotates_unrecognized_and_takes_precedence(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["my special area", "CA1"])
        metadata = {
            "BrainRegions": {
                "my special area": {"id": "MBA:42", "uri": "https://example.org/MBA_42"},
                # Overrides the offline result (MBA:382) with an explicit term.
                "CA1": {"id": "MBA:999", "uri": "https://example.org/MBA_999"},
            }
        }

        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 2
        dataframe = nwbfile.external_resources.to_dataframe()
        assert dict(zip(dataframe["key"], dataframe["entity_id"])) == {
            "my special area": "MBA:42",
            "CA1": "MBA:999",
        }

    def test_maps_one_area_to_multiple_ontology_terms(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1"])
        metadata = {
            "BrainRegions": {
                "CA1": [
                    {"id": "MBA:382", "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382"},
                    {"id": "UBERON:0003881", "uri": "http://purl.obolibrary.org/obo/UBERON_0003881"},
                ]
            }
        }

        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 2
        dataframe = nwbfile.external_resources.to_dataframe()
        assert sorted(dataframe["entity_id"].tolist()) == ["MBA:382", "UBERON:0003881"]

    def test_metadata_mapping_applies_regardless_of_species(self):
        # Ontology-agnostic and not gated on species; "CA1" is not in the rat's UBERON fallback
        # vocabulary, so only the metadata-defined region resolves.
        nwbfile = _make_nwbfile(species="Rattus norvegicus")
        _add_electrodes(nwbfile, ["my region", "CA1"])
        metadata = {
            "BrainRegions": {
                "my region": {"id": "UBERON:0002436", "uri": "http://purl.obolibrary.org/obo/UBERON_0002436"}
            }
        }

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
        metadata = {"BrainRegions": {"area": bad_value}}
        with pytest.raises((TypeError, ValueError)):
            add_brain_region_external_resources(nwbfile, metadata=metadata)

    def test_idempotent(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1", "VISp"])
        assert add_brain_region_external_resources(nwbfile) == 2
        assert add_brain_region_external_resources(nwbfile) == 0
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

        assert add_brain_region_external_resources(nwbfile) == 1
        assert nwbfile.external_resources is herd  # extended in place, not replaced
        assert len(herd.entities[:]) == 2


# ---------------------------------------------------------------------------
# OntologyAnnotationMixin (overridable hooks) and write/read round trip
# ---------------------------------------------------------------------------


class TestOntologyAnnotationMixin:
    def _mouse_recording_interface(self, brain_areas):
        from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

        interface = MockRecordingInterface(num_channels=len(brain_areas), durations=(0.1,))
        interface.recording_extractor.set_property("brain_area", list(brain_areas))
        return interface

    def _mouse_metadata(self, interface):
        metadata = interface.get_metadata()
        metadata["Subject"] = dict(subject_id="m1", species="Mus musculus", strain="C57BL/6J", sex="M", age="P30D")
        return metadata

    def test_default_hooks_annotate_species_strain_and_brain_region_through_create_nwbfile(self):
        interface = self._mouse_recording_interface(["CA1", "VISp"])
        nwbfile = interface.create_nwbfile(metadata=self._mouse_metadata(interface))

        entity_ids = set(nwbfile.external_resources.to_dataframe()["entity_id"].tolist())
        # Species (NCBITaxon), strain (RRID), and brain-region (MBA) references are all attached
        # by the mixin.
        assert "NCBITaxon:10090" in entity_ids
        assert "RRID:IMSR_JAX:000664" in entity_ids
        assert {"MBA:382", "MBA:385"}.issubset(entity_ids)

    def test_subclass_can_override_brain_region_hook(self):
        from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

        class NoBrainRegionInterface(MockRecordingInterface):
            def add_brain_region_external_resources(self, nwbfile, metadata=None):
                return 0  # disable brain-region annotation entirely

        interface = NoBrainRegionInterface(num_channels=2, durations=(0.1,))
        interface.recording_extractor.set_property("brain_area", ["CA1", "VISp"])
        nwbfile = interface.create_nwbfile(metadata=self._mouse_metadata(interface))

        entity_ids = nwbfile.external_resources.to_dataframe()["entity_id"].tolist()
        assert not any(entity_id.startswith("MBA:") for entity_id in entity_ids)
        assert "NCBITaxon:10090" in entity_ids  # species annotation is unaffected

    def test_subclass_can_override_species_hook(self):
        from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

        class NoSpeciesInterface(MockRecordingInterface):
            def add_species_external_resource(self, nwbfile, metadata=None):
                return False  # disable species annotation entirely

        interface = NoSpeciesInterface(num_channels=2, durations=(0.1,))
        interface.recording_extractor.set_property("brain_area", ["CA1", "VISp"])
        nwbfile = interface.create_nwbfile(metadata=self._mouse_metadata(interface))

        entity_ids = nwbfile.external_resources.to_dataframe()["entity_id"].tolist()
        assert not any(entity_id.startswith("NCBITaxon:") for entity_id in entity_ids)
        assert {"MBA:382", "MBA:385"}.issubset(set(entity_ids))  # brain-region annotation is unaffected

    def test_species_strain_and_brain_region_references_round_trip_through_file(self, tmp_path):
        from pynwb import NWBHDF5IO

        interface = self._mouse_recording_interface(["CA1", "VISp"])
        nwbfile = interface.create_nwbfile(metadata=self._mouse_metadata(interface))

        path = tmp_path / "ontology_herd.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(path, "r") as io:
            read_nwbfile = io.read()
            entity_ids = set(read_nwbfile.external_resources.to_dataframe()["entity_id"].tolist())

        assert {"NCBITaxon:10090", "RRID:IMSR_JAX:000664", "MBA:382", "MBA:385"}.issubset(entity_ids)

    def test_subclass_can_override_strain_hook(self):
        from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

        class NoStrainInterface(MockRecordingInterface):
            def add_strain_external_resource(self, nwbfile, metadata=None):
                # Override to disable strain annotation entirely.
                return False

        interface = NoStrainInterface(num_channels=2, durations=(0.1,))
        interface.recording_extractor.set_property("brain_area", ["CA1", "VISp"])
        nwbfile = interface.create_nwbfile(metadata=self._mouse_metadata(interface))

        # No strain reference was added, but species and brain-region references still are.
        entity_ids = nwbfile.external_resources.to_dataframe()["entity_id"].tolist()
        assert not any(entity_id.startswith("RRID:") for entity_id in entity_ids)
        assert "NCBITaxon:10090" in entity_ids
        assert {"MBA:382", "MBA:385"}.issubset(set(entity_ids))
