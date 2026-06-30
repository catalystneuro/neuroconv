import os
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np

from neuroconv.tools import get_package


class TDTLoadMixin:
    """Shared TDT-tank reading logic for interfaces constructed with ``folder_path``.

    Provides ``load`` (a thin wrapper around ``tdt.read_block``) and ``get_events`` (epoc
    extraction). The host interface must populate ``self.source_data["folder_path"]`` with the
    path to the TDT tank folder.
    """

    def load(self, t1: float = 0.0, t2: float = 0.0, evtype: list[str] = ["all"]):
        """
        Load the TDT data from the folder path.

        Parameters
        ----------
        t1 : float, optional
            Retrieve data starting at t1 (in seconds), default = 0 for start of recording.
        t2 : float, optional
            Retrieve data ending at t2 (in seconds), default = 0 for end of recording.
        evtype : list[str], optional
            List of strings, specifies what type of data stores to retrieve from the tank.
            Can contain 'all' (default), 'epocs', 'snips', 'streams', or 'scalars'. Ex. ['epocs', 'snips']

        Returns
        -------
        tdt.StructType
            TDT data object
        """
        tdt = get_package("tdt", installation_instructions="pip install tdt")
        folder_path = Path(self.source_data["folder_path"])
        assert folder_path.is_dir(), f"Folder path {folder_path} does not exist."
        for evtype_string in evtype:
            assert evtype_string in ["all", "epocs", "snips", "streams", "scalars"], (
                f"evtype must be a list containing some combination of 'all', 'epocs', 'snips', 'streams', or 'scalars', "
                f"but got {evtype_string}."
            )
        with open(os.devnull, "w", encoding="utf-8") as f, redirect_stdout(f):
            tdt_photometry = tdt.read_block(str(folder_path), t1=t1, t2=t2, evtype=evtype)
        return tdt_photometry

    def get_events(self) -> dict[str, dict[str, np.ndarray]]:
        """
        Get a dictionary of events from the TDT files (e.g. camera TTL pulses).

        The events dictionary maps from the names of each epoc in the TDT data to an event dictionary.
        Each event dictionary maps from "onset", "offset", and "data" to the corresponding arrays.

        Returns
        -------
        dict[str, dict[str, np.ndarray]]
            Dictionary of events.
        """
        events = {}
        tdt_photometry = self.load(evtype=["epocs"])
        for epoc_name in tdt_photometry.epocs.keys():
            events[epoc_name] = {
                "onset": tdt_photometry.epocs[epoc_name].onset,
                "offset": tdt_photometry.epocs[epoc_name].offset,
                "data": tdt_photometry.epocs[epoc_name].data,
            }
        return events
