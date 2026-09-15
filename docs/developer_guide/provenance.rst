.. _provenance:

The provenance record
---------------------

Every file NeuroConv writes carries a record of what produced it in ``general/source_script``, so that a
file can be traced back to the code that made it. This page specifies the format, so that anyone writing a
parser for it is reading a specification rather than reverse engineering one.

The record
~~~~~~~~~~

The first line names the record, so that a file can be recognized as carrying one without parsing it.
Every line after it is a ``key: value`` pair, and the last of them states the format the record is
written in.

.. code-block::

    NeuroConv provenance record
    neuroconv_version: 0.10.1
    execution_environment: script
    source_script: https://github.com/lab/conversions/blob/9f3c2ab.../convert_lab.py
    version_control: git
    repository: https://github.com/lab/conversions
    commit: 9f3c2ab1d4e7f09b2c5a8e3d6f10a4b7c9e2d5f8
    commit_date: 2026-08-14T11:02:31+02:00
    working_tree: clean
    commit_published: yes
    neuroconv_provenance_format: 1

To read it, split on newlines and keep the lines matching ``^([a-z_]+): (.*)$``. An absent key means
unknown or not applicable, so the cases that know less are shorter rather than filled with ``none``.

Always resolve ``neuroconv_provenance_format`` before interpreting anything else. The key numbers this
format, and it is incremented whenever a key changes meaning. A key is never reused with new semantics.

Files written before this record existed, and before NeuroConv v0.10.1, carry a single line reading
``Created using NeuroConv v<version>`` instead, with no header and no keys.

.. list-table::
    :header-rows: 1
    :widths: 25 25 50

    * - Key
      - Values
      - Meaning
    * - ``neuroconv_provenance_format``
      - integer
      - The format of this record. Currently ``1``.
    * - ``neuroconv_version``
      - PEP 440 version
      - The version of NeuroConv that wrote the file. Redundant with the first line, so that a parser
        needs no regular expression over prose.
    * - ``execution_environment``
      - ``script``, ``notebook``, ``interactive``
      - How the conversion was run.
    * - ``source_script``
      - URL or file name
      - A URL to the script as it stood at the recorded commit, where one can be built. Otherwise the
        script's path relative to the repository root, or its bare name when it is not in a repository.
        A path here describes the repository's own layout, never the writer's disk. Absent when no user
        script was running.
    * - ``version_control``
      - ``git``, ``none``
      - Absent when there is no script.
    * - ``repository``
      - URL
      - The ``origin`` remote, normalized to HTTPS. Absent when the repository has no remote, or its
        remote is a local path.
    * - ``commit``
      - full sha
      -
    * - ``commit_date``
      - ISO 8601
      - When the code was written, as opposed to when it ran. The time the conversion ran is
        ``/file_create_date``, which pynwb writes.
    * - ``working_tree``
      - ``clean``, ``modified``
      - Whether the checkout that ran matched the commit. Computed with
        ``git status --porcelain --untracked-files=no``, so modifications to tracked files count and
        untracked files, such as the output the conversion is writing, do not.
    * - ``commit_published``
      - ``yes``, ``no``
      - Whether the commit is reachable from a remote branch **on the machine that ran the conversion**,
        which is to say pushed and fetched. This is not a claim that the repository is public.

``source_script_file_name``, the attribute NWB requires alongside the dataset, is the base name of the
script, or ``neuroconv`` when no user script was running. It never carries a directory.

What is not claimed
~~~~~~~~~~~~~~~~~~~

A URL is written only when the working tree is clean, the script itself is tracked, the commit has been
pushed, and the host's URL layout is known, which currently means ``github.com``, ``gitlab.com`` or
``bitbucket.org``. A remote names its host but not the software running on it, so a self-hosted forge is
left out. The script's own tracking is checked separately from the working tree because an untracked
script leaves the tree clean while being absent from the commit. A link to a commit that is not what ran looks authoritative and is wrong, which is
worse than no link. The ``commit`` key is written either way, so nothing is withheld; it is only the link
that is conditioned.

Nothing distinguishes a public repository from a private one without a network request, and NeuroConv
makes none while writing a file. ``commit_published`` therefore means what its name says and nothing
stronger.

Turning the git keys off
~~~~~~~~~~~~~~~~~~~~~~~~

``repository``, ``commit`` and their siblings name a repository even when it is private, which discloses
its existence and its name. Set ``NEUROCONV_PROVENANCE`` to control this:

.. list-table::
    :header-rows: 1
    :widths: 25 75

    * - Value
      - Record
    * - ``full-git-info``
      - Everything above. This is the default, and what an unset variable means.
    * - ``no-git-info``
      - ``version_control``, ``repository``, ``commit``, ``commit_date``, ``working_tree`` and
        ``commit_published`` are omitted, and ``source_script`` falls back to the script's name.
        ``neuroconv_provenance_format``, ``neuroconv_version`` and ``execution_environment`` are kept.

Any other value is treated as ``no-git-info``, so a typo discloses less rather than more. The variable can
only remove keys, never add or change them.

A conversion that sets ``metadata["NWBFile"]["source_script"]`` itself replaces the record entirely, which
is how the NWB GUIDE writes its own.
