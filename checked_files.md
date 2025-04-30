# Checked Files

This file tracks the progress of updating Python typing annotations to Python 3.10 syntax.

Files that have been processed:

1. ./tests/test_minimal/test_utils/test_get_json_schema_from_method_signature.py - No changes needed (already using Python 3.10 syntax)
2. ./src/neuroconv/tools/roiextractors/roiextractors.py - Updated Optional[dict] to dict | None and Optional[str] to str | None
3. ./src/neuroconv/tools/spikeinterface/spikeinterface.py - Updated Optional[FilePath] to FilePath | None, Optional[pynwb.NWBFile] to pynwb.NWBFile | None, and Optional[dict] to dict | None
4. ./src/neuroconv/tools/nwb_helpers/_metadata_and_file_helpers.py - No changes needed (already using Python 3.10 syntax)
5. ./src/neuroconv/utils/__init__.py - No changes needed (already using Python 3.10 syntax)
6. ./src/neuroconv/utils/path.py - No changes needed (already using Python 3.10 syntax)
7. ./src/neuroconv/basedatainterface.py - No changes needed (already using Python 3.10 syntax)
8. ./src/neuroconv/datainterfaces/behavior/video/video_utils.py - No changes needed (already using Python 3.10 syntax)
9. ./src/neuroconv/datainterfaces/behavior/deeplabcut/_dlc_utils.py - No changes needed (already using Python 3.10 syntax)
10. ./src/neuroconv/datainterfaces/image/imageinterface.py - No changes needed (already using Python 3.10 syntax)
11. ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglxnidqinterface.py - No changes needed (already using Python 3.10 syntax)
12. ./src/neuroconv/datainterfaces/ecephys/baserecordingextractorinterface.py - Updated Optional[dict] to dict | None, Optional[float] to float | None, Optional[str] to str | None, and Union[np.ndarray, list[np.ndarray]] to np.ndarray | list[np.ndarray]
13. ./src/neuroconv/datainterfaces/ophys/baseimagingextractorinterface.py - No changes needed (already using Python 3.10 syntax)
14. ./src/neuroconv/datainterfaces/ophys/basesegmentationextractorinterface.py - No changes needed (already using Python 3.10 syntax)
15. ./src/neuroconv/tools/testing/data_interface_mixins.py - No changes needed (already using Python 3.10 syntax)
16. ./src/neuroconv/datainterfaces/ecephys/openephys/openephysdatainterface.py - Updated Optional[str] to str | None and Optional[int] to int | None
17. ./src/neuroconv/datainterfaces/ecephys/openephys/openephysbinarydatainterface.py - Updated Optional[str] to str | None and Optional[int] to int | None
18. ./src/neuroconv/datainterfaces/ecephys/openephys/_openephys_utils.py - Updated Union[datetime, None] to datetime | None
19. ./src/neuroconv/datainterfaces/ecephys/openephys/openephybinarysanaloginterface.py - Updated Optional[dict] to dict | None, Optional[str] to str | None, and removed typing import
20. ./src/neuroconv/datainterfaces/ecephys/openephys/openephyslegacydatainterface.py - Updated Optional[str] to str | None and Optional[int] to int | None
21. ./src/neuroconv/datainterfaces/ecephys/edf/edfdatainterface.py - Updated Optional[list] to list | None and removed typing import
22. ./src/neuroconv/datainterfaces/ecephys/spikegadgets/spikegadgetsdatainterface.py - Updated Optional[ArrayType] to ArrayType | None and removed typing import
23. ./src/neuroconv/datainterfaces/ecephys/basesortingextractorinterface.py - Updated Optional[DeepDict] to DeepDict | None, Optional[list[list[int]]] to list[list[int]] | None, and Union[np.ndarray, list[np.ndarray]] to np.ndarray | list[np.ndarray]
24. ./src/neuroconv/datainterfaces/ecephys/sortedrecordinginterface.py - Updated Optional[dict] to dict | None, Union[str, int] to str | int, and removed typing import
25. ./src/neuroconv/datainterfaces/ecephys/baselfpextractorinterface.py - Updated Optional[NWBFile] to NWBFile | None, Optional[dict] to dict | None, Optional[float] to float | None, and removed Optional import
26. ./src/neuroconv/datainterfaces/ecephys/phy/phydatainterface.py - Updated Optional[list[str]] to list[str] | None and removed typing import
27. ./src/neuroconv/datainterfaces/ecephys/axona/axona_utils.py - Updated Union[list, set] to list | set and removed typing import
28. ./src/neuroconv/datainterfaces/ecephys/axona/axonadatainterface.py - No changes needed (already using Python 3.10 syntax)
29. ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscopedatainterface.py - Updated Optional[float] to float | None, Optional[FilePath] to FilePath | None, Optional[list[int]] to list[int] | None, and removed typing import
30. ./src/neuroconv/datainterfaces/ecephys/blackrock/blackrockdatainterface.py - Updated Optional[FilePath] to FilePath | None, Optional[float] to float | None, and removed typing import
31. ./src/neuroconv/datainterfaces/ecephys/cellexplorer/cellexplorerdatainterface.py - Updated Optional[dict] to dict | None, Optional[float] to float | None, Optional[str] to str | None, Optional[int] to int | None, and removed Optional import
32. ./src/neuroconv/datainterfaces/ecephys/maxwell/maxonedatainterface.py - Updated Optional[DirectoryPath] to DirectoryPath | None and removed typing import
33. ./src/neuroconv/datainterfaces/ecephys/neuralynx/neuralynxdatainterface.py - Updated Optional[str] to str | None, Optional[float] to float | None, and removed typing import
34. ./src/neuroconv/datainterfaces/icephys/abf/abfdatainterface.py - Updated Optional[dict] to dict | None, Optional[FilePath] to FilePath | None, and removed typing import
35. ./src/neuroconv/nwbconverter.py - Updated Optional[dict] to dict | None, Optional[NWBFile] to NWBFile | None, Union[str, None] to str | None, Union[HDF5BackendConfiguration, ZarrBackendConfiguration] to HDF5BackendConfiguration | ZarrBackendConfiguration, and removed Optional import
