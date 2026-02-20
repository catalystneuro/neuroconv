.. _ci_workflows:

CI/CD Workflows
===============

NeuroConv uses `GitHub Actions <https://docs.github.com/en/actions/about-github-actions/understanding-github-actions>`_
for continuous integration and delivery. The workflows are organized as a two-tier hierarchy:
**entry-point workflows** (triggered by GitHub events like pull requests or cron schedules) delegate to
`reusable workflows <https://docs.github.com/en/actions/sharing-automations/reusing-workflows>`_
(called via ``workflow_call``). All workflow definitions live in ``.github/workflows/``.

Workflow Architecture
---------------------

The CI system has two layers:

- **Entry-point workflows** are triggered by GitHub events (pull requests, cron schedules, releases).
  They contain no test logic themselves; instead, they delegate to reusable workflows based on
  what changed and when.
- **Reusable workflows** contain the actual test and build steps. They accept parameters
  (Python versions, OS matrix) and can be called by multiple entry-points.

There are four entry-point workflows:

- ``deploy-tests.yml``: runs on every pull request and merge group.
- ``dailies.yml``: runs daily at 4AM UTC. Sends email on failure.
- ``dev-dailies.yml``: runs daily at 4AM UTC. Tests against development branches of upstream dependencies. Sends email on failure.
- ``weeklies.yml``: runs weekly on Sunday at 2AM UTC.

These delegate to the following reusable workflows:

- ``testing.yml``: main test suite (imports, minimal, modality isolation, full with coverage).
- ``dev-testing.yml``: same tests but against dev branches of upstream dependencies, ubuntu-only.
- ``doctests.yml``: executes code examples in the documentation gallery.
- ``live-service-testing.yml``: DANDI, EMBER, and Globus integration tests.
- ``formatwise-installation-testing.yml``: per-format isolated installation and doctest.
- ``neuroconv_docker_testing.yml``: Docker container CLI tests.
- ``rclone_docker_testing.yml``: Rclone Docker container tests.
- ``assess-file-changes.yml``: determines which files changed to route PR tests.
- ``build_docker_image_dev.yml``: builds and pushes a dev Docker image to GHCR.
- ``build_docker_rclone_with_config.yml``: rebuilds the Rclone Docker image.
- ``test-external-links.yml``: Sphinx linkcheck on documentation.

The following table shows which entry-point calls which reusable workflow:

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 35 15 15 15 15

   * - Reusable workflow
     - deploy-tests (PR)
     - dailies
     - dev-dailies
     - weeklies
   * - assess-file-changes
     - x
     -
     -
     -
   * - testing
     - x
     - x
     -
     -
   * - doctests
     - x :sup:`1`
     -
     -
     -
   * - live-service-testing
     - x
     -
     - x
     -
   * - formatwise-installation-testing
     -
     - x
     -
     -
   * - neuroconv_docker_testing
     -
     - x
     -
     -
   * - dev-testing
     -
     -
     - x
     -
   * - build_docker_image_dev
     -
     -
     - x
     -
   * - rclone_docker_testing
     -
     -
     - x
     -
   * - test-external-links
     -
     -
     - x
     -
   * - build_docker_rclone_with_config
     -
     -
     -
     - x

:sup:`1` Doctests run only when conversion gallery changed and source did not.


Configuration
-------------

Test Matrix
~~~~~~~~~~~

The test matrix is parameterized by two files that entry-point workflows load at runtime and pass as
JSON strings to reusable workflows:

- ``.github/workflows/all_python_versions.txt``: currently ``["3.10", "3.13"]``
- ``.github/workflows/all_os_versions.txt``: currently ``["ubuntu-latest", "macos-latest", "windows-latest", "macos-15-intel"]``

To add or remove a Python version or OS from the matrix, edit the corresponding file. All entry-point
workflows pick up the change automatically.

Test Data
~~~~~~~~~

Test data flows through three layers:

1. **GIN repositories**: canonical source (ephy_testing_data, ophys_testing_data, behavior_testing_data).
2. **S3 mirror**: maintained by ``update-s3-testing-data.yml`` (manual dispatch) for faster CI downloads.
3. **GitHub Actions cache**: the ``load-data`` composite action (in ``.github/actions/load-data/``)
   caches data keyed by the GIN repository HEAD hash for cross-OS reuse within CI runs.


Entry-Point Workflows
---------------------

deploy-tests.yml (Pull Requests and Merge Groups)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Triggered on ``pull_request`` (synchronize, opened, reopened, ready_for_review), ``merge_group``,
and ``workflow_dispatch``. Uses ``cancel-in-progress`` concurrency per branch.

Flow:

1. **load_python_and_os_versions**: reads the matrix config files.
2. **assess-file-changes**: calls the reusable ``assess-file-changes.yml`` workflow to determine what changed.
3. **Conditional routing:**

   - If ``SOURCE_CHANGED``: runs ``testing.yml`` and ``live-service-testing.yml``.
   - If only ``CONVERSION_GALLERY_CHANGED`` (and source did not change): runs ``doctests.yml`` only.
   - If ``SOURCE_CHANGED`` and the PR is not a draft: enforces that ``CHANGELOG.md`` was updated.

4. **Draft PR optimization:** when the PR is a draft, the matrix is reduced to Python 3.10 +
   ubuntu-latest only for faster feedback. When the PR is marked ready for review, the full matrix
   runs automatically (via the ``ready_for_review`` trigger type).
5. **check-final-status**: uses ``re-actors/alls-green`` to produce a single aggregated status check.
   This allows individual jobs to be skipped (e.g., doctests when source changed) without blocking merge.

dailies.yml (Daily Schedule)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Triggered daily at ``0 4 * * *`` UTC (8PM PST / 5AM CET) and via ``workflow_dispatch``.

Calls ``testing.yml`` (full matrix), ``neuroconv_docker_testing.yml``, and
``formatwise-installation-testing.yml``. Each sub-workflow has a corresponding email notification
job that fires on failure, sending to ``DAILY_FAILURE_EMAIL_LIST`` via ``dawidd6/action-send-mail``.

dev-dailies.yml (Daily Dev Schedule)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Same cron schedule as ``dailies.yml``. Purpose: detect upstream breakage early by testing against
development branches of key dependencies.

Calls ``build_and_upload_docker_image_dev.yml``, ``dev-testing.yml``, ``live-service-testing.yml``,
``rclone_docker_testing.yml``, and ``test-external-links.yml``. Each sub-workflow has an email
notification job on failure.

weeklies.yml (Weekly Schedule)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Triggered weekly on Sunday at ``0 2 * * 0`` UTC (6PM PST / 3AM CET) and via ``workflow_dispatch``.

Calls ``build_and_upload_docker_image_rclone_with_config.yml`` to rebuild the Rclone Docker image
and push to GHCR. Email notification on failure.

Standalone Scheduled Workflows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These run on their own weekly cron schedules and are not called by other workflows:

- **generic_aws_tests.yml**: Monday at noon EST. Runs ``tests/remote_transfer_services/aws_tools_tests.py``.
- **rclone_aws_tests.yml**: Tuesday at noon EST. Runs ``tests/remote_transfer_services/yaml_aws_tools_tests.py``.
- **neuroconv_deployment_aws_tests.yml**: Wednesday at noon EST. Runs ``tests/remote_transfer_services/neuroconv_deployment_aws_tools_tests.py``.

Release Pipeline
~~~~~~~~~~~~~~~~

The release pipeline is a chain of workflows triggered sequentially:

1. **auto-publish.yml**: triggered by a GitHub Release with a tag starting with ``v``. Builds sdist
   and wheel via ``python -m build`` and publishes to PyPI using Trusted Publishing (OIDC, no API token).
2. **build_and_upload_docker_image_latest_release.yml**: triggered by completion of ``auto-publish.yml``.
   Builds and pushes ``ghcr.io/catalystneuro/neuroconv:latest`` and version-tagged images to GHCR.
3. **build_and_upload_docker_image_yaml_variable.yml**: triggered by completion of step 2. Builds
   the YAML variable variant image on top of the latest release.


Reusable Workflows
------------------

assess-file-changes.yml
~~~~~~~~~~~~~~~~~~~~~~~~

Called by ``deploy-tests.yml``. Uses ``tj-actions/changed-files`` to inspect the diff and outputs
three boolean flags:

- ``SOURCE_CHANGED``: true if files under ``src/``, ``tests/``, ``pyproject.toml``, ``setup.py``,
  or ``.github/`` changed.
- ``CONVERSION_GALLERY_CHANGED``: true if files under ``docs/conversion_examples_gallery/`` changed.
- ``CHANGELOG_UPDATED``: true if ``CHANGELOG.md`` was modified.

testing.yml
~~~~~~~~~~~

Called by ``deploy-tests.yml`` and ``dailies.yml``. Inputs: ``python-versions`` and ``os-versions``
(JSON strings). Runs a single job per matrix entry with the following step sequence:

1. Install minimal neuroconv, verify initial imports.
2. Install test dependencies (``--group test``), run import structure tests.
3. Run minimal tests (``tests/test_minimal``).
4. Test each modality in an **isolated virtual environment**:

   - ecephys (``pip install ".[ecephys_minimal]"``)
   - ophys (``pip install ".[ophys_minimal]"``)
   - fiber_photometry (``pip install ".[fiber_photometry]"``)
   - behavior (``pip install ".[behavior]"``)

5. Load test data via the ``load-data`` composite action.
6. Install full requirements (``pip install ".[full]"``), install Wine (Linux only, for Plexon2 support).
7. Run full pytest with coverage.
8. Upload coverage to Codecov (Python 3.10 + ubuntu-latest only).

The modality isolation step catches dependency conflicts that would be hidden by a full installation.

dev-testing.yml
~~~~~~~~~~~~~~~

Called by ``dev-dailies.yml``. Inputs: ``python-versions`` (JSON string). Runs on **ubuntu-latest only**.

Installs full neuroconv then overlays dev/main branches of all major upstream dependencies
(PyNWB, SpikeInterface, HDMF, HDMF-Zarr, NEO, ROIExtractors, ProbeInterface, DANDI CLI).
Runs full pytest without coverage.

doctests.yml
~~~~~~~~~~~~

Called by ``deploy-tests.yml`` (when only the conversion gallery changed). Inputs: ``python-versions``
and ``os-versions``. Runs ``pytest docs`` to execute code examples in the documentation.

live-service-testing.yml
~~~~~~~~~~~~~~~~~~~~~~~~

Called by ``deploy-tests.yml`` and ``dev-dailies.yml``. Inputs: ``python-versions`` and ``os-versions``.

Uses ``max-parallel: 1`` to avoid concurrent API calls to DANDI/EMBER/Globus staging servers.

Includes a credential validation step with clear error messages for external contributors who lack
the required secrets (``DANDI_SANDBOX_API_KEY``, ``EMBER_API_KEY``, AWS credentials).

formatwise-installation-testing.yml
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Called by ``dailies.yml``. Dynamically discovers all formats from the conversion examples gallery.
For each format:

1. Creates a fresh virtual environment with ``uv``.
2. Installs only that format's extras (e.g., ``pip install ".[format_name]"``).
3. Runs the doctest for that format's gallery RST file.
4. Tears down the virtual environment.

Produces a GitHub Job Summary table with per-format pass/fail status.

Docker Testing Workflows
~~~~~~~~~~~~~~~~~~~~~~~~

- **neuroconv_docker_testing.yml**: called by ``dailies.yml``. Pulls the latest release and YAML
  variable Docker images from GHCR, then runs ``tests/remote_transfer_services/docker_yaml_conversion_specification_cli.py``.
- **rclone_docker_testing.yml**: called by ``dev-dailies.yml``. Pulls the rclone_with_config Docker
  image and runs tests with Rclone credentials for Google Drive integration.


Required Secrets
----------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Secret
     - Used by
   * - ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY``
     - testing, dev-testing, live-service-testing, Docker tests, AWS tests, data loading
   * - ``S3_GIN_BUCKET``
     - testing, dev-testing, live-service-testing, Docker tests, data loading
   * - ``CODECOV_TOKEN``
     - testing (coverage upload)
   * - ``DANDI_SANDBOX_API_KEY``
     - live-service-testing, dev-testing, deployment AWS tests
   * - ``EMBER_API_KEY``
     - live-service-testing
   * - ``RCLONE_DRIVE_ACCESS_TOKEN`` / ``RCLONE_DRIVE_REFRESH_TOKEN`` / ``RCLONE_EXPIRY_TOKEN``
     - rclone_docker_testing, rclone_aws_tests, deployment AWS tests
   * - ``DOCKER_UPLOADER_USERNAME`` / ``DOCKER_UPLOADER_PASSWORD``
     - Docker image build and push workflows
   * - ``MAIL_USERNAME`` / ``MAIL_PASSWORD``
     - Email notification jobs
   * - ``DAILY_FAILURE_EMAIL_LIST``
     - Email notification jobs
