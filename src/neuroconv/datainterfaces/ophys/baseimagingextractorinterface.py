"""Author: Ben Dichter."""

from typing import Literal, Optional

import numpy as np
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ophys import ImagingPlane, OnePhotonSeries, TwoPhotonSeries

from ...baseextractorinterface import BaseExtractorInterface
from ...utils import (
    DeepDict,
    dict_deep_update,
    fill_defaults,
    get_base_schema,
    get_schema_from_hdmf_class,
)


class BaseImagingExtractorInterface(BaseExtractorInterface):
    """Parent class for all ImagingExtractorInterfaces."""

    keywords = (
        "ophys",
        "optical electrophysiology",
        "fluorescence",
        "microscopy",
        "two photon",
        "one photon",
        "voltage imaging",
        "calcium imaging",
    )

    ExtractorModuleName = "roiextractors"

    def __init__(
        self,
        verbose: bool = False,
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries",
        **source_data,
    ):
        super().__init__(**source_data)
        self.imaging_extractor = self._extractor_instance
        self.verbose = verbose
        self.photon_series_type = photon_series_type

    def get_metadata_schema(
        self,
    ) -> dict:
        """
        Retrieve the metadata schema for the optical physiology (Ophys) data.

        Returns
        -------
        dict
            The metadata schema dictionary containing definitions for Device, ImagingPlane,
            and either OnePhotonSeries or TwoPhotonSeries based on the photon_series_type.
        """

        metadata_schema = super().get_metadata_schema()

        metadata_schema["required"] = ["Ophys"]

        # Initiate Ophys metadata
        metadata_schema["properties"]["Ophys"] = get_base_schema(tag="Ophys")
        metadata_schema["properties"]["Ophys"]["required"] = ["Device", "ImagingPlane", self.photon_series_type]
        metadata_schema["properties"]["Ophys"]["properties"] = dict(
            Device=dict(type="array", minItems=1, items={"$ref": "#/properties/Ophys/definitions/Device"}),
            ImagingPlane=dict(type="array", minItems=1, items={"$ref": "#/properties/Ophys/definitions/ImagingPlane"}),
        )
        metadata_schema["properties"]["Ophys"]["properties"].update(
            {
                self.photon_series_type: dict(
                    type="array",
                    minItems=1,
                    items={"$ref": f"#/properties/Ophys/definitions/{self.photon_series_type}"},
                ),
            }
        )

        # Schema definition for arrays

        imaging_plane_schema = get_schema_from_hdmf_class(ImagingPlane)
        imaging_plane_schema["properties"]["optical_channel"].pop("maxItems")
        metadata_schema["properties"]["Ophys"]["definitions"] = dict(
            Device=get_schema_from_hdmf_class(Device),
            ImagingPlane=imaging_plane_schema,
        )
        photon_series = dict(
            OnePhotonSeries=OnePhotonSeries,
            TwoPhotonSeries=TwoPhotonSeries,
        )[self.photon_series_type]
        metadata_schema["properties"]["Ophys"]["definitions"].update(
            {
                self.photon_series_type: get_schema_from_hdmf_class(photon_series),
            }
        )

        fill_defaults(metadata_schema, self.get_metadata())
        return metadata_schema

    def get_metadata(
        self,
    ) -> DeepDict:
        """
        Retrieve the metadata for the imaging data.

        Returns
        -------
        DeepDict
            Dictionary containing metadata including device information, imaging plane details,
            and photon series configuration.
        """

        from ...tools.roiextractors import get_nwb_imaging_metadata

        metadata = super().get_metadata()
        default_metadata = get_nwb_imaging_metadata(self.imaging_extractor, photon_series_type=self.photon_series_type)
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
        reinitialized_extractor = self.get_extractor()(**self.extractor_kwargs)
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
        parent_container: Literal["acquisition", "processing/ophys"] = "acquisition",
        stub_test: bool = False,
        stub_frames: int = 100,
        always_write_timestamps: bool = False,
    ):
        """
        Add imaging data to the NWB file

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file where the imaging data will be added.
        metadata : dict, optional
            Metadata for the NWBFile, by default None.
        photon_series_type : {"TwoPhotonSeries", "OnePhotonSeries"}, optional
            The type of photon series to be added, by default "TwoPhotonSeries".
        photon_series_index : int, optional
            The index of the photon series in the provided imaging data, by default 0.
        parent_container : {"acquisition", "processing/ophys"}, optional
            Specifies the parent container to which the photon series should be added, either as part of "acquisition" or
            under the "processing/ophys" module, by default "acquisition".
        stub_test : bool, optional
            If True, only writes a small subset of frames for testing purposes, by default False.
        stub_frames : int, optional
            The number of frames to write when stub_test is True. Will use min(stub_frames, total_frames) to avoid
            exceeding available frames, by default 100.
        """

        from ...tools.roiextractors import add_imaging_to_nwbfile

        if stub_test:
            stub_frames = min([stub_frames, self.imaging_extractor.get_num_frames()])
            imaging_extractor = self.imaging_extractor.frame_slice(start_frame=0, end_frame=stub_frames)
        else:
            imaging_extractor = self.imaging_extractor

        metadata = metadata or self.get_metadata()

        add_imaging_to_nwbfile(
            imaging=imaging_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
            photon_series_index=photon_series_index,
            parent_container=parent_container,
            always_write_timestamps=always_write_timestamps,
        )
