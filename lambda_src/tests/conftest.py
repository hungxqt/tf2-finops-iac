import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import json

@pytest.fixture(autouse=True)
def setup_test_env():
    default_exports = {
        "112233": {
            "source_account_id": "112233",
            "prefix": "cur",
            "export_name": "manifest",
            "allowed_raw_prefix": "cur"
        },
        "112233445566": {
            "source_account_id": "112233445566",
            "prefix": "finops-cur-export",
            "export_name": "finops-export",
            "allowed_raw_prefix": "finops-cur-export"
        }
    }
    old_env = os.environ.get("CUR_EXPORTS_JSON")
    os.environ["CUR_EXPORTS_JSON"] = json.dumps(default_exports)
    yield
    if old_env is not None:
        os.environ["CUR_EXPORTS_JSON"] = old_env
    else:
        os.environ.pop("CUR_EXPORTS_JSON", None)

