import warnings
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import numpy as np
from pydantic import ConfigDict, DirectoryPath, validate_call
from pynwb import NWBFile

from .spikeglxnidqeventsinterface import (
    _NEO_ADDRESSING_DEPRECATION,
    _SpikeGLXNIDQEventsInterface,
)
from ....basedatainterface import BaseDataInterface
from ....tools.signal_processing import get_rising_frames_from_ttl
from ....utils import (
    DeepDict,
    get_json_schema_from_method_signature,
    to_camel_case,
)


class SpikeGLXNIDQInterface(BaseDataInterface):
    """Primary data interface class for converting the high-pass (ap) SpikeGLX format."""

    display_name = "NIDQ Recording"
    keywords = ("Neuropixels", "nidq", "NIDQ", "SpikeGLX")
    associated_suffixes = (".nidq", ".meta", ".bin")
    info = "Interface for NIDQ board recording data."

    # Defaults for the digital half, as class attributes rather than only as __init__ assignments.
    # MockSpikeGLXNIDQInterface substitutes a synthetic recording by skipping this __init__ and setting
    # the handful of attributes it needs, so anything __init__ alone establishes is absent there. These
    # describe a board with no digital half, which is what such a subclass has.
    _uses_legacy_digital_path = False
    _digital_channel_groups: dict = {}
    _legacy_events_routing: dict = {}
    _events_interface = None

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=[])
        source_schema["properties"]["folder_path"]["description"] = "Path to the folder containing the .nidq.bin file."
        source_schema["properties"]["metadata_key"]["description"] = (
            "Key used to organize metadata in the metadata dictionary. This is especially useful "
            "when multiple NIDQ interfaces are used in the same conversion. The metadata_key is used "
            "to organize TimeSeries and Events metadata."
        )
        return source_schema

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __init__(
        self,
        folder_path: DirectoryPath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        verbose: bool = False,
        metadata_key: str = "spikeglx_nidq",
        analog_channel_groups: dict[str, dict] | None = None,
        digital_channel_groups: dict[str, dict] | None = None,
        detection_configuration: dict | None = None,
    ):
        """
        Read analog and digital channel data from the NIDQ board for the SpikeGLX recording.

        The NIDQ stream records both analog and digital (usually non-neural) signals.
        XD channels are converted to events directly.
        XA and MA channels can be organized into separate TimeSeries using analog_channel_groups.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing the .nidq.bin file.
        verbose : bool, default: False
            Whether to output verbose text.
        metadata_key : str, default: "spikeglx_nidq"
            Key used to organize metadata in the metadata dictionary. This is especially useful
            when multiple NIDQ interfaces are used in the same conversion. The metadata_key is used
            to organize TimeSeries and Events metadata. It addresses the entries; the written objects'
            names are their ``name`` fields.
        analog_channel_groups : dict[str, dict], optional
            Dictionary mapping group names to analog channel configurations.
            Each group specifies which channels to include and will be written as a separate
            TimeSeries in the NWB file.
            If None (default), all analog channels are written as a single TimeSeries.
            If empty dict {}, no analog channels are written.

            Channels are named as the board names them (``"XA0"``), which is what ``get_channel_names``
            returns. neo's stream-qualified ids (``"nidq#XA0"``) are also accepted, deprecated and
            removed on or after August 2027.

            Structure:
                {
                    "group_key": {
                        "channels": ["channel_name_1", "channel_name_2", ...],
                    },
                }

            Example:
                {
                    "audio": {
                        "channels": ["XA0"],
                    },
                    "accel": {
                        "channels": ["XA3", "XA4", "XA5"],
                    },
                }
        digital_channel_groups : dict[str, dict], optional
            **Deprecated.** Superseded by ``detection_configuration``, which reaches the same lines
            through the shared signal-encoded grammar and writes native ``pynwb.event.EventsTable``
            objects into ``nwbfile.events`` instead of ``ndx-events`` ``LabeledEvents`` objects into
            ``acquisition``. Passing it keeps the old behaviour and raises a ``FutureWarning``.

            Dictionary mapping group names to digital channel configurations.
            Each group specifies which channels to include and their label mappings.
            If empty dict {}, no digital channels are written.

            Only single-channel groups are supported (each group maps to one LabeledEvents object).


            Structure:
                {
                    "group_key": {
                        "channels": {
                            "channel_id": {"labels_map": {0: "label_a", 1: "label_b"}},
                        },
                    },
                }

            Example:
                {
                    "camera": {
                        "channels": {
                            "nidq#XD0": {"labels_map": {0: "exposure_end", 1: "frame_start"}},
                        },
                    },
                    "lick": {
                        "channels": {
                            "nidq#XD1": {"labels_map": {0: "no_lick", 1: "lick_detected"}},
                        },
                    },
                }
        detection_configuration : dict, optional
            Which NIDQ signals to derive events from and how, keyed by the board's own handle
            (``"XD0"`` for a digital word, ``"XA1"`` for an analog channel). SpikeGLX saves its digital
            lines packed into one integer word per channel, so a line is reached by naming the word and
            the bit: ``{"XD0": [{"signal_conditioning": {"bits": [0]}, "detection": "high_period"}]}``.
            An analog channel is cut into events with ``{"binarize": c}`` plus an
            ``event_name``. If None (default), every line of every digital word is read as a
            ``high_period`` and the analog channels are skipped.

            Mutually exclusive with the deprecated ``digital_channel_groups``.

        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "verbose",
                "metadata_key",
                "analog_channel_groups",
                "digital_channel_groups",
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
                f"Passing arguments positionally to SpikeGLXNIDQInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            verbose = positional_values.get("verbose", verbose)
            metadata_key = positional_values.get("metadata_key", metadata_key)
            analog_channel_groups = positional_values.get("analog_channel_groups", analog_channel_groups)
            digital_channel_groups = positional_values.get("digital_channel_groups", digital_channel_groups)

        self.folder_path = Path(folder_path)

        from spikeinterface.extractors.extractor_classes import (
            SpikeGLXRecordingExtractor,
        )

        self.recording_extractor = SpikeGLXRecordingExtractor(
            folder_path=self.folder_path,
            stream_id="nidq",
            all_annotations=True,
        )

        channel_ids = self.recording_extractor.get_channel_ids()
        # analog_channel_signatures are "XA" and "MA"
        self.analog_channel_ids = [ch for ch in channel_ids if "XA" in ch or "MA" in ch]
        self.has_analog_channels = len(self.analog_channel_ids) > 0
        self.has_digital_channels = len(self.analog_channel_ids) < len(channel_ids)

        # SpikeGLX groups NIDQ channels into four categories, {MN, MA, XA, XD}, and this interface covers
        # three of them: XA/MA become TimeSeries and XD becomes events. MN is multiplexed *neural* data
        # and is not written at all. The reason is lack of data rather than a decision that it does not
        # belong here: MN needs a Whisper multiplexer and no recording containing one was available, so
        # the right output shape was never settled. Say so rather than dropping the channel in silence,
        # since a missing channel is otherwise only discovered by noticing its absence from the file.
        unconverted_channel_ids = [ch for ch in channel_ids if not any(kind in ch for kind in ("XA", "MA", "XD"))]
        if unconverted_channel_ids:
            warnings.warn(
                f"The following NIDQ channels are not converted and will be absent from the NWB file: "
                f"{list(unconverted_channel_ids)}. This interface writes the analog channels (XA, MA) as "
                "TimeSeries and the digital word (XD) as events. The remaining category, multiplexed "
                "neural channels (MN), is unsupported only because no recording containing one was "
                "available when this was written, so there was nothing to build or test against. If you "
                "have such a file, please open an issue at "
                "https://github.com/catalystneuro/neuroconv/issues and support can be added.",
                UserWarning,
                stacklevel=2,
            )

        if digital_channel_groups is not None and detection_configuration is not None:
            raise ValueError(
                "Pass either detection_configuration or the deprecated digital_channel_groups, not both. "
                "They are two spellings of the same thing and write different NWB objects."
            )
        # The deprecated path is opt-in from here on: it is selected only by passing
        # digital_channel_groups, so the default conversion takes the events interface below.
        self._uses_legacy_digital_path = digital_channel_groups is not None
        if self._uses_legacy_digital_path:
            warnings.warn(
                "digital_channel_groups is deprecated and will be removed on or after August 2027. "
                "Use detection_configuration instead, which reaches the same lines through the shared "
                "signal-encoded grammar. Note that the events are now written as a pynwb EventsTable "
                "into nwbfile.events rather than as an ndx-events LabeledEvents into acquisition; the "
                "group still becomes one object with one row per edge, and labels_map still names the "
                "two edges, now through the table's event_type column.",
                FutureWarning,
                stacklevel=2,
            )

        if self.has_digital_channels and self._uses_legacy_digital_path:
            # Only to validate the deprecated argument (which channel names are legal, and that a
            # labels_map covers the values actually present). The write itself no longer goes through it.
            from spikeinterface.extractors.extractor_classes import (
                SpikeGLXEventExtractor,
            )

            self.event_extractor = SpikeGLXEventExtractor(folder_path=self.folder_path)

        self.metadata_key = metadata_key

        # Resolve to defaults if None, then validate
        self._analog_channel_groups = (
            self._normalize_analog_channel_groups(analog_channel_groups)
            if analog_channel_groups is not None
            else self._get_default_analog_channel_groups()
        )
        self._validate_analog_channel_groups()

        self._digital_channel_groups = digital_channel_groups if self._uses_legacy_digital_path else {}
        if self._uses_legacy_digital_path:
            self._validate_digital_channel_groups()

        super().__init__(
            verbose=verbose,
            folder_path=self.folder_path,
        )

        signal_info_key = (0, "nidq")  # Key format is (segment_index, stream_id)
        self._signals_info_dict = self.recording_extractor.neo_reader.signals_info_dict[signal_info_key]
        self.meta = self._signals_info_dict["meta"]

        # The events half of the board. Private and constructed here rather than by the user: NIDQ analog
        # and digital signals share one board and one clock, so the board keeps one public interface and
        # this object is the part of it that owns the EventsTable writer. It opens its own reader on the
        # same file rather than borrowing this one, for the reasons its own __init__ gives; both readers
        # see one immutable file and therefore one clock.
        # A deprecated digital_channel_groups is translated into the new grammar rather than writing
        # through a second path: each group becomes a rising and a falling spec on its line, routed into
        # one table, which is structurally what its LabeledEvents was. `None` is not translated, since
        # the new default is the better reading and nobody chose the old auto-generated names.
        self._legacy_events_routing = {}
        if self._uses_legacy_digital_path:
            detection_configuration, self._legacy_events_routing = self._translate_digital_channel_groups(
                self._digital_channel_groups
            )

        self._events_interface = None
        if self.has_digital_channels and not (self._uses_legacy_digital_path and not self._digital_channel_groups):
            self._events_interface = _SpikeGLXNIDQEventsInterface(
                folder_path=self.folder_path,
                detection_configuration=detection_configuration,
                metadata_key=self.metadata_key,
                verbose=verbose,
            )

    def _translate_digital_channel_groups(self, digital_channel_groups: dict) -> tuple[dict, dict]:
        """Map the deprecated argument onto ``detection_configuration``, plus the table routing it implies.

        A group named one line and gave a ``labels_map`` naming the two states it takes. The line's own
        values are what the old writer recorded, so ``labels_map[1]`` labels the rising edge and
        ``labels_map[0]`` the falling one (its labels sorted ``OFF`` before ``ON``). Both readings of the
        same line become two specs, and the returned routing sends them into a single table, which is the
        one ``LabeledEvents`` the group used to produce.

        A label names a state inside one group's table, so two groups may legitimately give theirs the
        same one, the way two ``LabeledEvents`` could each carry ``["off", "on"]``. An identifier is
        global, and ``event_name`` is both in the shared grammar, so the identifier is qualified by the
        group here and :meth:`_rewrite_legacy_events_metadata` puts the bare label back as what the
        ``event_type`` column shows. The routing carries both, keyed by identifier.
        """
        word_handles = [str(ch).split("#")[-1] for ch in self.recording_extractor.get_channel_ids() if "XD" in str(ch)]
        word_handle = word_handles[0]

        detection_configuration: dict[str, list] = {}
        routing: dict[str, dict] = {}
        for group_key, group_config in digital_channel_groups.items():
            channel_id, channel_config = next(iter(group_config["channels"].items()))
            line_name = str(channel_id).split("#")[-1]  # the reader's per-line name, e.g. "XD5"
            line = int(line_name[2:])
            labels_map = channel_config["labels_map"]
            rising_label = str(labels_map.get(1, f"{group_key}_on"))
            falling_label = str(labels_map.get(0, f"{group_key}_off"))
            rising_id = f"{group_key}_{rising_label}"
            falling_id = f"{group_key}_{falling_label}"
            detection_configuration.setdefault(word_handle, []).extend(
                [
                    {"signal_conditioning": {"bits": [line]}, "detection": "rising", "event_name": rising_id},
                    {"signal_conditioning": {"bits": [line]}, "detection": "falling", "event_name": falling_id},
                ]
            )
            routing[group_key] = {rising_id: rising_label, falling_id: falling_label}
        return detection_configuration, routing

    def _rewrite_legacy_events_metadata(self, metadata: dict) -> dict:
        """Move a deprecated-shape ``Events`` block onto the shape the events writer reads.

        The user edits ``metadata["Events"][metadata_key][group_key]`` with ``name``, ``description`` and
        ``meanings``, because that is what ``get_metadata`` handed them. Those edits arrive here rather
        than at ``get_metadata``, which is why the translation happens at write time.

        This deliberately does not propagate the metadata as the user wrote it, which is otherwise the
        rule. It is a temporary exception for the sake of backwards compatibility, and it goes when
        ``digital_channel_groups`` does.
        """
        metadata = deepcopy(dict(metadata))
        metadata["Events"] = dict(metadata.get("Events", {}))
        legacy_block = dict(metadata["Events"].pop(self.metadata_key, {}))
        default_metadata = self._get_default_events_metadata()

        event_tables = dict(metadata["Events"].get("EventTables", {}))
        event_types = {}
        for group_key, labels_by_event_type_source_id in self._legacy_events_routing.items():
            group_metadata = legacy_block.get(group_key, {})
            defaults = default_metadata.get(group_key, {})
            event_tables[group_key] = {
                "table_name": group_metadata.get("name", defaults.get("name", to_camel_case(group_key))),
                "description": group_metadata.get("description", defaults.get("description", "")),
            }
            # `meanings` was appended to the description as a stopgap; it has a real home now, as the
            # per-type description that the writer turns into a MeaningsTable.
            meanings = group_metadata.get("meanings", {})
            for event_type_source_id, label in labels_by_event_type_source_id.items():
                entry = {"event_name": label, "table_metadata_key": group_key}
                if label in meanings:
                    entry["event_description"] = meanings[label]
                event_types[event_type_source_id] = entry

        metadata["Events"]["EventTables"] = event_tables
        metadata["Events"][self.metadata_key] = {"event_types": event_types}
        return metadata

    def _resolve_channel_id(self, channel_name: str) -> str:
        """Map either spelling of a channel onto the reader's own id, which is what reads a trace.

        The board's name (``XA0``) is what a caller states and what :meth:`get_channel_names` shows;
        neo's stream-qualified id (``nidq#XA0``) is what ``get_traces`` and ``select_channels`` take.
        A name the board does not have comes back unchanged, so the caller's own spelling is what the
        validation below names in its error.
        """
        channel_name = str(channel_name)
        if "#" in channel_name:  # already neo addressing; the caller warns
            return channel_name
        for channel_id in self.recording_extractor.get_channel_ids():
            if str(channel_id).split("#")[-1] == channel_name:
                return str(channel_id)
        return channel_name

    def _normalize_analog_channel_groups(self, analog_channel_groups: dict) -> dict:
        """Rewrite a caller's ``channels`` onto the reader's ids, warning once on neo addressing.

        Everything downstream (validation, ``select_channels``, the group's channel names) works in the
        reader's ids, so the two accepted spellings collapse here and nowhere else.
        """
        normalized = {}
        used_neo_addressing = False
        for group_key, group_config in analog_channel_groups.items():
            if not isinstance(group_config, dict) or "channels" not in group_config:
                normalized[group_key] = group_config  # left for _validate_analog_channel_groups to reject
                continue
            channels = [str(channel_name) for channel_name in group_config["channels"]]
            used_neo_addressing |= any("#" in channel_name for channel_name in channels)
            normalized[group_key] = {
                **group_config,
                "channels": [self._resolve_channel_id(channel_name) for channel_name in channels],
            }
        if used_neo_addressing:
            warnings.warn(_NEO_ADDRESSING_DEPRECATION, FutureWarning, stacklevel=4)
        return normalized

    def _validate_analog_channel_groups(self) -> None:
        """Validate analog_channel_groups structure and channel IDs."""
        all_analog_ids_set = set(self.analog_channel_ids)
        for group_key, group_config in self._analog_channel_groups.items():
            if "channels" not in group_config:
                raise ValueError(f"Analog group '{group_key}' missing required 'channels' field.")

            channels = group_config["channels"]
            invalid_channels = set(channels) - all_analog_ids_set
            if invalid_channels:
                raise ValueError(
                    f"Invalid channels in group '{group_key}': {invalid_channels}. "
                    f"Available analog channels: {[name.split('#')[-1] for name in self.analog_channel_ids]}"
                )

    def _validate_digital_channel_groups(self) -> None:
        """Validate digital_channel_groups structure, channel IDs, and labels_map."""
        if not self.has_digital_channels:
            return

        all_digital_ids = set(self.event_extractor.channel_ids)
        for group_key, group_config in self._digital_channel_groups.items():
            if "channels" not in group_config:
                raise ValueError(f"Digital group '{group_key}' missing required 'channels' field.")

            channels_config = group_config["channels"]

            # Validate single-channel groups (temporary limitation)
            if len(channels_config) != 1:
                raise ValueError(
                    f"Digital group '{group_key}' has {len(channels_config)} channels. "
                    f"Currently only single-channel groups are supported. "
                    f"Multi-channel groups will be supported when ndx-events EventsTable "
                    f"is integrated into NWB core."
                )

            # Validate each channel in the group
            for channel_id, channel_config in channels_config.items():
                if channel_id not in all_digital_ids:
                    available_channels = sorted([str(ch) for ch in all_digital_ids])
                    raise ValueError(
                        f"Invalid digital channel '{channel_id}' in group '{group_key}'. "
                        f"Available digital channels: {available_channels}"
                    )
                if "labels_map" not in channel_config:
                    raise ValueError(
                        f"Channel '{channel_id}' in group '{group_key}' "
                        f"missing required 'labels_map' field. "
                        f"Example: {{'{channel_id}': {{'labels_map': {{0: 'off', 1: 'on'}}}}}}"
                    )

                # Validate labels_map covers all unique values from extractor
                labels_map = channel_config["labels_map"]
                events_structure = self.event_extractor.get_events(channel_id=channel_id)
                raw_labels = events_structure["label"]
                if raw_labels.size > 0:
                    num_unique_values = len(np.unique(raw_labels))
                    expected_keys = set(range(num_unique_values))
                    provided_keys = set(labels_map.keys())
                    if provided_keys != expected_keys:
                        example_labels = {i: f"label_{i}" for i in range(num_unique_values)}
                        raise ValueError(
                            f"Incomplete labels_map for channel '{channel_id}' in group '{group_key}'. "
                            f"Expected keys {expected_keys}, got {provided_keys}. "
                            f"labels_map must cover all {num_unique_values} unique values from the extractor. "
                            f"Example: {example_labels}"
                        )

    def _get_default_analog_channel_groups(self) -> dict:
        """
        Return default analog channel groups configuration.

        Creates a single group with all analog channels.
        Used when analog_channel_groups is None (backward compatibility).

        Returns
        -------
        dict
            Dictionary with single "nidq_analog" group containing all analog channels.
        """
        if not self.has_analog_channels:
            return {}

        return {
            "nidq_analog": {
                "channels": list(self.analog_channel_ids),
            }
        }

    def _get_default_events_metadata(self) -> dict:
        """
        Returns default metadata for digital channel events.

        Single source of truth for default digital channel event metadata.
        Each call returns a new instance to prevent accidental mutation of global state.

        Returns
        -------
        dict
            Dictionary mapping group keys to their NWB metadata (name, description).
        """
        default_metadata = {}
        for group_key, group_config in self._digital_channel_groups.items():
            channels_config = group_config["channels"]
            channel_id = next(iter(channels_config.keys()))
            channel_name = channel_id.split("#")[-1]

            # For auto-generated groups (key = channel_id), use legacy naming
            if group_key.startswith("nidq#"):
                default_name = f"EventsNIDQDigitalChannel{channel_name}"
            else:
                default_name = to_camel_case(group_key)

            default_metadata[group_key] = {
                "name": default_name,
                "description": f"On and Off Events from channel {channel_name}",
            }

        return default_metadata

    def _get_default_analog_metadata(self) -> dict:
        """
        Returns default metadata for analog channel TimeSeries.

        Structure depends on whether analog_channel_groups was provided at init.
        If grouping specified, creates metadata for each group.
        Otherwise, returns single TimeSeries configuration for all channels.

        Returns
        -------
        dict
            Dictionary with analog channel TimeSeries metadata.
        """
        metadata = {}

        # Get channel names for descriptions
        channel_names_property = self.recording_extractor.get_property(key="channel_names")

        for group_key, group_config in self._analog_channel_groups.items():
            channels = group_config["channels"]

            # Get names for these specific channels
            if channel_names_property is not None:
                indices = [i for i, ch_id in enumerate(self.analog_channel_ids) if ch_id in channels]
                group_channel_names = [str(channel_names_property[i]) for i in indices]
            else:
                group_channel_names = list(channels)

            # For default group, use legacy naming
            if group_key == "nidq_analog":
                default_name = "TimeSeriesNIDQ"
                description = f"Analog data from the NIDQ board. Channels are {group_channel_names} in that order."
            else:
                default_name = to_camel_case(group_key)
                description = (
                    f"Analog data from NIDQ board, group '{group_key}'. "
                    f"Channels are {group_channel_names} in that order."
                )

            metadata[group_key] = {
                "name": default_name,
                "description": description,
            }

        return metadata

    def _get_session_start_time(self) -> "datetime | None":
        """
        Fetches the session start time from the recording metadata.

        Returns
        -------
        datetime or None
            the session start time in datetime format.
        """

        session_start_time = self.meta.get("fileCreateTime", None)
        if session_start_time.startswith("0000-00-00"):
            # date was removed. This sometimes happens with human data to protect the
            # anonymity of medical patients.
            return
        if session_start_time:
            session_start_time = datetime.fromisoformat(session_start_time)

        return session_start_time

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        session_start_time = self._get_session_start_time()
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Device metadata
        device = dict(
            name="NIDQBoard",
            description="A NIDQ board used in conjunction with SpikeGLX.",
        )

        metadata["Devices"] = {"spikeglx_nidq_device": device}

        # TimeSeries metadata for analog channels
        if self.has_analog_channels:
            metadata["TimeSeries"][self.metadata_key] = self._get_default_analog_metadata()

        # Events metadata for digital channels
        if self._uses_legacy_digital_path:
            # The deprecated argument keeps the deprecated metadata shape, so code that edits
            # metadata["Events"][metadata_key][group_key]["name"] still finds the key it expects.
            # add_to_nwbfile translates it onto the writer's shape.
            if self._digital_channel_groups:
                metadata["Events"][self.metadata_key] = self._get_default_events_metadata()
        elif self._events_interface is not None:
            events_metadata = self._events_interface.get_metadata()["Events"][self.metadata_key]
            # A suppressed events half (detection_configuration={}) seeds nothing rather than an empty block.
            if events_metadata:
                metadata["Events"][self.metadata_key] = events_metadata

        return metadata

    def get_channel_names(self) -> list[str]:
        """
        Get a list of channel names from the recording extractor.

        Returns
        -------
        list of str
            The names of all channels in the NIDQ recording, as the board itself names them
            (``XA0``, ``XD0``), which is what ``~snsChanMap`` and the SpikeGLX user interface show.
        """
        return [str(channel_id).split("#")[-1] for channel_id in self.recording_extractor.get_channel_ids()]

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        stub_test: bool = False,
        iterator_type: str | None = "v2",
        iterator_options: dict | None = None,
        always_write_timestamps: bool = False,
    ):
        """
        Add NIDQ board data to an NWB file, including both analog and digital channels if present.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to which the NIDQ data will be added
        metadata : dict | None, default: None
            Metadata dictionary with device information. If None, uses default metadata
        stub_test : bool, default: False
            If True, only writes a small amount of data for testing
        iterator_type : str | None, default: "v2"
            Type of iterator to use for data streaming
        iterator_options : dict | None, default: None
            Additional options for the iterator
        always_write_timestamps : bool, default: False
            If True, always writes timestamps instead of using sampling rate
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "stub_test",
                "iterator_type",
                "iterator_options",
                "always_write_timestamps",
            ]
            num_positional_args_before_args = 2  # nwbfile, metadata
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"add_to_nwbfile() takes at most {len(parameter_names) + num_positional_args_before_args} positional arguments but "
                    f"{len(args) + num_positional_args_before_args} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to SpikeGLXNIDQInterface.add_to_nwbfile() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            stub_test = positional_values.get("stub_test", stub_test)
            iterator_type = positional_values.get("iterator_type", iterator_type)
            iterator_options = positional_values.get("iterator_options", iterator_options)
            always_write_timestamps = positional_values.get("always_write_timestamps", always_write_timestamps)

        from ....tools.spikeinterface import _stub_recording

        recording = self.recording_extractor
        if stub_test:
            recording = _stub_recording(recording=self.recording_extractor)

        metadata = metadata or self.get_metadata()

        # Add devices from the top-level registry, which is keyed by metadata key. The list shape this
        # interface used to emit is named rather than silently accepted, so a script written against it
        # is told what to change instead of failing on an attribute deep in here.
        device_metadata = metadata.get("Devices", {})
        if isinstance(device_metadata, list):
            raise ValueError(
                "metadata['Devices'] is a list. It is now a registry keyed by metadata key, so this "
                "interface's entry belongs under 'spikeglx_nidq_device': "
                "metadata['Devices'] = {'spikeglx_nidq_device': {'name': ..., 'description': ...}}."
            )
        for device in device_metadata.values():
            if device["name"] not in nwbfile.devices:
                nwbfile.create_device(**device)

        # Add analog and digital channels
        if self.has_analog_channels:
            self._add_analog_channels(
                nwbfile=nwbfile,
                recording=recording,
                iterator_type=iterator_type,
                iterator_options=iterator_options,
                always_write_timestamps=always_write_timestamps,
                metadata=metadata,
            )

        if self._events_interface is not None:
            events_metadata = (
                self._rewrite_legacy_events_metadata(metadata) if self._uses_legacy_digital_path else metadata
            )
            self._events_interface.add_to_nwbfile(nwbfile=nwbfile, metadata=events_metadata)

    def _add_analog_channels(
        self,
        nwbfile: NWBFile,
        recording,  # we pass the recording because it might be stubbed
        iterator_type: str | None,
        iterator_options: dict | None,
        always_write_timestamps: bool,
        metadata: dict,
    ):
        """
        Add analog channels from the NIDQ board to the NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the analog channels to
        recording : BaseRecording
            The recording extractor containing the analog channels
        iterator_type : str | None
            Type of iterator to use for data streaming
        iterator_options : dict | None
            Additional options for the iterator
        always_write_timestamps : bool
            If True, always writes timestamps instead of using sampling rate
        metadata : dict
            Metadata dictionary with TimeSeries information
        """
        from ....tools.spikeinterface import add_recording_as_time_series_to_nwbfile

        if not self._analog_channel_groups:
            return

        # Get TimeSeries configurations from metadata
        time_series_metadata = metadata.get("TimeSeries", {}).get(self.metadata_key, {})

        # Write each group as a TimeSeries
        for group_key, group_config in self._analog_channel_groups.items():
            # Check if this group has metadata
            if group_key not in time_series_metadata:
                continue

            channels = group_config["channels"]
            channel_recording = recording.select_channels(channel_ids=channels)

            # Get metadata for this group
            ts_metadata = {"TimeSeries": {group_key: time_series_metadata[group_key]}}

            # Write TimeSeries
            add_recording_as_time_series_to_nwbfile(
                recording=channel_recording,
                nwbfile=nwbfile,
                metadata=ts_metadata,
                iterator_type=iterator_type,
                iterator_options=iterator_options,
                always_write_timestamps=always_write_timestamps,
                metadata_key=group_key,
            )

    def get_event_times_from_ttl(self, channel_name: str) -> np.ndarray:
        """
        Return the start of event times from the rising part of TTL pulses on one of the NIDQ channels.

        Parameters
        ----------
        channel_name : str
            Name of the channel in the .nidq.bin file, as the board names it (``"XA0"``).

        Returns
        -------
        rising_times : numpy.ndarray
            The times of the rising TTL pulses.
        """
        if "#" in str(channel_name):
            warnings.warn(_NEO_ADDRESSING_DEPRECATION, FutureWarning, stacklevel=2)
        channel_id = self._resolve_channel_id(channel_name)

        # TODO: consider RAM cost of these operations and implement safer buffering version
        rising_frames = get_rising_frames_from_ttl(trace=self.recording_extractor.get_traces(channel_ids=[channel_id]))

        nidq_timestamps = self.recording_extractor.get_times()
        rising_times = nidq_timestamps[rising_frames]

        return rising_times
