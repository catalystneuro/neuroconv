from datetime import datetime, timedelta
from decimal import Decimal
from itertools import accumulate
from pathlib import Path

import numpy as np


def _read_annotations(file_path: Path) -> tuple[datetime, np.ndarray, np.ndarray, np.ndarray]:
    timestamps = []
    durations = []
    annotations = []
    recording_offset = Decimal(0)

    with file_path.open("rb") as file:
        fixed_header = file.read(256)
        version = fixed_header[:8]
        if version == b"0       ":
            sample_width, annotation_label = 2, b"EDF Annotations"
        elif version == b"\xffBIOSEMI":
            sample_width, annotation_label = 3, b"BDF Annotations"
        else:
            raise ValueError(f"Unrecognized EDF or BDF version in '{file_path}'.")

        header_size = int(fixed_header[184:192])
        record_count = int(fixed_header[236:244])
        signal_count = int(fixed_header[252:256])
        signal_headers = file.read(signal_count * 256)

        # Signal fields are stored field-major, with one label and sample count per signal.
        labels = [signal_headers[index : index + 16].rstrip(b" ") for index in range(0, 16 * signal_count, 16)]
        sample_counts = signal_headers[216 * signal_count : 224 * signal_count]
        signal_sizes = [
            int(sample_counts[index : index + 8]) * sample_width for index in range(0, len(sample_counts), 8)
        ]
        annotation_signals = [
            (offset, size)
            for label, offset, size in zip(labels, accumulate(signal_sizes, initial=0), signal_sizes)
            if label == annotation_label
        ]
        record_size = sum(signal_sizes)
        if annotation_signals and record_count == -1:
            record_count = (file.seek(0, 2) - header_size) // record_size

        if annotation_signals:
            for record_index in range(record_count):
                record_offset = header_size + record_index * record_size
                for signal_index, (offset, size) in enumerate(annotation_signals):
                    file.seek(record_offset + offset)
                    buffer = file.read(size)
                    if len(buffer) != size:
                        raise ValueError(f"Truncated annotation signal in record {record_index} of '{file_path}'.")
                    for list_index, annotation_list in enumerate(buffer.rstrip(b"\x00").split(b"\x00")):
                        if not annotation_list:
                            continue
                        timing, *texts = annotation_list.split(b"\x14")
                        onset_bytes, _, duration_bytes = timing.partition(b"\x15")
                        onset = Decimal(onset_bytes.decode("ascii"))
                        # The first list is relative to the header's whole second. Its first,
                        # empty annotation supplies time zero for the first data record.
                        if record_index == signal_index == list_index == 0:
                            recording_offset = onset
                        duration = float(duration_bytes) if duration_bytes else np.nan
                        for text in texts:
                            if text:
                                timestamps.append(float(onset - recording_offset))
                                durations.append(duration)
                                annotations.append(text.decode("utf-8"))

    start_time = _read_start_time(fixed_header) + timedelta(seconds=float(recording_offset))
    return start_time, np.asarray(timestamps), np.asarray(durations), np.asarray(annotations, dtype=str)


def _read_start_time(fixed_header: bytes) -> datetime:
    date = fixed_header[168:176].decode("ascii")
    time = datetime.strptime(fixed_header[176:184].decode("ascii"), "%H.%M.%S").time()
    if date.endswith(".yy"):
        recording_date = fixed_header[88:168].split()[1].decode("ascii")
        return datetime.combine(datetime.strptime(recording_date, "%d-%b-%Y").date(), time)

    day, month, year = map(int, date.split("."))
    year += 1900 if year >= 85 else 2000
    return datetime.combine(datetime(year, month, day).date(), time)
