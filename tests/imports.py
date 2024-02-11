"""
This module is meant for the tests to be run as stand-alone to emulate a fresh import.

Run them by using:
pytest tests/import_structure.py::TestImportStructure::test_name
"""

from unittest import TestCase


def _strip_magic_module_attributes(ls: list) -> list:
    exclude_keys = [
        "__name__",
        "__doc__",
        "__package__",
        "__loader__",
        "__spec__",
        "__path__",
        "__file__",
        "__cached__",
        "__builtins__",
    ]
    return list(filter(lambda key: key not in exclude_keys, ls))


def test_top_level():
    import neuroconv

    current_structure = _strip_magic_module_attributes(ls=neuroconv.__dict__)
    expected_structure = [
        # Sub-modules
        "basedatainterface",
        "basetemporalalignmentinterface",
        "baseextractorinterface",
        "nwbconverter",
        "tools",  # Attached to namespace by NWBConverter import
        "utils",  # Attached to namespace by NWBconverter import
        # Exposed attributes
        "NWBConverter",
        "ConverterPipe",
        "BaseDataInterface",
        "BaseTemporalAlignmentInterface",
        "BaseExtractorInterface",
        "run_conversion_from_yaml",
    ]
    assert sorted(current_structure) == sorted(expected_structure)


def test_tools():
    """Python dir() calls (and __dict__ as well) update dynamically based on global imports."""
    from neuroconv import tools

    current_structure = _strip_magic_module_attributes(ls=tools.__dict__)
    expected_structure = [
        # Sub-Packages
        "yaml_conversion_specification",  # Attached to namespace  by top __init__ call of NWBConverter
        # Sub-modules
        "importing",  # Attached to namespace by importing get_package
        "nwb_helpers",  # Attached to namespace by top __init__ call of NWBConverter
        "path_expansion",
        # Functions and classes imported on the __init__
        "get_package",
        "processes",
        "deploy_process",
        "LocalPathExpander",
        "get_module",
        "hdmf",
    ]
    assert sorted(current_structure) == sorted(expected_structure)


def test_datainterfaces():
    from neuroconv import datainterfaces

    current_structure = _strip_magic_module_attributes(ls=datainterfaces.__dict__)

    from neuroconv.datainterfaces import interface_list

    interface_name_list = [interface.__name__ for interface in interface_list]
    expected_structure = [
        # Sub-modules
        "behavior",
        "ecephys",
        "icephys",
        "ophys",
        "text",
        # Exposed attributes
        "interface_list",
        "interfaces_by_category",
    ] + interface_name_list

    assert sorted(current_structure) == sorted(expected_structure)


def test_guide_attributes():
    """The GUIDE fetches this information from each class to render the selection of interfaces."""
    from neuroconv.datainterfaces import interface_list

    guide_attribute_names = ["display_name", "keywords", "associated_suffixes", "info"]
    guide_attributes_per_interface = dict()
    for interface in interface_list:
        interface_guide_attributes = dict()
        for attribute in guide_attribute_names:
            attribute_value = getattr(interface, attribute)
            assert attribute_value is not None, f"{interface.__name__} is missing GUIDE related attribute {attribute}."
            if isinstance(attribute_value, tuple):
                assert (
                    len(attribute_value) > 0
                ), f"{interface.__name__} is missing entries in GUIDE related attribute {attribute}."

            interface_guide_attributes.update({attribute: getattr(interface, attribute)})
        guide_attributes_per_interface.update({interface.__name__: interface_guide_attributes})

    assert guide_attributes_per_interface == {
        "NeuralynxRecordingInterface": {
            "display_name": "Neuralynx Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (),
            "info": "Interface for Neuralynx recording data.",
        },
        "NeuralynxSortingInterface": {
            "display_name": None,
            "keywords": ("extracellular electrophysiology", "spike sorting"),
            "associated_suffixes": (),
            "info": None,
        },
        "NeuroScopeRecordingInterface": {
            "display_name": "NeuroScope Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".dat", ".xml"),
            "info": "Interface for converting NeuroScope recording data.",
        },
        "NeuroScopeSortingInterface": {
            "display_name": "NeuroScope Sorting",
            "keywords": ("extracellular electrophysiology", "spike sorting"),
            "associated_suffixes": (".res", ".clu", ".res.*", ".clu.*", ".xml"),
            "info": "Interface for converting NeuroScope recording data.",
        },
        "NeuroScopeLFPInterface": {
            "display_name": "NeuroScope LFP",
            "keywords": (
                "extracellular electrophysiology",
                "voltage",
                "recording",
                "extracellular electrophysiology",
                "LFP",
                "local field potential",
                "LF",
            ),
            "associated_suffixes": (".lfp", ".eeg", ".xml"),
            "info": "Interface for converting NeuroScope LFP data.",
        },
        "Spike2RecordingInterface": {
            "display_name": "Spike2 Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording", "CED"),
            "associated_suffixes": (".smr", ".smrx"),
            "info": "Interface for Spike2 recording data from CED (Cambridge Electronic Design).",
        },
        "SpikeGLXRecordingInterface": {
            "display_name": "SpikeGLX Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording", "Neuropixels"),
            "associated_suffixes": (".imec{probe_number}", ".ap", ".lf", ".meta", ".bin"),
            "info": "Interface for SpikeGLX recording data.",
        },
        "SpikeGLXLFPInterface": {
            "display_name": "SpikeGLX Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording", "Neuropixels"),
            "associated_suffixes": (".imec{probe_number}", ".ap", ".lf", ".meta", ".bin"),
            "info": "Interface for SpikeGLX recording data.",
        },
        "SpikeGLXNIDQInterface": {
            "display_name": "NIDQ Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording", "Neuropixels"),
            "associated_suffixes": (".nidq", ".meta", ".bin"),
            "info": "Interface for NIDQ board recording data.",
        },
        "SpikeGadgetsRecordingInterface": {
            "display_name": "SpikeGadgets Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".rec",),
            "info": "Interface for SpikeGadgets recording data.",
        },
        "IntanRecordingInterface": {
            "display_name": "Intan Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".rhd", ".rhs"),
            "info": "Interface for Intan recording data.",
        },
        "CellExplorerSortingInterface": {
            "display_name": "CellExplorer Sorting",
            "keywords": ("extracellular electrophysiology", "spike sorting"),
            "associated_suffixes": (".mat", ".sessionInfo", ".spikes", ".cellinfo"),
            "info": "Interface for CellExplorer sorting data.",
        },
        "CellExplorerRecordingInterface": {
            "display_name": "CellExplorer Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".dat", ".session", ".sessionInfo", ".mat"),
            "info": "Interface for CellExplorer recording data.",
        },
        "CellExplorerLFPInterface": {
            "display_name": "CellExplorer LFP",
            "keywords": (
                "extracellular electrophysiology",
                "voltage",
                "recording",
                "extracellular electrophysiology",
                "LFP",
                "local field potential",
                "LF",
            ),
            "associated_suffixes": (".lfp", ".session", ".mat"),
            "info": "Interface for CellExplorer LFP recording data.",
        },
        "BlackrockRecordingInterface": {
            "display_name": "Blackrock Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".ns{stream_number}",),
            "info": "Interface for Blackrock recording data.",
        },
        "BlackrockSortingInterface": {
            "display_name": None,
            "keywords": ("extracellular electrophysiology", "spike sorting"),
            "associated_suffixes": (),
            "info": None,
        },
        "OpenEphysRecordingInterface": {
            "display_name": "OpenEphys Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".dat", ".oebin", ".npy"),
            "info": "Interface for converting any OpenEphys recording data.",
        },
        "OpenEphysBinaryRecordingInterface": {
            "display_name": "OpenEphys Binary Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".dat", ".oebin", ".npy"),
            "info": "Interface for converting binary OpenEphys recording data.",
        },
        "OpenEphysLegacyRecordingInterface": {
            "display_name": "OpenEphys Legacy Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".continuous", ".openephys", ".xml"),
            "info": "Interface for converting legacy OpenEphys recording data.",
        },
        "OpenEphysSortingInterface": {
            "display_name": "OpenEphys Sorting",
            "keywords": ("extracellular electrophysiology", "spike sorting"),
            "associated_suffixes": (".spikes",),
            "info": "Interface for converting legacy OpenEphys sorting data.",
        },
        "PhySortingInterface": {
            "display_name": "Phy Sorting",
            "keywords": ("extracellular electrophysiology", "spike sorting"),
            "associated_suffixes": (".npy",),
            "info": "Interface for Phy sorting data.",
        },
        "KiloSortSortingInterface": {
            "display_name": "KiloSort Sorting",
            "keywords": ("extracellular electrophysiology", "spike sorting"),
            "associated_suffixes": (),
            "info": "Interface for KiloSort sorting data.",
        },
        "AxonaRecordingInterface": {
            "display_name": "Axona Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".bin", ".set"),
            "info": "Interface for Axona recording data.",
        },
        "AxonaPositionDataInterface": {"display_name": None, "keywords": (), "associated_suffixes": (), "info": None},
        "AxonaLFPDataInterface": {
            "display_name": None,
            "keywords": (
                "extracellular electrophysiology",
                "voltage",
                "recording",
                "extracellular electrophysiology",
                "LFP",
                "local field potential",
                "LF",
            ),
            "associated_suffixes": (),
            "info": None,
        },
        "AxonaUnitRecordingInterface": {
            "display_name": "Axona Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".bin", ".set"),
            "info": "Interface for Axona recording data.",
        },
        "EDFRecordingInterface": {
            "display_name": "EDF Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording", "European Data Format"),
            "associated_suffixes": (".edf",),
            "info": "Interface for European Data Format (EDF) recording data.",
        },
        "TdtRecordingInterface": {
            "display_name": "TDT Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".tbk", ".tbx", ".tev", ".tsq"),
            "info": "Interface for TDT recording data.",
        },
        "PlexonRecordingInterface": {
            "display_name": "Plexon Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".plx",),
            "info": "Interface for Plexon recording data.",
        },
        "PlexonSortingInterface": {
            "display_name": "Plexon Sorting",
            "keywords": ("extracellular electrophysiology", "spike sorting"),
            "associated_suffixes": (".plx",),
            "info": "Interface for Plexon sorting data.",
        },
        "BiocamRecordingInterface": {
            "display_name": "Biocam Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".bwr",),
            "info": "Interface for Biocam recording data.",
        },
        "AlphaOmegaRecordingInterface": {
            "display_name": "AlphaOmega Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".mpx",),
            "info": "Interface class for converting AlphaOmega recording data.",
        },
        "MEArecRecordingInterface": {
            "display_name": "MEArec Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".h5",),
            "info": "Interface for MEArec recording data.",
        },
        "MCSRawRecordingInterface": {
            "display_name": "MCSRaw Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".raw",),
            "info": "Interface for MCSRaw recording data.",
        },
        "MaxOneRecordingInterface": {
            "display_name": "MaxOne Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".raw", ".h5"),
            "info": "Interface for MaxOne recording data.",
        },
        "AbfInterface": {
            "display_name": "ABF Icephys",
            "keywords": (),
            "associated_suffixes": (".abf",),
            "info": "Interface for ABF intracellular electrophysiology data.",
        },
        "CaimanSegmentationInterface": {
            "display_name": "CaImAn Segmentation",
            "keywords": (),
            "associated_suffixes": (".hdf5",),
            "info": "Interface for Caiman segmentation data.",
        },
        "CnmfeSegmentationInterface": {
            "display_name": "CNMFE Segmentation",
            "keywords": (),
            "associated_suffixes": (".mat",),
            "info": "Interface for constrained non-negative matrix factorization (CNMFE) segmentation.",
        },
        "Suite2pSegmentationInterface": {
            "display_name": "Suite2p Segmentation",
            "keywords": (),
            "associated_suffixes": (),
            "info": None,
        },
        "ExtractSegmentationInterface": {
            "display_name": "EXTRACT Segmentation",
            "keywords": (),
            "associated_suffixes": (".mat",),
            "info": "Interface for EXTRACT segmentation.",
        },
        "SimaSegmentationInterface": {
            "display_name": "SIMA Segmentation",
            "keywords": (),
            "associated_suffixes": (),
            "info": None,
        },
        "SbxImagingInterface": {
            "display_name": "Scanbox Imaging",
            "keywords": (),
            "associated_suffixes": (),
            "info": None,
        },
        "TiffImagingInterface": {
            "display_name": "TIFF Imaging",
            "keywords": (),
            "associated_suffixes": (),
            "info": None,
        },
        "Hdf5ImagingInterface": {
            "display_name": "HDF5 Imaging",
            "keywords": (),
            "associated_suffixes": (".h5", ".hdf5"),
            "info": "Interface for HDF5 imaging data.",
        },
        "ScanImageImagingInterface": {
            "display_name": "ScanImage Imaging",
            "keywords": (),
            "associated_suffixes": (),
            "info": None,
        },
        "BrukerTiffMultiPlaneImagingInterface": {
            "display_name": "Bruker TIFF Imaging (single channel, multiple planes)",
            "keywords": (),
            "associated_suffixes": (".ome", ".tif", ".xml", ".env"),
            "info": "Interface for a single channel of multi-plane Bruker TIFF imaging data.",
        },
        "BrukerTiffSinglePlaneImagingInterface": {
            "display_name": "Bruker TIFF Imaging (single channel, single plane)",
            "keywords": (),
            "associated_suffixes": (".ome", ".tif", ".xml", ".env"),
            "info": "Interface for handling a single channel and a single plane of Bruker TIFF imaging data.",
        },
        "MicroManagerTiffImagingInterface": {
            "display_name": "Micro-Manager TIFF Imaging",
            "keywords": (),
            "associated_suffixes": (".ome", ".tif", ".json"),
            "info": "Interface for Micro-Manager TIFF imaging data.",
        },
        "MiniscopeImagingInterface": {
            "display_name": "Miniscope Imaging",
            "keywords": (),
            "associated_suffixes": (".avi", ".csv", ".json"),
            "info": "Interface for Miniscope imaging data.",
        },
        "VideoInterface": {
            "display_name": "Video",
            "keywords": ("movie", "natural behavior", "tracking"),
            "associated_suffixes": (".mp4", ".avi", ".wmv", ".mov", ".flx", ".mkv"),
            "info": "Interface for handling standard video file formats.",
        },
        "AudioInterface": {
            "display_name": "Wav Audio",
            "keywords": ("sound", "microphone"),
            "associated_suffixes": (".wav",),
            "info": "Interface for writing audio recordings to an NWB file.",
        },
        "DeepLabCutInterface": {
            "display_name": "DeepLabCut",
            "keywords": ("DLC",),
            "associated_suffixes": (".h5",),
            "info": "Interface for handling data from DeepLabCut.",
        },
        "SLEAPInterface": {
            "display_name": "SLEAP",
            "keywords": ("pose estimation", "tracking", "video"),
            "associated_suffixes": (),
            "info": "Interface for SLEAP pose estimation datasets.",
        },
        "MiniscopeBehaviorInterface": {
            "display_name": "Miniscope Behavior",
            "keywords": ("video",),
            "associated_suffixes": (".avi",),
            "info": "Interface for Miniscope behavior video data.",
        },
        "FicTracDataInterface": {
            "display_name": "FicTrac",
            "keywords": ("fictrack", "visual tracking", "fictive path", "spherical treadmill", "visual fixation"),
            "associated_suffixes": (".dat",),
            "info": "Interface for FicTrac .dat files.",
        },
        "NeuralynxNvtInterface": {
            "display_name": "Neuralynx NVT",
            "keywords": ("position tracking",),
            "associated_suffixes": (".nvt",),
            "info": "Interface for writing Neuralynx position tracking .nvt files to NWB.",
        },
        "LightningPoseDataInterface": {
            "display_name": "Lightning Pose",
            "keywords": ("pose estimation", "video"),
            "associated_suffixes": (".csv", ".mp4"),
            "info": "Interface for handling a single stream of lightning pose data.",
        },
        "CsvTimeIntervalsInterface": {
            "display_name": "CSV time interval table",
            "keywords": ("table", "trials", "epochs", "time intervals"),
            "associated_suffixes": (".csv",),
            "info": "Interface for writing a time intervals table from a comma separated value (CSV) file.",
        },
        "ExcelTimeIntervalsInterface": {
            "display_name": "Excel time interval table",
            "keywords": ("table", "trials", "epochs", "time intervals"),
            "associated_suffixes": (".xlsx", ".xls", ".xlsm"),
            "info": "Interface for writing a time intervals table from an excel file.",
        },
    }
    # Above assertion is for easy viewing of aggregated content for comparison
    # Below is preventive measure from adding interface without info
    assert not any(
        [
            value is None
            for inteface_attributes in guide_attributes_per_interface.values()
            for value in inteface_attributes
        ]
    )
