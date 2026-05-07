import numpy as np
from pydantic import FilePath

from ..basesortingextractorinterface import BaseSortingExtractorInterface


class MdaSortingInterface(BaseSortingExtractorInterface):
    """Data interface for converting a MountainSort ``firings.mda`` sorting file.

    The MDA sorting format (MountainSort v4 and earlier) is a 3xL float64 array
    storing, per spike event, ``(primary_channel, sample_time, unit_label)``. See
    https://mountainsort.readthedocs.io/en/latest/first_sort.html#format-of-the-firings-mda.

    This interface reads ``firings.mda`` files produced by ``ml_ms4alg`` (MountainSort v4
    standalone) or MountainLab-js pipelines. Modern SpikeInterface-wrapped MountainSort
    workflows produce ``firings.npz`` instead, which this interface does not read.

    In addition to spike times and unit labels, the interface surfaces the peak channel
    from row 0 of ``firings.mda`` as an ``mda_peak_channel`` property on the units table.
    The value is a 1-indexed integer position into the sorter's input channel subset,
    not a channel ID and not a row index into the NWB electrodes table. To lift it into
    a structural ``DynamicTableRegion`` on ``units.electrodes``, pair with
    :py:class:`~neuroconv.converters.SortedRecordingConverter`; the MountainSort
    conversion gallery entry shows the full worked example, and the
    :ref:`linking_sorted_data` how-to covers the general background on electrode linkage.

    If MountainSort wrote ``firings.mda`` without peak-channel tracking enabled (row 0
    is all zeros), the column carries no useful information and is not added to the
    units table.
    """

    display_name = "MountainSort Sorting"
    associated_suffixes = (".mda",)
    info = "Interface for MountainSort sorting data from firings.mda."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the firings.mda file"
        return source_schema

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import read_mda_sorting

        return read_mda_sorting

    def __init__(
        self,
        file_path: FilePath,
        sampling_frequency: int,
        verbose: bool = True,
    ):
        """
        Load and prepare sorting data for MountainSort

        Parameters
        ----------
        file_path: str or Path
            Path to the firings.mda file
        sampling_frequency : int
            The sampling frequency in Hz.
        verbose: bool, default: True
        """
        super().__init__(file_path=file_path, sampling_frequency=sampling_frequency, verbose=verbose)

        # Rename the extractor's "max_channel" property to avoid neuroconv's
        # auto-coercion of max_channel / max_electrode columns into a
        # DynamicTableRegion over the electrodes table. MDA values are 1-indexed
        # positions into the sorter's input subset, not electrodes rows, so the
        # coercion would silently misalign the linkage. Users wanting real
        # electrode linkage should use SortedRecordingConverter (see how-to).
        # If MountainSort wrote the file without peak-channel tracking enabled,
        # row 0 is all zeros and the column carries no useful information; drop
        # it rather than surfacing misleading zeros.
        self._has_peak_channel = False
        if "max_channel" in self.sorting_extractor.get_property_keys():
            values = np.asarray(self.sorting_extractor.get_property("max_channel"))
            self.sorting_extractor.delete_property("max_channel")
            if np.any(values != 0):
                self.sorting_extractor.set_property("mda_peak_channel", values)
                self._has_peak_channel = True

    def get_metadata(self):
        metadata = super().get_metadata()
        if self._has_peak_channel:
            metadata["Ecephys"]["UnitProperties"] = [
                dict(
                    name="mda_peak_channel",
                    description=(
                        "Integer 1-indexed position of the unit's peak channel within the "
                        "ordered list of channels that was passed to MountainSort, from row 0 "
                        "of the firings.mda file. This is an index, not a channel ID: if "
                        'MountainSort was run on recording channels whose IDs are "A-060" '
                        'through "A-063", the values stored here are 1 through 4 (positions '
                        "in the input list), not the channel IDs themselves. This is also NOT "
                        "a row index into the NWB electrodes table."
                    ),
                ),
            ]
        return metadata
