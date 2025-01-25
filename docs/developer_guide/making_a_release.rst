Release Process for Neuroconv
=============================

A simple to-do list for the Neuroconv release process:

1. **Format Changelog**:

   - Format and update the changelog.
   - Ensure correct formatting and add a header to indicate that the changes belong to a specific release and not upcoming ones.
   - Example: `Format Changelog Example <https://github.com/catalystneuro/neuroconv/commit/2fbea8f05e5bd92c445fcbb6bf24de45330fcbbc>`_

2. **Set the Correct Version for Release**:

   - The development version (the current code on `main`) should be one patch version ahead of the latest PyPI release and therefore ready for the next step.
   - If a minor version bump is necessary, change it accordingly.
   - Example: `Version Change Example <https://github.com/catalystneuro/neuroconv/commit/af91f09f300cb36ba4fee483196c8cb492c180ae>`_

3. **Perform Checks**:

   - Ensure that no requirement files include pointers to `git`-based dependencies (including specific branches or commit hashes). All dependencies for a PyPI release should point to the released package versions that are available on conda-forge or PyPI. This can be done efficiently by searching for `@ git` in the pyproject.toml on an IDE.

4. **Tag on GitHub**:

   - The title and tag should be the release version.
   - The changelog should be copied correspondingly.
   - Check the hashes in the markdown to ensure they match with the format of previous releases.

5. **Release**:

   - GitHub tagging triggers the `auto-publish.yml` action on the CI, which takes care of the rest.

6. **Bump Version Post-Release**:

   - To comply with the one patch version ahead policy, bump the version after the release.
   - Example: `Post-Release Version Bump <https://github.com/catalystneuro/neuroconv/commit/89d5e41f5140c3aa1ffa066974befb21c7a01567>`_
