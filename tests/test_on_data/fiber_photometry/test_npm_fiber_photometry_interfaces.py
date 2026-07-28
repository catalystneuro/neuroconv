"""On-data tests for the Neurophotometrics (NPM) fiber photometry interface.

The NPM interface is a thin wrapper over :class:`.CSVFiberPhotometryInterface`: it auto-detects the
``Flags``/``LedState`` column, masks its three lowest bits to the excitation LED, and reads the one
channel matching a given ``excitation_wavelength_in_nm``.

The gin fixtures under ``fiber_photometry_datasets/NPM`` are one directory per format property, and
this module is organized to match, one round-trip class per fixture and channel:

- ``header_and_state_column`` -- named columns, ``Flags`` 16/17/18, one ``Timestamp`` in seconds.
- ``multi_timestamp`` -- ``LedState`` naming, short ``G0``-``G3`` regions, two clocks and no
  ``Timestamp`` column, so the timestamps column must be chosen explicitly.
- ``multi_led_state_per_wavelength`` -- one excitation written under two state values (415 nm as both
  17 and 273), which is what the bit masking exists for.
- ``multi_wavelength_per_led_state`` -- the inverse: ``LedState`` 6 is 470 nm and 560 nm strobed in one
  frame, landing in different columns, so that frame belongs to both channels.
- ``red_and_green_emission`` -- three excitations and both emission bands as columns.
- ``startup_state_zero`` -- a startup frame coded 0 rather than 7 or 16.
- ``multiplexed_by_file`` -- one excitation per file, on two time axes that never coincide.
- ``no_header_no_state_column`` -- no state column at all, so the NPM interface rejects it (it belongs
  to ``CSVFiberPhotometryInterface`` with a stride demux).

Each round-trip is validated end-to-end through ``FiberPhotometryInterfaceTestMixin`` against literals
read off the file by hand. The fixtures are already stubbed to a few dozen frames, so each conversion
writes the whole recording and the expected arrays are the whole channel rather than a leading window.
Every recording's timestamps are irregular (real acquisition), so each series is written with an
explicit timestamps array rather than a rate. Construction/validation error paths, which the mixin
cannot express, live in a dedicated plain class.
"""

import numpy as np
import pytest
from pydantic import ValidationError

from neuroconv.datainterfaces import (
    NPMFiberPhotometryInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    FiberPhotometryInterfaceTestMixin,
)

try:
    from ..setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH

NPM_DATA_PATH = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "NPM"

HEADER_AND_STATE_COLUMN_FILE = str(NPM_DATA_PATH / "header_and_state_column" / "three_green_regions.csv")
MULTI_TIMESTAMP_FILE = str(NPM_DATA_PATH / "multi_timestamp" / "signals.csv")
MULTI_LED_STATE_PER_WAVELENGTH_FILE = str(
    NPM_DATA_PATH / "multi_led_state_per_wavelength" / "digital_input_transition.csv"
)
MULTI_WAVELENGTH_PER_LED_STATE_FILE = str(
    NPM_DATA_PATH / "multi_wavelength_per_led_state" / "simultaneous_470_and_560.csv"
)
RED_AND_GREEN_EMISSION_FILE = str(NPM_DATA_PATH / "red_and_green_emission" / "two_fiber_dual_color.csv")
STARTUP_STATE_ZERO_FILE = str(NPM_DATA_PATH / "startup_state_zero" / "one_fiber_dual_color.csv")
MULTIPLEXED_BY_FILE_415 = str(NPM_DATA_PATH / "multiplexed_by_file" / "FiberData415.csv")
MULTIPLEXED_BY_FILE_470 = str(NPM_DATA_PATH / "multiplexed_by_file" / "FiberData470.csv")
NO_HEADER_NO_STATE_COLUMN_FILE = str(NPM_DATA_PATH / "no_header_no_state_column" / "three_regions_milliseconds.csv")


class TestNPMHeaderAndStateColumnIsosbestic(FiberPhotometryInterfaceTestMixin):
    """Round-trip the 415 nm (isosbestic) channel of the headered, ``Flags``-labeled recording."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=HEADER_AND_STATE_COLUMN_FILE,
        excitation_wavelength_in_nm=415,
        data_columns="Region0G",
        metadata_key="isosbestic_region0",
    )
    save_directory = OUTPUT_PATH

    # The 20 Region0G samples of the 415 nm (Flags==17) channel; the Flags==16 startup frame is dropped.
    expected_response_series_data = np.array(
        [
            0.0039288397682929,
            0.0039215686274509,
            0.003860975787101,
            0.003856128359873,
            0.003844009791803,
            0.003851280932645,
            0.003846433505417,
            0.003831891223733,
            0.003851280932645,
            0.003860975787101,
            0.003817348942049,
            0.003836738650961,
            0.003834314937347,
            0.003856128359873,
            0.003853704646259,
            0.003831891223733,
            0.003824620082891,
            0.003851280932645,
            0.003851280932645,
            0.003851280932645,
        ]
    )
    expected_timestamps = np.array(
        [
            24106.962496,
            24107.012512,
            24107.062496,
            24107.112512,
            24107.162528,
            24107.212512,
            24107.262528,
            24107.312512,
            24107.362496,
            24107.412512,
            24107.462496,
            24107.512512,
            24107.562528,
            24107.612512,
            24107.662528,
            24107.712512,
            24107.762496,
            24107.812512,
            24107.862496,
            24107.912512,
        ]
    )

    def test_get_available_excitation_wavelengths(self):
        """The single-LED wavelengths are surfaced; the no-LED startup frame (Flags 16) is not."""
        assert self.data_interface_cls.get_available_excitation_wavelengths(HEADER_AND_STATE_COLUMN_FILE) == [415, 470]


class TestNPMHeaderAndStateColumnSignal(FiberPhotometryInterfaceTestMixin):
    """Round-trip the 470 nm (signal) channel of the same recording -- a different channel and timebase,
    selecting the Flags==18 rows."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=HEADER_AND_STATE_COLUMN_FILE,
        excitation_wavelength_in_nm=470,
        data_columns="Region0G",
        metadata_key="signal_region0",
    )
    save_directory = OUTPUT_PATH

    # The 20 Region0G samples of the 470 nm (Flags==18) channel, interleaved with the 415 nm frames above.
    expected_response_series_data = np.array(
        [
            0.00762985045687,
            0.007620155602414,
            0.007620155602414,
            0.0071596500157541,
            0.0071644974429821,
            0.0071620737293681,
            0.0071644974429821,
            0.0071960057199641,
            0.0071523788749121,
            0.0071717685838241,
            0.0071426840204561,
            0.0071596500157541,
            0.0071911582927361,
            0.0071572263021401,
            0.0071548025885261,
            0.0071596500157541,
            0.0071548025885261,
            0.0071863108655081,
            0.0071475314476841,
            0.0071475314476841,
        ]
    )
    expected_timestamps = np.array(
        [
            24106.937504,
            24106.98752,
            24107.037504,
            24107.08752,
            24107.137504,
            24107.18752,
            24107.237504,
            24107.28752,
            24107.337504,
            24107.38752,
            24107.437504,
            24107.48752,
            24107.537504,
            24107.58752,
            24107.637504,
            24107.68752,
            24107.737504,
            24107.78752,
            24107.837504,
            24107.88752,
        ]
    )


class TestNPMHeaderAndStateColumnMultiRegion(FiberPhotometryInterfaceTestMixin):
    """Round-trip all three region columns of one channel column-stacked into one multi-channel series."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=HEADER_AND_STATE_COLUMN_FILE,
        excitation_wavelength_in_nm=415,
        data_columns=["Region0G", "Region1G", "Region2G"],
        metadata_key="isosbestic_all_regions",
    )
    save_directory = OUTPUT_PATH

    # [Region0G, Region1G, Region2G] for the 415 nm channel, in column order.
    expected_response_series_data = np.array(
        [
            [0.0039288397682929, 0.0039264160546789, 0.0076003514613392],
            [0.0039215686274509, 0.0039264160546789, 0.0075517943026267],
            [0.003860975787101, 0.0038706706415569, 0.0072905105438401],
            [0.003856128359873, 0.0038706706415569, 0.0072234554199038],
            [0.003844009791803, 0.0038658232143289, 0.0071679615242323],
            [0.003851280932645, 0.0038876366368549, 0.006989918608953],
            [0.003846433505417, 0.003863399500715, 0.0069575471698113],
            [0.003831891223733, 0.003846433505417, 0.0069367369589345],
            [0.003851280932645, 0.0038779417823989, 0.0068534961154273],
            [0.003860975787101, 0.0038706706415569, 0.0068257491675915],
            [0.003817348942049, 0.0038803654960129, 0.0067563817980022],
            [0.003836738650961, 0.0038682469279429, 0.0065875878653348],
            [0.003834314937347, 0.003858552073487, 0.0064927857935627],
            [0.003856128359873, 0.0038682469279429, 0.0064927857935627],
            [0.003853704646259, 0.0038682469279429, 0.0064280429152793],
            [0.003831891223733, 0.003844009791803, 0.0063771735109138],
            [0.003824620082891, 0.0038803654960129, 0.0062638734739178],
            [0.003851280932645, 0.003856128359873, 0.0062060673325934],
            [0.003851280932645, 0.003863399500715, 0.0060765815760266],
            [0.003851280932645, 0.003863399500715, 0.0060418978912319],
        ]
    )
    expected_timestamps = np.array(
        [
            24106.962496,
            24107.012512,
            24107.062496,
            24107.112512,
            24107.162528,
            24107.212512,
            24107.262528,
            24107.312512,
            24107.362496,
            24107.412512,
            24107.462496,
            24107.512512,
            24107.562528,
            24107.612512,
            24107.662528,
            24107.712512,
            24107.762496,
            24107.812512,
            24107.862496,
            24107.912512,
        ]
    )


class TestNPMMultiTimestampSystemClock(FiberPhotometryInterfaceTestMixin):
    """Round-trip the 415 nm channel of the two-clock recording, choosing an explicit ``SystemTimestamp``.

    Also exercises ``LedState`` (vs ``Flags``) detection, the short ``G0``-``G3`` region naming, and the
    ``timestamps_column`` selection this file requires (it has no default ``Timestamp`` column)."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=MULTI_TIMESTAMP_FILE,
        excitation_wavelength_in_nm=415,
        data_columns="G0",
        timestamps_column="SystemTimestamp",
        metadata_key="isosbestic_g0",
    )
    save_directory = OUTPUT_PATH

    # The 20 G0 samples of the 415 nm (LedState==1) channel and their SystemTimestamp values (seconds).
    expected_response_series_data = np.array(
        [
            0.0771836007130125,
            0.0790616246498599,
            0.0791030048382989,
            0.0790839062897886,
            0.0789618877854172,
            0.0786998132586368,
            0.0787772684831508,
            0.0785671844495374,
            0.0787422544775486,
            0.0785852219675749,
            0.0785491469314999,
            0.0785512689924455,
            0.0785565741448094,
            0.0783730158730159,
            0.0785014005602241,
            0.0784621424327307,
            0.0784377387318564,
            0.078398480604363,
            0.0783857482386894,
            0.0783454290807232,
        ]
    )
    expected_timestamps = np.array(
        [
            1800.69552,
            1800.820544,
            1800.945536,
            1801.070528,
            1801.19552,
            1801.320544,
            1801.445536,
            1801.570528,
            1801.69552,
            1801.820544,
            1801.945536,
            1802.070496,
            1802.195488,
            1802.320512,
            1802.445504,
            1802.570496,
            1802.695488,
            1802.82048,
            1802.945504,
            1803.070496,
        ]
    )

    def test_ledstate_detection_excludes_all_leds_frame(self):
        """The state column is found whether named ``Flags`` or ``LedState``; the all-LEDs frame
        (LedState 7) is not a single-LED channel and is left out."""
        assert self.data_interface_cls.get_available_excitation_wavelengths(MULTI_TIMESTAMP_FILE) == [415, 470]

    def test_computer_timestamp_column_is_used(self):
        """An explicit ``ComputerTimestamp`` selects that column instead of ``SystemTimestamp``."""
        interface = self.data_interface_cls(
            file_path=MULTI_TIMESTAMP_FILE,
            excitation_wavelength_in_nm=415,
            data_columns="G0",
            timestamps_column="ComputerTimestamp",
        )
        # The ComputerTimestamp values of the same 20 rows the SystemTimestamp run above reads.
        np.testing.assert_array_equal(
            interface.get_original_timestamps(),
            np.array(
                [
                    35205063.952,
                    35205189.0654,
                    35205313.9613,
                    35205437.7307,
                    35205562.0603,
                    35205687.7617,
                    35205813.4242,
                    35205939.0534,
                    35206062.7216,
                    35206188.4197,
                    35206313.0116,
                    35206438.6732,
                    35206562.3455,
                    35206687.9764,
                    35206813.6738,
                    35206937.3426,
                    35207062.9684,
                    35207188.6684,
                    35207312.3412,
                    35207437.9666,
                ]
            ),
        )

    def test_default_timestamp_column_missing_fails_loudly(self):
        """This file has no ``Timestamp`` column, so the default fails loudly at construction."""
        with pytest.raises(AssertionError, match="Timestamp"):
            self.data_interface_cls(file_path=MULTI_TIMESTAMP_FILE, excitation_wavelength_in_nm=415, data_columns="G0")


class TestNPMMultiLedStatePerWavelength(FiberPhotometryInterfaceTestMixin):
    """Round-trip a channel written under two different state values (415 nm as both Flags 17 and 273).

    The window spans the moment a digital input goes high, which moves the bits above the excitation
    without changing the excitation itself. The expected 30 samples are the 15 Flags==17 frames followed
    by the 15 Flags==273 ones: matching the raw state value instead of the masked one returns half the
    channel, and no single value returns all of it."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=MULTI_LED_STATE_PER_WAVELENGTH_FILE,
        excitation_wavelength_in_nm=415,
        data_columns="Region0G",
        metadata_key="isosbestic_region0",
    )
    save_directory = OUTPUT_PATH

    # The 30 Region0G samples of the 415 nm channel; the digital input goes high at the 16th.
    expected_response_series_data = np.array(
        [
            0.003793111805909,
            0.003759179815313,
            0.003744637533629,
            0.003713129256647,
            0.003747061247243,
            0.003722824111103,
            0.003739790106401,
            0.003749484960857,
            0.003761603528927,
            0.003751908674471,
            0.003749484960857,
            0.003771298383383,
            0.003742213820015,
            0.003744637533629,
            0.003725247824717,
            0.003744637533629,
            0.003737366392787,
            0.003744637533629,
            0.003764027242541,
            0.003761603528927,
            0.003759179815313,
            0.003759179815313,
            0.003744637533629,
            0.003766450956155,
            0.003742213820015,
            0.003742213820015,
            0.003764027242541,
            0.003754332388085,
            0.003747061247243,
            0.003756756101699,
        ]
    )
    expected_timestamps = np.array(
        [
            24232.96384,
            24233.013856,
            24233.06384,
            24233.113856,
            24233.163872,
            24233.213856,
            24233.263872,
            24233.313856,
            24233.36384,
            24233.413856,
            24233.46384,
            24233.513856,
            24233.563872,
            24233.613856,
            24233.663872,
            24233.713856,
            24233.76384,
            24233.813856,
            24233.86384,
            24233.913856,
            24233.963872,
            24234.013856,
            24234.063872,
            24234.113856,
            24234.16384,
            24234.213856,
            24234.26384,
            24234.313856,
            24234.363872,
            24234.413856,
        ]
    )


class TestNPMRedAndGreenEmissionRed(FiberPhotometryInterfaceTestMixin):
    """Round-trip the 560 nm channel's red region columns of the three-excitation recording.

    The state column holds 17/18/20 (415/470/560 with output 0 held high), so the constant bit above
    the excitation has to be masked off here too."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=RED_AND_GREEN_EMISSION_FILE,
        excitation_wavelength_in_nm=560,
        data_columns=["Region0R", "Region1R"],
        metadata_key="red_signal",
    )
    save_directory = OUTPUT_PATH

    # [Region0R, Region1R] for the 560 nm (Flags==20) channel.
    expected_response_series_data = np.array(
        [
            [0.0131822208849439, 0.0150643768661684],
            [0.0115356969727362, 0.0128430421635191],
            [0.0114771910469218, 0.0128658640953957],
            [0.0114002975444227, 0.0127422452977311],
            [0.0113702087825753, 0.0127878891614842],
            [0.0113451348143691, 0.0126718776744451],
            [0.0113434632164886, 0.0126794849850707],
            [0.0113668655868144, 0.0127004050892908],
            [0.0113183892482824, 0.0127023069169472],
            [0.0114119987295856, 0.0126889941233525],
            [0.011385253163499, 0.012721325193511],
            [0.0113785667719773, 0.0126623685361633],
            [0.0113802383698577, 0.0127555580913258],
            [0.0113936111529011, 0.0127498526083566],
            [0.0112849572906742, 0.0127688708849204],
            [0.0113066880631195, 0.0126471539149122],
            [0.0113150460525216, 0.0126585648808505],
            [0.0113250756398041, 0.0126756813297579],
            [0.0112765993012721, 0.0126205283277229],
            [0.0113083596609999, 0.0127080123999163],
        ]
    )
    expected_timestamps = np.array(
        [
            10251.828192,
            10251.853184,
            10251.878176,
            10251.903168,
            10251.92816,
            10251.953152,
            10251.978144,
            10252.003136,
            10252.02816,
            10252.053152,
            10252.078144,
            10252.103136,
            10252.128128,
            10252.15312,
            10252.178112,
            10252.203136,
            10252.228128,
            10252.25312,
            10252.278112,
            10252.303104,
        ]
    )


class TestNPMRedAndGreenEmissionGreen(FiberPhotometryInterfaceTestMixin):
    """Round-trip the 470 nm channel's green region columns of the same three-excitation recording."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=RED_AND_GREEN_EMISSION_FILE,
        excitation_wavelength_in_nm=470,
        data_columns=["Region2G", "Region3G"],
        metadata_key="green_signal",
    )
    save_directory = OUTPUT_PATH

    # [Region2G, Region3G] for the 470 nm (Flags==18) channel.
    expected_response_series_data = np.array(
        [
            [0.0728328865058088, 0.35632614642986],
            [0.0724070861588603, 0.35454569445544],
            [0.0718936725717991, 0.351732509962262],
            [0.0716466032346808, 0.349345085723836],
            [0.071504669785698, 0.346660333043042],
            [0.0711875098564895, 0.345091001856104],
            [0.0709632199618006, 0.341512504508308],
            [0.0705198969668296, 0.337670106176163],
            [0.0701186283271128, 0.334351991132927],
            [0.0700485377350225, 0.331781595545351],
            [0.0697121028929892, 0.328285787172653],
            [0.069281045751634, 0.325514826836971],
            [0.0688324659622562, 0.321327597885273],
            [0.0687343391333298, 0.318470429894703],
            [0.0686817711892621, 0.315873644208693],
            [0.0683278136992062, 0.313320842020074],
            [0.0679791130035571, 0.309518908505529],
            [0.0674867265941229, 0.307092778789398],
            [0.0675515603918064, 0.304949902796471],
            [0.0673868475003943, 0.30231265229286],
        ]
    )
    expected_timestamps = np.array(
        [
            10251.81984,
            10251.844832,
            10251.869824,
            10251.894848,
            10251.91984,
            10251.944832,
            10251.969824,
            10251.994816,
            10252.019808,
            10252.0448,
            10252.069824,
            10252.094816,
            10252.119808,
            10252.1448,
            10252.169792,
            10252.194784,
            10252.219776,
            10252.244768,
            10252.26976,
            10252.294784,
        ]
    )

    def test_all_three_excitations_are_available(self):
        """This recording strobes three excitations, each on its own frame."""
        assert self.data_interface_cls.get_available_excitation_wavelengths(RED_AND_GREEN_EMISSION_FILE) == [
            415,
            470,
            560,
        ]


class TestNPMStartupStateZeroRed(FiberPhotometryInterfaceTestMixin):
    """Round-trip the 560 nm channel of the recording whose startup frame is coded 0 rather than 7 or 16.

    All three codings mean a frame that is not a single excitation, so keying on any particular value
    rather than on the excitation bits fails on at least one recording."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=STARTUP_STATE_ZERO_FILE,
        excitation_wavelength_in_nm=560,
        data_columns="Region0R",
        metadata_key="red_signal",
    )
    save_directory = OUTPUT_PATH

    # The 20 Region0R samples of the 560 nm (LedState==4) channel; the LedState==0 startup frame is dropped.
    expected_response_series_data = np.array(
        [
            0.0168964624736802,
            0.016521514064063,
            0.0162123215322519,
            0.0159758801843963,
            0.0157366407140808,
            0.0156415045504467,
            0.0155589599378817,
            0.0154330444271894,
            0.0155603589991116,
            0.0154778143865466,
            0.0155967345910894,
            0.0155323777745133,
            0.0157044623057928,
            0.015963288633327,
            0.0160262463886732,
            0.0159031290004407,
            0.0159604905108672,
            0.0158597581023133,
            0.0156638895301253,
            0.0156540961015159,
        ]
    )
    expected_timestamps = np.array(
        [
            6155.088512,
            6155.128512,
            6155.168512,
            6155.208512,
            6155.24848,
            6155.28848,
            6155.32848,
            6155.36848,
            6155.40848,
            6155.44848,
            6155.48848,
            6155.52848,
            6155.56848,
            6155.608448,
            6155.648448,
            6155.688448,
            6155.728448,
            6155.768448,
            6155.808448,
            6155.848448,
        ]
    )

    def test_startup_frame_is_not_a_channel(self):
        """The LedState==0 startup frame carries no excitation and is not surfaced as a channel."""
        assert self.data_interface_cls.get_available_excitation_wavelengths(STARTUP_STATE_ZERO_FILE) == [415, 470, 560]


class TestNPMStartupStateZeroGreen(FiberPhotometryInterfaceTestMixin):
    """Round-trip the 415 nm channel of the same recording, whose excitations cycle 2, 1, 4."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=STARTUP_STATE_ZERO_FILE,
        excitation_wavelength_in_nm=415,
        data_columns="Region1G",
        metadata_key="green_isosbestic",
    )
    save_directory = OUTPUT_PATH

    # The 20 Region1G samples of the 415 nm (LedState==1) channel, the second frame of each cycle.
    expected_response_series_data = np.array(
        [
            0.00403293960417445,
            0.00403949083809936,
            0.00404735231880925,
            0.0040290088638195,
            0.00403293960417445,
            0.00403293960417445,
            0.00403949083809936,
            0.00401721664275466,
            0.0040145961491847,
            0.00400149368133488,
            0.00401852688953964,
            0.00402638837024954,
            0.00402638837024954,
            0.00402507812346455,
            0.00401197565561474,
            0.00404866256559423,
            0.00402769861703452,
            0.00400280392811986,
            0.00404866256559423,
            0.00397921948599019,
        ]
    )
    expected_timestamps = np.array(
        [
            6155.075168,
            6155.115168,
            6155.155168,
            6155.195168,
            6155.235168,
            6155.275168,
            6155.315136,
            6155.355136,
            6155.395136,
            6155.435136,
            6155.475136,
            6155.515136,
            6155.555136,
            6155.595136,
            6155.635104,
            6155.675104,
            6155.715104,
            6155.755104,
            6155.795104,
            6155.835104,
        ]
    )


class TestNPMMultiplexedByFile415(FiberPhotometryInterfaceTestMixin):
    """Round-trip the 415 nm file of a recording written as one file per excitation.

    The separation already happened during acquisition, so the file holds a constant ``LedState`` of 1
    plus the shared startup frame (7), which is dropped."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=MULTIPLEXED_BY_FILE_415,
        excitation_wavelength_in_nm=415,
        data_columns=["Region0G", "Region1G"],
        metadata_key="isosbestic",
    )
    save_directory = OUTPUT_PATH

    # [Region0G, Region1G]; the LedState==7 startup frame at 7849.631552 is excluded.
    expected_response_series_data = np.array(
        [
            [0.0234150204584452, 0.00392156862745098],
            [0.022919324797982, 0.00392156862745098],
            [0.0224500271312714, 0.00392156862745098],
            [0.0220579680388735, 0.00392156862745098],
            [0.0216610204291141, 0.00392156862745098],
            [0.0213823749395046, 0.00392156862745098],
            [0.0209824942193282, 0.00392156862745098],
            [0.0207683771588915, 0.00392156862745098],
            [0.0204516012338618, 0.00392156862745098],
            [0.02029028016093, 0.00392156862745098],
            [0.0199627494977048, 0.00392156862745098],
            [0.0197320114782388, 0.00392156862745098],
            [0.0195667795914177, 0.00392156862745098],
            [0.0193291976476454, 0.00392156862745098],
            [0.0192568475906942, 0.00392156862745098],
            [0.0190916157038732, 0.00392156862745098],
            [0.0189879791358079, 0.00392156862745098],
            [0.0189586480316385, 0.00392156862745098],
            [0.0187992823656513, 0.00392156862745098],
            [0.0187259546052278, 0.00392156862745098],
            [0.0186232957406348, 0.00392156862745098],
            [0.0185284585038204, 0.00392156862745098],
            [0.0183759367621394, 0.00392156862745098],
            [0.0183172745538006, 0.00392156862745098],
            [0.0182566569385171, 0.00392156862745098],
            [0.0181735521433704, 0.00392156862745098],
            [0.0181031574933638, 0.00392156862745098],
            [0.0180914250516961, 0.00392156862745098],
            [0.0180572054301651, 0.00392156862745098],
            [0.0180542723197481, 0.00392156862745098],
            [0.0179301039787643, 0.00392156862745098],
            [0.0179242377579304, 0.00392156862745098],
            [0.0178342890384775, 0.00392156862745098],
            [0.0178225565968098, 0.00392156862745098],
            [0.0177707383127771, 0.00392156862745098],
            [0.0177785599405556, 0.00392156862745098],
            [0.0177052321801321, 0.00392156862745098],
            [0.0176719902620734, 0.00392156862745098],
            [0.0177042544766598, 0.00392156862745098],
            [0.0175859523565098, 0.00392156862745098],
        ]
    )
    expected_timestamps = np.array(
        [
            7849.648192,
            7849.664832,
            7849.681504,
            7849.698176,
            7849.714848,
            7849.73152,
            7849.74816,
            7849.764832,
            7849.781504,
            7849.798144,
            7849.814816,
            7849.831488,
            7849.84816,
            7849.8648,
            7849.881472,
            7849.898144,
            7849.914816,
            7849.931488,
            7849.948128,
            7849.9648,
            7849.981472,
            7849.998112,
            7850.014784,
            7850.031456,
            7850.048128,
            7850.064768,
            7850.08144,
            7850.098112,
            7850.114784,
            7850.131424,
            7850.148096,
            7850.164768,
            7850.18144,
            7850.19808,
            7850.214752,
            7850.231424,
            7850.248096,
            7850.264736,
            7850.281408,
            7850.29808,
        ]
    )

    def test_only_its_own_excitation_is_available(self):
        """Each file of the pair holds exactly one excitation, named in the filename and the state column."""
        assert self.data_interface_cls.get_available_excitation_wavelengths(MULTIPLEXED_BY_FILE_415) == [415]
        assert self.data_interface_cls.get_available_excitation_wavelengths(MULTIPLEXED_BY_FILE_470) == [470]


class TestNPMMultiplexedByFile470(FiberPhotometryInterfaceTestMixin):
    """Round-trip the 470 nm sibling file of the same recording.

    Its timestamps interleave with the 415 nm file's rather than coinciding: splitting a strobed
    recording by excitation splits the time axis with it, so the two files agree only on the startup
    frame despite identical row counts."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=MULTIPLEXED_BY_FILE_470,
        excitation_wavelength_in_nm=470,
        data_columns=["Region0G", "Region1G"],
        metadata_key="signal",
    )
    save_directory = OUTPUT_PATH

    # [Region0G, Region1G]; note the timestamps fall between the 415 nm file's.
    expected_response_series_data = np.array(
        [
            [0.0164293291487625, 0.00392679042322655],
            [0.0161389512174852, 0.00392679042322655],
            [0.0139410738117236, 0.00392156862745098],
            [0.0156158798597973, 0.00392548497428266],
            [0.0153714539917189, 0.00393984491266547],
            [0.0152599957958751, 0.0039346231168899],
            [0.0150097037069627, 0.00393201221900211],
            [0.0149148664701483, 0.00392809587217044],
            [0.0148073190881937, 0.00392809587217044],
            [0.0146997717062392, 0.00392809587217044],
            [0.0145149857499719, 0.00392940132111433],
            [0.0144700113902455, 0.0039346231168899],
            [0.0143331329041215, 0.00393070677005822],
            [0.0142118976735546, 0.00393201221900211],
            [0.0141268374714633, 0.00392679042322655],
            [0.0141199935471571, 0.00393070677005822],
            [0.0140202677929811, 0.00393201221900211],
            [0.0139762711367269, 0.00392809587217044],
            [0.0138794784929679, 0.00392679042322655],
            [0.0138442811679646, 0.00392417952533876],
            [0.0137504216346224, 0.00393070677005822],
            [0.0137377114894824, 0.00392809587217044],
            [0.0136829600950328, 0.00392940132111433],
            [0.0136135431484985, 0.00393070677005822],
            [0.0135431484984919, 0.00393331766794601],
            [0.0135177282082117, 0.00392679042322655],
            [0.0135470593123811, 0.00393201221900211],
            [0.013518705911684, 0.00392940132111433],
            [0.0135314160568241, 0.00393331766794601],
            [0.0135353268707134, 0.00393201221900211],
            [0.0134492889651498, 0.00392809587217044],
            [0.0134228909713973, 0.00392940132111433],
            [0.0133828051290324, 0.00392548497428266],
            [0.013453199779039, 0.00392548497428266],
            [0.0134072477158403, 0.00393070677005822],
            [0.0133104550720812, 0.0039346231168899],
            [0.0132742800436056, 0.00393070677005822],
            [0.0133114327755535, 0.00393070677005822],
            [0.0132713469331886, 0.00392940132111433],
            [0.0131550002199833, 0.00393070677005822],
        ]
    )
    expected_timestamps = np.array(
        [
            7849.639872,
            7849.656512,
            7849.673184,
            7849.689856,
            7849.706496,
            7849.723168,
            7849.73984,
            7849.75648,
            7849.773152,
            7849.789824,
            7849.806496,
            7849.823168,
            7849.839808,
            7849.85648,
            7849.873152,
            7849.889824,
            7849.906464,
            7849.923136,
            7849.939808,
            7849.956448,
            7849.97312,
            7849.989792,
            7850.006464,
            7850.023136,
            7850.039776,
            7850.056448,
            7850.07312,
            7850.089792,
            7850.106432,
            7850.123104,
            7850.139776,
            7850.156416,
            7850.173088,
            7850.18976,
            7850.206432,
            7850.223072,
            7850.239744,
            7850.256416,
            7850.273088,
            7850.28976,
        ]
    )


class TestNPMSimultaneousExcitation470(FiberPhotometryInterfaceTestMixin):
    """Round-trip the 470 nm half of a recording that strobes 470 nm and 560 nm in the same frame.

    ``LedState`` alternates 6 (470 + 560 together) and 1 (415 alone), and the file contains no 2
    anywhere. The two simultaneous excitations do not interfere because their emission bands land in
    different columns, so a single LedState==6 frame carries a valid 470 nm measurement in G0/G2 and a
    valid 560 nm measurement in R1/R3 on a shared timestamp. Matching the masked state word exactly
    would find no 470 nm rows at all here, since 6 equals neither 2 nor 4."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=MULTI_WAVELENGTH_PER_LED_STATE_FILE,
        excitation_wavelength_in_nm=470,
        data_columns=["G0", "G2"],
        timestamps_column="SystemTimestamp",
        metadata_key="green_signal",
    )
    save_directory = OUTPUT_PATH

    # [G0, G2] for the LedState==6 frames, which carry the 470 nm measurement.
    expected_response_series_data = np.array(
        [
            [0.0322489494628381, 0.0304037759441116],
            [0.0321984382961717, 0.0303739278205233],
            [0.0321609459071901, 0.0303513950299769],
            [0.0321463209166741, 0.0303377423495938],
            [0.0321254401498681, 0.0303229160863697],
            [0.0320886663297847, 0.0303190432629945],
            [0.0320819455971487, 0.0303069944791607],
            [0.0320657143938015, 0.0303067988820205],
            [0.0320139351643737, 0.0303040996414863],
            [0.0320183733840389, 0.0302867306154402],
            [0.0320105536636764, 0.0302824665977847],
            [0.0319833325830629, 0.0302713957996517],
            [0.0319287636155597, 0.0302727649796328],
            [0.0318718275975684, 0.0302608726735111],
            [0.0318712781037051, 0.0302569998501359],
            [0.0318871288882239, 0.0302466332017075],
            [0.0318681079468014, 0.0302404914515064],
            [0.0318749554857135, 0.0302368142252715],
            [0.0318660367776243, 0.0302297336087977],
            [0.0318707708786005, 0.0302332934767486],
            [0.0318886505635377, 0.0302294597728015],
            [0.0318603727639562, 0.0302302421613621],
            [0.031877111192408, 0.0302300074447939],
            [0.0318808308431751, 0.0302106824473461],
            [0.0319212820452669, 0.0302281688316764],
            [0.0319170551693952, 0.0302171371529714],
            [0.03191887272602, 0.0302139293598728],
            [0.0319245790084468, 0.030222809470036],
            [0.0319258470712083, 0.0302263302185589],
            [0.0319144767751135, 0.030214203195869],
        ]
    )
    expected_timestamps = np.array(
        [
            15964.488946287,
            15964.55459387,
            15964.620238971,
            15964.685883788,
            15964.75155078,
            15964.817196409,
            15964.882838987,
            15964.94850415,
            15965.014150268,
            15965.079798664,
            15965.145442747,
            15965.21111039,
            15965.276755289,
            15965.342400512,
            15965.408047565,
            15965.473712685,
            15965.53935803,
            15965.605002563,
            15965.670650105,
            15965.736314655,
            15965.801959878,
            15965.867604978,
            15965.933250976,
            15965.998916869,
            15966.06456437,
            15966.130209511,
            15966.195875691,
            15966.261518432,
            15966.327165038,
            15966.392810383,
        ]
    )


class TestNPMSimultaneousExcitation560(FiberPhotometryInterfaceTestMixin):
    """Round-trip the 560 nm half of the same simultaneously-strobed frames, in the red columns.

    The same rows as the 470 nm class above, on the same timestamps, read through different columns --
    which is what "one frame, two excitations" means."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=MULTI_WAVELENGTH_PER_LED_STATE_FILE,
        excitation_wavelength_in_nm=560,
        data_columns=["R1", "R3"],
        timestamps_column="SystemTimestamp",
        metadata_key="red_signal",
    )
    save_directory = OUTPUT_PATH

    # [R1, R3] for the same LedState==6 frames, sharing the timestamps of the 470 nm class above.
    expected_response_series_data = np.array(
        [
            [0.0313642447900042, 0.0340057363995777],
            [0.0313299552419325, 0.0339595754745],
            [0.0312931052230663, 0.0339335610548588],
            [0.0312910983675788, 0.0339320353971656],
            [0.0312773271868194, 0.0339236638395667],
            [0.0312574316367273, 0.0338980406142058],
            [0.0312366018608049, 0.0338895516983229],
            [0.0312340413900104, 0.0338793806470346],
            [0.0312089556964161, 0.0338620898598445],
            [0.0311877107090134, 0.0338212882964072],
            [0.0311916898190318, 0.0337943741299213],
            [0.0311786798593194, 0.0337745796993371],
            [0.0311489922384864, 0.0337350690770249],
            [0.0311189586080866, 0.0336990009643795],
            [0.0311103429698728, 0.0336920377061898],
            [0.031112384426317, 0.0336766246515452],
            [0.031103353576623, 0.0336594512226392],
            [0.0310954991594563, 0.0336430993017219],
            [0.0310831812188775, 0.0336485369022183],
            [0.0310691332304647, 0.0336497887239153],
            [0.0310813127672167, 0.0336246349316908],
            [0.0310669187692371, 0.0336325761755813],
            [0.0310827660073973, 0.0336281556802137],
            [0.0310793405126858, 0.0336136423724139],
            [0.0310861915021088, 0.0336135641335578],
            [0.0310722819175227, 0.0336062488005158],
            [0.0310850496705383, 0.0336086350856258],
            [0.0310741503691836, 0.0336007720805914],
            [0.031067576187414, 0.0336010067971595],
            [0.031063112664002, 0.033599089945186],
        ]
    )
    expected_timestamps = np.array(
        [
            15964.488946287,
            15964.55459387,
            15964.620238971,
            15964.685883788,
            15964.75155078,
            15964.817196409,
            15964.882838987,
            15964.94850415,
            15965.014150268,
            15965.079798664,
            15965.145442747,
            15965.21111039,
            15965.276755289,
            15965.342400512,
            15965.408047565,
            15965.473712685,
            15965.53935803,
            15965.605002563,
            15965.670650105,
            15965.736314655,
            15965.801959878,
            15965.867604978,
            15965.933250976,
            15965.998916869,
            15966.06456437,
            15966.130209511,
            15966.195875691,
            15966.261518432,
            15966.327165038,
            15966.392810383,
        ]
    )


class TestNPMFiberPhotometryConstruction:
    """Channel discovery and construction/validation error paths, which the round-trip mixin cannot express."""

    @pytest.mark.parametrize(
        "file_path, expected_wavelengths",
        [
            pytest.param(HEADER_AND_STATE_COLUMN_FILE, [415, 470], id="header_and_state_column"),
            pytest.param(MULTI_TIMESTAMP_FILE, [415, 470], id="multi_timestamp"),
            pytest.param(MULTI_LED_STATE_PER_WAVELENGTH_FILE, [415, 470], id="multi_led_state_per_wavelength"),
            pytest.param(RED_AND_GREEN_EMISSION_FILE, [415, 470, 560], id="red_and_green_emission"),
            pytest.param(STARTUP_STATE_ZERO_FILE, [415, 470, 560], id="startup_state_zero"),
            # The startup frame is all-bits-set, so without excluding it these would report all three.
            pytest.param(MULTIPLEXED_BY_FILE_415, [415], id="multiplexed_by_file_415"),
            pytest.param(MULTIPLEXED_BY_FILE_470, [470], id="multiplexed_by_file_470"),
            # LedState 6 is 470 nm and 560 nm strobed together, so both are present despite neither
            # ever appearing on its own.
            pytest.param(MULTI_WAVELENGTH_PER_LED_STATE_FILE, [415, 470, 560], id="multi_wavelength_per_led_state"),
        ],
    )
    def test_get_available_excitation_wavelengths(self, file_path, expected_wavelengths):
        """Every recording's channels are discoverable before construction: a wavelength is present when
        any frame has its bit set, and the leading startup frame does not count as a measurement."""
        assert NPMFiberPhotometryInterface.get_available_excitation_wavelengths(file_path) == expected_wavelengths

    def test_absent_wavelength_raises(self):
        """This recording carries only 415/470 nm, so requesting 560 nm fails loudly."""
        with pytest.raises(AssertionError, match="560 nm"):
            NPMFiberPhotometryInterface(
                file_path=HEADER_AND_STATE_COLUMN_FILE, excitation_wavelength_in_nm=560, data_columns="Region0G"
            )

    def test_unknown_wavelength_rejected(self):
        """excitation_wavelength_in_nm is a closed set; an out-of-set value is rejected up front."""
        with pytest.raises(ValidationError):
            NPMFiberPhotometryInterface(
                file_path=HEADER_AND_STATE_COLUMN_FILE, excitation_wavelength_in_nm=500, data_columns="Region0G"
            )

    def test_missing_state_column_raises(self):
        """A file without a Flags/LedState column fails loudly.

        The header-less recording has no column names at all, let alone a state column, so its rows
        carry no excitation label; it belongs to CSVFiberPhotometryInterface with a stride demux.
        """
        with pytest.raises(ValueError, match="Flags"):
            NPMFiberPhotometryInterface(
                file_path=NO_HEADER_NO_STATE_COLUMN_FILE, excitation_wavelength_in_nm=415, data_columns="Region0G"
            )
