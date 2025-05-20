"""Inscopix segmentation interface for NeuroConv."""

from pathlib import Path
import numpy as np
import inspect

from pynwb import NWBFile
from roiextractors import InscopixSegmentationExtractor

from neuroconv.datainterfaces.ophys.basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from neuroconv.utils import FilePathType


class InscopixSegmentationInterface(BaseSegmentationExtractorInterface):
    """Conversion interface for Inscopix segmentation data."""
    
    display_name = "Inscopix Segmentation" 
    associated_suffixes = (".isxd",)
    info = "Interface for EXTRACT segmentation."
    
    # ExtractorName = "InscopixSegmentationExtractor"

    def __init__(
        self,
        file_path: FilePathType,
        verbose: bool = True,
    ):
        """
        Initialize a new InscopixSegmentationInterface instance.
        
        Parameters
        ----------
        file_path : FilePathType
            Path to the Inscopix segmentation file (.isxd).
        verbose : bool, default: True
            Whether to print detailed information during processing.
        """
        super().__init__(file_path=file_path)
        self.verbose = verbose