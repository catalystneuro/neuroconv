import ndx_probeinterface
from probeinterface import Probe, ProbeGroup
from pynwb.file import NWBFile

from ...utils import DeepDict


def add_probe(probe: Probe, nwbfile: NWBFile, metadata: DeepDict = None):
    """Add a probe to an NWBFile.

    Parameters
    ----------
    probe : Probe
        Probe object to add to the NWBFile.
    nwbfile : NWBFile
        NWBFile to add the probe to.
    metadata : dict, optional
        Metadata to add to the probe, by default None
    """
    ndx_probes = ndx_probeinterface.Probe.from_probeinterface(probe)
    ndx_probe = ndx_probes[0]
    if ndx_probe.name not in nwbfile.devices:
        nwbfile.add_device(ndx_probe)


def add_probe_group(probe_group: ProbeGroup, nwbfile: NWBFile, metadata: DeepDict = None):
    """Add a probe group to an NWBFile.

    Parameters
    ----------
    probe_group : ProbeGroup
        ProbeGroup object to add to the NWBFile.
    nwbfile : NWBFile
        NWBFile to add the probe to.
    metadata : dict, optional
        Metadata to add to the probe, by default None
    """
    ndx_probes = ndx_probeinterface.Probe.from_probeinterface(probe_group)
    for ndx_probe in ndx_probes:
        if ndx_probe.name not in nwbfile.devices:
            nwbfile.add_device(ndx_probe)
