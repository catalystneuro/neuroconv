"""Sphinx directive rendering an interface's ``get_metadata_template()`` as YAML and JSON.

The block is generated when the documentation builds rather than checked in, so it cannot drift from
what the method actually returns. Both formats are shown because ``load_dict_from_file`` accepts
``.yaml``, ``.yml`` and ``.json`` alike, so a conversion specification may be written in either.
"""

import json

import yaml
from docutils import nodes
from docutils.parsers.rst import Directive, directives
from docutils.statemachine import StringList

TAB_INDENT = " " * 4
CODE_INDENT = " " * 12


class MetadataTemplateDirective(Directive):
    """Render the metadata template of the interface expression given as the argument.

    The argument is evaluated against ``neuroconv.tools.testing``, so a mock interface is named
    directly with the keyword arguments that size it::

        .. metadata-template:: MockFiberPhotometryInterface(num_fibers=2, metadata_key="gcamp_dms")
           :exclude: NWBFile

    ``exclude`` drops top-level keys that are not what the block is illustrating, such as the
    session-level ``NWBFile`` entry and its freshly generated identifier.
    """

    required_arguments = 1
    final_argument_whitespace = True
    option_spec = {"exclude": directives.unchanged}

    def run(self) -> list[nodes.Node]:
        from neuroconv.tools import testing

        interface = eval(self.arguments[0], vars(testing).copy())  # noqa: S307 (the docs build is trusted)
        template = interface.get_metadata_template()

        # Normalized through JSON so DeepDict, datetimes and numpy scalars all arrive as the plain
        # types both dumpers accept.
        template = json.loads(json.dumps(template, default=str))
        for key in self.options.get("exclude", "").split():
            template.pop(key, None)

        blocks = (
            # A wide line width so a long description stays on its line instead of being folded, which
            # is valid YAML but reads as an accident in a block meant to be copied.
            ("YAML", "yaml", yaml.safe_dump(template, sort_keys=False, default_flow_style=False, width=200)),
            ("JSON", "json", json.dumps(template, indent=4)),
        )

        lines = [".. tab-set::", ""]
        for tab_title, language, dumped in blocks:
            lines += [f"{TAB_INDENT}.. tab-item:: {tab_title}", ""]
            lines += [f"{TAB_INDENT * 2}.. code-block:: {language}", ""]
            lines += [f"{CODE_INDENT}{line}" if line else "" for line in dumped.splitlines()]
            lines += [""]

        container = nodes.container()
        self.state.nested_parse(StringList(lines), self.content_offset, container)
        return container.children


def setup(app):
    """Register the directive with Sphinx."""
    app.add_directive("metadata-template", MetadataTemplateDirective)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
