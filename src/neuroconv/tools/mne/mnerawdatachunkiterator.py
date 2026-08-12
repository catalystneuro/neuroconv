from typing import Iterable

import numpy as np
from tqdm import tqdm

from ..hdmf import GenericDataChunkIterator
from ..iterative_write import get_electrical_series_chunk_shape


class MNERawDataChunkIterator(GenericDataChunkIterator):
    """DataChunkIterator specifically for use on MNE ``Raw`` objects."""

    def __init__(
        self,
        raw: "mne.io.BaseRaw",  # noqa: F821
        buffer_gb: float | None = None,
        buffer_shape: tuple | None = None,
        chunk_mb: float | None = None,
        chunk_shape: tuple | None = None,
        display_progress: bool = False,
        progress_bar_class: tqdm | None = None,
        progress_bar_options: dict | None = None,
    ):
        """
        Initialize an Iterable object which returns DataChunks with data and their selections on each iteration.

        Parameters
        ----------
        raw : mne.io.BaseRaw
            The MNE ``Raw`` object which handles the data access. A ``Raw`` read with ``preload=False``
            is served from disk one selection at a time; a preloaded one (which some formats force, such
            as an EEGLAB ``.set`` carrying its data inline) is served from memory through the same call.
        buffer_gb : float, optional
            The upper bound on size in gigabytes (GB) of each selection from the iteration.
            The buffer_shape will be set implicitly by this argument.
            Cannot be set if `buffer_shape` is also specified.
            The default is 1GB.
        buffer_shape : tuple, optional
            Manual specification of buffer shape to return on each iteration.
            Must be a multiple of chunk_shape along each axis.
            Cannot be set if `buffer_gb` is also specified.
            The default is None.
        chunk_mb : float, optional
            The upper bound on size in megabytes (MB) of the internal chunk for the HDF5 dataset.
            The chunk_shape will be set implicitly by this argument.
            Cannot be set if `chunk_shape` is also specified.
            The default is 10MB, as recommended by the HDF5 group.
        chunk_shape : tuple, optional
            Manual specification of the internal chunk shape for the HDF5 dataset.
            Cannot be set if `chunk_mb` is also specified.
            The default is None.
        display_progress : bool, optional
            Display a progress bar with iteration rate and estimated completion time.
        progress_bar_class : dict, optional
            The progress bar class to use.
            Defaults to tqdm.tqdm if the TQDM package is installed.
        progress_bar_options : dict, optional
            Dictionary of keyword arguments to be passed directly to tqdm.
            See https://github.com/tqdm/tqdm#parameters for options.
        """
        self.raw = raw
        # Resolved once: MNE's `picks` takes an index array, and the channel axis of a selection indexes
        # into this same order as `raw.ch_names`.
        self.channel_indices = np.arange(len(raw.ch_names))
        super().__init__(
            buffer_gb=buffer_gb,
            buffer_shape=buffer_shape,
            chunk_mb=chunk_mb,
            chunk_shape=chunk_shape,
            display_progress=display_progress,
            progress_bar_class=progress_bar_class,
            progress_bar_options=progress_bar_options,
        )

    def _get_default_chunk_shape(self, chunk_mb: float = 10.0) -> tuple[int, int]:
        assert chunk_mb > 0, f"chunk_mb ({chunk_mb}) must be greater than zero!"

        number_of_frames, number_of_channels = self.shape

        return get_electrical_series_chunk_shape(
            number_of_channels=number_of_channels,
            number_of_frames=number_of_frames,
            dtype=self._get_dtype(),
            chunk_mb=chunk_mb,
        )

    @property
    def shape(self) -> tuple[int, int]:
        """Return (num_samples, num_channels); MNE's own axis order is the transpose of this."""
        return (int(self.raw.n_times), len(self.raw.ch_names))

    @property
    def ndim(self) -> int:
        """Return the number of dimensions (always 2: samples x channels)."""
        return 2

    def __len__(self) -> int:
        """Return the number of samples in the Raw."""
        return int(self.raw.n_times)

    def __getitem__(self, selection):
        """Enable array-like slicing, lazily reading only the requested samples from the Raw."""
        resolved = self._convert_index_to_slices(selection)
        return self._get_data(resolved)

    def _get_data(self, selection: tuple[slice]) -> Iterable:
        sample_selection, channel_selection = selection
        data = self.raw.get_data(
            picks=self.channel_indices[channel_selection],
            start=sample_selection.start,
            stop=sample_selection.stop,
        )
        # MNE returns (n_channels, n_times); the ElectricalSeries stores (n_times, n_channels).
        return data.T

    def _get_dtype(self) -> np.dtype:
        # MNE applies the calibration on read and always returns float64, whatever the source file stores.
        return np.dtype("float64")

    def _get_maxshape(self) -> tuple[int, int]:
        return self.shape
