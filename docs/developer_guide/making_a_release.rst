.. _making_a_release:

Release Process for Neuroconv
=============================

A simple to-do list for the Neuroconv release process:

1. **Format Changelog**:

   - Double check changelog entries to ensure they are in the correct format.
   - Set the data to the current date of the release: `Example <https://github.com/catalystneuro/neuroconv/commit/129ab774ccb04677a2037ff6deab9d647d7b0e25>`_


2. **Set the Correct Version for Release**:

   - The development version (the current code on `main`) should be one patch version ahead of the latest PyPI release and carry a ``.dev0`` suffix, so it is already the right number for this step.
   - Drop the ``.dev0``, so that ``0.10.1.dev0`` becomes ``0.10.1``. Nothing may be published to PyPI with that suffix; see step 6 for why it is there.
   - If a minor version bump is necessary, change it accordingly `Example <https://github.com/catalystneuro/neuroconv/commit/760022080845a1a8438c68fcf9d918e287b6ca3d>`_

3. **Perform Checks**:

   - Clear the deprecations that come due at this version. A deprecation names the version it is removed in
     (see :ref:`deprecations`), so search the source for the version being released and remove what names it.
     Removals happen at a minor version, never in a patch.
   - Ensure that no requirement files include pointers to `git`-based dependencies (including specific branches or commit hashes). All dependencies for a PyPI release should point to the released package versions that are available on conda-forge or PyPI. This can be done efficiently by searching for `@ git` in the pyproject.toml on an IDE.

4. **Tag on GitHub**:

   - The title and tag should be the release version (e.g `v0.7.2`).
   - The changelog should be copied correspondingly.
   - Check the hashes in the markdown to ensure they match with the format of previous releases.

5. **Release**:

   - GitHub tagging triggers the `auto-publish.yml` action on the CI, which takes care of the rest.

6. **Post-Release: Bump Version and Update Changelog**:

   - To comply with the one patch version ahead policy, bump the version after the release `Example <https://github.com/catalystneuro/neuroconv/commit/1f4c90d1d1a8095937f9a9bca883e89b36341d5c>`_, and give it a ``.dev0`` suffix: after releasing ``0.10.1``, `main` becomes ``0.10.2.dev0``.
   - The suffix stays on `main` for the whole cycle. Every NWB file records the NeuroConv version that wrote it in its provenance record (see :ref:`provenance`), so ``0.10.2.dev0`` says the file was written from a checkout and ``0.10.2`` says it was written by the release. Without the suffix the two are indistinguishable and every file written during development claims to have been written by a version that did not exist yet.
   - PyPI only ever sees the clean number, since the suffix is dropped at step 2, so pins such as ``neuroconv==0.10.2`` resolve exactly as before. A ``.dev`` version is a pre-release, so ``pip install neuroconv`` would never resolve it even if one were published by mistake.
   - Update the changelog with a new Upcoming header and the empty sections `Example <https://github.com/catalystneuro/neuroconv/commit/bb555d04375f21a266d5bbe5e0eaece823f3393b>`_.
