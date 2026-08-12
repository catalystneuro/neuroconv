from neuroconv.tools.testing.mock_interfaces import MockInterface
from neuroconv.utils import DeepDict


def test_metadata_template_defaults_to_the_metadata():
    # Every interface answers get_metadata_template(), so a caller never has to know which of them
    # scaffold a provenance chain and which have nothing to scaffold. One with nothing to add answers
    # with its metadata unchanged, rather than raising or returning an empty structure.
    class InterfaceWithFixedMetadata(MockInterface):
        def get_metadata(self) -> DeepDict:
            return DeepDict(NWBFile=dict(session_description="A session with no chain to scaffold."))

    interface = InterfaceWithFixedMetadata()

    assert interface.get_metadata_template() == interface.get_metadata()
