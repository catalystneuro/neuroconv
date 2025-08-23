Release Process for Neuroconv
=============================

A simple to-do list for the Neuroconv release process:

1. **Format Changelog**:

   - Double check changelog entries to ensure they are in the correct format.
   - Set the data to the current date of the release: `Example <https://github.com/catalystneuro/neuroconv/commit/760022080845a1a8438c68fcf9d918e287b6ca3d>`_


2. **Set the Correct Version for Release**:

   - The development version (the current code on `main`) should be one patch version ahead of the latest PyPI release and therefore ready for the next step.
   - If a minor version bump is necessary, change it accordingly `Example <https://github.com/catalystneuro/neuroconv/commit/af91f09f300cb36ba4fee483196c8cb492c180ae>`_

3. **Perform Checks**:

   - Ensure that no requirement files include pointers to `git`-based dependencies (including specific branches or commit hashes). All dependencies for a PyPI release should point to the released package versions that are available on conda-forge or PyPI. This can be done efficiently by searching for `@ git` in the pyproject.toml on an IDE.

4. **Tag on GitHub**:

   - The title and tag should be the release version (e.g `v0.7.2`).
   - The changelog should be copied correspondingly.
   - Check the hashes in the markdown to ensure they match with the format of previous releases.

5. **Release**:

   - GitHub tagging triggers the `auto-publish.yml` action on the CI, which takes care of the rest.

6. **Post-Release: Bump Version and Update Changelog**:

   - To comply with the one patch version ahead policy, bump the version after the release `Example <https://github.com/catalystneuro/neuroconv/commit/1f4c90d1d1a8095937f9a9bca883e89b36341d5c>`_.
   - Update the changelog with a new Upcoming header and the empty sections `Example <https://github.com/catalystneuro/neuroconv/commit/bb555d04375f21a266d5bbe5e0eaece823f3393b>`_.
