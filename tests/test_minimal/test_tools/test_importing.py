"""
This module is meant for the tests to be run as stand-alone to emulate a fresh import.

Run them by using:
pytest tests/import_structure.py::TestImportStructure::test_name
"""

from neuroconv import get_data_interfaces_summaries


def test_guide_attributes():
    """The GUIDE fetches this information from each class to render the selection of interfaces."""
    data_interface_summaries = get_data_interfaces_summaries()

    # Blocking assertion when adding new interfaces
    for interface_name, interface_summary in data_interface_summaries.items():
        for key, value in interface_summary.items():
            assert value is not None, f"{interface_name} is missing GUIDE related attribute {key}."
            if isinstance(value, tuple):
                assert len(value) > 0, f"{interface_name} is missing entries in GUIDE related attribute {key}."

    # For easier reference to global commonalities
    assert data_interface_summaries == {
        "NeuralynxRecordingInterface": {
            "display_name": "Neuralynx Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".nse", ".ntt", ".nse", ".nev"),
            "info": "Interface for Neuralynx recording data.",
        },
        "NeuralynxSortingInterface": {
            "display_name": "Neuralynx Sorting",
            "keywords": ("extracellular electrophysiology", "spike sorting"),
            "associated_suffixes": (".nse", ".ntt", ".nse", ".nev"),
            "info": "Interface for Neuralynx sorting data.",
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
            "associated_suffixes": (".ns0", ".ns1", ".ns2", ".ns3", ".ns4", ".ns5"),
            "info": "Interface for Blackrock recording data.",
        },
        "BlackrockSortingInterface": {
            "display_name": "Blackrock Sorting",
            "keywords": ("extracellular electrophysiology", "spike sorting"),
            "associated_suffixes": (".nev",),
            "info": "Interface for Blackrock sorting data.",
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
            "associated_suffixes": (".npy",),
            "info": "Interface for KiloSort sorting data.",
        },
        "AxonaRecordingInterface": {
            "display_name": "Axona Recording",
            "keywords": ("extracellular electrophysiology", "voltage", "recording"),
            "associated_suffixes": (".bin", ".set"),
            "info": "Interface for Axona recording data.",
        },
        "AxonaPositionDataInterface": {
            "display_name": "Axona Position",
            "keywords": ("position tracking",),
            "associated_suffixes": (".bin", ".set"),
            "info": "Interface for Axona position data.",
        },
        "AxonaLFPDataInterface": {
            "display_name": "Axona LFP",
            "keywords": (
                "extracellular electrophysiology",
                "voltage",
                "recording",
                "extracellular electrophysiology",
                "LFP",
                "local field potential",
                "LF",
            ),
            "associated_suffixes": (".bin", ".set"),
            "info": "Interface for Axona LFP data.",
        },
        "AxonaUnitRecordingInterface": {
            "display_name": "Axona Units",
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
            "keywords": ("intracellular electrophysiology", "patch clamp", "current clamp"),
            "associated_suffixes": (".abf",),
            "info": "Interface for ABF intracellular electrophysiology data.",
        },
        "CaimanSegmentationInterface": {
            "display_name": "CaImAn Segmentation",
            "keywords": ("segmentation", "roi", "cells"),
            "associated_suffixes": (".hdf5",),
            "info": "Interface for Caiman segmentation data.",
        },
        "CnmfeSegmentationInterface": {
            "display_name": "CNMFE Segmentation",
            "keywords": ("segmentation", "roi", "cells"),
            "associated_suffixes": (".mat",),
            "info": "Interface for constrained non-negative matrix factorization (CNMFE) segmentation.",
        },
        "Suite2pSegmentationInterface": {
            "display_name": "Suite2p Segmentation",
            "keywords": ("segmentation", "roi", "cells"),
            "associated_suffixes": (".npy",),
            "info": "Interface for Suite2p segmentation.",
        },
        "ExtractSegmentationInterface": {
            "display_name": "EXTRACT Segmentation",
            "keywords": ("segmentation", "roi", "cells"),
            "associated_suffixes": (".mat",),
            "info": "Interface for EXTRACT segmentation.",
        },
        "SimaSegmentationInterface": {
            "display_name": "SIMA Segmentation",
            "keywords": ("segmentation", "roi", "cells"),
            "associated_suffixes": (".sima",),
            "info": "Interface for SIMA segmentation.",
        },
        "SbxImagingInterface": {
            "display_name": "Scanbox Imaging",
            "keywords": (
                "ophys",
                "optical electrophysiology",
                "fluorescence",
                "microscopy",
                "two photon",
                "one photon",
                "voltage imaging",
                "calcium imaging",
            ),
            "associated_suffixes": (".sbx",),
            "info": "Interface for Scanbox imaging data.",
        },
        "TiffImagingInterface": {
            "display_name": "TIFF Imaging",
            "keywords": (
                "ophys",
                "optical electrophysiology",
                "fluorescence",
                "microscopy",
                "two photon",
                "one photon",
                "voltage imaging",
                "calcium imaging",
            ),
            "associated_suffixes": (".tif", ".tiff"),
            "info": "Interface for multi-page TIFF files.",
        },
        "Hdf5ImagingInterface": {
            "display_name": "HDF5 Imaging",
            "keywords": (
                "ophys",
                "optical electrophysiology",
                "fluorescence",
                "microscopy",
                "two photon",
                "one photon",
                "voltage imaging",
                "calcium imaging",
            ),
            "associated_suffixes": (".h5", ".hdf5"),
            "info": "Interface for HDF5 imaging data.",
        },
        "ScanImageImagingInterface": {
            "display_name": "ScanImage Imaging",
            "keywords": (
                "ophys",
                "optical electrophysiology",
                "fluorescence",
                "microscopy",
                "two photon",
                "one photon",
                "voltage imaging",
                "calcium imaging",
            ),
            "associated_suffixes": (".tif",),
            "info": "Interface for ScanImage TIFF files.",
        },
        "BrukerTiffMultiPlaneImagingInterface": {
            "display_name": "Bruker TIFF Imaging (single channel, multiple planes)",
            "keywords": (
                "ophys",
                "optical electrophysiology",
                "fluorescence",
                "microscopy",
                "two photon",
                "one photon",
                "voltage imaging",
                "calcium imaging",
            ),
            "associated_suffixes": (".ome", ".tif", ".xml", ".env"),
            "info": "Interface for a single channel of multi-plane Bruker TIFF imaging data.",
        },
        "BrukerTiffSinglePlaneImagingInterface": {
            "display_name": "Bruker TIFF Imaging (single channel, single plane)",
            "keywords": (
                "ophys",
                "optical electrophysiology",
                "fluorescence",
                "microscopy",
                "two photon",
                "one photon",
                "voltage imaging",
                "calcium imaging",
            ),
            "associated_suffixes": (".ome", ".tif", ".xml", ".env"),
            "info": "Interface for handling a single channel and a single plane of Bruker TIFF imaging data.",
        },
        "MicroManagerTiffImagingInterface": {
            "display_name": "Micro-Manager TIFF Imaging",
            "keywords": (
                "ophys",
                "optical electrophysiology",
                "fluorescence",
                "microscopy",
                "two photon",
                "one photon",
                "voltage imaging",
                "calcium imaging",
            ),
            "associated_suffixes": (".ome", ".tif", ".json"),
            "info": "Interface for Micro-Manager TIFF imaging data.",
        },
        "MiniscopeImagingInterface": {
            "display_name": "Miniscope Imaging",
            "keywords": (
                "ophys",
                "optical electrophysiology",
                "fluorescence",
                "microscopy",
                "two photon",
                "one photon",
                "voltage imaging",
                "calcium imaging",
            ),
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
            "associated_suffixes": (".slp", ".mp4"),
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
