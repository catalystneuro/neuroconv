"""Author: Ben Dichter."""
from typing import Literal, Optional

import numpy as np
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ophys import ImagingPlane, OnePhotonSeries, TwoPhotonSeries

from ...baseextractorinterface import BaseExtractorInterface
from ...utils import (
    dict_deep_update,
    fill_defaults,
    get_base_schema,
    get_schema_from_hdmf_class,
)


class BaseImagingExtractorInterface(BaseExtractorInterface):
    """Parent class for all ImagingExtractorInterfaces."""

    ExtractorModuleName = "roiextractors"

    def __init__(self, verbose: bool = True, **source_data):
        super().__init__(**source_data)
        self.imaging_extractor = self.get_extractor()(**source_data)
        self.verbose = verbose

    def get_metadata_schema(
        self, photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries"
    ) -> dict:
        metadata_schema = super().get_metadata_schema()

        metadata_schema["required"] = ["Ophys"]

        # Initiate Ophys metadata
        metadata_schema["properties"]["Ophys"] = get_base_schema(tag="Ophys")
        metadata_schema["properties"]["Ophys"]["required"] = ["Device", "ImagingPlane", photon_series_type]
        metadata_schema["properties"]["Ophys"]["properties"] = dict(
            Device=dict(type="array", minItems=1, items={"$ref": "#/properties/Ophys/properties/definitions/Device"}),
            ImagingPlane=dict(
                type="array", minItems=1, items={"$ref": "#/properties/Ophys/properties/definitions/ImagingPlane"}
            ),
        )
        metadata_schema["properties"]["Ophys"]["properties"].update(
            {
                photon_series_type: dict(
                    type="array",
                    minItems=1,
                    items={"$ref": f"#/properties/Ophys/properties/definitions/{photon_series_type}"},
                ),
            }
        )

        # Schema definition for arrays

        imaging_plane_schema = get_schema_from_hdmf_class(ImagingPlane)
        imaging_plane_schema["properties"]["optical_channel"].pop("maxItems")
        metadata_schema["properties"]["Ophys"]["properties"]["definitions"] = dict(
            Device=get_schema_from_hdmf_class(Device),
            ImagingPlane=imaging_plane_schema,
        )
        photon_series = dict(
            OnePhotonSeries=OnePhotonSeries,
            TwoPhotonSeries=TwoPhotonSeries,
        )[photon_series_type]
        metadata_schema["properties"]["Ophys"]["properties"]["definitions"].update(
            {
                photon_series_type: get_schema_from_hdmf_class(photon_series),
            }
        )

        fill_defaults(metadata_schema, self.get_metadata())
        return metadata_schema

    def get_metadata(self) -> dict:
        from ...tools.roiextractors import get_nwb_imaging_metadata

        metadata = super().get_metadata()
        default_metadata = get_nwb_imaging_metadata(self.imaging_extractor)
        metadata = dict_deep_update(default_metadata, metadata)

        # fix troublesome data types
        if "TwoPhotonSeries" in metadata["Ophys"]:
            for two_photon_series in metadata["Ophys"]["TwoPhotonSeries"]:
                if "dimension" in two_photon_series:
                    two_photon_series["dimension"] = list(two_photon_series["dimension"])
                if "rate" in two_photon_series:
                    two_photon_series["rate"] = float(two_photon_series["rate"])
        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        reinitialized_extractor = self.get_extractor()(**self.source_data)
        return reinitialized_extractor.frame_to_time(frames=np.arange(stop=reinitialized_extractor.get_num_frames()))

    def get_timestamps(self) -> np.ndarray:
        return self.imaging_extractor.frame_to_time(frames=np.arange(stop=self.imaging_extractor.get_num_frames()))

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        self.imaging_extractor.set_times(times=aligned_timestamps)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "TwoPhotonSeries",
        photon_series_index: int = 0,
        stub_test: bool = False,
        stub_frames: int = 100,
    ):
        from ...tools.roiextractors import add_imaging

        if stub_test:
            stub_frames = min([stub_frames, self.imaging_extractor.get_num_frames()])
            imaging_extractor = self.imaging_extractor.frame_slice(start_frame=0, end_frame=stub_frames)
        else:
            imaging_extractor = self.imaging_extractor

        add_imaging(
            imaging=imaging_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
            photon_series_index=photon_series_index,
        )
