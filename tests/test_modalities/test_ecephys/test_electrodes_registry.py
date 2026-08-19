"""The electrodes table written from ``metadata["Ecephys"]["ElectrodesTable"]["rows"]`` rather than derived."""

import json

import numpy as np
import pytest
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile
from spikeinterface.core.generate import generate_recording

from neuroconv.tools.spikeinterface import (
    add_recording_metadata_to_nwbfile,
    add_recording_to_nwbfile,
)
from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface


def _interface(num_channels=4, groups=None, properties=None):
    interface = MockRecordingInterface(num_channels=num_channels, durations=[0.1])
    recording = interface.recording_extractor
    if groups is not None:
        recording.set_channel_groups(groups)
    for key, values in (properties or {}).items():
        recording.set_property(key, np.asarray(values))
    return interface


def _with_column_descriptions(metadata, column_descriptions):
    """Stand in for an interface whose ``get_metadata`` describes some of its electrodes columns.

    Those descriptions arrive under the older ``Ecephys.Electrodes`` list, which is what the template
    reads them out of.
    """
    metadata["Ecephys"]["Electrodes"] = column_descriptions
    return metadata


class TestTemplate:
    """What ``get_metadata_template`` states, and that it states the table the writer would derive."""

    def test_every_electrode_is_stated_once(self):
        interface = _interface(num_channels=4, groups=[0, 0, 1, 1])
        metadata = interface.get_metadata_template()

        assert list(metadata["Ecephys"]["ElectrodesTable"]["rows"]) == ["0_0", "0_1", "1_2", "1_3"]
        assert list(metadata["Ecephys"]["ElectrodeGroups"]) == ["0", "1"]
        first_entry = metadata["Ecephys"]["ElectrodesTable"]["rows"]["0_0"]
        assert first_entry["electrode_group_metadata_key"] == "0"
        assert first_entry["electrode_name"] == "0"

    def test_keys_and_values_are_plain_python(self):
        """A registry is validated as JSON and written to YAML, so a numpy scalar cannot reach it."""
        interface = _interface(properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        metadata = interface.get_metadata_template()

        assert all(type(key) is str for key in metadata["Ecephys"]["ElectrodesTable"]["rows"])
        for entry in metadata["Ecephys"]["ElectrodesTable"]["rows"].values():
            assert all(not isinstance(value, np.generic) for value in entry.values())
        json.dumps(metadata["Ecephys"]["ElectrodesTable"]["rows"])

    def test_the_channel_to_electrode_map_covers_every_channel(self):
        interface = _interface(num_channels=4)
        metadata = interface.get_metadata_template()

        mapping = metadata["Ecephys"]["ElectricalSeries"][interface.metadata_key]["channel_to_electrode"]
        assert set(mapping) == {str(channel_id) for channel_id in interface.channel_ids}
        assert set(mapping.values()) == set(metadata["Ecephys"]["ElectrodesTable"]["rows"])

    def test_it_validates_against_the_interface_schema(self):
        interface = _interface(properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        metadata = interface.get_metadata_template()
        metadata["NWBFile"]["session_start_time"] = "2020-01-01T00:00:00"

        interface.validate_metadata(metadata=metadata)

    def test_a_column_description_the_interface_already_supplies_is_carried_over(self):
        """Stating the table must not silently downgrade what the interface already said about it."""
        interface = _interface(properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        interface.get_metadata = lambda: _with_column_descriptions(
            MockRecordingInterface.get_metadata(interface),
            [{"name": "imp", "description": "Impedance in ohms."}],
        )

        metadata = interface.get_metadata_template()

        assert metadata["Ecephys"]["ElectrodesTable"]["columns"]["imp"]["description"] == "Impedance in ohms."
        nwbfile = interface.create_nwbfile(metadata=metadata)
        assert nwbfile.electrodes["imp"].description == "Impedance in ohms."

    def test_writing_the_template_reproduces_the_derived_table(self):
        """The registry is a restatement of the recording, so writing it changes no column value."""
        properties = {"imp": [1.0, 2.0, 3.0, 4.0], "brain_area": ["V1", "V1", "CA1", "CA1"]}
        derived = _interface(groups=[0, 0, 1, 1], properties=properties).create_nwbfile()
        stated_interface = _interface(groups=[0, 0, 1, 1], properties=properties)
        stated = stated_interface.create_nwbfile(metadata=stated_interface.get_metadata_template())

        derived_table = derived.electrodes.to_dataframe()
        stated_table = stated.electrodes.to_dataframe()
        shared_columns = sorted(set(derived_table.columns) & set(stated_table.columns) - {"group"})
        assert shared_columns == ["channel_name", "group_name", "imp", "location"]
        for column in shared_columns:
            assert derived_table[column].tolist() == stated_table[column].tolist(), column


class TestRegistryWrites:
    def test_the_group_link_is_the_only_thing_that_decides_a_row_s_group(self):
        """Regrouping in metadata, with no ``set_property`` on the recording.

        This is what the registry exists for: the recording reports one channel group and the file gets
        two electrode groups, because the rows say so.
        """
        interface = _interface(num_channels=4, groups=[0, 0, 0, 0])
        metadata = interface.get_metadata_template()
        metadata["Ecephys"]["ElectrodeGroups"] = {
            "shank0": {"name": "Shank0", "description": "front", "location": "V1"},
            "shank1": {"name": "Shank1", "description": "back", "location": "CA1"},
        }
        for index, entry in enumerate(metadata["Ecephys"]["ElectrodesTable"]["rows"].values()):
            entry["electrode_group_metadata_key"] = "shank0" if index < 2 else "shank1"

        nwbfile = interface.create_nwbfile(metadata=metadata)

        assert sorted(nwbfile.electrode_groups) == ["Shank0", "Shank1"]
        assert list(nwbfile.electrodes["group_name"][:]) == ["Shank0", "Shank0", "Shank1", "Shank1"]
        assert interface.recording_extractor.get_property("group_name") is None

    def test_row_order_is_registry_order(self):
        interface = _interface(num_channels=4)
        metadata = interface.get_metadata_template()
        registry = metadata["Ecephys"]["ElectrodesTable"]["rows"]
        metadata["Ecephys"]["ElectrodesTable"]["rows"] = {key: registry[key] for key in reversed(list(registry))}

        nwbfile = interface.create_nwbfile(metadata=metadata)

        assert list(nwbfile.electrodes["electrode_name"][:]) == ["3", "2", "1", "0"]
        # The series still reaches the channels it recorded, in channel order.
        assert nwbfile.acquisition["ElectricalSeries"].electrodes.data[:] == [3, 2, 1, 0]

    def test_a_declared_electrode_no_channel_references_is_still_written(self):
        interface = _interface(num_channels=4)
        metadata = interface.get_metadata_template()
        interface.remove_channels(channel_ids=list(interface.channel_ids)[2:])

        nwbfile = interface.create_nwbfile(metadata=metadata)

        assert len(nwbfile.electrodes) == 4
        assert nwbfile.acquisition["ElectricalSeries"].electrodes.data[:] == [0, 1]
        # Nothing supplied a channel name for the rows this recording does not reach.
        assert list(nwbfile.electrodes["channel_name"][:]) == ["0", "1", "", ""]

    def test_channel_to_electrode_decides_which_row_a_channel_reaches(self):
        interface = _interface(num_channels=4)
        metadata = interface.get_metadata_template()
        keys = list(metadata["Ecephys"]["ElectrodesTable"]["rows"])
        metadata["Ecephys"]["ElectricalSeries"][interface.metadata_key]["channel_to_electrode"] = {
            channel_id: keys[3 - index]
            for index, channel_id in enumerate(
                metadata["Ecephys"]["ElectricalSeries"][interface.metadata_key]["channel_to_electrode"]
            )
        }

        nwbfile = interface.create_nwbfile(metadata=metadata)

        assert nwbfile.acquisition["ElectricalSeries"].electrodes.data[:] == [3, 2, 1, 0]

    def test_a_row_omitting_a_column_gets_a_null(self):
        interface = _interface(num_channels=4, properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        metadata = interface.get_metadata_template()
        del metadata["Ecephys"]["ElectrodesTable"]["rows"]["ElectrodeGroup_2"]["imp"]

        nwbfile = interface.create_nwbfile(metadata=metadata)

        impedances = list(nwbfile.electrodes["imp"][:])
        assert impedances[:2] == [1.0, 2.0]
        assert np.isnan(impedances[2])
        assert impedances[3] == 4.0

    def test_a_multi_dimensional_column_keeps_its_shape(self):
        interface = _interface(num_channels=4)
        interface.recording_extractor.set_property("coords", np.arange(8, dtype="float64").reshape(4, 2))
        metadata = interface.get_metadata_template()
        assert metadata["Ecephys"]["ElectrodesTable"]["rows"]["ElectrodeGroup_0"]["coords"] == [0.0, 1.0]

        nwbfile = interface.create_nwbfile(metadata=metadata)

        assert np.asarray(nwbfile.electrodes["coords"][:]).shape == (4, 2)

    def test_a_ragged_column_is_written_with_an_index(self):
        """Raggedness is read off the values, the same as on the path that derives the table."""
        ragged = np.empty(4, dtype=object)
        for index, value in enumerate([[1], [1, 2], [1, 2, 3], []]):
            ragged[index] = value
        interface = _interface(num_channels=4)
        interface.recording_extractor.set_property("neighbors", ragged)
        metadata = interface.get_metadata_template()

        stated = interface.create_nwbfile(metadata=metadata)

        derived_interface = _interface(num_channels=4)
        derived_interface.recording_extractor.set_property("neighbors", ragged)
        derived = derived_interface.create_nwbfile()

        assert [list(value) for value in stated.electrodes["neighbors"][:]] == [[1], [1, 2], [1, 2, 3], []]
        assert [list(value) for value in stated.electrodes["neighbors"][:]] == [
            list(value) for value in derived.electrodes["neighbors"][:]
        ]


class TestElectrodeColumns:
    def test_a_column_is_renamed_and_described(self):
        interface = _interface(properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        metadata = interface.get_metadata_template()
        metadata["Ecephys"]["ElectrodesTable"]["columns"]["imp"] = {
            "column_name": "impedance",
            "description": "Electrode impedance in ohms, measured at 1 kHz.",
        }

        nwbfile = interface.create_nwbfile(metadata=metadata)

        assert "impedance" in nwbfile.electrodes.colnames
        assert "imp" not in nwbfile.electrodes.colnames
        assert nwbfile.electrodes["impedance"].description == "Electrode impedance in ohms, measured at 1 kHz."

    def test_a_declared_dtype_survives_a_json_round_trip(self):
        """The reason the dtype is stated: the value alone cannot carry it through YAML or JSON."""
        interface = _interface(properties={"shank": np.array([0, 1, 0, 1], dtype="int32")})
        metadata = interface.get_metadata_template()
        assert metadata["Ecephys"]["ElectrodesTable"]["columns"]["shank"]["dtype"] == "int32"

        round_tripped = json.loads(json.dumps(dict(metadata["Ecephys"]), default=str))
        assert all(type(entry["shank"]) is int for entry in round_tripped["ElectrodesTable"]["rows"].values())

        nwbfile = mock_NWBFile()
        add_recording_to_nwbfile(
            recording=interface.recording_extractor,
            nwbfile=nwbfile,
            metadata={"Ecephys": round_tripped},
            metadata_key=interface.metadata_key,
            iterator_type=None,
        )
        assert np.asarray(nwbfile.electrodes["shank"][:]).dtype == np.dtype("int32")

    def test_a_categorical_column_is_written_as_labels_with_their_meanings(self):
        interface = _interface(properties={"shank_side": [0, 1, 0, 1]})
        metadata = interface.get_metadata_template()
        metadata["Ecephys"]["ElectrodesTable"]["columns"]["shank_side"] = {
            "column_name": "shank_side",
            "description": "Which face of the shank the contact sits on.",
            "column_categories": {
                "labels": {0: "front", 1: "back"},
                "meanings": {0: "contact on the front face", 1: "contact on the back face"},
            },
        }

        nwbfile = interface.create_nwbfile(metadata=metadata)

        assert list(nwbfile.electrodes["shank_side"][:]) == ["front", "back", "front", "back"]
        meanings_table = nwbfile.electrodes.meanings_tables["shank_side_meanings"]
        assert list(meanings_table["value"].data) == ["front", "back"]
        assert list(meanings_table["meaning"].data) == [
            "contact on the front face",
            "contact on the back face",
        ]

    def test_a_dtype_the_values_cannot_be_written_as_is_refused(self):
        interface = _interface(properties={"port": ["A", "A", "B", "B"]})
        metadata = interface.get_metadata_template()
        metadata["Ecephys"]["ElectrodesTable"]["columns"]["port"] = {"column_name": "port", "dtype": "float64"}

        with pytest.raises(ValueError, match="declares dtype 'float64'"):
            interface.create_nwbfile(metadata=metadata)

    def test_a_column_described_but_stated_by_no_row(self):
        """Silent otherwise: the writer only looks a description up by a field it found on a row."""
        interface = _interface(properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        metadata = interface.get_metadata_template()
        metadata["Ecephys"]["ElectrodesTable"]["columns"]["impedance"] = {
            "column_name": "impedance",
            "description": "Renamed the entry but not the rows.",
        }

        with pytest.raises(ValueError, match="which no row states"):
            interface.create_nwbfile(metadata=metadata)


class TestSharedRows:
    """Two recordings over the same contacts land on one set of rows, without a format-specific hack."""

    def test_two_interfaces_over_the_same_contacts_write_one_set_of_rows(self):
        raw = _interface(num_channels=4)
        raw.metadata_key = "raw"
        lfp = _interface(num_channels=4)
        lfp.metadata_key = "lfp"

        metadata = raw.get_metadata_template()
        lfp_metadata = lfp.get_metadata_template()
        metadata["Ecephys"]["ElectricalSeries"].update(lfp_metadata["Ecephys"]["ElectricalSeries"])
        metadata["Ecephys"]["ElectricalSeries"]["raw"]["name"] = "ElectricalSeriesRaw"
        metadata["Ecephys"]["ElectricalSeries"]["lfp"]["name"] = "ElectricalSeriesLFP"
        assert list(metadata["Ecephys"]["ElectrodesTable"]["rows"]) == list(
            lfp_metadata["Ecephys"]["ElectrodesTable"]["rows"]
        )

        nwbfile = mock_NWBFile()
        raw.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        lfp.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert len(nwbfile.electrodes) == 4
        assert len(nwbfile.acquisition) == 2
        regions = [series.electrodes.data[:] for series in nwbfile.acquisition.values()]
        assert regions == [[0, 1, 2, 3], [0, 1, 2, 3]]

    def test_a_second_call_adds_no_rows_and_no_columns(self):
        interface = _interface(num_channels=4, properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        metadata = interface.get_metadata_template()

        nwbfile = mock_NWBFile()
        add_recording_metadata_to_nwbfile(
            recording=interface.recording_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key=interface.metadata_key,
        )
        colnames_after_first = nwbfile.electrodes.colnames
        add_recording_metadata_to_nwbfile(
            recording=interface.recording_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key=interface.metadata_key,
        )

        assert len(nwbfile.electrodes) == 4
        assert nwbfile.electrodes.colnames == colnames_after_first

    def test_two_recordings_of_one_probe_share_rows_though_their_channels_are_named_differently(self):
        """Contact identity, not the channel name, is what puts two bands on one row.

        This is what the SpikeGLX interface fabricates a joined ``AP0,LF0`` channel name to achieve
        today. Here the two recordings keep their own names and land on one set of rows anyway.
        """
        recordings = {}
        for band in ("ap", "lf"):
            recording = generate_recording(num_channels=4, durations=[0.1])
            recording.set_property("channel_name", np.array([f"{band.upper()}{index}" for index in range(4)]))
            recordings[band] = recording

        assert list(recordings["ap"].get_probe().contact_ids) == list(recordings["lf"].get_probe().contact_ids)

        contact_ids = list(recordings["ap"].get_probe().contact_ids)
        metadata = {
            "Ecephys": {
                "ElectrodeGroups": {"probe": {"name": "Probe", "description": "", "location": ""}},
                "ElectrodesTable": {
                    "rows": {
                        f"probe_{contact}": {"electrode_group_metadata_key": "probe", "electrode_name": contact}
                        for contact in contact_ids
                    }
                },
                "ElectricalSeries": {
                    band: {
                        "name": f"ElectricalSeries{band.upper()}",
                        "channel_to_electrode": {
                            str(channel_id): f"probe_{contact}"
                            for channel_id, contact in zip(recordings[band].get_channel_ids(), contact_ids)
                        },
                    }
                    for band in ("ap", "lf")
                },
            }
        }

        nwbfile = mock_NWBFile()
        for band in ("ap", "lf"):
            add_recording_to_nwbfile(
                recording=recordings[band],
                nwbfile=nwbfile,
                metadata=metadata,
                metadata_key=band,
                iterator_type=None,
            )

        assert len(nwbfile.electrodes) == 4
        regions = [series.electrodes.data[:] for series in nwbfile.acquisition.values()]
        assert regions == [[0, 1, 2, 3], [0, 1, 2, 3]]
        # The row keeps the name the recording that created it supplied, which is a limitation of a
        # per-electrode ``channel_name`` column rather than of the registry.
        assert list(nwbfile.electrodes["channel_name"][:]) == ["AP0", "AP1", "AP2", "AP3"]


class TestOtherWritersFindTheRows:
    """The rest of the ecephys pipeline matches a recording's channels against rows already written."""

    def test_a_sorting_reaches_the_rows_the_registry_wrote(self):
        from neuroconv.converters import SortedRecordingConverter
        from neuroconv.tools.testing.mock_interfaces import MockSortingInterface

        recording_interface = _interface(num_channels=4)
        sorting_interface = MockSortingInterface(num_units=3, durations=[0.1])
        sorting_interface.sorting_extractor = sorting_interface.sorting_extractor.rename_units(
            new_unit_ids=["a", "b", "c"]
        )
        converter = SortedRecordingConverter(
            recording_interface=recording_interface,
            sorting_interface=sorting_interface,
            unit_ids_to_channel_ids={"a": ["0"], "b": ["1", "2"], "c": ["3"]},
        )

        metadata = converter.get_metadata()
        metadata["Ecephys"].update(recording_interface.get_metadata_template()["Ecephys"])
        nwbfile = converter.create_nwbfile(metadata=metadata)

        assert len(nwbfile.electrodes) == 4
        assert list(nwbfile.units["unit_name"][:]) == ["a", "b", "c"]
        # Flattened, the ragged region is one unit's rows after another, which is what the mapping asked
        # for. Every index resolves, which is the point: nothing fell back to appending a new row.
        assert list(nwbfile.units["electrodes"].target.data[:]) == [0, 1, 2, 3]


class TestRegistryValidation:
    def test_an_electrode_the_channels_resolve_to_but_nobody_declared(self):
        interface = _interface(num_channels=4)
        metadata = interface.get_metadata_template()
        del metadata["Ecephys"]["ElectrodesTable"]["rows"]["ElectrodeGroup_2"]
        del metadata["Ecephys"]["ElectricalSeries"][interface.metadata_key]["channel_to_electrode"]

        with pytest.raises(ValueError, match="does not declare"):
            interface.create_nwbfile(metadata=metadata)

    def test_a_channel_to_electrode_map_that_misses_a_channel(self):
        interface = _interface(num_channels=4)
        metadata = interface.get_metadata_template()
        mapping = metadata["Ecephys"]["ElectricalSeries"][interface.metadata_key]["channel_to_electrode"]
        del mapping[next(iter(mapping))]

        with pytest.raises(ValueError, match="does not cover every channel"):
            interface.create_nwbfile(metadata=metadata)

    def test_an_electrode_stating_no_group(self):
        interface = _interface(num_channels=4)
        metadata = interface.get_metadata_template()
        del metadata["Ecephys"]["ElectrodesTable"]["rows"]["ElectrodeGroup_0"]["electrode_group_metadata_key"]

        with pytest.raises(ValueError, match="states no 'electrode_group_metadata_key'"):
            interface.create_nwbfile(metadata=metadata)

    def test_an_electrode_pointing_at_a_group_nobody_declared(self):
        interface = _interface(num_channels=4)
        metadata = interface.get_metadata_template()
        metadata["Ecephys"]["ElectrodesTable"]["rows"]["ElectrodeGroup_0"]["electrode_group_metadata_key"] = "absent"

        with pytest.raises(ValueError, match="does not declare the keys"):
            interface.create_nwbfile(metadata=metadata)

    def test_two_electrodes_describing_one_contact(self):
        interface = _interface(num_channels=4)
        metadata = interface.get_metadata_template()
        metadata["Ecephys"]["ElectrodesTable"]["rows"]["ElectrodeGroup_1"]["electrode_name"] = "0"

        with pytest.raises(ValueError, match="both describe the electrode named"):
            interface.create_nwbfile(metadata=metadata)

    def test_two_group_keys_sharing_a_name(self):
        interface = _interface(num_channels=4)
        metadata = interface.get_metadata_template()
        metadata["Ecephys"]["ElectrodeGroups"]["duplicate"] = {"name": "ElectrodeGroup"}
        metadata["Ecephys"]["ElectrodesTable"]["rows"]["ElectrodeGroup_0"]["electrode_group_metadata_key"] = "duplicate"

        with pytest.raises(ValueError, match="Use 1 key to share an electrode group"):
            interface.create_nwbfile(metadata=metadata)


class TestBackwardCompatibility:
    def test_the_column_description_list_still_annotates_a_derived_table(self):
        recording = generate_recording(num_channels=4, durations=[0.1])
        recording.set_property("imp", np.array([1.0, 2.0, 3.0, 4.0]))
        metadata = {"Ecephys": {"Electrodes": [{"name": "imp", "description": "Impedance in ohms."}]}}

        nwbfile = mock_NWBFile()
        add_recording_to_nwbfile(recording=recording, nwbfile=nwbfile, metadata=metadata, iterator_type=None)

        assert nwbfile.electrodes["imp"].description == "Impedance in ohms."
        assert list(nwbfile.electrodes["imp"][:]) == [1.0, 2.0, 3.0, 4.0]

    def test_metadata_without_a_registry_is_not_mutated(self):
        interface = _interface(num_channels=4)
        metadata = interface.get_metadata()
        before = json.dumps(dict(metadata["Ecephys"]), default=str)

        interface.create_nwbfile(metadata=metadata)

        assert json.dumps(dict(metadata["Ecephys"]), default=str) == before


def test_the_registry_survives_a_file_round_trip(tmp_path):
    interface = _interface(num_channels=4, groups=[0, 0, 1, 1], properties={"imp": [1.0, 2.0, 3.0, 4.0]})
    metadata = interface.get_metadata_template()
    metadata["Ecephys"]["ElectrodesTable"]["columns"]["imp"] = {
        "column_name": "impedance",
        "description": "Electrode impedance in ohms.",
    }
    metadata["NWBFile"]["session_description"] = "registry round trip"

    nwbfile_path = tmp_path / "registry.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        read_nwbfile = io.read()
        table = read_nwbfile.electrodes.to_dataframe()
        assert table["impedance"].tolist() == [1.0, 2.0, 3.0, 4.0]
        assert table["electrode_name"].tolist() == ["0", "1", "2", "3"]
        assert table["group_name"].tolist() == ["0", "0", "1", "1"]
        assert read_nwbfile.acquisition["ElectricalSeries"].electrodes.data[:].tolist() == [0, 1, 2, 3]
