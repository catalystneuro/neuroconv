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


def _assemble_birthdate(year: int, month: int, day: int) -> datetime | None:
    """Build a birthdate, rejecting impossible calendar dates and dates in the future."""
    try:
        birthdate = datetime(year=year, month=month, day=day)
    except ValueError:
        return None
    # A birthdate cannot be in the future; such a value means the field was misread, not that the
    # subject is unborn, and passing it on would put a nonsense date in the NWB file.
    return None if birthdate > datetime.now() else birthdate


def _parse_birthdate(birthdate) -> datetime | None:
    """
    Coerce an EDF birthdate into a datetime, or None when it cannot be read.

    NWB's ``Subject.date_of_birth`` must be a datetime, but the readers hand the EDF+ patient field's
    birthdate back as a string (``"02 may 1951"`` via pyedflib, ``"02-MAY-1951"`` straight from the
    header), so an absent or unreadable value is dropped rather than passed on to pynwb.

    Only the ``DD-MMM-YYYY`` form the EDF+ spec defines for this field is accepted, plus ISO
    ``YYYY-MM-DD``. Notably ``DD.MM.YY`` is *not*: no reader emits it for a birthdate (the two-digit
    form belongs to the header's separate ``startdate`` field), and Python's POSIX rule for ``%y`` maps
    00-68 to the 2000s, so ``"02.05.51"`` would have become 2051 — a birthdate in the future.
    """
    if not birthdate:
        return None
    if isinstance(birthdate, datetime):
        return _assemble_birthdate(birthdate.year, birthdate.month, birthdate.day)
    # A plain date is not a datetime, and pynwb requires the latter.
    if isinstance(birthdate, date):
        return _assemble_birthdate(birthdate.year, birthdate.month, birthdate.day)

    text = str(birthdate).strip()
    named_month = re.match(r"^(\d{1,2})[-\s]([A-Za-z]{3,})[-\s](\d{4})$", text)
    if named_month:
        abbreviation = named_month.group(2)[:3].upper()
        if abbreviation in _MONTH_ABBREVIATIONS:
            return _assemble_birthdate(
                year=int(named_month.group(3)),
                month=_MONTH_ABBREVIATIONS.index(abbreviation) + 1,
                day=int(named_month.group(1)),
            )
    iso = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", text)
    if iso:
        return _assemble_birthdate(year=int(iso.group(1)), month=int(iso.group(2)), day=int(iso.group(3)))
    return None


def _parse_sex(sex) -> str | None:
    """
    Map an EDF+ sex subfield onto the single letter NWB expects, or None when it is unknown.

    pyedflib normalizes the field to ``"Female"``/``"Male"`` whichever form was written, while the
    header itself holds ``F``/``M``, and EDF+ uses a bare ``X`` for an unknown subfield.
    """
    text = str(sex or "").strip().upper()
    if text.startswith("F"):
        return "F"
    if text.startswith("M"):
        return "M"
    return None


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
