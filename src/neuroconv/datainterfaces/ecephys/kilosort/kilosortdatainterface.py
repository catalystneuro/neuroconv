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

    def _get_waveform_data(self) -> dict | None:
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
        templates = templates * float(gain_to_uV) * 1e-6
        waveform_means = np.where(footprint_masks[:, np.newaxis, :], templates, 0.0)
        waveform_means = waveform_means[cluster_ids].astype("float32")

        return dict(
            means=waveform_means,
            sampling_rate=self.sorting_extractor.get_sampling_frequency(),
            unit="volts",
            peak_sample=self._get_peak_sample(folder_path=folder_path),
            source_description=(
                "These are the templates Kilosort fit, unwhitened with whitening_mat_inv.npy and converted to "
                f"volts with a gain of {gain_to_uV} microvolts per unit given to the interface; the sorter "
                "stores them whitened and in the units of its input. The channel axis holds every channel "
                "Kilosort sorted, in the order of channel_map.npy, and is the same for every unit; a unit is "
                "exactly zero on the channels its template was not fit on. The geometry of those channels is "
                "in channel_positions.npy in the sorter folder, and is not written here because a phy folder "
                "states no acquisition device to hang an electrodes table on."
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
        if waveform_data_dict is None:
            waveform_data_dict = self._get_waveform_data()

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
