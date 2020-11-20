"""Authors: Cody Baker."""
from pathlib import Path
import spikeextractors as se


def save_si_object(object_name: str, si_object, spikeinterface_folder,
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
    -------
    spikeinterface_folder: str
        The output spikeinterface folder
    """
    Path(spikeinterface_folder).mkdir(parents=True, exist_ok=True)

    if isinstance(si_object, se.RecordingExtractor):
        if not si_object.is_dumpable or cache_raw:
            cache = se.CacheRecordingExtractor(si_object, save_path=spikeinterface_folder / "raw.dat")
        else:
            cache = si_object

    elif isinstance(si_object, se.SortingExtractor):  # TODO: asssumes a single extractor at the moment (not  iterable)
        if not si_object.is_dumpable or cache_raw:
            cache = se.CacheSortingExtractor(si_object, spikeinterface_folder / "sorting.npz")
        else:
            cache = si_object
    else:
        raise ValueError("The 'si_object' argument shoulde be a SpikeInterface Extractor!")

    json_file = spikeinterface_folder / f"{object_name}.json"
    pkl_file = spikeinterface_folder / f"{object_name}.pkl"
    cache.dump_to_json(spikeinterface_folder / json_file)
    cache.dump_to_pickle(
        spikeinterface_folder / pkl_file,
        include_properties=include_properties,
        include_features=include_features
    )
