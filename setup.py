from pathlib import Path
from shutil import copy

root = Path(__file__).parent
# Create a local copy for the gin test configuration file based on the master file `base_gin_test_config.json`
gin_config_file_base = root / "base_gin_test_config.json"
gin_config_file_local = root / "tests/test_on_data/gin_test_config.json"
if not gin_config_file_local.exists():
    gin_config_file_local.parent.mkdir(parents=True, exist_ok=True)
    copy(src=gin_config_file_base, dst=gin_config_file_local)
