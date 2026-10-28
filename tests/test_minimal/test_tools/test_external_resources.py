"""Tests for neuroconv.tools.external_resources: writing the terms stated in metadata into the file as HERD."""

from datetime import datetime
from pathlib import Path

import pytest
from dateutil.tz import tzutc
from jsonschema import ValidationError
from pynwb import NWBFile
from pynwb.file import Subject

from neuroconv.tools.external_resources import add_external_resources_to_nwbfile
from neuroconv.utils import load_dict_from_file
from neuroconv.utils.json_schema import validate_metadata

MOUSE_SPECIES_TERM = {"id": "NCBITaxon:10090", "uri": "http://purl.obolibrary.org/obo/NCBITaxon_10090"}
CA1_TERM = {"id": "MBA:382", "uri": "https://purl.brain-bican.org/ontology/mbao/MBA_382"}
C57BL6J_STRAIN_TERM = {"id": "RRID:IMSR_JAX:000664", "uri": "https://scicrunch.org/resolver/RRID:IMSR_JAX:000664"}


def _make_nwbfile(species="Mus musculus", with_subject=True, **subject_kwargs) -> NWBFile:
    nwbfile = NWBFile(
        session_description="d",
        identifier="id",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )
    if with_subject:
        nwbfile.subject = Subject(subject_id="s1", species=species, **subject_kwargs)
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
        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 0
        assert nwbfile.external_resources is None

    def test_species_term_from_metadata_is_annotated(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        metadata = {"ExternalResources": {"species": {"Mus musculus": MOUSE_SPECIES_TERM}}}
        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 1

        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["Mus musculus"]
        assert dataframe["entity_id"].tolist() == ["NCBITaxon:10090"]

        objects = nwbfile.external_resources.objects.to_dataframe()
        assert objects["object_id"].tolist() == [nwbfile.subject.object_id]
        assert objects["relative_path"].tolist() == ["species"]

    def test_several_terms_share_one_key(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        second_term = {"id": "EXAMPLE:1", "uri": "https://example.org/1"}
        metadata = {"ExternalResources": {"species": {"Mus musculus": [MOUSE_SPECIES_TERM, second_term]}}}
        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 2

        herd = nwbfile.external_resources
        assert sorted(herd.to_dataframe()["entity_id"]) == ["EXAMPLE:1", "NCBITaxon:10090"]
        assert len(herd.keys[:]) == 1


# ---------------------------------------------------------------------------
# Strain HERD annotation (metadata -> file)
# ---------------------------------------------------------------------------


class TestStrainExternalResource:
    @pytest.mark.parametrize(
        "subject_kwargs, metadata",
        [
            (dict(), {"ExternalResources": {"strain": {"C57BL/6J": C57BL6J_STRAIN_TERM}}}),  # no strain on the subject
            (dict(strain="C57BL/6J"), {"Subject": {"strain": "C57BL/6J"}}),  # metadata but no ontology term
            (dict(strain="C57BL/6J"), {"ExternalResources": {"strain": {"B6": C57BL6J_STRAIN_TERM}}}),  # another value
        ],
        ids=["no_strain", "no_term", "term_for_another_value"],
    )
    def test_noop_cases(self, subject_kwargs, metadata):
        nwbfile = _make_nwbfile(**subject_kwargs)
        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 0
        assert nwbfile.external_resources is None

    def test_strain_term_from_metadata_is_annotated(self):
        nwbfile = _make_nwbfile(strain="C57BL/6J")
        metadata = {"ExternalResources": {"strain": {"C57BL/6J": C57BL6J_STRAIN_TERM}}}
        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 1

        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["C57BL/6J"]
        assert dataframe["entity_id"].tolist() == ["RRID:IMSR_JAX:000664"]
        objects = nwbfile.external_resources.objects.to_dataframe()
        assert objects["relative_path"].tolist() == ["strain"]
        # Idempotent.
        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 0

    def test_species_and_strain_share_one_herd(self, tmp_path):
        from pynwb import NWBHDF5IO

        nwbfile = _make_nwbfile(species="Mus musculus", strain="C57BL/6J")
        metadata = {
            "ExternalResources": {
                "species": {"Mus musculus": MOUSE_SPECIES_TERM},
                "strain": {"C57BL/6J": C57BL6J_STRAIN_TERM},
            }
        }
        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 2

        path = tmp_path / "strain.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)
        assert _written_references(path) == {MOUSE_REFERENCE, ("Subject", "C57BL/6J", "RRID:IMSR_JAX:000664")}


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
        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 0
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

        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 5
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

        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 2
        dataframe = nwbfile.external_resources.to_dataframe()
        assert sorted(dataframe["entity_id"].tolist()) == ["MBA:382", "UBERON:0003881"]

    def test_annotation_is_species_agnostic(self):
        # The writer never looks at the subject; a rat file is annotated from metadata alone.
        nwbfile = _make_nwbfile(species="Rattus norvegicus")
        _add_electrodes(nwbfile, ["my region", "CA1"])
        metadata = _brain_regions_metadata(
            {"my region": {"id": "UBERON:0002436", "uri": "http://purl.obolibrary.org/obo/UBERON_0002436"}}
        )

        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 1
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
            add_external_resources_to_nwbfile(nwbfile, metadata=metadata)


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
            {"strain": {"C57BL/6J": C57BL6J_STRAIN_TERM}},
            {"brain_regions": {"CA1": [BRAIN_REGION_TERM, {"id": "UBERON:0003881", "uri": "https://example.org/U"}]}},
            {"brain_regions": {"CA1": {**BRAIN_REGION_TERM, "label": "Field CA1"}}},  # extra keys are allowed
            {"anatomy": {"Snout": {"id": "UBERON:0006333", "uri": "http://purl.obolibrary.org/obo/UBERON_0006333"}}},
        ],
        ids=["empty", "species", "strain", "list_of_terms", "term_with_label", "anatomy"],
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

        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 2
        # Idempotent on wrapped values too.
        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 0

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
