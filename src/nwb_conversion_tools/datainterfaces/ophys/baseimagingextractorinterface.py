"""Author: Ben Dichter."""
from typing import Optional

from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ophys import ImagingPlane, TwoPhotonSeries

from ...basedatainterface import BaseDataInterface
from ...tools.roiextractors import write_imaging, get_nwb_imaging_metadata
from ...utils import (
    get_schema_from_hdmf_class,
    fill_defaults,
    get_base_schema,
    OptionalFilePathType,
    dict_deep_update,
)


class BaseImagingExtractorInterface(BaseDataInterface):
    IX = None

    def __init__(self, verbose=True, **source_data):
        super().__init__(**source_data)
        self.imaging_extractor = self.IX(**source_data)
        self.verbose = verbose

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        self.imaging_extractor._sampling_frequency = float(self.imaging_extractor._sampling_frequency)

        metadata_schema["required"] = ["Ophys"]

        # Initiate Ophys metadata
        metadata_schema["properties"]["Ophys"] = get_base_schema(tag="Ophys")
        metadata_schema["properties"]["Ophys"]["required"] = ["Device", "ImagingPlane", "TwoPhotonSeries"]
        metadata_schema["properties"]["Ophys"]["properties"] = dict(
            Device=dict(type="array", minItems=1, items={"$ref": "#/properties/Ophys/properties/definitions/Device"}),
            ImagingPlane=dict(
                type="array", minItems=1, items={"$ref": "#/properties/Ophys/properties/definitions/ImagingPlane"}
            ),
            TwoPhotonSeries=dict(
                type="array", minItems=1, items={"$ref": "#/properties/Ophys/properties/definitions/TwoPhotonSeries"}
            ),
        )

        # Schema definition for arrays
        metadata_schema["properties"]["Ophys"]["properties"]["definitions"] = dict(
            Device=get_schema_from_hdmf_class(Device),
            ImagingPlane=get_schema_from_hdmf_class(ImagingPlane),
            TwoPhotonSeries=get_schema_from_hdmf_class(TwoPhotonSeries),
        )

        fill_defaults(metadata_schema, self.get_metadata())
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        default_metadata = get_nwb_imaging_metadata(self.imaging_extractor)
        metadata = dict_deep_update(default_metadata, metadata)
        _ = metadata.pop("NWBFile")

        # fix troublesome data types
        if "TwoPhotonSeries" in metadata["Ophys"]:
            for two_photon_series in metadata["Ophys"]["TwoPhotonSeries"]:
                if "dimension" in two_photon_series:
                    two_photon_series["dimension"] = list(two_photon_series["dimension"])
                if "rate" in two_photon_series:
                    two_photon_series["rate"] = float(two_photon_series["rate"])
        return metadata

    def run_conversion(
        self,
        nwbfile_path: OptionalFilePathType = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        save_path: OptionalFilePathType = None,
    ):
        write_imaging(
            imaging=self.imaging_extractor,
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            verbose=self.verbose,
            save_path=save_path,
        )
