import re
import warnings
from datetime import date, datetime

from pydantic import FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....tools import get_package
from ....utils import DeepDict

# Month abbreviations are matched against this table rather than through ``strptime("%b")``, which
# resolves them via LC_TIME and would silently fail to parse an English month name under another
# locale — dropping the birthdate on machines that are configured differently.
_MONTH_ABBREVIATIONS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _warn_unreadable(field: str, value) -> None:
    """
    Warn that a subject field was present in the header but could not be interpreted.

    "The file did not state this" and "the file stated something I could not read" are different
    situations, and only the second is the user's to act on — otherwise an exporter writing an
    unexpected format produces a silently subject-less NWB file with no indication why.
    """
    # stacklevel=3 lands on extract_subject_metadata, the innermost public caller. No fixed value can
    # point at the user's own line, because both extract_subject_metadata and get_metadata are public
    # entry points and sit at different depths; the offending value is in the message, which is the
    # actionable part.
    warnings.warn(
        f"The EDF header's {field} could not be interpreted and was left out of the NWB Subject: "
        f"{value!r}. Set metadata['Subject'] explicitly if this field matters for your conversion.",
        UserWarning,
        stacklevel=3,
    )


# Floor on a plausible birth year. This is a judgement call rather than a derived constraint: it only
# has to be low enough never to reject a real subject and high enough to catch a misread field, and
# 1850 clears both — EDF itself dates from 1992, so no subject of an EDF recording was born before it,
# while "02-MAY-0001" is plainly garbage.
_EARLIEST_PLAUSIBLE_BIRTH_YEAR = 1850


def _assemble_birthdate(year: int, month: int, day: int, tzinfo=None) -> datetime | None:
    """Build a birthdate, rejecting impossible calendar dates and implausible years."""
    if year < _EARLIEST_PLAUSIBLE_BIRTH_YEAR:
        return None
    try:
        birthdate = datetime(year=year, month=month, day=day, tzinfo=tzinfo)
    except ValueError:
        return None
    # A birthdate cannot be in the future; such a value means the field was misread, not that the
    # subject is unborn, and passing it on would put a nonsense date in the NWB file.
    now = datetime.now(tz=birthdate.tzinfo)
    return None if birthdate > now else birthdate


def _parse_birthdate(birthdate) -> datetime | None:
    """
    Coerce an EDF birthdate into a datetime, or None when it cannot be read.

    NWB's ``Subject.date_of_birth`` must be a datetime, but the readers hand the EDF+ patient field's
    birthdate back as a string — pyedflib normalizes it to ``"02 may 1951"`` — so an absent or
    unreadable value is dropped rather than passed on to pynwb.

    Accepted forms are the ``DD-MMM-YYYY`` the EDF+ spec defines for this field (in any case, and
    space- or hyphen-separated, which covers what pyedflib emits as well as a direct header read) and
    ISO ``YYYY-MM-DD``. Notably ``DD.MM.YY`` is *not*: no reader emits it for a birthdate — the
    two-digit form belongs to the header's separate ``startdate`` field — and Python's POSIX rule for
    ``%y`` maps 00-68 to the 2000s, so ``"02.05.51"`` would have become 2051, a date in the future.
    """
    # An absent field is not a problem and stays silent. Only a value that is *present* and unreadable
    # is worth telling the user about: this whole change exists because metadata was being discarded
    # without a trace, and dropping a birthdate the exporter did write would repeat that in miniature.
    if birthdate is None or (isinstance(birthdate, str) and not birthdate.strip()):
        return None

    parsed = None
    if isinstance(birthdate, date):
        # datetime is a subclass of date, so this covers both. The time of day is dropped because a
        # birthdate has none; any tzinfo is preserved rather than silently discarded.
        parsed = _assemble_birthdate(
            birthdate.year, birthdate.month, birthdate.day, tzinfo=getattr(birthdate, "tzinfo", None)
        )
    else:
        text = str(birthdate).strip()
        named_month = re.match(r"^(\d{1,2})[-\s]([A-Za-z]{3,})[-\s](\d{4})$", text)
        abbreviation = named_month.group(2)[:3].upper() if named_month else None
        if abbreviation in _MONTH_ABBREVIATIONS:
            parsed = _assemble_birthdate(
                year=int(named_month.group(3)),
                month=_MONTH_ABBREVIATIONS.index(abbreviation) + 1,
                day=int(named_month.group(1)),
            )
        elif iso := re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", text):
            parsed = _assemble_birthdate(year=int(iso.group(1)), month=int(iso.group(2)), day=int(iso.group(3)))

    if parsed is None:
        _warn_unreadable(field="date of birth", value=birthdate)
    return parsed


# EDF+ mandates F/M for the sex subfield and pyedflib normalizes it to Female/Male, so an exact
# allowlist covers everything any reader emits. Prefix matching would be looser than the input space
# and can invert the value outright — "mujer" starts with an M — which is the very failure this
# extraction exists to avoid.
_SEX_BY_HEADER_VALUE = {
    "F": "F",
    "FEMALE": "F",
    "M": "M",
    "MALE": "M",
    "O": "O",
    "OTHER": "O",
}

# Ways of saying "unknown". These are declarations, not failures: the file stated its subject's sex
# perfectly clearly, as unknown. "X" is EDF+'s own marker and "U" is NWB's — the very value this falls
# back to — so warning that either "could not be interpreted" would report a malformed file where there
# is none. They map to None so the caller's "U" default applies, but silently.
_SEX_MEANING_UNKNOWN = ("", "X", "U", "UNKNOWN", "N/A", "NA", "?", "-")


def _parse_sex(sex) -> str | None:
    """
    Map an EDF+ sex subfield onto the letter NWB expects, or None when it is not stated.

    Anything outside the allowlist is treated as not stated, so the caller's ``"U"`` default applies
    rather than a guess. An empty field and EDF+'s bare ``X`` mean "unknown" and pass silently; any
    other unrecognized value warns, since the file did state something.
    """
    if sex is None:
        return None
    # Note: not ``str(sex or "")`` — that would fold a numeric 0 into the silent path, hiding the one
    # input shape the allowlist cannot interpret.
    text = str(sex).strip().upper()
    if text in _SEX_MEANING_UNKNOWN:
        return None
    mapped = _SEX_BY_HEADER_VALUE.get(text)
    if mapped is None:
        _warn_unreadable(field="subject sex", value=sex)
    return mapped


class EDFRecordingInterface(BaseRecordingExtractorInterface):
    """
    Data interface class for converting European Data Format (EDF) data.

    Uses the :py:func:`~spikeinterface.extractors.read_edf` reader from SpikeInterface.

    Not supported on M1 macs.
    """

    display_name = "EDF Recording"
    keywords = BaseRecordingExtractorInterface.keywords + ("European Data Format",)
    associated_suffixes = (".edf",)
    info = "Interface for European Data Format (EDF) recording data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the .edf file."
        return source_schema

    @staticmethod
    def get_available_channel_ids(file_path: FilePath) -> list:
        """
        Get all available channel names from an EDF file.

        Parameters
        ----------
        file_path : FilePath
            Path to the EDF file

        Returns
        -------
        list
            List of all channel names in the EDF file
        """
        from spikeinterface.extractors import read_edf

        # Load the recording to inspect channels
        recording = read_edf(file_path=file_path, all_annotations=True, use_names_as_ids=True)

        # Get all channel IDs
        channel_ids = recording.get_channel_ids()

        # Clean up to avoid dangling references
        del recording

        return channel_ids.tolist()

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import EDFRecordingExtractor

        return EDFRecordingExtractor

    def _initialize_extractor(self, interface_kwargs: dict):
        """Override to add use_names_as_ids and pop channels_to_skip."""
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)
        self.extractor_kwargs.pop("es_key", None)
        self.extractor_kwargs.pop("channels_to_skip")
        self.extractor_kwargs["all_annotations"] = True
        self.extractor_kwargs["use_names_as_ids"] = True

        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    def __init__(
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
        channels_to_skip: list | None = None,
    ):
        """
        Load and prepare data for EDF.
        Currently, only continuous EDF+ files (EDF+C) and original EDF files (EDF) are supported


        Parameters
        ----------
        file_path : str or Path
            Path to the edf file
        verbose : bool, default: False
            Allows verbose.
        es_key : str, default: "ElectricalSeries"
            Key for the ElectricalSeries metadata
        channels_to_skip : list, default: None
            Channels to skip when adding the data to the nwbfile. These parameter can be used to skip non-neural
            channels that are present in the EDF file.

        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "verbose",
                "es_key",
                "channels_to_skip",
            ]
            num_positional_args_before_args = 1  # file_path
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
                f"Passing arguments positionally to EDFRecordingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            verbose = positional_values.get("verbose", verbose)
            es_key = positional_values.get("es_key", es_key)
            channels_to_skip = positional_values.get("channels_to_skip", channels_to_skip)

        get_package(
            package_name="pyedflib",
            excluded_platforms_and_python_versions=dict(darwin=dict(arm=["3.9"])),
        )

        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key, channels_to_skip=channels_to_skip)
        self.edf_header = self.recording_extractor.neo_reader.edf_header

        # We remove the channels that are not neural
        if channels_to_skip:
            self.recording_extractor = self.recording_extractor.remove_channels(remove_channel_ids=channels_to_skip)

    def extract_nwb_file_metadata(self) -> dict:
        nwbfile_metadata = dict(
            session_start_time=self.edf_header["startdate"],
            experimenter=self.edf_header["technician"],
        )

        # Filter empty values
        nwbfile_metadata = {property: value for property, value in nwbfile_metadata.items() if value}

        return nwbfile_metadata

    def extract_subject_metadata(self) -> dict:
        # "sex" is the current pyedflib key; "gender" is the older one, still populated, so fall back to
        # it rather than defaulting sex when the header in fact states it.
        sex = self.edf_header.get("sex") or self.edf_header.get("gender")
        subject_metadata = dict(
            subject_id=self.edf_header["patientcode"],
            date_of_birth=_parse_birthdate(self.edf_header["birthdate"]),
            sex=_parse_sex(sex),
        )

        # Filter empty values
        subject_metadata = {property: value for property, value in subject_metadata.items() if value}

        return subject_metadata

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        nwbfile_metadata = self.extract_nwb_file_metadata()
        metadata["NWBFile"].update(nwbfile_metadata)

        subject_metadata = self.extract_subject_metadata()
        if subject_metadata:
            # NOTE: assigning rather than updating in place. ``metadata`` is a DeepDict (a defaultdict),
            # and ``dict.get`` does not go through ``__missing__``, so the previous
            # ``metadata.get("Subject", dict()).update(...)`` mutated a throwaway dict and every EDF
            # file silently lost its subject metadata.
            # Once "Subject" is present the metadata schema requires subject_id, species and sex, so
            # fill them whenever the header carried anything at all; otherwise reading a patient code
            # out of the file would turn valid metadata into invalid metadata. These are fallbacks only:
            # extract_subject_metadata supplies sex when the header states it.
            subject_metadata.setdefault("subject_id", "Unknown")
            # "Unknown species" is shaped like a binomial name on purpose: nwbinspector's
            # check_subject_species_form requires "Genus species" or an NCBI taxonomy URL, so a plainer
            # "unknown" would be flagged on every converted file.
            subject_metadata.setdefault("species", "Unknown species")
            subject_metadata.setdefault("sex", "U")
            # NOTE: the ``.get`` here is a read, not the bug fixed above — it deliberately avoids
            # materialising "Subject" on this defaultdict, and its result is used rather than mutated.
            metadata["Subject"] = {**metadata.get("Subject", dict()), **subject_metadata}

        return metadata
