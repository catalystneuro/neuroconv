"""
This module contains informal tests for the TDTFiberPhotometryInterface.

These tests will be formalized into the testing structure in the future and this file will be deleted.
"""

import shutil
from datetime import datetime
from pathlib import Path

from zoneinfo import ZoneInfo

from neuroconv.datainterfaces import TDTFiberPhotometryInterface
from neuroconv.utils import dict_deep_update, load_dict_from_file


def main():
    folder_path = Path(
        "/Volumes/T7/CatalystNeuro/NWB/Lerner/raw_data/FP Experiments/Photometry/Punishment Sensitive/Late RI60/Photo_249_391-200721-120136"
    )
    editable_metadata_path = Path(
        "/Users/pauladkisson/Documents/CatalystNeuro/NWB/neuroconv/src/neuroconv/datainterfaces/ophys/tdt_fp/metadata.yaml"
    )

    interface = TDTFiberPhotometryInterface(folder_path=folder_path, verbose=True)
    metadata = interface.get_metadata()
    metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    output_dir_path = Path("/Volumes/T7/CatalystNeuro/NWB/Lerner/conversion_nwb")
    if output_dir_path.exists():
        shutil.rmtree(output_dir_path, ignore_errors=True)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    nwbfile_path = output_dir_path / "test_medpc.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


if __name__ == "__main__":
    main()
