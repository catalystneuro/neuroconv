"""Converter that combines several :class:`AxonIntracellularInterface` instances (for example dual patch)."""

from pynwb import NWBFile

from .axonintracellularinterface import AxonIntracellularInterface
from ....nwbconverter import ConverterPipe
from ....tools.icephys import (
    _build_icephys_hierarchical_tables,
    _disambiguate_run_labels,
    _validate_grouping_levels,
)


class AxonIntracellularConverter(ConverterPipe):
    """
    Combine one or more :class:`AxonIntracellularInterface` instances into a single NWB icephys table.

    Each interface writes its own electrode's continuous ``PatchClampSeries`` and one intracellular-recordings
    row per sweep, tagging each row with the run-level grouping columns (``sequence``, ``stimulus_type``, and the
    optional ``repetition`` / ``condition``). This converter aligns the files on one timeline, then hands off to
    :func:`~neuroconv.tools.icephys._build_icephys_hierarchical_tables`, which reads those columns back and
    builds the ``SimultaneousRecordings`` / ``SequentialRecordings`` / ``Repetitions`` / ``ExperimentalConditions``
    tables. The aggregator is deliberately format-agnostic so other icephys interfaces can reuse it.

    Interfaces from several files are placed on one timeline by their header start times (``rec_datetime``), the
    earliest file being the session origin. That requires real start times (ABF version 2); combining version-1
    files (placeholder time only) is not yet supported.
    """

    display_name = "Axon Intracellular Converter"
    keywords = AxonIntracellularInterface.keywords
    associated_suffixes = AxonIntracellularInterface.associated_suffixes
    info = "Combines several AxonIntracellularInterface instances (dual patch, multi-file) into one icephys hierarchy."

    def get_metadata(self) -> dict:
        interfaces = list(self.data_interface_objects.values())
        self._assign_run_identities(interfaces)  # before super(), which builds each interface's metadata
        metadata = super().get_metadata()
        if interfaces:
            session_start_datetime, _ = self._compute_alignment(interfaces)
            if session_start_datetime is not None:
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

        # Align the files onto one timeline before the interfaces write their series.
        _, starting_time_shifts = self._compute_alignment(interfaces)
        for interface, shift in starting_time_shifts.items():
            interface._starting_time_shift = shift

        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)

        if interfaces:
            _build_icephys_hierarchical_tables(nwbfile)

    @staticmethod
    def _assign_run_identities(interfaces: list[AxonIntracellularInterface]) -> None:
        """Give each distinct file a unique, human-readable run identity, the disambiguation a lone interface can't
        do because it can't see its siblings.

        Interfaces sharing a file path (dual patch) keep one identity; distinct files get the shortest path-suffix
        that's unique (the bare stem unless it collides across folders, which Clampex's per-folder ``0000.abf``
        naming makes common). This overrides the interface's stem default so ``sequence`` and the device/electrode/
        series keys are unique per file, no silent cross-cell merge, no duplicate-name clash.
        """
        paths = list(dict.fromkeys(interface._file_path for interface in interfaces))
        labels = _disambiguate_run_labels(paths)
        for interface in interfaces:
            interface._run_identity = labels[interface._file_path]

    @staticmethod
    def _compute_alignment(interfaces: list[AxonIntracellularInterface]):
        """
        Return ``(session_start_datetime, {interface: starting_time_shift_seconds})`` from header start times.

        A single file (one or more electrodes) already shares one clock, so every shift is 0. Several files are
        placed by their ``rec_datetime``, the earliest being the origin; that needs real (ABF version 2) start
        times, so a multi-file set with any version-1 file raises rather than trusting a placeholder time.
        """
        file_paths = {str(interface._file_path) for interface in interfaces}
        if len(file_paths) == 1:
            return interfaces[0]._recording_start_datetime, {interface: 0.0 for interface in interfaces}

        # Aligning files by rec_datetime needs real header start times (ABF version 2); a version-1 file
        # carries only a placeholder time.
        all_real_start_times = all(
            interface._reader._axon_info.get("fFileVersionNumber", 0) >= 2
            and interface._recording_start_datetime is not None
            for interface in interfaces
        )
        if not all_real_start_times:
            raise NotImplementedError(
                "Combining multiple ABF files on one timeline requires real header start times (ABF version 2). "
                "At least one file is version 1, which stores only a placeholder time; pass explicit per-file "
                "offsets instead (not yet supported)."
            )

        start_datetimes = {interface: interface._recording_start_datetime for interface in interfaces}
        session_start_datetime = min(start_datetimes.values())
        starting_time_shifts = {
            interface: (start_datetime - session_start_datetime).total_seconds()
            for interface, start_datetime in start_datetimes.items()
        }
        return session_start_datetime, starting_time_shifts
