"""Converter that combines several :class:`WaveSurferIntracellularInterface` instances (the runs of a session)."""

from pynwb import NWBFile

from .wavesurferintracellularinterface import WaveSurferIntracellularInterface
from ....nwbconverter import ConverterPipe
from ....tools.icephys import (
    _add_sweep_time_intervals_to_nwbfile,
    _build_icephys_hierarchical_tables,
    _disambiguate_run_labels,
    _validate_grouping_levels,
)


class WaveSurferIntracellularConverter(ConverterPipe):
    """
    Combine one or more :class:`WaveSurferIntracellularInterface` instances into a single NWB icephys table.

    Each interface writes one electrode's run as a continuous ``PatchClampSeries`` and one intracellular-recordings
    row per sweep, tagging each row with the run-level grouping columns (``sequence``, ``stimulus_type``, and the
    optional ``repetition`` / ``condition``). This converter places the runs on one timeline by their
    ``ClockAtRunStart``, the earliest run being the session start, then builds the ``SimultaneousRecordings`` /
    ``SequentialRecordings`` / ``Repetitions`` / ``ExperimentalConditions`` tables with
    :func:`~neuroconv.tools.icephys._build_icephys_hierarchical_tables` and the sweep start and stop times with
    :func:`~neuroconv.tools.icephys._add_sweep_time_intervals_to_nwbfile`.

    It is also worth using for a single run: that is where its hierarchy and sweep tables come from.
    """

    display_name = "WaveSurfer Intracellular Converter"
    keywords = WaveSurferIntracellularInterface.keywords
    associated_suffixes = WaveSurferIntracellularInterface.associated_suffixes
    info = "Combines several WaveSurferIntracellularInterface instances into one icephys hierarchy."

    def __init__(
        self,
        data_interfaces: list[WaveSurferIntracellularInterface] | dict[str, WaveSurferIntracellularInterface],
        verbose: bool = False,
    ):
        super().__init__(data_interfaces=data_interfaces, verbose=verbose)
        interfaces = list(self.data_interface_objects.values())
        if interfaces:
            _, starting_times = self._compute_alignment(interfaces)
            for interface, starting_time in starting_times.items():
                interface.temporal_alignment.move_start_to(starting_time)

    def get_metadata(self) -> dict:
        interfaces = list(self.data_interface_objects.values())
        self._assign_run_identities(interfaces)  # before super(), which builds each interface's metadata
        metadata = super().get_metadata()
        if interfaces:
            session_start_datetime, _ = self._compute_alignment(interfaces)
            metadata["NWBFile"]["session_start_time"] = session_start_datetime
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        conversion_options: dict | None = None,
    ) -> None:
        interfaces = list(self.data_interface_objects.values())
        self._assign_run_identities(interfaces)
        _validate_grouping_levels(
            repetitions=[interface._repetition for interface in interfaces],
            conditions=[interface._condition for interface in interfaces],
        )

        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)

        if interfaces:
            _build_icephys_hierarchical_tables(nwbfile)
            _add_sweep_time_intervals_to_nwbfile(nwbfile)

    @staticmethod
    def _assign_run_identities(interfaces: list[WaveSurferIntracellularInterface]) -> None:
        """Give each distinct file a unique run identity: the shortest path suffix that no other file shares.

        Interfaces sharing a file (two electrodes recorded together) keep one identity, so their rows group into
        one simultaneous recording per sweep.
        """
        paths = list(dict.fromkeys(interface._file_path for interface in interfaces))
        labels = _disambiguate_run_labels(paths)
        for interface in interfaces:
            interface._run_identity = labels[interface._file_path]

    @staticmethod
    def _compute_alignment(interfaces: list[WaveSurferIntracellularInterface]):
        """Return ``(session_start_datetime, {interface: starting_time_seconds})``, keeping current alignment.

        Each run starts at its ``ClockAtRunStart``, so the earliest run is the origin and every other run starts at
        its offset from it.
        """
        start_datetimes = {interface: interface._recording_start_datetime for interface in interfaces}
        session_start_datetime = min(start_datetimes.values())
        starting_times = {
            interface: interface.temporal_alignment[interface._alignment_key]._get_start_time()
            + (start_datetime - session_start_datetime).total_seconds()
            for interface, start_datetime in start_datetimes.items()
        }
        return session_start_datetime, starting_times
