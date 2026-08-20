"""Converter that combines several :class:`BrukerVoltageRecordingInterface` instances (for example dual patch)."""

from pynwb import NWBFile

from .brukervoltagerecordinginterface import BrukerVoltageRecordingInterface
from ....nwbconverter import ConverterPipe
from ....tools.icephys import (
    _add_sweep_time_intervals_to_nwbfile,
    _build_icephys_hierarchical_tables,
    _disambiguate_run_labels,
    _validate_grouping_levels,
)


class BrukerVoltageRecordingConverter(ConverterPipe):
    """
    Combine one or more :class:`BrukerVoltageRecordingInterface` instances into a single NWB icephys table.

    Each interface writes one electrode's cycles as a continuous ``PatchClampSeries`` and one
    intracellular-recordings row per cycle, tagging each row with the run-level grouping columns (``sequence``,
    the optional ``stimulus_type``, and the optional ``repetition`` / ``condition``). This converter aligns the
    electrodes on one timeline, then hands off to
    :func:`~neuroconv.tools.icephys._build_icephys_hierarchical_tables`, which reads those columns back and
    builds the ``SimultaneousRecordings`` / ``SequentialRecordings`` / ``Repetitions`` / ``ExperimentalConditions``
    tables, and to :func:`~neuroconv.tools.icephys._add_sweep_time_intervals_to_nwbfile`, which writes the sweep
    start and stop times as a ``TimeIntervals`` table. Both are deliberately format-agnostic, and the interfaces
    never call them, because building those tables locks their membership and no single interface knows whether
    it is the last contributor to the file.

    So it is also worth using for a single electrode: that is where its hierarchy and sweep tables come from.
    """

    display_name = "Bruker VoltageRecording Converter"
    keywords = BrukerVoltageRecordingInterface.keywords
    associated_suffixes = BrukerVoltageRecordingInterface.associated_suffixes
    info = "Combines several BrukerVoltageRecordingInterface instances into one icephys hierarchy."

    def __init__(
        self,
        data_interfaces: list[BrukerVoltageRecordingInterface] | dict[str, BrukerVoltageRecordingInterface],
        verbose: bool = False,
    ):
        super().__init__(data_interfaces=data_interfaces, verbose=verbose)
        # Place the electrodes on one timeline here, where every interface is finally in view. It happens once, at
        # construction, because ``shift_times`` accumulates and a per-write placement would stack up over repeated
        # writes. Nothing is lost by doing it early: the placement comes from cycle start times that do not change.
        # A user shifting afterwards moves the placed set as a block.
        interfaces = list(self.data_interface_objects.values())
        if interfaces:
            _, starting_time_shifts = self._compute_alignment(interfaces)
            for interface, starting_time_shift in starting_time_shifts.items():
                interface.alignment.shift_times(starting_time_shift)

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
    def _assign_run_identities(interfaces: list[BrukerVoltageRecordingInterface]) -> None:
        """Give each distinct run a unique, human-readable identity, the disambiguation a lone interface can't
        do because it can't see its siblings.

        A run is identified by the acquisition stem its cycles share, which PrairieView writes into the XML's
        ``DataFile``. Interfaces over the same run (the ``Primary`` and ``Secondary`` outputs of one electrode,
        say) keep one identity; distinct runs get the shortest path-suffix that is unique, since the stem alone
        collides across session folders. This overrides the interface's default so ``sequence`` and the
        electrode key are unique per run, with no silent cross-cell merge.
        """
        run_paths_by_interface = {
            interface: interface._file_paths[0].with_name(interface._cycle_headers[0].stem + ".csv")
            for interface in interfaces
        }
        labels = _disambiguate_run_labels(list(dict.fromkeys(run_paths_by_interface.values())))
        for interface, run_path in run_paths_by_interface.items():
            interface._run_identity = labels[run_path]
        BrukerVoltageRecordingConverter._check_one_amplifier_per_run(interfaces)

    @staticmethod
    def _check_one_amplifier_per_run(interfaces: list[BrukerVoltageRecordingInterface]) -> None:
        """Refuse two interfaces that claim one electrode but report different amplifiers.

        Interfaces over one run share an electrode by design, which is what puts an amplifier's ``Primary``
        and ``Secondary`` outputs on a single pipette. Two different ``PatchclampDevice`` values under one run
        mean two headstages, so they are two electrodes rather than one, and letting them merge would attribute
        one cell's data to the other's amplifier (the metadata merge keeps whichever device link came last).
        """
        devices_by_run: dict[str, dict[str, str]] = {}
        for interface in interfaces:
            device_name = interface._response_signal.patchclamp_device
            recorded = devices_by_run.setdefault(interface._run_identity, {})
            recorded[device_name] = interface._response_signal_name
            if len(recorded) > 1:
                described = ", ".join(f"{name!r} on {device!r}" for device, name in sorted(recorded.items()))
                raise ValueError(
                    f"Run '{interface._run_identity}' has signals on more than one amplifier ({described}), so "
                    "they are separate electrodes rather than two outputs of one. Give them distinct "
                    "`metadata_key` values and point each series at its own electrode entry."
                )

    @staticmethod
    def _compute_alignment(interfaces: list[BrukerVoltageRecordingInterface]):
        """
        Return ``(session_start_datetime, {interface: starting_time_shift_seconds})`` from the cycle timestamps.

        Every cycle carries its own ``DateTime`` with the rig's UTC offset, so unlike ABF there is no version
        of the format that lacks a real start time and no fallback to arrange for. The earliest cycle of the
        whole set is the session origin, and electrodes recorded together resolve to the same shift.
        """
        start_datetimes = {interface: interface._recording_start_datetime for interface in interfaces}
        session_start_datetime = min(start_datetimes.values())
        starting_time_shifts = {
            interface: (start_datetime - session_start_datetime).total_seconds()
            for interface, start_datetime in start_datetimes.items()
        }
        return session_start_datetime, starting_time_shifts
