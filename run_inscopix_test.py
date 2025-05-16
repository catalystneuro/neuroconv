from pathlib import Path
import json

from neuroconv.datainterfaces.ophys.inscopix.inscopiximagingdatainterface import InscopixImagingInterface

# If you have setup_paths.py in repo
from tests.test_on_data.setup_paths import OPHYS_DATA_PATH

file_path = OPHYS_DATA_PATH / "imaging_datasets" / "inscopix" / "movie_128x128x100_part1.isxd"
print("Checking file path:", file_path)
print("File exists:", file_path.exists())

print("Creating interface...")
interface = InscopixImagingInterface(file_path=str(file_path))

print("Getting metadata...")
metadata = interface.get_metadata()
print("Metadata received.")

print(json.dumps(metadata, indent=2, default=str))
print("Device:", metadata["Ophys"]["Device"])
print("ImagingPlane:", metadata["Ophys"]["ImagingPlane"])
print("OnePhotonSeries:", metadata["Ophys"]["OnePhotonSeries"])
