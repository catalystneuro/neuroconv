"""Author: Ben Dichter."""

import warnings
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
        verbose: bool = True,
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries",
        **source_data,
    ):
        super().__init__(**source_data)
        self.imaging_extractor = self._extractor_instance
        self.verbose = verbose
        self.photon_series_type = photon_series_type

    def get_metadata_schema(
        self, photon_series_type: Optional[Literal["OnePhotonSeries", "TwoPhotonSeries"]] = None
    ) -> dict:
        """
        Retrieve the metadata schema for the optical physiology (Ophys) data, with optional handling of photon series type.

        Parameters
        ----------
        photon_series_type : {"OnePhotonSeries", "TwoPhotonSeries"}, optional
            The type of photon series to include in the schema. If None, the value from the instance is used.
            This argument is deprecated and will be removed in a future version. Set `photon_series_type` during
            the initialization of the `BaseImagingExtractorInterface` instance.

        """

        if photon_series_type is not None:
            warnings.warn(
                "The 'photon_series_type' argument is deprecated and will be removed in a future version. "
                "Please set 'photon_series_type' during the initialization of the BaseImagingExtractorInterface instance.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.photon_series_type = photon_series_type
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
        self, photon_series_type: Optional[Literal["OnePhotonSeries", "TwoPhotonSeries"]] = None
    ) -> DeepDict:
        """
        Retrieve the metadata for the imaging data, with optional handling of photon series type.

        Parameters
        ----------
        photon_series_type : {"OnePhotonSeries", "TwoPhotonSeries"}, optional
            The type of photon series to include in the metadata. If None, the value from the instance is used.
            This argument is deprecated and will be removed in a future version. Instead, set `photon_series_type`
            during the initialization of the `BaseImagingExtractorInterface` instance.
        """

        if photon_series_type is not None:
            warnings.warn(
                "The 'photon_series_type' argument is deprecated and will be removed in a future version. "
                "Please set 'photon_series_type' during the initialization of the BaseImagingExtractorInterface instance.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.photon_series_type = photon_series_type

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
    ):
        """
        Add imaging data to the NWBFile, including options for photon series and stubbing.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile object to which the imaging data will be added.
        metadata : dict, optional
            Metadata dictionary containing information about the imaging data. If None, default metadata is used.
        photon_series_type : {"TwoPhotonSeries", "OnePhotonSeries"}, optional
            The type of photon series to be added to the NWBFile. Default is "TwoPhotonSeries".
        photon_series_index : int, optional
            The index of the photon series in the NWBFile, used to differentiate between multiple series, by default 0.
        parent_container : {"acquisition", "processing/ophys"}, optional
            The container in the NWBFile where the data will be added, by default "acquisition".
        stub_test : bool, optional
            If True, only a subset of the imaging data (up to `stub_frames`) will be added for testing purposes,
            by default False.
        stub_frames : int, optional
            The number of frames to include in the subset if `stub_test` is True, by default 100.

        """
        from ...tools.roiextractors import add_imaging_to_nwbfile

        if stub_test:
            stub_frames = min([stub_frames, self.imaging_extractor.get_num_frames()])
            imaging_extractor = self.imaging_extractor.frame_slice(start_frame=0, end_frame=stub_frames)
        else:
            imaging_extractor = self.imaging_extractor

        add_imaging_to_nwbfile(
            imaging=imaging_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
            photon_series_index=photon_series_index,
            parent_container=parent_container,
        )
