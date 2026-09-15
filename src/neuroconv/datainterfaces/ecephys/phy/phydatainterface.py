import warnings
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import DirectoryPath, validate_call
from pynwb.file import NWBFile

from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import DeepDict


class PhySortingInterface(BaseSortingExtractorInterface):
    """
    Primary data interface class for converting Phy data.

    Uses :py:func:`~spikeinterface.extractors.read_phy` from SpikeInterface.
    """

    display_name = "Phy Sorting"
    associated_suffixes = (".npy",)
    info = "Interface for Phy sorting data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["exclude_cluster_groups"]["items"] = dict(type="string")
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to the output Phy folder (containing the params.py)."
        return source_schema

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import read_phy

        return read_phy

    def get_max_channel(self) -> np.ndarray:
        """
        The channel on which each unit's template has the largest amplitude.

        This follows what Phy itself does when it picks a unit's "best channel": templates are
        un-whitened with ``whitening_mat_inv.npy`` when that file is present (Kilosort writes whitened
        templates; spikeinterface's ``export_to_phy`` writes none), the amplitude on each channel is
        peak-to-peak, and the largest one wins. A cluster that was merged in Phy is represented by the
        template most of its spikes were assigned to.

        Returns
        -------
        numpy.ndarray
            One entry per unit, in the order of ``self.sorting_extractor.unit_ids``. Each value is an index
            into the recording's channels (``channel_map.npy``), which is the electrode table row when the
            electrodes were written from that recording in order.
        """
        folder_path = Path(self.source_data["folder_path"])

        templates = np.load(folder_path / "templates.npy")  # (n_templates, n_samples, n_template_channels)
        channel_map = np.load(folder_path / "channel_map.npy").ravel()
        whitening_mat_inv_path = folder_path / "whitening_mat_inv.npy"
        if whitening_mat_inv_path.exists():
            templates = templates @ np.load(whitening_mat_inv_path)

        spike_clusters = np.load(folder_path / "spike_clusters.npy").ravel()
        spike_templates = np.load(folder_path / "spike_templates.npy").ravel()
        cluster_ids = self.sorting_extractor.get_property("original_cluster_id")
        template_ids = np.empty(len(cluster_ids), dtype=int)
        for i, cluster_id in enumerate(cluster_ids):
            spike_mask = spike_clusters == cluster_id
            if spike_mask.any():
                template_ids[i] = np.bincount(spike_templates[spike_mask]).argmax()
            else:  # a cluster with no spikes has no better answer than its own id
                template_ids[i] = cluster_id

        amplitude = np.ptp(templates[template_ids], axis=1)  # (n_units, n_template_channels)
        return channel_map[np.argmax(amplitude, axis=1)]

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        exclude_cluster_groups: list[str] | None = None,
        verbose: bool = False,
    ):
        """
        Initialize a PhySortingInterface.

        Parameters
        ----------
        folder_path : str or Path
            Path to the output Phy folder (containing the params.py).
        exclude_cluster_groups : str or list of str, optional
            Cluster groups to exclude (e.g. "noise" or ["noise", "mua"]).
        verbose : bool, default: False
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "exclude_cluster_groups",
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
                f"Passing arguments positionally to PhySortingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            exclude_cluster_groups = positional_values.get("exclude_cluster_groups", exclude_cluster_groups)
            verbose = positional_values.get("verbose", verbose)

        super().__init__(folder_path=folder_path, exclude_cluster_groups=exclude_cluster_groups, verbose=verbose)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: DeepDict | None = None,
        stub_test: bool = False,
        write_ecephys_metadata: bool = False,
        write_as: Literal["units", "processing"] | None = None,
        units_name: str = "units",
        units_description: str = "Imported from Phy",
        unit_electrode_indices: list[list[int]] | None = None,
        *,
        parent_container: Literal["units", "processing"] = "units",
        waveform_data_dict: dict | None = None,
        include_max_channel: bool = True,
    ):
        """
        Add the Phy sorting to the NWBFile.

        All parameters other than ``include_max_channel`` are those of
        :meth:`BaseSortingExtractorInterface.add_to_nwbfile` and are passed through unchanged.

        Parameters
        ----------
        include_max_channel : bool, default: True
            Add a ``max_channel`` column giving, for each unit, the channel with the largest template
            amplitude, computed by :meth:`get_max_channel`. When the file has an electrodes table the column
            references its rows, so the electrodes must have been written from the same recording in the same
            order; if they do not line up the column is skipped with a warning.
        """
        if include_max_channel and "max_channel" not in self.sorting_extractor.get_property_keys():
            max_channels = self.get_max_channel()
            if nwbfile.electrodes is not None and max_channels.max() >= len(nwbfile.electrodes):
                warnings.warn(
                    f"Not adding 'max_channel': the largest channel index is {max_channels.max()} but the "
                    f"electrodes table has {len(nwbfile.electrodes)} rows, so the two do not describe the same "
                    "recording channels."
                )
            else:
                self.sorting_extractor.set_property("max_channel", max_channels)

        return super().add_to_nwbfile(
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
