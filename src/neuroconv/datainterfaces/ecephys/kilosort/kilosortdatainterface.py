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

        super().__init__(folder_path=folder_path, keep_good_only=keep_good_only, verbose=verbose, gain_to_uV=gain_to_uV)

    def _initialize_extractor(self, interface_kwargs: dict):
        # ``gain_to_uV`` describes what the sorted data means rather than how to read the folder, so it
        # belongs to the source data but is not an argument of the extractor.
        extractor_kwargs = {key: value for key, value in interface_kwargs.items() if key != "gain_to_uV"}
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

    def _generate_recording_with_channel_metadata(self):
        """
        Build a recording that carries the channel geometry stored in the sorter folder.

        A phy folder states the geometry of the channels Kilosort sorted (`channel_map.npy`,
        `channel_positions.npy` and, for Kilosort 4, `channel_shanks.npy`), so an electrodes table can be
        written from a sorter folder alone. Only the identity of the device and the electrode group has to
        be invented, and the user overrides both through metadata.

        Returns
        -------
        spikeinterface.core.NumpyRecording
            A single-sample recording whose channels are the ones Kilosort sorted, in its own order, named
            by their index in the recording it was run on.
        """
        from spikeinterface.core import NumpyRecording

        folder_path = Path(self.source_data["folder_path"])
        channel_map = np.load(folder_path / "channel_map.npy").reshape(-1)
        channel_positions = np.load(folder_path / "channel_positions.npy")

        recording = NumpyRecording(
            traces_list=[np.empty(shape=(1, channel_map.size))],
            sampling_frequency=self.sorting_extractor.get_sampling_frequency(),
            channel_ids=[str(channel_index) for channel_index in channel_map],
        )
        recording.set_property(key="location", values=channel_positions)

        channel_shanks_file_path = folder_path / "channel_shanks.npy"
        if channel_shanks_file_path.is_file():
            recording.set_channel_groups(groups=np.load(channel_shanks_file_path).reshape(-1).astype(int))

        return recording

    def _get_peak_sample(self, folder_path: Path) -> int | None:
        """Read the sample the templates are aligned on, which only Kilosort 4 records."""
        ops_file_path = folder_path / "ops.npy"
        if not ops_file_path.is_file():
            return None

        ops = np.load(ops_file_path, allow_pickle=True).item()
        peak_sample = ops.get("nt0min")
        return None if peak_sample is None else int(peak_sample)

    def _get_gains_to_micro_volts(self, channel_map: np.ndarray):
        """
        Resolve the gain that turns the sorter's units into microvolts, one value per sorted channel.

        Kilosort records no scaling of its own, so the gain is either given to the interface or read from a
        registered recording. Nothing else in this interface depends on it.

        Returns
        -------
        tuple of (np.ndarray or None, str or None)
            The per-channel gains and a phrase naming where they came from, or a pair of Nones when no
            gain is available.
        """
        gain_to_uV = self.source_data["gain_to_uV"]
        if gain_to_uV is not None:
            gains = np.full(shape=channel_map.size, fill_value=float(gain_to_uV))
            return gains, f"a gain of {gain_to_uV} microvolts per unit given to the interface"

        if self.sorting_extractor.has_recording():
            recording_gains = self.sorting_extractor._recording.get_channel_gains()
            if recording_gains is not None:
                gains = np.asarray(recording_gains, dtype=float)[channel_map]
                unique_gains = np.unique(gains)
                if unique_gains.size == 1:
                    provenance = f"a gain of {unique_gains[0]} microvolts per unit from the registered recording"
                else:
                    provenance = "the per-channel gains of the registered recording"
                return gains, provenance

        warnings.warn(
            "No gain is available to convert the Kilosort templates to volts, so no waveforms will be written. "
            "Kilosort stores none itself: either register the recording it was run on with "
            "`register_recording()` or construct the interface with `gain_to_uV`.",
            UserWarning,
            stacklevel=4,
        )
        return None, None

    def _add_electrodes_and_get_waveform_data(
        self,
        nwbfile: NWBFile,
        metadata: DeepDict,
    ) -> tuple[list[list[int]] | None, dict | None]:
        """
        Write the electrodes table when the file has none, and reconstruct the templates from the folder.

        Each template is restricted to its footprint, the channels Kilosort fit it on, which is the sorter's
        own answer to which channels a unit is on and needs no threshold of ours. The footprint is the
        non-zero column mask of `templates.npy` and must be taken before unwhitening: the dense inverse
        spreads every template over all channels, and those values are the inverse-whitening of a zero, a
        statement about the noise covariance rather than about the cell.

        Returns
        -------
        tuple of (list of lists of int or None, dict or None)
            The electrodes of each unit and the waveform data to write, either of which is None when the
            folder does not carry what it takes to build it.
        """
        folder_path = Path(self.source_data["folder_path"])
        geometry_file_paths = [folder_path / "channel_map.npy", folder_path / "channel_positions.npy"]
        if not all(file_path.is_file() for file_path in geometry_file_paths):
            warnings.warn(
                f"The channel geometry of {folder_path} is incomplete, so its units are written without "
                "electrodes and without waveforms.",
                UserWarning,
                stacklevel=3,
            )
            return None, None

        channel_map = np.load(folder_path / "channel_map.npy").reshape(-1)
        if nwbfile.electrodes is None:
            # The dict-based writers are called directly rather than through
            # ``add_recording_metadata_to_nwbfile``, whose routing would send an old-list-format metadata
            # dict to helpers that only speak that format. This path is new, so it supports one format.
            from ....tools.spikeinterface.spikeinterface import (
                _add_electrode_groups_to_nwbfile,
                _add_electrodes_to_nwbfile,
            )

            recording = self._generate_recording_with_channel_metadata()
            _add_electrode_groups_to_nwbfile(recording=recording, nwbfile=nwbfile, metadata=metadata)
            _add_electrodes_to_nwbfile(recording=recording, nwbfile=nwbfile, metadata=metadata)
            # Our own table holds one row per sorted channel, in the order Kilosort saw them.
            electrode_indices = np.arange(channel_map.size)
        elif self.sorting_extractor.has_recording():
            # `channel_map` holds indices into the channels of the binary Kilosort was fed, and the
            # registered recording is that binary, so its channel ids identify the rows exactly. Resolving
            # them through the table's own identity keeps this right when the file holds several probes.
            from ....tools.spikeinterface.spikeinterface import (
                _build_channel_id_to_electrodes_table_map,
            )

            recording = self.sorting_extractor._recording
            channel_id_to_electrode_row = _build_channel_id_to_electrodes_table_map(
                recording=recording, nwbfile=nwbfile
            )
            electrode_rows = [channel_id_to_electrode_row[channel_id] for channel_id in recording.channel_ids]
            if any(electrode_row is None for electrode_row in electrode_rows):
                raise ValueError(
                    "The channels of the recording registered to this sorting are not all in the electrodes "
                    "table of the file, so the units cannot be linked to the electrodes they came from."
                )
            electrode_indices = np.asarray(electrode_rows)[channel_map]
        else:
            raise ValueError(
                f"The file already has an electrodes table that this interface did not write, and "
                f"{folder_path} states which channels its units came from only as indices into the "
                "recording Kilosort was run on, which is not enough to find their rows. Attach that "
                "recording with `register_recording(recording_interface=...)` so the units can be linked "
                "to their electrodes."
            )

        templates_file_path = folder_path / "templates.npy"
        whitening_file_path = folder_path / "whitening_mat_inv.npy"
        if not templates_file_path.is_file() or not whitening_file_path.is_file():
            warnings.warn(
                f"No templates found in {folder_path}, so its units are written without electrodes and "
                "without waveforms.",
                UserWarning,
                stacklevel=3,
            )
            return None, None

        templates = np.load(templates_file_path)
        cluster_ids = self.sorting_extractor.get_property("original_cluster_id")
        if cluster_ids is None:
            cluster_ids = self.sorting_extractor.unit_ids
        cluster_ids = np.asarray(cluster_ids, dtype=int)
        if cluster_ids.max(initial=-1) >= templates.shape[0]:
            raise ValueError(
                f"This sorting has cluster ids up to {cluster_ids.max()} but {templates_file_path} holds only "
                f"{templates.shape[0]} templates. Ids beyond the template count are produced by merges and "
                "splits done in phy, whose waveforms Kilosort never wrote, so this is curated output rather "
                "than Kilosort output and reading its templates is not supported."
            )

        footprint_masks = np.abs(templates).sum(axis=1) != 0
        templates = np.einsum("ij,klj->kli", np.load(whitening_file_path), templates)

        gains_to_micro_volts, gain_provenance = self._get_gains_to_micro_volts(channel_map=channel_map)

        # waveform_mean is rectangular, so a unit whose footprint is narrower than the widest one is padded
        # with its real channels first and its own `electrodes` entry declares how much of the row is data.
        number_of_units = cluster_ids.size
        width = int(footprint_masks[cluster_ids].sum(axis=1).max(initial=0))
        waveform_means = np.zeros(shape=(number_of_units, templates.shape[1], width), dtype="float32")

        unit_electrode_indices = []
        max_electrodes = []
        for unit_index, cluster_id in enumerate(cluster_ids):
            channels = np.flatnonzero(footprint_masks[cluster_id])
            unit_electrode_indices.append([int(electrode_indices[channel]) for channel in channels])

            template = templates[cluster_id][:, channels]
            if gains_to_micro_volts is not None:
                template = template * gains_to_micro_volts[channels] * 1e-6
                waveform_means[unit_index, :, : channels.size] = template
            if channels.size > 0:
                max_electrodes.append(int(electrode_indices[channels[np.argmax(np.ptp(template, axis=0))]]))

        # The peak channel is a different question from the footprint and is free to answer here.
        if len(max_electrodes) == number_of_units:
            self.sorting_extractor.set_property(key="max_electrode", values=np.array(max_electrodes))

        if gains_to_micro_volts is None:
            return unit_electrode_indices, None

        waveform_data_dict = dict(
            means=waveform_means,
            sampling_rate=self.sorting_extractor.get_sampling_frequency(),
            unit="volts",
            peak_sample=self._get_peak_sample(folder_path=folder_path),
            source_description=(
                "These are the templates Kilosort fit, unwhitened with whitening_mat_inv.npy and converted "
                f"to volts with {gain_provenance}; the sorter stores them whitened and in the units of its "
                "input."
            ),
        )
        return unit_electrode_indices, waveform_data_dict

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
        if metadata is None:
            metadata = self.get_metadata()

        # The electrodes table is written from the sorter folder when the file has none, both because the
        # `electrodes` column of the units table needs it and because it is worth having on its own for a
        # conversion with no raw data. A table that is already there is used as it stands, so a recording
        # interface in the same conversion keeps ownership of it.
        if unit_electrode_indices is None and waveform_data_dict is None:
            unit_electrode_indices, waveform_data_dict = self._add_electrodes_and_get_waveform_data(
                nwbfile=nwbfile,
                metadata=metadata,
            )

        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            stub_test=stub_test,
            write_ecephys_metadata=False,
            write_as=write_as,
            units_name=units_name,
            units_description=units_description,
            unit_electrode_indices=unit_electrode_indices,
            parent_container=parent_container,
            waveform_data_dict=waveform_data_dict,
        )
