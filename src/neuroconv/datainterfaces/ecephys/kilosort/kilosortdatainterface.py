import warnings
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import DirectoryPath
from pynwb import NWBFile

from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import DeepDict


class KiloSortSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a KiloSortingExtractor from spikeinterface."""

    display_name = "KiloSort Sorting"
    associated_suffixes = (".npy",)
    info = "Interface for KiloSort sorting data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to the output Phy folder (containing the params.py)"
        return source_schema

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import read_kilosort

        return read_kilosort

    def __init__(
        self,
        folder_path: DirectoryPath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        keep_good_only: bool = False,
        verbose: bool = False,
        gain_to_uV: float | None = None,
        write_electrodes_table: bool = False,
    ):
        """
        Load and prepare sorting data for kilosort

        Parameters
        ----------
        folder_path: str or Path
            Path to the output Phy folder (containing the params.py)
        keep_good_only: bool, default: False
            If True, only Kilosort-labeled 'good' units are returned
        verbose: bool, default: True
        gain_to_uV: float, optional
            Microvolts per unit of the data Kilosort was run on. Kilosort records no scaling of its own and
            the schema fixes `waveform_mean` to volts, so without this and without a registered recording
            the templates cannot be converted and no waveforms are written.
        write_electrodes_table: bool, default: False
            If True, write an electrodes table from the geometry in the sorter folder and link each unit to
            the channels its template was fit on. A phy folder states no acquisition device, so this invents
            a Device and an ElectrodeGroup, which is why it is opt-in. Leave it False when a recording
            interface writes the electrodes table, and use
            :py:class:`~neuroconv.converters.SortedRecordingConverter` to link the units to it.
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "keep_good_only",
                "verbose",
            ]
            num_positional_args_before_args = 1  # folder_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to KiloSortSortingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            keep_good_only = positional_values.get("keep_good_only", keep_good_only)
            verbose = positional_values.get("verbose", verbose)

        super().__init__(
            folder_path=folder_path,
            keep_good_only=keep_good_only,
            verbose=verbose,
            gain_to_uV=gain_to_uV,
            write_electrodes_table=write_electrodes_table,
        )

    def _initialize_extractor(self, interface_kwargs: dict):
        # These describe what the sorted data means and how it should be written rather than how to read
        # the folder, so they belong to the source data but are not arguments of the extractor.
        not_extractor_arguments = {"gain_to_uV", "write_electrodes_table"}
        extractor_kwargs = {key: value for key, value in interface_kwargs.items() if key not in not_extractor_arguments}
        return super()._initialize_extractor(interface_kwargs=extractor_kwargs)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        # See Kilosort save_to_phy() docstring for more info on these fields: https://github.com/MouseLand/Kilosort/blob/main/kilosort/io.py
        # Or see phy documentation: https://github.com/cortex-lab/phy/blob/master/phy/apps/base.py
        metadata["Ecephys"]["UnitProperties"] = [
            dict(name="n_spikes", description="Number of spikes recorded from each unit."),
            dict(name="fr", description="Average firing rate of each unit."),
            dict(name="depth", description="Estimated depth of each unit in micrometers."),
            dict(name="Amplitude", description="Per-template amplitudes, computed as the L2 norm of the template."),
            dict(
                name="ContamPct",
                description="Contamination rate for each template, computed as fraction of refractory period violations relative to expectation based on a Poisson process.",
            ),
            dict(
                name="KSLabel",
                description="Label indicating whether each template is 'mua' (multi-unit activity) or 'good' (refractory).",
            ),
            dict(name="original_cluster_id", description="Original cluster ID assigned by Kilosort."),
            dict(
                name="amp",
                description="For every template, the maximum amplitude of the template waveforms across all channels.",
            ),
            dict(name="ch", description="The channel label of the best channel, as defined by the user."),
            dict(name="sh", description="The shank label of the best channel."),
            dict(
                name="max_electrode",
                description="Index into the electrodes table for the electrode with maximum spike amplitude for this unit.",
            ),
        ]
        return metadata

    def _get_peak_sample(self, folder_path: Path) -> int | None:
        """Read the sample the templates are aligned on, which only Kilosort 4 records."""
        ops_file_path = folder_path / "ops.npy"
        if not ops_file_path.is_file():
            return None

        ops = np.load(ops_file_path, allow_pickle=True).item()
        peak_sample = ops.get("nt0min")
        return None if peak_sample is None else int(peak_sample)

    def _get_footprint_masks(self) -> np.ndarray:
        """The channels Kilosort fit each template on, as a (n_templates, n_channels) boolean mask."""
        templates = np.load(Path(self.source_data["folder_path"]) / "templates.npy")
        return np.abs(templates).sum(axis=1) != 0

    def _get_cluster_ids(self) -> np.ndarray:
        """The template row each of this interface's units was written at."""
        cluster_ids = self.sorting_extractor.get_property("original_cluster_id")
        if cluster_ids is None:
            cluster_ids = self.sorting_extractor.unit_ids
        return np.asarray(cluster_ids, dtype=int)

    def _get_peak_channels(self) -> np.ndarray:
        """
        The channel each unit's template is largest on, as an index into the channels Kilosort sorted.

        Unwhitening is needed because the whitened template peaks elsewhere, but the gain is not: it is a
        single number, so it cannot move an argmax, and this stays available for a folder with no gain.
        """
        folder_path = Path(self.source_data["folder_path"])
        templates = np.load(folder_path / "templates.npy")
        footprint_masks = np.abs(templates).sum(axis=1) != 0
        templates = np.einsum("ij,klj->kli", np.load(folder_path / "whitening_mat_inv.npy"), templates)

        peak_channels = []
        for cluster_id in self._get_cluster_ids():
            channels = np.flatnonzero(footprint_masks[cluster_id])
            peak_to_peak = np.ptp(templates[cluster_id][:, channels], axis=0)
            peak_channels.append(channels[np.argmax(peak_to_peak)])
        return np.asarray(peak_channels)

    def _generate_recording_with_channel_metadata(self):
        """
        Build a recording carrying the channel geometry stored in the sorter folder.

        A phy folder records the geometry of the channels Kilosort sorted (`channel_map.npy`,
        `channel_positions.npy` and, for Kilosort 4, `channel_shanks.npy`) but no acquisition device, so an
        electrodes table can be written from the folder alone only by inventing the Device and the
        ElectrodeGroup. That invention is why `write_electrodes_table` is opt-in.

        Returns
        -------
        spikeinterface.core.NumpyRecording
            A single-sample recording whose channels are the ones Kilosort sorted, in its own order, named
            by their index in the recording it was run on.
        """
        from spikeinterface.core import NumpyRecording

        folder_path = Path(self.source_data["folder_path"])
        channel_map = np.load(folder_path / "channel_map.npy").reshape(-1)

        recording = NumpyRecording(
            traces_list=[np.empty(shape=(1, channel_map.size))],
            sampling_frequency=self.sorting_extractor.get_sampling_frequency(),
            channel_ids=[str(channel_index) for channel_index in channel_map],
        )
        recording.set_property(key="location", values=np.load(folder_path / "channel_positions.npy"))

        channel_shanks_file_path = folder_path / "channel_shanks.npy"
        if channel_shanks_file_path.is_file():
            recording.set_channel_groups(groups=np.load(channel_shanks_file_path).reshape(-1).astype(int))

        return recording

    def _add_electrodes_table_to_nwbfile(self, nwbfile: NWBFile, metadata: DeepDict | None) -> list[list[int]]:
        """
        Write the folder's geometry as an electrodes table and return each unit's rows in it.

        The dict-based writers are called directly rather than through ``add_recording_metadata_to_nwbfile``,
        whose routing would send an old-list-format metadata dict to helpers that only speak that format.
        This path is new, so it supports one format. Both writers read metadata and never write to it.

        Because this table is written here, its rows are the sorted channels in Kilosort's own order, so a
        unit's rows are the positions of its footprint and no mapping is needed.
        """
        from ....tools.spikeinterface.spikeinterface import (
            _add_electrode_groups_to_nwbfile,
            _add_electrodes_to_nwbfile,
        )

        recording = self._generate_recording_with_channel_metadata()
        _add_electrode_groups_to_nwbfile(recording=recording, nwbfile=nwbfile, metadata=metadata)
        _add_electrodes_to_nwbfile(recording=recording, nwbfile=nwbfile, metadata=metadata)

        footprint_masks = self._get_footprint_masks()
        return [
            [int(channel) for channel in np.flatnonzero(footprint_masks[cluster_id])]
            for cluster_id in self._get_cluster_ids()
        ]

    def get_unit_ids_to_channel_ids(
        self,
        *,
        recording_interface: "BaseRecordingExtractorInterface | None" = None,
        channel_ids: list | np.ndarray | None = None,
    ) -> dict:
        """
        Build the unit-to-channel mapping that :py:class:`~neuroconv.converters.SortedRecordingConverter` takes.

        Each unit maps to the channels Kilosort fit its template on, in ascending channel order, named by the
        channel ids of the recording. `channel_map.npy` states which channels of the sorted binary those are,
        so the caller supplies the recording whose channels that binary holds, and by doing so asserts that it
        is the recording Kilosort was run on, with the same channels in the same order. This interface cannot
        verify that assertion, only reject the mismatches the sorter folder records.

        Parameters
        ----------
        recording_interface : BaseRecordingExtractorInterface, optional
            The recording Kilosort was run on. Its channel count and sampling frequency are checked against
            what the sorter folder states.
        channel_ids : list or np.ndarray, optional
            The channel ids of that recording, in its own order, for a caller who has no interface. Only the
            length can be checked.

        Returns
        -------
        dict
            Maps each unit id of this interface to a list of channel ids.
        """
        if (recording_interface is None) == (channel_ids is None):
            raise ValueError("Pass exactly one of `recording_interface` or `channel_ids`.")

        if recording_interface is not None:
            recording = recording_interface.recording_extractor
            channel_ids = recording.channel_ids
            self._validate_recording(recording=recording)

        channel_ids = np.asarray(channel_ids)
        channel_map = np.load(Path(self.source_data["folder_path"]) / "channel_map.npy").reshape(-1)
        if channel_map.max(initial=-1) >= channel_ids.size:
            raise ValueError(
                f"Kilosort sorted channel {channel_map.max()} of its input binary, but the recording given "
                f"here has only {channel_ids.size} channels. This is not the recording Kilosort was run on."
            )

        footprint_masks = self._get_footprint_masks()
        return {
            unit_id: [channel_ids[channel_map[channel]] for channel in np.flatnonzero(footprint_masks[cluster_id])]
            for unit_id, cluster_id in zip(self.sorting_extractor.unit_ids, self._get_cluster_ids())
        }

    def _validate_recording(self, recording) -> None:
        """
        Reject recordings the sorter folder can prove are not the one Kilosort was run on.

        `params.py` records the channel count and sampling rate of the binary, and Kilosort 4 repeats them in
        `ops.npy` as `n_chan_bin` and `fs`. Note the check is against the channel count of the **binary**, not
        the length of `channel_map.npy`, which is a subset whenever channels were excluded from the sort.
        Nothing here is conclusive: a different recording of the same shape passes.
        """
        folder_path = Path(self.source_data["folder_path"])
        params = {}
        exec((folder_path / "params.py").read_text(encoding="utf-8"), params)

        number_of_channels_in_binary = params.get("n_channels_dat")
        if number_of_channels_in_binary is not None and recording.get_num_channels() != number_of_channels_in_binary:
            raise ValueError(
                f"Kilosort was run on a binary with {number_of_channels_in_binary} channels but this recording "
                f"has {recording.get_num_channels()}. If channels were removed before sorting, pass the "
                "recording that was sorted rather than the raw one."
            )

        sampling_frequency = params.get("sample_rate")
        if sampling_frequency is not None and not np.isclose(recording.get_sampling_frequency(), sampling_frequency):
            raise ValueError(
                f"Kilosort was run at {sampling_frequency} Hz but this recording is at "
                f"{recording.get_sampling_frequency()} Hz."
            )

    def _get_waveform_data(self, unit_electrode_indices: list[list[int]] | None = None) -> dict | None:
        """
        Reconstruct the templates from the sorter folder, in volts.

        The templates are stored whitened and in the units of whatever Kilosort was fed, so they are
        unwhitened with `whitening_mat_inv.npy` and scaled by the gain. Unwhitening with the dense inverse
        fills every channel, and those off-footprint values are the inverse-whitening of a zero: a statement
        about the noise covariance rather than about the cell. They are therefore zeroed again afterwards,
        using the footprint mask taken from the whitened templates, so the array claims signal only on the
        channels Kilosort fit each template on.

        The channel axis spans every channel Kilosort sorted, in `channel_map.npy` order, so column ``i``
        means the same channel for every unit. Nothing states which electrodes those channels are, because
        this interface has no way to know: `channel_map.npy` indexes the binary Kilosort was run on, and
        connecting that to an electrodes table takes an assertion only the user can make.

        Returns
        -------
        dict or None
            The waveform data to write, or None when the folder or the gain does not allow it.
        """
        folder_path = Path(self.source_data["folder_path"])
        templates_file_path = folder_path / "templates.npy"
        whitening_file_path = folder_path / "whitening_mat_inv.npy"
        if not templates_file_path.is_file() or not whitening_file_path.is_file():
            warnings.warn(
                f"No templates found in {folder_path}, so its units are written without waveforms.",
                UserWarning,
                stacklevel=3,
            )
            return None

        gain_to_uV = self.source_data["gain_to_uV"]
        if gain_to_uV is None:
            warnings.warn(
                "No gain is available to convert the Kilosort templates to volts, so no waveforms will be "
                "written. Kilosort stores none itself: construct the interface with `gain_to_uV` to write "
                "them.",
                UserWarning,
                stacklevel=3,
            )
            return None

        templates = np.load(templates_file_path)
        cluster_ids = self._get_cluster_ids()
        if cluster_ids.max(initial=-1) >= templates.shape[0]:
            raise ValueError(
                f"This sorting has cluster ids up to {cluster_ids.max()} but {templates_file_path} holds only "
                f"{templates.shape[0]} templates. Ids beyond the template count are produced by merges and "
                "splits done in phy, whose waveforms Kilosort never wrote, so this is curated output rather "
                "than Kilosort output and reading its templates is not supported."
            )

        # The footprint is the set of channels Kilosort fit each template on, and it is only visible here,
        # while the templates are still whitened: they are exactly zero off the footprint, and unwhitening
        # is about to destroy that. Summing the absolute value over the sample axis collapses each
        # (template, channel) pair to zero or non-zero.
        footprint_masks = np.abs(templates).sum(axis=1) != 0

        # Kilosort learns its templates on whitened data, so they are in no physical unit until the
        # whitening is undone. The einsum applies the inverse whitening matrix across the channel axis of
        # every template, leaving the units of whatever Kilosort was fed.
        templates = np.einsum("ij,klj->kli", np.load(whitening_file_path), templates)

        # Those units are the recording's, so the gain converts them to microvolts and 1e-6 to the volts
        # that the schema fixes `waveform_mean` to. No offset: Kilosort high-passes before anything else,
        # so the templates carry no DC term to correct.
        templates = templates * float(gain_to_uV) * 1e-6

        # Templates are indexed by cluster id, which is the row Kilosort wrote them at, while the units of
        # this interface may be a filtered subset in a different order. Selecting by `cluster_ids` puts both
        # arrays in the order of `self.sorting_extractor.unit_ids`, which is what the units table expects.
        templates = templates[cluster_ids]
        footprint_masks = footprint_masks[cluster_ids]

        footprint_sizes = footprint_masks.sum(axis=1)
        electrode_counts = None if unit_electrode_indices is None else [len(unit) for unit in unit_electrode_indices]
        write_footprint = electrode_counts is not None and electrode_counts == footprint_sizes.tolist()

        if write_footprint:
            # The units are linked to electrodes, and those electrodes are this unit's footprint, so the
            # channel axis is narrowed to it and column `j` is the electrode at position `j` of the unit's
            # `electrodes` entry. Both are in ascending channel order, which is what `get_unit_ids_to_channel_ids`
            # produces. The array stays rectangular, so a narrower unit is padded on the right and its own
            # `electrodes` entry declares how much of the row is data.
            waveform_means = np.zeros(
                shape=(cluster_ids.size, templates.shape[1], int(footprint_sizes.max(initial=0))), dtype="float32"
            )
            for unit_index, mask in enumerate(footprint_masks):
                channels = np.flatnonzero(mask)
                waveform_means[unit_index, :, : channels.size] = templates[unit_index][:, channels]
            axis_description = (
                "Column j of the channel axis is the electrode at position j of this unit's electrodes entry; "
                "a unit with fewer electrodes than the width of the array is zero-padded on the right."
            )
        else:
            # `whitening_mat_inv` is dense, so unwhitening spread every template over every channel. Off the
            # footprint those values are the inverse-whitening of a zero, which describes the noise covariance
            # rather than the cell, so they are put back to zero. The array stays probe-width, which keeps
            # column `i` the same channel for every unit and leaves the footprint readable as the non-zero set.
            waveform_means = np.where(footprint_masks[:, np.newaxis, :], templates, 0.0).astype("float32")
            axis_description = (
                "The channel axis holds every channel Kilosort sorted, in the order of channel_map.npy, and is "
                "the same for every unit; a unit is exactly zero on the channels its template was not fit on. "
                "The geometry of those channels is in channel_positions.npy in the sorter folder, and is not "
                "written here because a phy folder states no acquisition device to hang an electrodes table on."
            )
            if electrode_counts is not None:
                warnings.warn(
                    "The electrodes given for each unit are not the channels Kilosort fit its template on, so "
                    "the waveforms are written over every sorted channel instead of over those electrodes. "
                    "Use `get_unit_ids_to_channel_ids()` to derive the mapping from the templates themselves.",
                    UserWarning,
                    stacklevel=3,
                )

        return dict(
            means=waveform_means,
            sampling_rate=self.sorting_extractor.get_sampling_frequency(),
            unit="volts",
            peak_sample=self._get_peak_sample(folder_path=folder_path),
            source_description=(
                "These are the templates Kilosort fit, unwhitened with whitening_mat_inv.npy and converted to "
                f"volts with a gain of {gain_to_uV} microvolts per unit given to the interface; the sorter "
                f"stores them whitened and in the units of its input. {axis_description}"
            ),
        )

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: DeepDict | None = None,
        *,
        stub_test: bool = False,
        write_ecephys_metadata: bool = False,
        write_as: Literal["units", "processing"] | None = None,
        units_name: str = "units",
        units_description: str = "Autogenerated by neuroconv.",
        unit_electrode_indices: list[list[int]] | None = None,
        parent_container: Literal["units", "processing"] = "units",
        waveform_data_dict: dict | None = None,
    ):
        if self.source_data["write_electrodes_table"]:
            if unit_electrode_indices is not None:
                raise ValueError(
                    "This interface was constructed with `write_electrodes_table=True`, but electrodes were "
                    "also supplied for its units, so they already exist and were written by something that "
                    "knows the recording. Drop `write_electrodes_table` and keep the supplied electrodes, "
                    "which are the real ones."
                )
            unit_electrode_indices = self._add_electrodes_table_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        # The layout follows the linkage: with electrodes to label the channel axis the templates are
        # narrowed to each unit's footprint, and without them the axis has to be self-describing, so it
        # spans every sorted channel.
        if waveform_data_dict is None:
            waveform_data_dict = self._get_waveform_data(unit_electrode_indices=unit_electrode_indices)

        # The peak channel is a different question from the footprint and is free to answer, but it can only
        # be written as a row of an electrodes table, so it arrives with the linkage rather than on its own.
        footprint_masks = self._get_footprint_masks()[self._get_cluster_ids()]
        units_are_on_their_footprint = (
            unit_electrode_indices is not None
            and [len(electrodes) for electrodes in unit_electrode_indices] == footprint_masks.sum(axis=1).tolist()
        )
        if units_are_on_their_footprint:
            max_electrodes = [
                electrodes[int(np.flatnonzero(np.flatnonzero(mask) == peak_channel)[0])]
                for electrodes, mask, peak_channel in zip(
                    unit_electrode_indices, footprint_masks, self._get_peak_channels()
                )
            ]
            self.sorting_extractor.set_property(key="max_electrode", values=np.asarray(max_electrodes))

        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            stub_test=stub_test,
            write_ecephys_metadata=write_ecephys_metadata,
            write_as=write_as,
            units_name=units_name,
            units_description=units_description,
            unit_electrode_indices=unit_electrode_indices,
            parent_container=parent_container,
            waveform_data_dict=waveform_data_dict,
        )
