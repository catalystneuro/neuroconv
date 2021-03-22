"""Authors: Cody Baker, Alessio Buccino."""
from pathlib import Path
import numpy as np
import uuid
from datetime import datetime

from pynwb import NWBFile
from pynwb.file import Subject
import spikeextractors as se

from .json_schema_utils import dict_deep_update


def get_default_nwbfile_metadata():
    """
    Return structure with defaulted metadata values required for a NWBFile.

    These standard defaults are
        metadata["NWBFile"]["session_description"] = "no description"
        metadata["NWBFile"]["session_description"] = datetime(1970, 1, 1)

    Proper conversions should override these fields prior to calling NWBConverter.run_conversion()
    """
    metadata = dict(
        NWBFile=dict(
            session_description="no description",
            session_start_time=datetime(1970, 1, 1),
            identifier=str(uuid.uuid4())
        )
    )
    return metadata


def make_nwbfile_from_metadata(metadata: dict):
    """Make NWBFile from available metadata."""
    metadata = dict_deep_update(get_default_nwbfile_metadata(), metadata)
    nwbfile_kwargs = metadata["NWBFile"]
    if "Subject" in metadata:
        # convert ISO 8601 string to datetime
        if "date_of_birth" in metadata["Subject"] and isinstance(metadata["Subject"]["date_of_birth"], str):
            metadata["Subject"]["date_of_birth"] = datetime.fromisoformat(metadata["Subject"]["date_of_birth"])
        nwbfile_kwargs.update(subject=Subject(**metadata["Subject"]))
    # convert ISO 8601 string to datetime
    if isinstance(nwbfile_kwargs.get("session_start_time", None), str):
        nwbfile_kwargs["session_start_time"] = datetime.fromisoformat(metadata["NWBFile"]["session_start_time"])
    return NWBFile(**nwbfile_kwargs)


def check_regular_timestamps(ts):
    """Check whether rate should be used instead of timestamps."""
    time_tol_decimals = 9
    uniq_diff_ts = np.unique(np.diff(ts).round(decimals=time_tol_decimals))
    return len(uniq_diff_ts) == 1


def save_si_object(object_name: str, si_object, output_folder,
                   cache_raw=False, include_properties=True, include_features=False):
    """
    Save an arbitrary SI object to a temprary location for NWB conversion.

    Parameters
    ----------
    object_name: str
        The unique name of the SpikeInterface object.
    si_object: RecordingExtractor or SortingExtractor
        The extractor to be saved.
    output_folder: str or Path
        The folder where the object is saved.
    cache_raw: bool
        If True, the Extractor is cached to a binary file (not recommended for RecordingExtractor objects)
        (default False).
    include_properties: bool
        If True, properties (channel or unit) are saved (default True).
    include_features: bool
        If True, spike features are saved (default False)
    """
    Path(output_folder).mkdir(parents=True, exist_ok=True)

    if isinstance(si_object, se.RecordingExtractor):
        if not si_object.is_dumpable:
            cache = se.CacheRecordingExtractor(si_object, save_path=output_folder / "raw.dat")
        elif cache_raw:
            # save to json before caching to keep history (in case it's needed)
            json_file = output_folder / f"{object_name}.json"
            si_object.dump_to_json(output_folder / json_file)
            cache = se.CacheRecordingExtractor(si_object, save_path=output_folder / "raw.dat")
        else:
            cache = si_object

    elif isinstance(si_object, se.SortingExtractor):
        if not si_object.is_dumpable:
            cache = se.CacheSortingExtractor(si_object, save_path=output_folder / "sorting.npz")
        elif cache_raw:
            # save to json before caching to keep history (in case it's needed)
            json_file = output_folder / f"{object_name}.json"
            si_object.dump_to_json(output_folder / json_file)
            cache = se.CacheSortingExtractor(si_object, save_path=output_folder / "sorting.npz")
        else:
            cache = si_object
    else:
        raise ValueError("The 'si_object' argument shoulde be a SpikeInterface Extractor!")

    pkl_file = output_folder / f"{object_name}.pkl"
    cache.dump_to_pickle(
        output_folder / pkl_file,
        include_properties=include_properties,
        include_features=include_features
    )
