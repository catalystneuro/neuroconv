import copy
from pathlib import Path

import numpy as np
from pydantic import FilePath
from pynwb import NWBFile

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....tools import get_package
from ....utils import DeepDict


def _load_eeg_struct(file_path: FilePath) -> dict:
    """Load the EEGLAB ``EEG`` structure from a ``.set`` file using pymatreader."""
    get_package(package_name="pymatreader")
    from pymatreader import read_mat

    contents = read_mat(str(file_path))
    # The struct is normally stored under the top-level "EEG" key, but some files
    # store the fields directly at the top level.
    return contents.get("EEG", contents)


def _read_fdt_data(
    set_path: Path, data_filename: str, number_of_channels: int, number_of_points: int, number_of_trials: int
) -> np.ndarray:
    """
    Read the external ``.fdt`` binary referenced by an EEGLAB ``.set`` file.

    The ``.fdt`` is written by EEGLAB's ``floatwrite`` as little-endian ``float32`` in MATLAB
    column-major order of a ``(n_channels, n_points, n_trials)`` array, i.e. the channel index
    varies fastest, then the sample index, then the trial index.

    Returns
    -------
    numpy.ndarray
        Data with shape ``(n_channels, n_points, n_trials)``.
    """
    # EEGLAB may store a full or relative path in EEG.data; only the file name is meaningful here.
    candidate = set_path.parent / Path(data_filename).name
    if not candidate.exists():
        # Fall back to the EEGLAB convention of matching the .set stem with a .fdt extension.
        candidate = set_path.with_suffix(".fdt")
    if not candidate.exists():
        raise FileNotFoundError(
            f"The EEGLAB file '{set_path.name}' references external data file '{data_filename}', but it was not "
            f"found next to the .set file (looked for '{set_path.parent / Path(data_filename).name}'). "
            "The .set and .fdt files must be kept together."
        )

    flat = np.fromfile(candidate, dtype="<f4")
    expected_size = number_of_channels * number_of_points * number_of_trials
    if flat.size != expected_size:
        raise ValueError(
            f"The EEGLAB data file '{candidate.name}' has {flat.size} samples but the header "
            f"(nbchan={number_of_channels}, pnts={number_of_points}, trials={number_of_trials}) "
            f"implies {expected_size}."
        )
    # Column-major write of (n_channels, n_points, n_trials) -> reverse-shape C-order then transpose back.
    return flat.reshape((number_of_trials, number_of_points, number_of_channels)).transpose(2, 1, 0).astype("float64")


def _get_inline_data(data, number_of_channels: int, number_of_points: int, number_of_trials: int) -> np.ndarray:
    """Normalize an inline ``EEG.data`` array to shape ``(n_channels, n_points, n_trials)``."""
    array = np.asarray(data, dtype="float64")
    if array.ndim == 2:
        # Guard against a transposed (n_points, n_channels) layout.
        if array.shape[0] == number_of_points and array.shape[0] != number_of_channels:
            array = array.T
        array = array[:, :, np.newaxis]
    if array.shape != (number_of_channels, number_of_points, number_of_trials):
        array = array.reshape((number_of_channels, number_of_points, number_of_trials))
    return array


def _extract_channel_info(eeg_struct: dict, number_of_channels: int):
    """Return ``(channel_names, locations)`` from the EEGLAB ``chanlocs`` struct."""
    channel_locations = eeg_struct.get("chanlocs")
    channel_locations = channel_locations if isinstance(channel_locations, dict) else dict()

    labels = channel_locations.get("labels")
    if labels is not None and len(labels) == number_of_channels:
        channel_names = [str(label).strip() for label in labels]
    else:
        channel_names = [str(index) for index in range(number_of_channels)]

    locations = None
    if all(key in channel_locations for key in ("X", "Y", "Z")):
        x = _coerce_coordinate(channel_locations["X"], number_of_channels)
        y = _coerce_coordinate(channel_locations["Y"], number_of_channels)
        z = _coerce_coordinate(channel_locations["Z"], number_of_channels)
        if x is not None and y is not None and z is not None:
            locations = np.column_stack([x, y, z])

    return channel_names, locations


def _coerce_coordinate(values, number_of_channels: int):
    """
    Coerce a chanlocs coordinate field to a float array of length ``number_of_channels``.

    EEGLAB stores a missing per-channel coordinate (e.g. for EOG channels) as an empty value, which
    makes the field an inhomogeneous array. Missing entries are filled with ``NaN``. Returns ``None``
    if the field cannot be aligned to the channels.
    """
    # ``values`` may be an inhomogeneous Python list (scalars mixed with empty entries for channels
    # that lack a location), so iterate the raw sequence rather than array-ifying it wholesale.
    values = list(values) if isinstance(values, (list, tuple)) else list(np.atleast_1d(values))
    if len(values) != number_of_channels:
        return None
    coordinate = np.full(number_of_channels, fill_value=np.nan, dtype="float64")
    for index, value in enumerate(values):
        scalar = np.atleast_1d(value).ravel()
        if scalar.size == 1 and not isinstance(scalar[0], (str, bytes)):
            coordinate[index] = float(scalar[0])
    return coordinate


def _extract_epoch_info(
    eeg_struct: dict,
    sampling_frequency: float,
    number_of_points: int,
    number_of_trials: int,
    epoch_start_time: float,
) -> "list[dict] | None":
    """
    Recover per-epoch timing from ``EEG.event`` + ``EEG.urevent``.

    Epoched EEGLAB datasets keep, for each epoch, the original (continuous-recording) latency of its
    time-locking event in ``EEG.urevent``. From that we recover where each epoch actually sat in the
    source recording, so epochs can be placed on a shared, real session timeline.

    Returns
    -------
    list of dict or None
        One dict per epoch ``{"onset": float, "label": str}`` where ``onset`` is the real recording
        time (seconds) of the epoch's **first sample** and ``label`` is its time-locking event type.
        Returns ``None`` when the timing cannot be recovered (no events/urevents), so the caller can
        fall back to epoch-relative placement.
    """
    event_struct = eeg_struct.get("event")
    urevent_struct = eeg_struct.get("urevent")
    if not (isinstance(event_struct, dict) and "latency" in event_struct and "epoch" in event_struct):
        return None
    if not (isinstance(urevent_struct, dict) and "latency" in urevent_struct and "urevent" in event_struct):
        return None

    latencies = np.atleast_1d(event_struct["latency"]).astype("float64")
    epochs = np.atleast_1d(event_struct["epoch"]).astype("int64")
    urevent_refs = np.atleast_1d(event_struct["urevent"]).astype("int64")
    types = np.atleast_1d(event_struct.get("type", np.full(len(latencies), "")))
    urevent_latencies = np.atleast_1d(urevent_struct["latency"]).astype("float64")

    # 1-based within-epoch sample at the time-locking event (epoch-relative t == 0).
    lock_within_sample = 1.0 - epoch_start_time * sampling_frequency

    info = []
    for epoch in range(1, number_of_trials + 1):
        indices = np.where(epochs == epoch)[0]
        if len(indices) == 0:
            return None
        within = latencies[indices] - (epoch - 1) * number_of_points
        locking = indices[int(np.argmin(np.abs(within - lock_within_sample)))]
        reference = int(urevent_refs[locking])
        if reference < 1 or reference > len(urevent_latencies):
            return None
        locking_event_time = (urevent_latencies[reference - 1] - 1.0) / sampling_frequency
        info.append(dict(onset=locking_event_time + epoch_start_time, label=str(types[locking]).strip()))
    return info


def _events_from_struct(struct: dict, sampling_frequency: float, latency_to_time) -> list[dict]:
    """Build event dicts from an EEGLAB event-like struct (``EEG.event`` or ``EEG.urevent``)."""
    latencies = np.atleast_1d(struct["latency"])
    types = np.atleast_1d(struct.get("type", np.full(len(latencies), "")))
    durations = struct.get("duration")
    durations = np.atleast_1d(durations) if durations is not None else np.zeros(len(latencies))

    events = []
    for index, latency in enumerate(latencies):
        duration_in_samples = float(durations[index]) if index < len(durations) else 0.0
        duration_in_samples = 0.0 if np.isnan(duration_in_samples) else duration_in_samples
        start_time = latency_to_time(index, float(latency))
        stop_time = start_time + duration_in_samples / sampling_frequency
        label = str(types[index] if index < len(types) else "").strip()
        events.append(dict(start_time=start_time, stop_time=stop_time, label=label))
    return events


def _extract_events(
    eeg_struct: dict,
    sampling_frequency: float,
    number_of_points: int,
    number_of_trials: int,
    epoch_onsets: list,
) -> list[dict]:
    """
    Convert EEGLAB events into a list of ``{start_time, stop_time, label}`` dicts on the shared timeline.

    For epoched data, ``EEG.event`` lists each event once per *containing* epoch, so overlapping epochs
    duplicate events; ``EEG.urevent`` holds the unique original events at their real latencies, so it is
    used when available. Otherwise ``EEG.event`` is used: for epoched data each event is placed at its
    epoch's real onset plus its within-epoch offset; for continuous data at its latency in seconds.
    """
    is_epoched = number_of_trials > 1
    urevent_struct = eeg_struct.get("urevent")
    if is_epoched and isinstance(urevent_struct, dict) and "latency" in urevent_struct:
        # urevent latencies are 1-based samples in the original continuous recording.
        return _events_from_struct(
            urevent_struct, sampling_frequency, lambda index, latency: (latency - 1.0) / sampling_frequency
        )

    event_struct = eeg_struct.get("event")
    if not isinstance(event_struct, dict) or "latency" not in event_struct:
        return []

    epoch_indices = np.atleast_1d(event_struct["epoch"]) if (is_epoched and "epoch" in event_struct) else None

    def latency_to_time(index, latency):
        if is_epoched:
            epoch_index = int(epoch_indices[index]) - 1 if epoch_indices is not None else int((latency - 1.0) // number_of_points)
            within_epoch_sample = latency - epoch_index * number_of_points  # 1-based
            return epoch_onsets[epoch_index] + (within_epoch_sample - 1.0) / sampling_frequency
        return epoch_onsets[0] + (latency - 1.0) / sampling_frequency

    return _events_from_struct(event_struct, sampling_frequency, latency_to_time)


def _clean_cell(value):
    """Coerce a (possibly empty / numpy-wrapped) MATLAB cell value to a clean string, or ``None``."""
    if value is None:
        return None
    array = np.atleast_1d(value).ravel()
    if array.size == 0:
        return None
    scalar = array[0]
    if isinstance(scalar, bytes):
        scalar = scalar.decode(errors="ignore")
    text = str(scalar).strip()
    if not text or text.lower() == "n/a":
        return None
    return text


def _parse_bids_pinfo(pinfo) -> dict:
    """Parse the EEGLAB ``BIDS.pInfo`` table (header row + one row per subject) into a dict."""
    if pinfo is None:
        return dict()
    rows = list(pinfo)
    if len(rows) < 2:
        return dict()
    header = [str(name).strip() for name in rows[0]]
    values = rows[1]  # single-subject .set files have one data row
    return {column: value for column, value in zip(header, values)}


def _map_sex(value) -> "str | None":
    """Map an EEGLAB/BIDS gender value to an NWB sex code (``M``/``F``/``O``/``U``)."""
    text = _clean_cell(value)
    if text is None:
        return None
    mapping = {"MALE": "M", "FEMALE": "F", "OTHER": "O", "UNKNOWN": "U"}
    if text.upper() in mapping:
        return mapping[text.upper()]
    if text[0].upper() in ("M", "F", "O", "U"):
        return text[0].upper()
    return None


def _to_iso_age(value) -> "str | None":
    """Convert an age in years to an ISO 8601 duration string (e.g. ``35`` -> ``P35Y``)."""
    text = _clean_cell(value)
    if text is None:
        return None
    try:
        years = float(text)
    except ValueError:
        return None
    if years <= 0:
        return None
    return f"P{int(years)}Y" if years == int(years) else f"P{years}Y"


def _extract_subject_metadata(eeg_struct: dict) -> dict:
    """Extract subject metadata from ``EEG.subject`` and the EEGLAB ``BIDS.pInfo`` table."""
    subject_metadata = dict()

    subject = eeg_struct.get("subject")
    subject_id = _clean_cell(subject) if not isinstance(subject, str) else (subject.strip() or None)
    if subject_id:
        subject_metadata["subject_id"] = subject_id

    bids = eeg_struct.get("BIDS")
    if isinstance(bids, dict):
        fields = _parse_bids_pinfo(bids.get("pInfo"))
        if "subject_id" not in subject_metadata:
            participant_id = _clean_cell(fields.get("participant_id"))
            if participant_id:
                subject_metadata["subject_id"] = participant_id
        sex = _map_sex(fields.get("Gender") if "Gender" in fields else fields.get("Sex"))
        if sex:
            subject_metadata["sex"] = sex
        age = _to_iso_age(fields.get("Age"))
        if age:
            subject_metadata["age"] = age

    return subject_metadata


def _read_eeglab_recording(file_path: FilePath):
    """
    Read an EEGLAB ``.set`` file (with optional external ``.fdt``) into a SpikeInterface recording.

    Handles both EEGLAB layouts (self-contained ``.set`` with inline data, and a ``.set`` + ``.fdt``
    pair). Continuous data becomes a single-segment recording. Epoched data (``EEG.trials > 1``)
    becomes a multi-segment recording with one segment per epoch, each segment starting at the epoch's
    real time in the source recording (recovered from ``EEG.urevent``) so all epochs live on a shared
    session timeline; when that timing cannot be recovered, epochs fall back to the epoch-relative
    start (``EEG.xmin``).

    Returns
    -------
    tuple
        ``(recording, events, subject_metadata, epochs)`` where ``epochs`` is a list of per-epoch
        dicts (empty for continuous data).
    """
    from spikeinterface.core import NumpyRecording

    file_path = Path(file_path)
    eeg_struct = _load_eeg_struct(file_path=file_path)

    sampling_frequency = float(eeg_struct["srate"])
    number_of_channels = int(eeg_struct["nbchan"])
    number_of_points = int(eeg_struct["pnts"])
    number_of_trials = int(np.atleast_1d(eeg_struct.get("trials", 1)).ravel()[0])
    epoch_start_time = float(np.atleast_1d(eeg_struct.get("xmin", 0.0)).ravel()[0])
    is_epoched = number_of_trials > 1

    data = eeg_struct.get("data")
    if isinstance(data, str):
        traces = _read_fdt_data(
            set_path=file_path,
            data_filename=data,
            number_of_channels=number_of_channels,
            number_of_points=number_of_points,
            number_of_trials=number_of_trials,
        )
    else:
        traces = _get_inline_data(
            data=data,
            number_of_channels=number_of_channels,
            number_of_points=number_of_points,
            number_of_trials=number_of_trials,
        )

    # Real first-sample time of each epoch on the shared session timeline. Recovered from urevent when
    # possible; otherwise epochs fall back to the epoch-relative start (xmin) and simply overlap.
    epoch_info = (
        _extract_epoch_info(
            eeg_struct=eeg_struct,
            sampling_frequency=sampling_frequency,
            number_of_points=number_of_points,
            number_of_trials=number_of_trials,
            epoch_start_time=epoch_start_time,
        )
        if is_epoched
        else None
    )
    if is_epoched:
        epoch_onsets = [info["onset"] for info in epoch_info] if epoch_info is not None else [
            epoch_start_time
        ] * number_of_trials
    else:
        epoch_onsets = [0.0]

    # One SpikeInterface segment per epoch; each segment is (n_points, n_channels) in microvolts.
    traces_per_segment = [traces[:, :, trial_index].T.astype("float32") for trial_index in range(number_of_trials)]
    t_starts = epoch_onsets if is_epoched else None

    channel_names, locations = _extract_channel_info(eeg_struct=eeg_struct, number_of_channels=number_of_channels)
    events = _extract_events(
        eeg_struct=eeg_struct,
        sampling_frequency=sampling_frequency,
        number_of_points=number_of_points,
        number_of_trials=number_of_trials,
        epoch_onsets=epoch_onsets,
    )

    epochs = []
    if is_epoched:
        epoch_duration = number_of_points / sampling_frequency
        for index, onset in enumerate(epoch_onsets):
            label = epoch_info[index]["label"] if epoch_info is not None else ""
            epochs.append(dict(epoch_index=index, start_time=onset, stop_time=onset + epoch_duration, label=label))

    recording = NumpyRecording(
        traces_list=traces_per_segment,
        sampling_frequency=sampling_frequency,
        channel_ids=channel_names,
        t_starts=t_starts,
    )
    # Gain of 1.0 with the data already in microvolts lets the ecephys writer scale microvolts to volts.
    recording.set_channel_gains(gains=np.ones(number_of_channels))
    recording.set_channel_offsets(offsets=np.zeros(number_of_channels))
    recording.set_property(key="channel_name", values=np.asarray(channel_names))
    if locations is not None:
        recording.set_property(key="location", values=np.asarray(locations, dtype="float64"))

    subject_metadata = _extract_subject_metadata(eeg_struct=eeg_struct)

    return recording, events, subject_metadata, epochs


class EEGLABRecordingInterface(BaseRecordingExtractorInterface):
    """
    Data interface for converting EEGLAB (.set / .fdt) data to NWB.

    Reads EEGLAB datasets directly (without MNE), supporting both layouts: a self-contained ``.set``
    file with inline data, and a ``.set`` file paired with an external ``.fdt`` binary. The ``.set``
    structure is read with pymatreader and the ``.fdt`` binary with NumPy.

    Continuous datasets are written as a single ``ElectricalSeries``. Epoched datasets
    (``EEG.trials > 1``) are written as one ``ElectricalSeries`` per epoch into the same NWB file
    (named ``ElectricalSeriesEpoch{index}``), each placed at the epoch's real time in the source
    recording (recovered from ``EEG.urevent``) so they share one session timeline. The per-epoch
    boundaries and time-locking event types are written to the NWB ``epochs`` table. In both cases
    ``EEG.event`` markers are written to a ``TimeIntervals`` table named ``"events"`` (disable with
    ``write_events=False``; disable the epochs table with ``write_epochs=False``).
    """

    display_name = "EEGLAB Recording"
    keywords = BaseRecordingExtractorInterface.keywords + ("EEG", "EEGLAB")
    associated_suffixes = (".set", ".fdt")
    info = "Interface for EEGLAB (.set / .fdt) recording data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the EEGLAB .set file."
        return source_schema

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.core import NumpyRecording

        return NumpyRecording

    def _initialize_extractor(self, interface_kwargs: dict):
        """Read the EEGLAB file into a NumpyRecording, caching events, subject metadata, and epochs."""
        recording, events, subject_metadata, epochs = _read_eeglab_recording(file_path=interface_kwargs["file_path"])
        self._eeglab_events = events
        self._eeglab_subject_metadata = subject_metadata
        self._eeglab_epochs = epochs
        return recording

    def __init__(
        self,
        file_path: FilePath,
        *,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
    ):
        """
        Load and prepare data for EEGLAB.

        Parameters
        ----------
        file_path : str or Path
            Path to the EEGLAB ``.set`` file. If the dataset stores its data in a separate ``.fdt``
            file, that file must be located next to the ``.set`` (the standard EEGLAB layout).
        verbose : bool, default: False
            Allows verbose.
        es_key : str, default: "ElectricalSeries"
            Key for the ElectricalSeries metadata.
        """
        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key)

    @property
    def is_epoched(self) -> bool:
        """Whether the EEGLAB dataset is epoched (``EEG.trials > 1``)."""
        return self.recording_extractor.get_num_segments() > 1

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        if self.es_key is not None:
            metadata["Ecephys"][self.es_key]["description"] = "EEG data imported from an EEGLAB dataset."

        # Populate Subject when the .set carries any real subject info, filling the schema-required
        # fields (subject_id, sex, species) with defaults so the metadata stays valid (cf. Inscopix).
        subject_metadata = dict(getattr(self, "_eeglab_subject_metadata", dict()))
        if subject_metadata:
            subject_metadata.setdefault("subject_id", "Unknown")
            subject_metadata.setdefault("species", "Unknown species")
            subject_metadata.setdefault("sex", "U")
            if "Subject" in metadata:
                metadata["Subject"].update(subject_metadata)
            else:
                metadata["Subject"] = subject_metadata

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        write_events: bool = True,
        write_epochs: bool = True,
        **conversion_options,
    ):
        """
        Add the EEGLAB data to an NWBFile.

        Continuous datasets are written as one ``ElectricalSeries``. Epoched datasets are written as one
        ``ElectricalSeries`` per epoch (named ``ElectricalSeriesEpoch{index}``) sharing a single
        electrodes table, each placed at the epoch's real time on the shared session timeline.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile to add the data to.
        metadata : dict, optional
            Metadata dictionary for constructing the NWBFile.
        write_events : bool, default: True
            If True, the EEGLAB ``EEG.event`` markers are written to a ``TimeIntervals`` table named
            ``"events"``.
        write_epochs : bool, default: True
            If True and the dataset is epoched, the per-epoch boundaries (and time-locking event types)
            are written to the NWB ``epochs`` table.
        **conversion_options
            Additional keyword arguments forwarded to the recording ``add_to_nwbfile`` method.
        """
        metadata = metadata if metadata is not None else self.get_metadata()

        # For epoched data the recording is multi-segment, so the ecephys writer emits one
        # ElectricalSeries per epoch and appends the segment index to the series name. Marking the name
        # with "Epoch" lets downstream consumers recognize the epoch split (vs. e.g. an offset split).
        if self.is_epoched and self.es_key is not None:
            metadata = copy.deepcopy(metadata)
            series_metadata = metadata["Ecephys"].setdefault(self.es_key, dict())
            series_metadata["name"] = f"{series_metadata.get('name', self.es_key)}Epoch"

        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **conversion_options)

        if write_events and getattr(self, "_eeglab_events", None):
            self._add_events_to_nwbfile(nwbfile=nwbfile)
        if write_epochs and getattr(self, "_eeglab_epochs", None):
            self._add_epochs_to_nwbfile(nwbfile=nwbfile)

    def _add_events_to_nwbfile(self, nwbfile: NWBFile):
        from pynwb.epoch import TimeIntervals

        events_table = TimeIntervals(
            name="events",
            description="Events imported from the EEGLAB EEG.event structure.",
        )
        events_table.add_column(name="label", description="The EEGLAB event type.")
        for event in self._eeglab_events:
            events_table.add_row(start_time=event["start_time"], stop_time=event["stop_time"], label=event["label"])
        nwbfile.add_time_intervals(events_table)

    def _add_epochs_to_nwbfile(self, nwbfile: NWBFile):
        """Write per-epoch boundaries (real session times) and locking-event types to the epochs table."""
        if nwbfile.epochs is None or "epoch_index" not in nwbfile.epochs.colnames:
            nwbfile.add_epoch_column(name="epoch_index", description="0-based index of the epoch (EEGLAB trial).")
            nwbfile.add_epoch_column(name="label", description="Type of the time-locking event for the epoch.")
        for epoch in self._eeglab_epochs:
            nwbfile.add_epoch(
                start_time=epoch["start_time"],
                stop_time=epoch["stop_time"],
                epoch_index=epoch["epoch_index"],
                label=epoch["label"],
            )
