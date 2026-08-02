"""Tests for the events half of ``SpikeGLXNIDQInterface``.

Driven through the public interface rather than through the private
``_SpikeGLXNIDQEventsInterface``, since that class is constructed by its parent and never by a user.
What is covered here is what is specific to NIDQ: the packed-word addressing (a line is word plus bit,
not a named channel), the analog channels being derivable through the same grammar, and the suppression
case that only exists because this interface writes more than events. The zero-configuration default and
the deprecated ``digital_channel_groups`` path live in ``test_nidq_interface.py`` alongside the analog
tests.

The validator's own rejections (a word spec with no ``bits``, an analog spec with no cut,
``bits`` aimed at an analog signal, a numeric ``binarize`` fan-out with no ``event_name``) are format
independent and belong on ``MockSignalEncodedEventsInterface``, which declares both kinds, rather than
here where they would need gin data to reach the same code.
"""

import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import SpikeGLXNIDQInterface

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

# Eight analog channels plus one digital word, so it exercises both kinds. The word never toggles here,
# which is why the derivation tests below use the analog channels.
BOTH_KINDS_FOLDER = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"
# One digital word carrying a real TTL train on bit 0, and no analog channels at all.
DIGITAL_ONLY_FOLDER = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"


def _events_interface(interface):
    """The private events half the public interface builds."""
    return interface._events_interface


class TestSignalInventory:
    """The inventory is what the validator gates on, and it is settled from the header alone."""

    def test_words_and_analog_channels_are_classified_from_their_names(self):
        """``XD`` is a packed word and ``XA``/``MA`` are analog, which decides which cut each admits.

        SpikeGLX saves its digital lines packed into one integer channel, so ``~snsChanMap`` lists a
        single ``XD0`` entry rather than one per line. The handle is therefore the word, and the bit
        positions it carries come from ``niXDChans1``.
        """
        interface = SpikeGLXNIDQInterface(folder_path=BOTH_KINDS_FOLDER)
        available_signals = _events_interface(interface)._available_signals

        assert available_signals["XD0"] == {
            "kind": "word",
            "channel_id": "nidq#XD0",
            "bits": [0, 1, 2, 3, 4, 5, 6, 7],
        }
        for index in range(8):
            assert available_signals[f"XA{index}"] == {"kind": "analog", "channel_id": f"nidq#XA{index}"}

    def test_the_stream_prefix_is_dropped_from_the_handle(self):
        """The handle is the board's own name, not the reader's stream-qualified channel id."""
        interface = SpikeGLXNIDQInterface(folder_path=DIGITAL_ONLY_FOLDER)
        available_signals = _events_interface(interface)._available_signals

        assert set(available_signals) == {"XD0"}
        assert available_signals["XD0"]["channel_id"] == "nidq#XD0"


class TestAnalogDerivation:
    """An analog channel is derivable through the same grammar, cut with ``binarize``."""

    def test_a_cut_is_in_stored_values_not_the_physical_unit(self):
        """The cut is compared against the samples as stored, so it is in ADC counts, not volts.

        Worth pinning because the companion `TimeSeries` this same interface writes for the same channel
        declares `unit="V"` with a conversion factor, so the two numbers differ by ~10^4 and a reader
        could reasonably assume otherwise. `signal_conditioning` is a raw-signal vocabulary throughout:
        `bits` indexes stored bit positions and `binarize` derives its cut from stored values, so
        `binarize` cutting at stored values is the consistent choice rather than an oversight.

        `XA3` here is noise spanning 167 to 561 with exactly one sample above 550, so that cut isolates a
        single excursion. An arbitrary cut (its mean, say) would derive 12636 events from noise, which
        says nothing about the path and takes a quarter of a minute to write.
        """
        counts_threshold = 550.0
        interface = SpikeGLXNIDQInterface(
            folder_path=BOTH_KINDS_FOLDER,
            detection_configuration={
                "XA3": [{"signal_conditioning": {"binarize": counts_threshold}, "detection": "high_period"}]
            },
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        # One spec on one signal, so the identifier is the handle unchanged (no fan-out suffix).
        assert set(nwbfile.events.keys()) == {"XA3"}
        crossings = nwbfile.events["XA3"]
        assert crossings.colnames == ("timestamp", "duration")
        assert len(crossings) == 1

        # On the recording's clock (t_start 5.92), not on a zero-based one, and one sample wide at
        # 11574 Hz. Both come from reading the clock at the two edges rather than assuming a period.
        assert crossings["timestamp"][0] == pytest.approx(11.1225312)
        assert crossings["duration"][0] == pytest.approx(1 / interface.recording_extractor.get_sampling_frequency())

        # The same cut in the physical unit is four orders of magnitude away, so the two readings are not
        # merely offset: passing volts here would find nothing at all rather than something slightly off.
        analog_series = nwbfile.acquisition["TimeSeriesNIDQ"]
        assert analog_series.unit == "V"
        assert counts_threshold * analog_series.conversion == pytest.approx(0.0336, abs=1e-4)

    def test_analog_and_digital_can_be_derived_together(self):
        """One configuration addresses both halves of the board, since they are one signal inventory."""
        interface = SpikeGLXNIDQInterface(
            folder_path=BOTH_KINDS_FOLDER,
            detection_configuration={
                "XA3": [{"signal_conditioning": {"binarize": 550.0}, "detection": "rising"}],
                "XD0": [{"signal_conditioning": {"bits": [0]}, "detection": "high_period"}],
            },
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert set(nwbfile.events.keys()) == {"XA3", "XD0"}
        assert len(nwbfile.events["XA3"]) == 1
        # XD0 is held at zero throughout this recording: the line existed, nothing fired.
        assert len(nwbfile.events["XD0"]) == 0


class TestSignalAddressing:
    """How a signal is named, decided from the header at construction with no sample read."""

    def test_the_readers_stream_qualified_id_is_also_accepted(self):
        """`nidq#XD0` works as well as `XD0`, because this interface's own API hands back the former.

        `get_channel_names()` returns stream-qualified ids and the released `analog_channel_groups` keys
        on them, so refusing that spelling would make the interface contradict itself. The board's own
        handle stays canonical: the derived identifier, and hence the table name, has no prefix.
        """
        interface = SpikeGLXNIDQInterface(
            folder_path=DIGITAL_ONLY_FOLDER,
            detection_configuration={"nidq#XD0": [{"signal_conditioning": {"bits": [0]}, "detection": "rising"}]},
        )
        assert "nidq#XD0" in interface.get_channel_names()  # the spelling the user would have on hand

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
        assert set(nwbfile.events.keys()) == {"XD0"}

    def test_giving_one_signal_under_both_spellings_is_refused(self):
        """The two spellings collapse to one key, so accepting both would drop one entry in silence."""
        with pytest.raises(ValueError, match="names the signal 'XD0' twice"):
            SpikeGLXNIDQInterface(
                folder_path=DIGITAL_ONLY_FOLDER,
                detection_configuration={
                    "nidq#XD0": [{"signal_conditioning": {"bits": [0]}, "detection": "rising"}],
                    "XD0": [{"signal_conditioning": {"bits": [1]}, "detection": "rising"}],
                },
            )


class TestSuppression:
    """``{}`` is the reason an empty configuration is allowed rather than refused."""

    def test_empty_configuration_keeps_the_analog_and_writes_no_events(self):
        """The case a pure events interface cannot have: keep the rest of the board, skip the events.

        A converter builds this interface for you, so dropping it is not an option; ``{}`` is how you
        say "analog yes, events no", matching what ``analog_channel_groups={}`` already means.
        """
        interface = SpikeGLXNIDQInterface(folder_path=BOTH_KINDS_FOLDER, detection_configuration={})

        metadata = interface.get_metadata()
        assert "Events" not in metadata  # no empty block seeded either

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert set(nwbfile.acquisition) == {"TimeSeriesNIDQ"}
        assert not nwbfile.events
