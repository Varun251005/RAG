import sys
import io
import pytest
from pathlib import Path

buf = io.StringIO()
sys.stdout = buf
sys.stderr = buf

try:
    res = pytest.main(["tests/test_api_layer.py", "-vv"])
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    Path("pytest_err.log").write_text(f"CODE: {res}\n\nOUTPUT:\n{buf.getvalue()}")
except Exception as exc:
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    Path("pytest_err.log").write_text(f"EXCEPTION: {exc}\n\nOUTPUT:\n{buf.getvalue()}")
