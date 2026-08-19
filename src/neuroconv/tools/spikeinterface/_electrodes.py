"""The electrodes table written from metadata rather than derived from the recording.

``metadata["Ecephys"]["ElectrodesTable"]`` states the table as one block with two aspects. ``rows`` holds
one entry per physical contact, keyed by a handle, each stating its column values in full and pointing at
its group with ``electrode_group_metadata_key``. ``columns`` describes those columns, keyed by the field a
row states, in the shape the events tables already use. A channel reaches a row through
``channel_to_electrode`` on the series entry, or, when that is absent, through the same key derivation the
block was generated with.

The block is an override layer: absent, the pipeline derives the table from the recording exactly as it
always has. Present, it is authoritative and the recording is consulted only for ``channel_name``, which is
the acquisition system's own label for a channel and so cannot be restated in metadata.

``Ecephys.Electrodes`` is a different thing and keeps its old meaning, the list of column descriptions that
annotates a derived table. One key, one meaning: a block written in the wrong shape is refused by the schema
instead of being read as the other feature.
"""

import numpy as np
import pynwb
from hdmf.common import MeaningsTable

# Fields of an electrode entry that address other metadata rather than describing a column.
_STRUCTURAL_ELECTRODE_FIELDS = ("electrode_group_metadata_key",)
# Columns the writer owns: the group link and the two identity columns, which are not taken from an
# entry's own fields even when one states them.
_WRITER_OWNED_COLUMNS = ("group", "group_name", "channel_name")


def _electrodes_table_is_stated(metadata: dict | None) -> bool:
    """Whether ``Ecephys.ElectrodesTable`` states the table, rather than leaving it to be derived.

    Presence of the block is the whole test; there is no shape to sniff, because the block means one
    thing. An empty ``rows`` counts as stated rather than as absent, so it is refused downstream for
    leaving the recording's channels with nowhere to go, which is what a user who deleted a row they
    still record means.
    """
    if metadata is None:
        return False
    electrodes_table = metadata.get("Ecephys", {}).get("ElectrodesTable")
    return isinstance(electrodes_table, dict) and isinstance(electrodes_table.get("rows"), dict)


def _derive_electrode_keys(recording) -> list[str]:
    """One electrode key per channel, derived from the most specific physical identity available.

    ``(group, contact)`` when the recording carries contact identifiers, ``(group, channel)`` otherwise,
    which is the common case: of the formats measured only SpikeGLX supplies contact ids without a
    user-attached probe. The channel is never appended on top of a known contact, since that is what
    would put two bands of one contact on separate rows.

    The group qualifies the key because contact ids are unique per probe and not per recording: two
    probes in one SpikeGLX run were measured sharing 70 identical contact ids, and the group names are
    already probe-qualified, so the group separates them.
    """
    from .spikeinterface import _get_channel_name, _get_electrode_name, _get_group_name

    group_names = _get_group_name(recording=recording)
    electrode_names = _get_electrode_name(recording=recording)
    identities = _get_channel_name(recording=recording) if electrode_names is None else np.asarray(electrode_names)

    # Plain strings, not the numpy ones the properties are held as: these become dictionary keys of a
    # metadata dictionary that gets validated as JSON and written to YAML by the conversion specification.
    return [str(f"{group_name}_{identity}") for group_name, identity in zip(group_names, identities)]


def _as_plain_value(value):
    """A property value as a Python object, since a metadata entry is validated and serialized as JSON.

    The dtype a numpy scalar carries is what a round trip through YAML or JSON would drop, which is why
    the ``columns`` block states it separately rather than relying on the value to keep it.
    """
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _is_ragged(values: list) -> bool:
    """Whether a column's values are sequences of differing length, which needs an indexed column.

    Equal-length sequences are a rectangular array, which is how a multi-dimensional electrode property
    is written; only the uneven case needs the index. Inferred from the values rather than declared,
    since the length of a row is not something a specification could restate.
    """
    sequences = [value for value in values if isinstance(value, (list, tuple, np.ndarray))]
    if not sequences or len(sequences) != len(values):
        return len(sequences) > 0 and len(sequences) != len(values)
    return len({len(value) for value in sequences}) > 1


def _get_registry_dtype(data: np.ndarray) -> str | None:
    """The dtype worth stating in a ``columns`` entry, or ``None`` when there is none.

    Numeric and boolean columns only. A numpy string dtype carries its width (``<U7``), which a user
    editing a value would silently truncate against, and the width is not information the file keeps;
    object columns have no dtype to restate. Everything else is declared so that a metadata dictionary
    surviving a YAML or JSON round trip, which widens ``int32`` to a Python ``int``, still writes the
    column the source measured.
    """
    dtype = data.dtype
    if dtype.kind in "iufcb":
        return str(dtype)
    return None


def _build_electrodes_metadata(
    recording,
    *,
    group_metadata_key_by_name: dict[str, str],
    property_descriptions: dict | None = None,
) -> dict:
    """The ``ElectrodesTable`` block and the ``channel_to_electrode`` map for a recording.

    Every row is stated in full, so a user edits rather than authors. The rows are in the recording's
    channel order, which becomes the table's row order.

    Parameters
    ----------
    recording : BaseRecording
        The recording whose channels the rows are derived from.
    group_metadata_key_by_name : dict of str to str
        Maps a channel group name to the ``ElectrodeGroups`` key it was filed under, so each row can
        point at its group.
    property_descriptions : dict of str to str, optional
        What the interface already says about a column, which is the column-description list its
        ``get_metadata`` emits. Carried into ``columns`` so that stating the table does not
        silently downgrade a description the interface was already supplying.

    Returns
    -------
    dict
        ``{"ElectrodesTable": {"rows": ..., "columns": ...}, "channel_to_electrode": ...}``.
    """
    from .spikeinterface import _build_electrode_column_data, _get_group_name

    property_descriptions = dict() if property_descriptions is None else property_descriptions
    column_data = _build_electrode_column_data(recording=recording, property_descriptions=property_descriptions)
    group_names = _get_group_name(recording=recording)
    electrode_keys = _derive_electrode_keys(recording=recording)
    channel_ids = recording.get_channel_ids()

    # ``electrode_name`` is written for every row, including the formats with no probe, where it holds
    # the channel's name. That is what the key already derives from, and stating it makes the row's
    # identity readable in the file, which is what lets a second interface over the same contacts find
    # the row it should reference instead of adding its own.
    electrode_names = column_data.get("electrode_name")
    if electrode_names is None:
        identities = [key.removeprefix(f"{group_name}_") for key, group_name in zip(electrode_keys, group_names)]
    else:
        identities = np.asarray(electrode_names["data"]).tolist()

    row_columns = [
        column_name for column_name in column_data if column_name not in (*_WRITER_OWNED_COLUMNS, "electrode_name")
    ]

    electrodes = {}
    for channel_index, electrode_key in enumerate(electrode_keys):
        # A key seen twice is two channels on one contact, which is the case the design exists to
        # support. The second channel states nothing new about the row, so the first one wins.
        if electrode_key in electrodes:
            continue
        entry = {
            "electrode_group_metadata_key": group_metadata_key_by_name[group_names[channel_index]],
            "electrode_name": identities[channel_index],
        }
        for column_name in row_columns:
            entry[column_name] = _as_plain_value(column_data[column_name]["data"][channel_index])
        electrodes[electrode_key] = entry

    electrode_columns = {}
    for column_name in row_columns:
        specification = {"column_name": column_name, "description": column_data[column_name]["description"]}
        dtype = _get_registry_dtype(np.asarray(column_data[column_name]["data"]))
        if dtype is not None:
            specification["dtype"] = dtype
        electrode_columns[column_name] = specification

    # The two identity columns are written by the writer rather than stated by a row, but they are still
    # columns of the table and an interface may already describe them, so they get an entry whose only
    # job is to carry that description.
    for column_name in ("electrode_name", "channel_name"):
        description = property_descriptions.get(column_name)
        if description is not None:
            electrode_columns[column_name] = {"column_name": column_name, "description": description}

    channel_to_electrode = {
        str(channel_id): electrode_key for channel_id, electrode_key in zip(channel_ids, electrode_keys)
    }

    return {
        "ElectrodesTable": {"rows": electrodes, "columns": electrode_columns},
        "channel_to_electrode": channel_to_electrode,
    }


def _resolve_channel_to_electrode_key(recording, metadata: dict, metadata_key: str | None) -> dict:
    """Map each of the recording's channel ids to the electrode key it is recorded by.

    ``channel_to_electrode`` on the series entry is the statement; the key derivation is the default
    for a registry the user has not remapped. The map may name channels the recording no longer has,
    which is the ``stub_test`` and ``remove_channels`` case where the registry describes the full set,
    but it may never miss one the recording does have.
    """
    ecephys_metadata = metadata.get("Ecephys", {})
    registry = ecephys_metadata["ElectrodesTable"]["rows"]

    channel_to_electrode = None
    if metadata_key is not None:
        series_entry = ecephys_metadata.get("ElectricalSeries", {}).get(metadata_key, {})
        channel_to_electrode = series_entry.get("channel_to_electrode")

    channel_ids = recording.get_channel_ids()
    if channel_to_electrode is None:
        electrode_key_by_channel = dict(zip(channel_ids, _derive_electrode_keys(recording=recording)))
    else:
        # Channel ids reach here as strings whenever the metadata has been through
        # ``validate_metadata``, which round-trips it as JSON, so both sides are compared as strings.
        stated = {str(channel_id): electrode_key for channel_id, electrode_key in channel_to_electrode.items()}
        unmapped = [channel_id for channel_id in channel_ids if str(channel_id) not in stated]
        if unmapped:
            raise ValueError(
                f"metadata['Ecephys']['ElectricalSeries']['{metadata_key}']['channel_to_electrode'] does not "
                f"cover every channel of the recording. Missing: {unmapped[:10]}"
                f"{' and more' if len(unmapped) > 10 else ''}. A partial mapping is not filled in, since a "
                "channel with no electrode has nowhere to be written."
            )
        electrode_key_by_channel = {channel_id: stated[str(channel_id)] for channel_id in channel_ids}

    undeclared = sorted({key for key in electrode_key_by_channel.values() if key not in registry})
    if undeclared:
        raise ValueError(
            f"Channels of this recording resolve to electrode keys that metadata['Ecephys']['ElectrodesTable']['rows'] "
            f"does not declare: {undeclared[:10]}{' and more' if len(undeclared) > 10 else ''}. "
            f"Declared keys: {sorted(registry)[:10]}{' and more' if len(registry) > 10 else ''}."
        )

    return electrode_key_by_channel


def _validate_electrodes_registry(registry: dict, group_name_by_key: dict[str, str]) -> None:
    """Reject a registry that would write two rows for one contact.

    A row's identity in the file is ``(group_name, electrode_name)``, which is what a later call matches
    against. Two keys resolving to one identity would write the contact twice on the first call and be
    unresolvable on the second.
    """
    key_by_identity: dict[tuple[str, str], str] = {}
    for electrode_key, entry in registry.items():
        group_metadata_key = entry.get("electrode_group_metadata_key")
        identity = (group_name_by_key[group_metadata_key], str(entry.get("electrode_name", electrode_key)))
        if identity in key_by_identity:
            raise ValueError(
                f"metadata['Ecephys']['ElectrodesTable']['rows'] keys '{key_by_identity[identity]}' and '{electrode_key}' "
                f"both describe the electrode named '{identity[1]}' in group '{identity[0]}'. Use 1 key per "
                "electrode; two channels reach one row through 'channel_to_electrode', not through two rows."
            )
        key_by_identity[identity] = electrode_key


def _apply_column_categories(column_name: str, data: np.ndarray, categories: dict) -> np.ndarray:
    """Rewrite a column's raw values to their display labels, as the events tables do.

    The raw value is not recoverable afterwards, which is why categories are declared only where the
    value is an arbitrary hardware encoding rather than a number that means something.
    """
    labels = {str(raw_value): label for raw_value, label in categories.get("labels", {}).items()}
    relabelled = [labels.get(str(value), str(value)) for value in data]
    return np.array(relabelled, dtype=str)


def _add_meanings_table(table, column_name: str, categories: dict) -> None:
    """Attach the vocabulary of a categorical column, matching what the events writer produces."""
    meanings = {raw_value: meaning for raw_value, meaning in (categories.get("meanings") or {}).items() if meaning}
    if not meanings:
        return

    labels = categories.get("labels", {})
    column = table[column_name]
    meanings_table = next(
        (existing for existing in (table.meanings_tables or {}).values() if existing.target is column), None
    )
    creating = meanings_table is None
    if creating:
        meanings_table = MeaningsTable(target=column, description="Meaning of each label.")
    existing_labels = set(meanings_table["value"].data)
    for raw_value, meaning in meanings.items():
        label = str(labels.get(raw_value, raw_value))
        if label in existing_labels:
            continue
        meanings_table.add_row(value=label, meaning=meaning)
        existing_labels.add(label)
    if creating:
        table.add_meanings_table(meanings_table)


def _add_electrodes_from_registry_to_nwbfile(
    recording,
    nwbfile: pynwb.NWBFile,
    metadata: dict,
    *,
    metadata_key: str | None = None,
    null_values_for_properties: dict | None = None,
) -> dict:
    """Write the electrodes table from ``metadata["Ecephys"]["ElectrodesTable"]``.

    Every declared row is written, whether or not a channel of this recording references it, so the
    table's row order is the registry's order rather than an artifact of which interface wrote first.
    A second call over the same metadata finds those rows by ``(group_name, electrode_name)`` and adds
    none.

    Returns
    -------
    dict
        Maps each of the recording's channel ids to its row index in the electrodes table.
    """
    from .spikeinterface import (
        _add_electrode_groups_to_nwbfile,
        _get_channel_name,
        _get_null_value_for_column,
        _get_null_value_for_property,
    )

    null_values_for_properties = dict() if null_values_for_properties is None else null_values_for_properties
    ecephys_metadata = metadata.get("Ecephys", {})
    electrodes_table_metadata = ecephys_metadata["ElectrodesTable"]
    registry = electrodes_table_metadata["rows"]
    column_specifications = electrodes_table_metadata.get("columns", {})

    electrode_key_by_channel = _resolve_channel_to_electrode_key(
        recording=recording, metadata=metadata, metadata_key=metadata_key
    )

    # Every group the registry points at is written, whether or not the recording carries a channel in
    # it. Gating on the recording is what the registry exists to remove: a user regrouping in metadata
    # states the group here and nowhere else, so there is no channel property left to gate on.
    group_metadata_keys = []
    for electrode_key, entry in registry.items():
        group_metadata_key = entry.get("electrode_group_metadata_key")
        if group_metadata_key is None:
            raise ValueError(
                f"metadata['Ecephys']['ElectrodesTable']['rows']['{electrode_key}'] states no "
                "'electrode_group_metadata_key'. Every electrode belongs to a group; name the key of its "
                "entry in metadata['Ecephys']['ElectrodeGroups']."
            )
        if group_metadata_key not in group_metadata_keys:
            group_metadata_keys.append(group_metadata_key)

    group_name_by_key = _add_electrode_groups_to_nwbfile(
        recording=recording,
        nwbfile=nwbfile,
        metadata=metadata,
        electrode_group_metadata_keys=group_metadata_keys,
    )
    _validate_electrodes_registry(registry=registry, group_name_by_key=group_name_by_key)

    # Rows already in the file are addressed by the identity columns rather than by the metadata key,
    # which exists only inside a metadata dictionary. Renaming a key therefore changes nothing about
    # what a later call matches on.
    def row_identity(group_name, electrode_name):
        return f"{group_name}_{electrode_name}"

    existing_rows = {}
    electrodes_table = nwbfile.electrodes
    if electrodes_table is not None and len(electrodes_table) > 0 and "electrode_name" in electrodes_table.colnames:
        for row_index in range(len(electrodes_table)):
            identity = row_identity(
                electrodes_table["group_name"][row_index], electrodes_table["electrode_name"][row_index]
            )
            existing_rows.setdefault(identity, row_index)

    previous_table_size = len(electrodes_table) if electrodes_table is not None else 0
    previous_columns = set(electrodes_table.colnames) if electrodes_table is not None else set()

    # The row values, in registry order, with the writer-owned columns resolved.
    channel_names_by_key = {}
    channel_name_array = _get_channel_name(recording=recording)
    for channel_id, channel_name in zip(recording.get_channel_ids(), channel_name_array):
        channel_names_by_key.setdefault(electrode_key_by_channel[channel_id], channel_name)

    ordered_keys = list(registry)
    row_index_by_key = {}
    rows_to_add = []
    for electrode_key in ordered_keys:
        entry = registry[electrode_key]
        group_name = group_name_by_key[entry["electrode_group_metadata_key"]]
        electrode_name = str(entry.get("electrode_name", electrode_key))
        identity = row_identity(group_name, electrode_name)
        if identity in existing_rows:
            row_index_by_key[electrode_key] = existing_rows[identity]
            continue
        rows_to_add.append(electrode_key)

    # Columns come from the union of the entries' own fields, since a field a single row states is a
    # column the table has to carry, with a null in every row that does not state it.
    declared_columns = []
    for entry in registry.values():
        for field in entry:
            if field in _STRUCTURAL_ELECTRODE_FIELDS or field in _WRITER_OWNED_COLUMNS:
                continue
            # ``electrode_name`` is a field of an entry but the identity block below is what writes it,
            # so it is not built twice.
            if field == "electrode_name" or field in declared_columns:
                continue
            declared_columns.append(field)

    # A ``columns`` entry naming a field no row states describes nothing. It is silent otherwise, since
    # the writer only ever looks a specification up by a field it found on a row, so a renamed field or a
    # typo leaves the column undescribed with no sign of it.
    describable = set(declared_columns).union({"electrode_name", "channel_name"})
    undescribed = sorted(set(column_specifications) - describable)
    if undescribed:
        raise ValueError(
            f"metadata['Ecephys']['ElectrodesTable']['columns'] describes {undescribed}, which no row "
            f"states. Columns of this table: {sorted(describable)}. A description is keyed by the field "
            "the rows use, so rename the entry to match the rows or drop it."
        )

    column_data = {}
    for field in declared_columns:
        specification = column_specifications.get(field, {})
        values = [registry[electrode_key].get(field) for electrode_key in ordered_keys]
        stated = [value for value in values if value is not None]
        if not stated:
            continue
        # A row omitting a column means null, the same as a channel lacking a property today.
        null_value = (
            _get_null_value_for_property(
                property=field, sample_data=stated[0], null_values_for_properties=null_values_for_properties
            )
            if len(stated) != len(values)
            else None
        )
        values = [null_value if value is None else value for value in values]

        # Raggedness is a property of the values, not something a specification declares, and it is what
        # separates a column numpy can hold from one that has to be written with an index. A column of
        # equal-length sequences stays a rectangular array, which is how a two-dimensional electrode
        # property is written today.
        ragged = _is_ragged(values)
        if ragged:
            data = np.empty(shape=len(values), dtype=object)
            for position, value in enumerate(values):
                data[position] = list(value)
        else:
            data = np.asarray(values)
        dtype = specification.get("dtype")
        if dtype is not None and not ragged:
            try:
                data = data.astype(dtype)
            except (TypeError, ValueError) as exception:
                raise ValueError(
                    f"metadata['Ecephys']['ElectrodesTable']['columns']['{field}'] declares dtype '{dtype}', which the "
                    f"values of that column cannot be written as: {exception}"
                ) from exception
        categories = specification.get("column_categories")
        if categories is not None:
            data = _apply_column_categories(column_name=field, data=data, categories=categories)
        column_data[specification.get("column_name", field)] = {
            "description": specification.get("description", "no description"),
            "data": data,
            "categories": categories,
            "ragged": ragged,
        }

    # The identity columns, which the writer owns. A ``columns`` entry for either of them
    # carries only a description, since the values are not a row's to state.
    column_data["electrode_name"] = {
        "description": column_specifications.get("electrode_name", {}).get("description", "unique electrode reference"),
        "data": np.array([str(registry[key].get("electrode_name", key)) for key in ordered_keys], dtype=str),
        "categories": None,
    }
    column_data["channel_name"] = {
        "description": column_specifications.get("channel_name", {}).get("description", "unique channel reference"),
        "data": np.array(
            [str(channel_names_by_key.get(key, "")) for key in ordered_keys],
            dtype=str,
        ),
        "categories": None,
    }

    group_objects = [
        nwbfile.electrode_groups[group_name_by_key[registry[key]["electrode_group_metadata_key"]]]
        for key in ordered_keys
    ]
    group_names = [group.name for group in group_objects]
    locations = [str(registry[key].get("location", "unknown")) for key in ordered_keys]

    # ``location`` is required by the schema, so it is written by row rather than as a column, along
    # with anything the table already carries from an earlier call.
    row_only_columns = {"group", "group_name", "location"}.union(previous_columns)
    null_values_for_rows = {}
    if rows_to_add:
        for column_name in previous_columns.difference({"group", "group_name", "location"}):
            if column_name in column_data:
                continue
            null_values_for_rows[column_name] = _get_null_value_for_column(
                column=nwbfile.electrodes[column_name],
                property=column_name,
                null_values_for_properties=null_values_for_properties,
            )

    key_position = {electrode_key: position for position, electrode_key in enumerate(ordered_keys)}
    for electrode_key in rows_to_add:
        position = key_position[electrode_key]
        electrode_kwargs = dict(null_values_for_rows)
        electrode_kwargs.update(
            group=group_objects[position], group_name=group_names[position], location=locations[position]
        )
        for column_name in previous_columns.intersection(column_data):
            electrode_kwargs[column_name] = column_data[column_name]["data"][position]
        nwbfile.add_electrode(**electrode_kwargs, enforce_unique_id=True)

    # Rows added above are appended in registry order, so their indices follow the previous table.
    next_row_index = previous_table_size
    for electrode_key in ordered_keys:
        if electrode_key in row_index_by_key:
            continue
        row_index_by_key[electrode_key] = next_row_index
        next_row_index += 1

    table_size = len(nwbfile.electrodes)
    indices_for_registry = [row_index_by_key[electrode_key] for electrode_key in ordered_keys]
    registry_index_set = set(indices_for_registry)
    indices_for_null_values = [index for index in range(table_size) if index not in registry_index_set]

    for column_name, column in column_data.items():
        if column_name in previous_columns or column_name in row_only_columns:
            continue
        data = column["data"]
        ragged = column.get("ragged", False)
        if indices_for_null_values:
            if ragged:
                # A ragged column takes an empty row whatever its element type is.
                extended_data = np.empty(shape=table_size, dtype=object)
                for position, index in enumerate(indices_for_registry):
                    extended_data[index] = data[position]
                for index in indices_for_null_values:
                    extended_data[index] = null_values_for_properties.get(column_name, [])
            else:
                null_value = _get_null_value_for_property(
                    property=column_name,
                    sample_data=data[0],
                    null_values_for_properties=null_values_for_properties,
                )
                extended_data = np.empty(shape=(table_size, *data.shape[1:]), dtype=data.dtype)
                extended_data[indices_for_registry] = data
                extended_data[indices_for_null_values] = null_value
            data = extended_data
        if ragged:
            data = [list(value) for value in data]
        nwbfile.add_electrode_column(column_name, description=column["description"], data=data, index=bool(ragged))
        if column["categories"] is not None:
            _add_meanings_table(table=nwbfile.electrodes, column_name=column_name, categories=column["categories"])

    return {
        channel_id: row_index_by_key[electrode_key] for channel_id, electrode_key in electrode_key_by_channel.items()
    }
