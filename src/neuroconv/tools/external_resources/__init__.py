"""Tools for writing the ontology terms stated in metadata into an NWB file as HERD.

``add_external_resources_to_nwbfile`` takes the terms in ``metadata["ExternalResources"]``, keyed by the
value they describe, and writes them into the file as HERD references. Nothing is inferred, and
``run_conversion`` runs it automatically just before writing.
"""

from ._annotate import add_external_resources_to_nwbfile

__all__ = ["add_external_resources_to_nwbfile"]
