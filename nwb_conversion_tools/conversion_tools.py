"""Authors: Cody Baker."""
from pathlib import Path
import spikeextractors as se


def save_si_object(si_object, source_folder):
    """Take an arbitrary SpikeInterface object and save to a temporary location for NWB conversion."""
    # TODO
    # Cache, dump to pickle (checks for what is/isnt dumbable)
    # return pickle file location?
    spikeinterface_folder = Path(source_folder) / "spikeinterface"
    spikeinterface_folder.mkdir(parents=True, exist_ok=True)
    cache_folder = spikeinterface_folder / "cache"
    cache_folder.mkdir(parents=True, exist_ok=True)

    if isinstance(si_object, se.RecordingExtractor):
        cache = se.CacheRecordingExtractor(si_object, save_path=cache_folder / "raw.dat")
        cache_file = cache_folder / "raw.pkl"

    if isinstance(si_object, se.SortingExtractor):  # asssumes a single sorting extractor at the moment, not an iterable
        cache = se.CacheSortingExtractor(si_object, cache_folder / "sorting.npz")
        cache_file = cache_folder / "raw.pkl"

    cache.dump_to_pickle(cache_folder / cache_file)  # TODO, this can also take options like 'include_features' in the future

    # TODO: extend to include cases below
    # if cache_raw:
    #     recording_lfp_cache = se.CacheRecordingExtractor(
    #         recording_lf_sync,
    #         save_path=cache_folder / 'lfp.dat'
    #     )
    # else:
    #     recording_lfp_cache = recording_lf_sync
    # recording_lfp_cache.dump_to_pickle(cache_folder / 'lfp.pkl')

    # if cache_processed:
    #     recording_processed_cache = se.CacheRecordingExtractor(
    #         recording_processed,
    #         save_path=cache_folder / 'processed.dat'
    #     )
    # else:
    #     recording_processed_cache = recording_processed
    # recording_processed_cache.dump_to_pickle(cache_folder / 'raw.pkl')

    # iterable sorter output
    # for result_name, sorting in sorting_outputs.items():
    #     rec_name, sorter = result_name
    #     sorting_cache = se.CacheSortingExtractor(si_object, cache_folder / f'sorting_{sorter}.npz')
    #     sorting_cache.dump_to_pickle(cache_folder / f'sorting_{sorter}.pkl', include_features=False)

    # Curated output
    # for (sorter, sorting_curated) in zip(sorter_names_curation, sorting_auto_curated):
    #     if cache_curated:
    #         sorting_auto_cache = se.CacheSortingExtractor(sorting_curated, cache_folder / f'sorting_{sorter}_auto.npz')
    #     else:
    #         sorting_auto_cache = sorting_curated
    #     sorting_auto_cache.dump_to_pickle(cache_folder / f'sorting_{sorter}_auto.pkl', include_features=False)

    # Ensamble output
    # if cache_comparison:
    #     sorting_ensamble_cache = se.CacheSortingExtractor(sorting, cache_folder / f'sorting_ensamble.npz')
    # else:
    #     sorting_ensamble_cache = sorting_ensamble
    # sorting_ensamble_cache.dump_to_pickle(cache_folder / f'sorting_ensamble.pkl', include_features=False)

    return cache_folder
