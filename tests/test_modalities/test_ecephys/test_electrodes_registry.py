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


def _without_blanks(metadata):
    """Delete every blank the template offers, which is what a user who knows nothing more does.

    A blank left ``None`` is refused at write time, so a test that is not about the blanks deletes them
    and writes what the recording derives.
    """
    ecephys = metadata["Ecephys"]
    blank_device_keys = {key for key, entry in (metadata.get("Devices") or {}).items() if entry.get("name") is None}
    for key in blank_device_keys:
        del metadata["Devices"][key]
    for key in [key for key, entry in (metadata.get("DeviceModels") or {}).items() if entry.get("name") is None]:
        del metadata["DeviceModels"][key]
    for group in ecephys["ElectrodeGroups"].values():
        if group.get("device_metadata_key") in blank_device_keys:
            del group["device_metadata_key"]
    entries = [
        *ecephys["ElectricalSeries"].values(),
        *ecephys["ElectrodeGroups"].values(),
        *ecephys["ElectrodesTable"]["rows"].values(),
        *ecephys["ElectrodesTable"]["columns"].values(),
    ]
    for entry in entries:
        for field in [field for field, value in entry.items() if value is None]:
            del entry[field]
    return metadata


class TestTemplate:
    """What ``get_metadata_template`` states, and that it states the table the writer would derive."""

    def test_every_electrode_is_stated_once(self):
        interface = _interface(num_channels=4, groups=[0, 0, 1, 1])
        metadata = _without_blanks(interface.get_metadata_template())

        assert list(metadata["Ecephys"]["ElectrodesTable"]["rows"]) == ["0_0", "0_1", "1_2", "1_3"]
        assert list(metadata["Ecephys"]["ElectrodeGroups"]) == ["0", "1"]
        first_entry = metadata["Ecephys"]["ElectrodesTable"]["rows"]["0_0"]
        assert first_entry["electrode_group_metadata_key"] == "0"
        # No probe, so no contact to name: the channel carries the identity and the row says nothing
        # about an electrode it cannot name.
        assert "electrode_name" not in first_entry

    def test_keys_and_values_are_plain_python(self):
        """A registry is validated as JSON and written to YAML, so a numpy scalar cannot reach it."""
        interface = _interface(properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        metadata = _without_blanks(interface.get_metadata_template())

        assert all(type(key) is str for key in metadata["Ecephys"]["ElectrodesTable"]["rows"])
        for entry in metadata["Ecephys"]["ElectrodesTable"]["rows"].values():
            assert all(not isinstance(value, np.generic) for value in entry.values())
        json.dumps(metadata["Ecephys"]["ElectrodesTable"]["rows"])

    def test_the_channel_to_electrode_map_covers_every_channel(self):
        interface = _interface(num_channels=4)
        metadata = _without_blanks(interface.get_metadata_template())

        mapping = metadata["Ecephys"]["ElectricalSeries"][interface.metadata_key]["channel_to_electrode"]
        assert set(mapping) == {str(channel_id) for channel_id in interface.channel_ids}
        assert set(mapping.values()) == set(metadata["Ecephys"]["ElectrodesTable"]["rows"])

    def test_it_validates_against_the_interface_schema_once_the_blanks_are_gone(self):
        interface = _interface(properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        metadata = _without_blanks(interface.get_metadata_template())
        metadata["NWBFile"]["session_start_time"] = "2020-01-01T00:00:00"

        interface.validate_metadata(metadata=metadata)

    def test_what_only_the_experimenter_can_supply_is_left_blank(self):
        """The blanks are the checklist: what comes back ``None`` is what the source could not say."""
        interface = _interface(num_channels=4, properties={"imp": [1.0, 2.0, 3.0, 4.0], "quality": ["good"] * 4})
        metadata = interface.get_metadata_template()
        ecephys = metadata["Ecephys"]

        assert ecephys["ElectricalSeries"][interface.metadata_key]["description"] is None
        assert ecephys["ElectrodeGroups"]["ElectrodeGroup"] == {
            "name": "ElectrodeGroup",
            "description": None,
            "location": None,
            "device_metadata_key": "probe",
        }
        assert metadata["Devices"]["probe"] == {
            "name": None,
            "description": None,
            "serial_number": None,
            "device_model_metadata_key": "probe_model",
        }
        assert metadata["DeviceModels"]["probe_model"] == {
            "name": None,
            "manufacturer": None,
            "model_number": None,
            "description": None,
        }
        # What the recording carries is filled; ``location``, which NWB requires, and the other columns
        # the schema defines are offered blank.
        assert ecephys["ElectrodesTable"]["rows"]["ElectrodeGroup_0"] == {
            "electrode_group_metadata_key": "ElectrodeGroup",
            "imp": 1.0,
            "quality": "good",
            "location": None,
            "x": None,
            "y": None,
            "z": None,
            "rel_x": None,
            "rel_y": None,
            "rel_z": None,
            "filtering": None,
        }
        # A column NWB predefines carries pynwb's own description; one of the recording's own has nothing
        # to say about itself.
        assert ecephys["ElectrodesTable"]["columns"]["imp"]["description"] == "Impedance of the channel, in ohms."
        assert ecephys["ElectrodesTable"]["columns"]["quality"] == {"column_name": "quality", "description": None}

    def test_a_blank_left_in_place_is_refused(self):
        """The template must fail as returned, and say which blank it is failing on."""
        from jsonschema.exceptions import ValidationError

        interface = _interface(num_channels=4, properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        metadata = interface.get_metadata_template()
        metadata["NWBFile"]["session_start_time"] = "2020-01-01T00:00:00"
        with pytest.raises(ValidationError):
            interface.validate_metadata(metadata=metadata)

        metadata = _without_blanks(interface.get_metadata_template())
        metadata["Ecephys"]["ElectrodesTable"]["rows"]["ElectrodeGroup_0"]["location"] = None
        with pytest.raises(ValueError, match="leaves 'location' blank"):
            interface.create_nwbfile(metadata=metadata)

        metadata = _without_blanks(interface.get_metadata_template())
        metadata["Ecephys"]["ElectrodesTable"]["columns"]["imp"]["description"] = None
        with pytest.raises(ValueError, match="leaves 'description' blank"):
            interface.create_nwbfile(metadata=metadata)

        metadata = _without_blanks(interface.get_metadata_template())
        metadata["Ecephys"]["ElectricalSeries"][interface.metadata_key]["description"] = None
        with pytest.raises(ValueError, match="leaves \\['description'\\] blank"):
            interface.create_nwbfile(metadata=metadata)

        metadata = _without_blanks(interface.get_metadata_template())
        metadata["Ecephys"]["ElectrodeGroups"]["ElectrodeGroup"]["location"] = None
        with pytest.raises(ValueError, match="leaves \\['location'\\] blank"):
            interface.create_nwbfile(metadata=metadata)

    def test_an_attached_probe_prefills_the_device(self):
        """A probe that names its model is what the writer would fall to, so the template states it."""
        from probeinterface import Probe

        interface = _interface(num_channels=4)
        probe = Probe(ndim=2, si_units="um")
        probe.set_contacts(
            positions=np.array([[0, 0], [0, 20], [0, 40], [0, 60]]), shapes="circle", shape_params={"radius": 5}
        )
        probe.set_contact_ids(["e0", "e1", "e2", "e3"])
        probe.annotate(model_name="ASSY-156-P-1", manufacturer="cambridgeneurotech")
        probe.set_device_channel_indices(np.arange(4))
        interface.set_probe(probe, group_mode="by_probe")

        metadata = interface.get_metadata_template()

        assert metadata["Devices"]["probe"] == {
            "name": "ProbeASSY-156-P-1",
            "device_model_metadata_key": "cambridgeneurotech_ASSY-156-P-1",
        }
        assert metadata["DeviceModels"]["cambridgeneurotech_ASSY-156-P-1"] == {
            "name": "ASSY-156-P-1",
            "model_number": "ASSY-156-P-1",
            "manufacturer": "cambridgeneurotech",
        }
        assert metadata["Ecephys"]["ElectrodeGroups"]["0"]["device_metadata_key"] == "probe"

        nwbfile = interface.create_nwbfile(metadata=_without_blanks(metadata))
        assert list(nwbfile.devices) == ["ProbeASSY-156-P-1"]
        assert nwbfile.devices["ProbeASSY-156-P-1"].model.manufacturer == "cambridgeneurotech"

    def test_a_column_description_the_interface_already_supplies_is_carried_over(self):
        """Stating the table must not silently downgrade what the interface already said about it."""
        interface = _interface(properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        interface.get_metadata = lambda: _with_column_descriptions(
            MockRecordingInterface.get_metadata(interface),
            [{"name": "imp", "description": "Impedance in ohms."}],
        )

        metadata = _without_blanks(interface.get_metadata_template())

        assert metadata["Ecephys"]["ElectrodesTable"]["columns"]["imp"]["description"] == "Impedance in ohms."
        nwbfile = interface.create_nwbfile(metadata=metadata)
        assert nwbfile.electrodes["imp"].description == "Impedance in ohms."

    def test_a_group_the_interface_already_describes_is_kept(self):
        """Stating the table must not lose the device link and description an interface emits for a group.

        SpikeGLX and Intan both describe their groups in ``get_metadata``, and the first version of the
        template replaced those entries with placeholders, so a file written from it lost the device.
        """
        interface = _interface(num_channels=4, groups=[0, 0, 1, 1])

        def get_metadata():
            metadata = MockRecordingInterface.get_metadata(interface)
            metadata["Devices"] = {"headstage": {"name": "MyProbe", "description": "The probe the header names."}}
            metadata["Ecephys"]["ElectrodeGroups"] = {
                "port_0": {"name": "0", "description": "Headstage port 0.", "device_metadata_key": "headstage"},
            }
            return metadata

        interface.get_metadata = get_metadata
        metadata = interface.get_metadata_template()

        groups = metadata["Ecephys"]["ElectrodeGroups"]
        assert groups["port_0"] == {
            "name": "0",
            "description": "Headstage port 0.",
            "device_metadata_key": "headstage",
            "location": None,
        }
        assert groups["1"] == {"name": "1", "description": None, "location": None, "device_metadata_key": "probe"}
        assert set(metadata["Devices"]) == {"headstage", "probe"}
        rows = metadata["Ecephys"]["ElectrodesTable"]["rows"]
        assert [entry["electrode_group_metadata_key"] for entry in rows.values()] == ["port_0", "port_0", "1", "1"]

        nwbfile = interface.create_nwbfile(metadata=_without_blanks(metadata))
        assert nwbfile.electrode_groups["0"].device.name == "MyProbe"
        assert nwbfile.electrode_groups["0"].description == "Headstage port 0."

    def test_writing_the_template_reproduces_the_derived_table(self):
        """The template states the table the writer would derive, so with its blanks deleted it changes nothing."""
        properties = {
            "imp": [1.0, 2.0, 3.0, 4.0],
            "shank": np.array([0, 1, 0, 1], dtype="int32"),
            "port": ["A", "A", "B", "B"],
            "coords": np.arange(8, dtype="float64").reshape(4, 2),
        }
        stated = _interface(num_channels=4, groups=[0, 0, 1, 1], properties=properties)
        derived = _interface(num_channels=4, groups=[0, 0, 1, 1], properties=properties)

        from_template = stated.create_nwbfile(metadata=_without_blanks(stated.get_metadata_template()))
        from_recording = derived.create_nwbfile()

        assert from_template.electrodes.colnames == from_recording.electrodes.colnames
        for column_name in from_recording.electrodes.colnames:
            if column_name == "group":
                continue
            np.testing.assert_array_equal(
                np.asarray(from_template.electrodes[column_name][:]),
                np.asarray(from_recording.electrodes[column_name][:]),
                err_msg=column_name,
            )
            assert np.asarray(from_template.electrodes[column_name][:]).dtype == (
                np.asarray(from_recording.electrodes[column_name][:]).dtype
            ), column_name
        assert list(from_template.electrodes["group_name"][:]) == list(from_recording.electrodes["group_name"][:])
        assert sorted(from_template.electrode_groups) == sorted(from_recording.electrode_groups)


class TestRegistryWrites:
    def test_the_group_link_is_the_only_thing_that_decides_a_row_s_group(self):
        """Regrouping in metadata, with no ``set_property`` on the recording.

        This is what the registry exists for: the recording reports one channel group and the file gets
        two electrode groups, because the rows say so.
        """
        interface = _interface(num_channels=4, groups=[0, 0, 0, 0])
        metadata = _without_blanks(interface.get_metadata_template())
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

    def test_row_order_is_channel_order_with_the_declared_rows_after_it(self):
        """The recording is the spine of the table, so reordering a stated block does not reorder it."""
        interface = _interface(num_channels=4)
        metadata = _without_blanks(interface.get_metadata_template())
        registry = metadata["Ecephys"]["ElectrodesTable"]["rows"]
        metadata["Ecephys"]["ElectrodesTable"]["rows"] = {key: registry[key] for key in reversed(list(registry))}
        metadata["Ecephys"]["ElectrodesTable"]["rows"]["spare"] = {"electrode_group_metadata_key": "ElectrodeGroup"}

        nwbfile = interface.create_nwbfile(metadata=metadata)

        assert list(nwbfile.electrodes["channel_name"][:]) == ["0", "1", "2", "3", ""]
        assert nwbfile.acquisition["ElectricalSeries"].electrodes.data[:] == [0, 1, 2, 3]

    def test_a_row_states_one_column_and_the_recording_supplies_the_rest(self):
        """What ``add_recording_to_nwbfile`` on its own needs: annotate one cell, keep every other."""
        interface = _interface(num_channels=4, properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        metadata = interface.get_metadata()
        metadata["Ecephys"]["ElectrodesTable"] = {"rows": {"ElectrodeGroup_2": {"brain_area": "CA1"}}}

        nwbfile = interface.create_nwbfile(metadata=metadata)

        assert list(nwbfile.electrodes["imp"][:]) == [1.0, 2.0, 3.0, 4.0]
        assert list(nwbfile.electrodes["brain_area"][:]) == ["", "", "CA1", ""]

    def test_a_row_the_metadata_does_not_state_comes_from_the_recording(self):
        interface = _interface(num_channels=4, properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        metadata = _without_blanks(interface.get_metadata_template())
        del metadata["Ecephys"]["ElectrodesTable"]["rows"]["ElectrodeGroup_2"]

        nwbfile = interface.create_nwbfile(metadata=metadata)

        assert len(nwbfile.electrodes) == 4
        assert list(nwbfile.electrodes["imp"][:]) == [1.0, 2.0, 3.0, 4.0]

    def test_a_declared_electrode_no_channel_references_is_still_written(self):
        interface = _interface(num_channels=4)
        metadata = _without_blanks(interface.get_metadata_template())
        interface.remove_channels(channel_ids=list(interface.channel_ids)[2:])

        nwbfile = interface.create_nwbfile(metadata=metadata)

        assert len(nwbfile.electrodes) == 4
        assert nwbfile.acquisition["ElectricalSeries"].electrodes.data[:] == [0, 1]
        # Nothing supplied a channel name for the rows this recording does not reach.
        assert list(nwbfile.electrodes["channel_name"][:]) == ["0", "1", "", ""]

    def test_channel_to_electrode_decides_which_row_a_channel_reaches(self):
        interface = _interface(num_channels=4)
        metadata = _without_blanks(interface.get_metadata_template())
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
        metadata = _without_blanks(interface.get_metadata_template())
        # Stated rather than deleted: a row that says nothing about a column inherits the recording's value,
        # so stating the null is how a row says it has none.
        metadata["Ecephys"]["ElectrodesTable"]["rows"]["ElectrodeGroup_2"]["imp"] = None

        nwbfile = interface.create_nwbfile(metadata=metadata)

        impedances = list(nwbfile.electrodes["imp"][:])
        assert impedances[:2] == [1.0, 2.0]
        assert np.isnan(impedances[2])
        assert impedances[3] == 4.0

    def test_a_multi_dimensional_column_keeps_its_shape(self):
        interface = _interface(num_channels=4)
        interface.recording_extractor.set_property("coords", np.arange(8, dtype="float64").reshape(4, 2))
        metadata = _without_blanks(interface.get_metadata_template())
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
        metadata = _without_blanks(interface.get_metadata_template())

        stated = interface.create_nwbfile(metadata=metadata)

        derived_interface = _interface(num_channels=4)
        derived_interface.recording_extractor.set_property("neighbors", ragged)
        derived = derived_interface.create_nwbfile()

        assert [list(value) for value in stated.electrodes["neighbors"][:]] == [[1], [1, 2], [1, 2, 3], []]
        assert [list(value) for value in stated.electrodes["neighbors"][:]] == [
            list(value) for value in derived.electrodes["neighbors"][:]
        ]


class TestElectrodeColumns:
    def test_a_column_nwb_predefines_gets_pynwb_s_description(self):
        """Whether the table is derived or stated, ``imp`` says what pynwb says and not "no description"."""
        derived = _interface(properties={"imp": [1.0, 2.0, 3.0, 4.0]}).create_nwbfile()
        stated_interface = _interface(properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        stated = stated_interface.create_nwbfile(metadata=_without_blanks(stated_interface.get_metadata_template()))

        for nwbfile in (derived, stated):
            assert nwbfile.electrodes["imp"].description == "Impedance of the channel, in ohms."
            assert nwbfile.electrodes["location"].description == "Location of the electrode (channel)."

    def test_a_blank_electrode_name_is_a_row_with_no_contact(self):
        """The contact identifier is the format's, never the experimenter's, so ``None`` reads as absent."""
        interface = _interface(num_channels=4)
        metadata = _without_blanks(interface.get_metadata_template())
        for entry in metadata["Ecephys"]["ElectrodesTable"]["rows"].values():
            entry["electrode_name"] = None

        nwbfile = interface.create_nwbfile(metadata=metadata)

        assert "electrode_name" not in nwbfile.electrodes.colnames
        assert nwbfile.acquisition["ElectricalSeries"].electrodes.data[:] == [0, 1, 2, 3]

    def test_a_column_is_renamed_and_described(self):
        interface = _interface(properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        metadata = _without_blanks(interface.get_metadata_template())
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
        metadata = _without_blanks(interface.get_metadata_template())
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
        metadata = _without_blanks(interface.get_metadata_template())
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
        metadata = _without_blanks(interface.get_metadata_template())
        metadata["Ecephys"]["ElectrodesTable"]["columns"]["port"] = {"column_name": "port", "dtype": "float64"}

        with pytest.raises(ValueError, match="declares dtype 'float64'"):
            interface.create_nwbfile(metadata=metadata)

    def test_a_column_described_but_stated_by_no_row(self):
        """Silent otherwise: the writer only looks a description up by a field it found on a row."""
        interface = _interface(properties={"imp": [1.0, 2.0, 3.0, 4.0]})
        metadata = _without_blanks(interface.get_metadata_template())
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

        metadata = _without_blanks(raw.get_metadata_template())
        lfp_metadata = _without_blanks(lfp.get_metadata_template())
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
        metadata = _without_blanks(interface.get_metadata_template())

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
        metadata["Ecephys"].update(_without_blanks(recording_interface.get_metadata_template())["Ecephys"])
        nwbfile = converter.create_nwbfile(metadata=metadata)

        assert len(nwbfile.electrodes) == 4
        assert list(nwbfile.units["unit_name"][:]) == ["a", "b", "c"]
        # Flattened, the ragged region is one unit's rows after another, which is what the mapping asked
        # for. Every index resolves, which is the point: nothing fell back to appending a new row.
        assert list(nwbfile.units["electrodes"].target.data[:]) == [0, 1, 2, 3]

    def test_a_probes_contact_ids_do_not_capture_another_recordings_channels(self):
        """The fallback that lets a probe-less recording find a stated row must not over-match.

        A probe whose contact ids read like the next recording's channel names, in a group of the same
        name, is close enough to collide: both are '0', '1', ... by default. The row's own channel name
        is what keeps them apart.
        """
        probed = generate_recording(num_channels=4, durations=[0.1])
        probed.set_property("channel_name", np.array(["a", "b", "c", "d"]))
        assert list(probed.get_probe().contact_ids) == ["0", "1", "2", "3"]

        plain = generate_recording(num_channels=4, durations=[0.1])
        plain.delete_property("contact_vector")
        assert not plain.has_probe()

        nwbfile = mock_NWBFile()
        for recording, name in ((probed, "A"), (plain, "B")):
            add_recording_to_nwbfile(
                recording=recording,
                nwbfile=nwbfile,
                metadata={"Ecephys": {name: {"name": name}}},
                es_key=name,
                iterator_type=None,
            )

        assert len(nwbfile.electrodes) == 8
        assert list(nwbfile.acquisition["A"].electrodes.data) == [0, 1, 2, 3]
        assert list(nwbfile.acquisition["B"].electrodes.data) == [4, 5, 6, 7]


class TestRegistryValidation:
    def test_an_electrode_the_channels_resolve_to_but_nobody_declared(self):
        interface = _interface(num_channels=4)
        metadata = _without_blanks(interface.get_metadata_template())
        mapping = metadata["Ecephys"]["ElectricalSeries"][interface.metadata_key]["channel_to_electrode"]
        mapping[next(iter(mapping))] = "nobody_declared_this"

        with pytest.raises(ValueError, match="does not declare"):
            interface.create_nwbfile(metadata=metadata)

    def test_a_channel_to_electrode_map_that_misses_a_channel(self):
        interface = _interface(num_channels=4)
        metadata = _without_blanks(interface.get_metadata_template())
        mapping = metadata["Ecephys"]["ElectricalSeries"][interface.metadata_key]["channel_to_electrode"]
        del mapping[next(iter(mapping))]

        with pytest.raises(ValueError, match="does not cover every channel"):
            interface.create_nwbfile(metadata=metadata)

    @pytest.mark.parametrize("field", ["group_name", "channel_name"])
    def test_a_row_stating_a_column_the_writer_derives(self, field):
        """Silently dropping it is the failure: a user who set ``group_name`` believes the row moved."""
        interface = _interface(num_channels=4)
        metadata = _without_blanks(interface.get_metadata_template())
        metadata["Ecephys"]["ElectrodesTable"]["rows"]["ElectrodeGroup_0"][field] = "elsewhere"

        with pytest.raises(ValueError, match="which the writer derives"):
            interface.create_nwbfile(metadata=metadata)

    def test_an_electrode_stating_no_group(self):
        interface = _interface(num_channels=4)
        metadata = _without_blanks(interface.get_metadata_template())
        metadata["Ecephys"]["ElectrodesTable"]["rows"]["spare"] = {"electrode_name": "spare"}

        with pytest.raises(ValueError, match="states no 'electrode_group_metadata_key'"):
            interface.create_nwbfile(metadata=metadata)

    def test_an_electrode_pointing_at_a_group_nobody_declared(self):
        interface = _interface(num_channels=4)
        metadata = _without_blanks(interface.get_metadata_template())
        metadata["Ecephys"]["ElectrodesTable"]["rows"]["ElectrodeGroup_0"]["electrode_group_metadata_key"] = "absent"

        with pytest.raises(ValueError, match="does not declare the keys"):
            interface.create_nwbfile(metadata=metadata)

    def test_two_electrodes_describing_one_contact(self):
        interface = _interface(num_channels=4)
        metadata = _without_blanks(interface.get_metadata_template())
        metadata["Ecephys"]["ElectrodesTable"]["rows"]["ElectrodeGroup_0"]["electrode_name"] = "0"
        metadata["Ecephys"]["ElectrodesTable"]["rows"]["ElectrodeGroup_1"]["electrode_name"] = "0"

        with pytest.raises(ValueError, match="both describe the electrode named"):
            interface.create_nwbfile(metadata=metadata)

    def test_two_group_keys_sharing_a_name(self):
        interface = _interface(num_channels=4)
        metadata = _without_blanks(interface.get_metadata_template())
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
    metadata = _without_blanks(interface.get_metadata_template())
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
        assert table["channel_name"].tolist() == ["0", "1", "2", "3"]
        assert table["group_name"].tolist() == ["0", "0", "1", "1"]
        assert read_nwbfile.acquisition["ElectricalSeries"].electrodes.data[:].tolist() == [0, 1, 2, 3]
