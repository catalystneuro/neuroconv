import numpy as np
from hdmf.common import DynamicTable, VectorIndex
from pynwb import TimeSeries
from pynwb.event import DurationVectorData
from pynwb.file import NWBFile


def _get_nwbfile_times(nwbfile: NWBFile) -> dict[str, np.ndarray]:
    """Collect every time an NWB file holds, keyed by the field's path in the file.

    Which fields count as times is decided per neurodata type: a ``TimeSeries`` contributes its timestamps,
    computed from ``starting_time`` and ``rate`` when they are not stored, and a table contributes the columns
    named ``timestamp`` or ending in ``_time``. Durations are not times and are left out because a shift never
    changes them.

    Returns
    -------
    dict[str, numpy.ndarray]
        The times, keyed for example by ``"acquisition/video/timestamps"`` or ``"events/Tick/timestamp"``.
    """
    times = {}
    for container in nwbfile.objects.values():
        ancestors = [ancestor for ancestor in container.get_ancestors() if not isinstance(ancestor, NWBFile)]
        path = "/".join(reversed([container.name, *(ancestor.name for ancestor in ancestors)]))
        if isinstance(container, TimeSeries):
            times[f"{path}/timestamps"] = np.asarray(container.get_timestamps())
        elif isinstance(container, DynamicTable):
            for column_name in container.colnames:
                is_time_column = column_name == "timestamp" or column_name.endswith("_time")
                if is_time_column and not isinstance(container[column_name], VectorIndex):
                    times[f"{path}/{column_name}"] = np.asarray(container[column_name].data)
    return times


def _get_nwbfile_durations(nwbfile: NWBFile) -> dict[str, np.ndarray]:
    """Collect every duration an NWB file holds, keyed by the column's path in the file.

    A duration is a column typed ``DurationVectorData``, which in the core schema only an ``EventsTable``
    carries. Durations are kept apart from the times because operations treat them differently: a shift
    leaves a duration as it was, and a remap stretches it with the clock.

    Returns
    -------
    dict[str, numpy.ndarray]
        The durations, keyed for example by ``"Tick/duration"``.
    """
    durations = {}
    for container in nwbfile.objects.values():
        if isinstance(container, DurationVectorData):
            ancestors = [ancestor for ancestor in container.get_ancestors() if not isinstance(ancestor, NWBFile)]
            path = "/".join(reversed([container.name, *(ancestor.name for ancestor in ancestors)]))
            durations[path] = np.asarray(container.data)
    return durations
