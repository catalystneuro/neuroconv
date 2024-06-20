"""
This module contains informal tests for the TDTFiberPhotometryInterface.

These tests will be formalized into the testing structure in the future and this file will be deleted.
"""

from datetime import datetime
from pathlib import Path

from neuroconv.datainterfaces import TDTFiberPhotometryInterface


def main():
    folder_path = Path(
        "/Volumes/T7/CatalystNeuro/NWB/Lerner/raw_data/FP Experiments/Photometry/Punishment Sensitive/Early RI60/Photo_112_283-190620-093542"
    )

    interface = TDTFiberPhotometryInterface(folder_path=folder_path, verbose=True)
    metadata = interface.get_metadata()
    metadata["NWBFile"]["session_start_time"] = datetime.now()
    metadata["Ophys"]["FiberPhotometry"] = {
        "FiberPhotometryTable": {
            "name": "fiber_photometry_table",
            "description": "Contains the metadata for the fiber photometry experiment.",
        },
        "FiberPhotometryResponseSeries": [
            {
                "name": "fiber_photometry_response_series",
                "description": "The fluorescence from the DMS calcium signal, DMS isosbestic control, DLS calcium signal, and DLS isosbestic control.",
                "data": ["Dv2A", "Dv1A", "Dv4B", "Dv3B"],
                "unit": "a.u.",
            }
        ],
        # TODO: Complete this metadata
    }
    output_dir_path = Path("/Volumes/T7/CatalystNeuro/NWB/Lerner/conversion_nwb")
    nwbfile_path = output_dir_path / "test_medpc.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


if __name__ == "__main__":
    main()
