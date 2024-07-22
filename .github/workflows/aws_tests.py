name: AWS Tests
on:
  schedule:
    - cron: "0 16 * * 1"  # Weekly at noon on Monday
  pull_request: # TODO, remove when done with this PR

env:
  AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
  AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
  DANDI_API_KEY: ${{ secrets.DANDI_API_KEY }}

jobs:
  run:
    name: ${{ matrix.os }} Python ${{ matrix.python-version }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.9", "3.10", "3.11", "3.12"]
        os: [ubuntu-latest, macos-13, windows-latest]
    steps:
      - uses: actions/checkout@v4
      - run: git fetch --prune --unshallow --tags
      - name: Setup Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Global Setup
        run: |
          python -m pip install -U pip  # Official recommended way
          git config --global user.email "CI@example.com"
          git config --global user.name "CI Almighty"

      - name: Install full requirements
        run: pip install .[aws,test]

      - name: Run subset of tests that use S3 live services
        run: pytest -rsx -n auto tests/test_minimal/test_tools/s3_tools.py
