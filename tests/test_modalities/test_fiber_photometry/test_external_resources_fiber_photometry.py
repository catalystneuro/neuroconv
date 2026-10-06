"""Ontology annotation of fiber-photometry locations (``ndx-fiber-photometry`` / ``ndx-ophys-devices``).

These live here rather than in ``tests/test_minimal`` because they need the fiber-photometry extensions,
which the fiber-photometry test job installs.
"""

from datetime import datetime

from dateutil.tz import tzutc
from ndx_fiber_photometry import (
    FiberPhotometry,
    FiberPhotometryIndicators,
    FiberPhotometryTable,
    FiberPhotometryViruses,
    FiberPhotometryVirusInjections,
)
from ndx_ophys_devices import Indicator, ViralVector, ViralVectorInjection
from pynwb import NWBHDF5IO, NWBFile
from pynwb.file import Subject

from neuroconv.tools.external_resources import (
    add_brain_region_external_resources,
    add_external_resources_to_nwbfile,
    infer_brain_region_external_resources,
)


def _make_nwbfile(species="Mus musculus") -> NWBFile:
    nwbfile = NWBFile(session_description="d", identifier="id", session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()))
    nwbfile.subject = Subject(subject_id="s1", species=species)
    return nwbfile


def _add_virus_injection(nwbfile: NWBFile, injection_location) -> None:
    """Add a viral vector injection inside ``FiberPhotometry`` lab metadata, where NeuroConv puts it."""

    viral_vector = ViralVector(
        name="virus0", construct_name="AAV", description="d", manufacturer="m", titer_in_vg_per_ml=1e12
    )
    injection = ViralVectorInjection(
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
    indicator = Indicator(name="indicator0", label="GCaMP", description="d", manufacturer="m")
    nwbfile.add_lab_meta_data(
        FiberPhotometry(
            name="fiber_photometry",
            fiber_photometry_table=FiberPhotometryTable(name="fiber_photometry_table", description="d"),
            fiber_photometry_viruses=FiberPhotometryViruses(viral_vectors=[viral_vector]),
            fiber_photometry_virus_injections=FiberPhotometryVirusInjections(viral_vector_injections=[injection]),
            fiber_photometry_indicators=FiberPhotometryIndicators(indicators=[indicator]),
        )
    )


class TestFiberPhotometryExternalResources:
    def test_virus_injection_location_is_resolved(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        _add_virus_injection(nwbfile, injection_location="VTA")

        assert (
            infer_brain_region_external_resources(nwbfile)["ExternalResources"]["brain_regions"]["VTA"]["id"]
            == "MBA:749"
        )

    def test_virus_injection_location_is_annotated(self, tmp_path):
        nwbfile = _make_nwbfile()
        _add_virus_injection(nwbfile, injection_location="VTA")
        mapping = {"VTA": {"id": "MBA:749", "uri": "https://example.org/MBA_749"}}

        assert (
            add_brain_region_external_resources(nwbfile, metadata={"ExternalResources": {"brain_regions": mapping}})
            == 1
        )

        path = tmp_path / "injection.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(path, "r") as io:
            dataframe = io.read().external_resources.to_dataframe()
        rows = set(zip(dataframe["object_type"], dataframe["relative_path"], dataframe["key"], dataframe["entity_id"]))
        assert rows == {("ViralVectorInjection", "location", "VTA", "MBA:749")}

    def test_file_on_disk_is_annotated_without_importing_the_extensions(self, tmp_path):
        # A file read back with load_namespaces=True knows the extension types even when the extension
        # packages are never imported. The HERD must resolve them through the reading IO's type map:
        # pynwb's global type map does not have them and HDMF failed with "'NoneType' object has no
        # attribute 'parent'". The test process has imported the extensions, so annotate in a fresh one.
        import subprocess
        import sys

        nwbfile = _make_nwbfile(species="Mus musculus")
        _add_virus_injection(nwbfile, injection_location="VTA")
        path = tmp_path / "written_without_herd.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)

        annotate_in_fresh_process = f"""
import sys
from pynwb import NWBHDF5IO
from neuroconv.tools.external_resources import (
    add_external_resources_to_nwbfile,
    infer_brain_region_external_resources,
    infer_species_external_resources,
)
from neuroconv.utils import dict_deep_update

with NWBHDF5IO({str(path)!r}, "r+", load_namespaces=True) as io:
    nwbfile = io.read()
    metadata = dict_deep_update(infer_species_external_resources(nwbfile), infer_brain_region_external_resources(nwbfile))
    add_external_resources_to_nwbfile(nwbfile, metadata=metadata)
    io.write(nwbfile)
assert not any(module.startswith("ndx_") for module in sys.modules), "an extension was imported"
"""
        result = subprocess.run(
            [sys.executable, "-c", annotate_in_fresh_process], capture_output=True, encoding="utf-8"
        )
        assert result.returncode == 0, result.stderr

        with NWBHDF5IO(path, "r") as io:
            dataframe = io.read().external_resources.to_dataframe()
        rows = set(zip(dataframe["object_type"], dataframe["key"], dataframe["entity_id"]))
        assert rows == {("Subject", "Mus musculus", "NCBITaxon:10090"), ("ViralVectorInjection", "VTA", "MBA:749")}

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
        metadata["ExternalResources"] = dict(
            brain_regions={"CA1": {"id": "MBA:382", "uri": "https://example.org/MBA_382"}}
        )
        series_metadata = fiber_photometry_metadata[interface.metadata_key]
        series_metadata["fiber_photometry_table_region"] = ["row0"]
        series_metadata["fiber_photometry_table_region_description"] = "d"

        nwbfile = interface.create_nwbfile(metadata=metadata)
        add_external_resources_to_nwbfile(nwbfile, metadata=metadata)

        dataframe = nwbfile.external_resources.to_dataframe()
        by_key = dict(zip(dataframe["key"], dataframe["entity_id"]))
        assert by_key["CA1"] == "MBA:382"
        objects = nwbfile.external_resources.objects.to_dataframe()
        location_column = get_fiber_photometry_table(nwbfile)["location"]
        assert location_column.object_id in objects["object_id"].tolist()
