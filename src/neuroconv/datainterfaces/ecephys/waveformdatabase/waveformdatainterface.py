import warnings
from datetime import date, datetime, time
from typing import Any, Dict, Optional

import wfdb
from pynwb import NWBFile, TimeSeries
from wfdb import MultiRecord

from neuroconv.basedatainterface import BaseDataInterface


class WFDBDataInterface(BaseDataInterface):
    """Enhanced data interface for WFDB (Waveform Database) files - extracts only actual WFDB data."""

    display_name = "WFDB Data"
    associated_suffixes = (".dat", ".hea", ".atr")
    info = "Interface for WFDB (Waveform Database) physiological signal data."

    def __init__(self, file_path: str, verbose: bool = False):
        super().__init__(file_path=file_path, verbose=verbose)
        self.file_path = file_path
        self._record = None
        self._is_multisegment = False
        self._segments = []
        
        import wfdb
        from wfdb import MultiRecord

        try:
            record = wfdb.rdrecord(self.file_path, m2s=False, physical=True)
            if isinstance(record, MultiRecord):
                self._is_multisegment = True
                self._segments = record.segments
        except Exception as e:
            warnings.warn(f"Could not check for multi-segment: {e}")

    def _load_record(self) -> wfdb.Record:
        if self._record is None:
            if self._is_multisegment:
                self._record = wfdb.rdrecord(self.file_path, m2s=False, physical=True)
            else:
                self._record = wfdb.rdrecord(self.file_path, physical=True)
        return self._record

    def _get_channel_sampling_rates(self, record) -> list[Optional[float]]:
        base_fs = getattr(record, "fs", None)
        n_channels = getattr(record, "n_sig", 0)
        if not base_fs or n_channels == 0:
            return [None] * n_channels

        base_fs = float(base_fs)
        if hasattr(record, "samps_per_frame") and record.samps_per_frame:
            return [
                float(base_fs * record.samps_per_frame[i]) if i < len(record.samps_per_frame) else base_fs
                for i in range(n_channels)
            ]
        else:
            return [base_fs] * n_channels

    def _extract_channel_info(self, record_or_segment) -> dict[str, list]:
        if not hasattr(record_or_segment, "p_signal") or record_or_segment.p_signal is None:
            return {"channel_names": [], "units": [], "sampling_rates": []}

        n_channels = getattr(record_or_segment, "n_sig", 0)

        channel_names = []
        sig_name = getattr(record_or_segment, "sig_name", [])
        for i in range(n_channels):
            name = sig_name[i] if i < len(sig_name) and sig_name[i] else f"Channel_{i}"
            channel_names.append(str(name))

        units = []
        record_units = getattr(record_or_segment, "units", [])
        for i in range(n_channels):
            unit = record_units[i] if i < len(record_units) and record_units[i] else "unknown"
            units.append(str(unit))

        sampling_rates = self._get_channel_sampling_rates(record_or_segment)

        return {"channel_names": channel_names, "units": units, "sampling_rates": sampling_rates}

    def get_session_start_time(self) -> Optional[datetime]:
        record = self._load_record()
        base_date = getattr(record, "base_date", None)
        base_time = getattr(record, "base_time", None)

        if base_date and base_time:
            return datetime.combine(base_date, base_time)
        if base_date:
            return datetime.combine(base_date, time(0, 0, 0))
        if base_time:
            return datetime.combine(date.today(), base_time)

        return None

    def get_channel_info(self) -> dict[str, list]:
        record = self._load_record()
        return self._extract_channel_info(record)

    def get_channel_info_from_segment(self, segment) -> dict[str, list]:
        return self._extract_channel_info(segment)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: Optional[Dict] = None):
        record = self._load_record()

        if self._is_multisegment:
            for seg_idx, segment in enumerate(record.segments):
                if not hasattr(segment, "p_signal") or segment.p_signal is None:
                    continue
                data = segment.p_signal
                _, n_channels = data.shape

                channel_info = self.get_channel_info_from_segment(segment)
                for ch_idx in range(n_channels):
                    ts = TimeSeries(
                        name=f"{channel_info['channel_names'][ch_idx]}_segment{seg_idx}",
                        data=data[:, ch_idx],
                        unit=channel_info["units"][ch_idx],
                        rate=channel_info["sampling_rates"][ch_idx],
                        starting_time=0.0,
                    )
                    nwbfile.add_acquisition(ts)
        else:
            if not hasattr(record, "p_signal") or record.p_signal is None:
                return
            data = record.p_signal
            _, n_channels = data.shape

            channel_info = self.get_channel_info()
            for i in range(n_channels):
                ts = TimeSeries(
                    name=channel_info["channel_names"][i],
                    data=data[:, i],
                    unit=channel_info["units"][i],
                    rate=channel_info["sampling_rates"][i],
                    starting_time=0.0,
                )
                nwbfile.add_acquisition(ts)

    def _get_signal_name(self, record, channel_index: int) -> str:
        if (
            hasattr(record, "sig_name")
            and record.sig_name
            and channel_index < len(record.sig_name)
            and record.sig_name[channel_index] is not None
        ):
            return str(record.sig_name[channel_index])
        return f"Channel_{channel_index}"

    def get_metadata(self) -> dict[str, Any]:
        record = self._load_record()
        metadata = super().get_metadata()

        if hasattr(record, "record_name"):
            metadata["NWBFile"]["session_id"] = str(record.record_name)

        session_start_time = self.get_session_start_time()
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        description_parts = []
        if hasattr(record, "n_sig"):
            description_parts.append(f"{record.n_sig} channel recording")

        rates = self._get_channel_sampling_rates(record)
        unique_rates = sorted(set(r for r in rates if r is not None))
        if len(unique_rates) == 1:
            description_parts.append(f"sampled at {unique_rates[0]} Hz")
        elif len(unique_rates) > 1:
            rates_str = ", ".join(f"{r} Hz" for r in unique_rates)
            description_parts.append(f"multiple sampling rates: {rates_str}")

        if hasattr(record, "sig_len") and hasattr(record, "fs") and record.fs:
            duration_sec = record.sig_len / record.fs
            description_parts.append(f"duration {duration_sec:.2f} seconds")
        elif hasattr(record, "sig_len"):
            description_parts.append(f"{record.sig_len} samples")

        if description_parts:
            metadata["NWBFile"]["session_description"] = "; ".join(description_parts)

        exp_desc_parts = []
        if hasattr(record, "fmt"):
            fmt_list = record.fmt if isinstance(record.fmt, list) else [record.fmt]
            exp_desc_parts.append(f"Data formats: {', '.join(fmt_list)}")
        if hasattr(record, "file_name"):
            file_list = record.file_name if isinstance(record.file_name, list) else [record.file_name]
            exp_desc_parts.append(f"Source files: {', '.join(file_list)}")

        if exp_desc_parts:
            metadata["NWBFile"]["experiment_description"] = "; ".join(exp_desc_parts)

        if hasattr(record, "comments"):
            if isinstance(record.comments, list):
                valid_comments = [c for c in record.comments if c and str(c).strip()]
                if valid_comments:
                    metadata["NWBFile"]["notes"] = "; ".join(valid_comments)
            elif str(record.comments).strip():
                metadata["NWBFile"]["notes"] = str(record.comments)

        data_collection_notes = []
        if hasattr(record, "adc_gain"):
            data_collection_notes.append(f"ADC gains: {record.adc_gain}")
        if hasattr(record, "baseline"):
            data_collection_notes.append(f"Baselines: {record.baseline}")
        if hasattr(record, "adc_res"):
            data_collection_notes.append(f"ADC resolution: {record.adc_res}")
        if hasattr(record, "checksum"):
            data_collection_notes.append(f"Checksums: {record.checksum}")

        if data_collection_notes:
            metadata["NWBFile"]["data_collection"] = "; ".join(data_collection_notes)

        return metadata
