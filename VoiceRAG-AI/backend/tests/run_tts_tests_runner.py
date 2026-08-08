import sys
import io
import time
import pytest
from pathlib import Path

buf = io.StringIO()
sys.stdout = buf
sys.stderr = buf

t0 = time.perf_counter()
try:
    res = pytest.main(["tests/test_tts_voice.py", "-vv", "-s"])
    t1 = time.perf_counter()
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    Path("tts_test_results.log").write_text(f"PYTEST CODE: {res}\nTOTAL TIME: {t1-t0:.2f}s\n\nOUTPUT:\n{buf.getvalue()}")
except Exception as exc:
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    Path("tts_test_results.log").write_text(f"EXCEPTION: {exc}\n\nOUTPUT:\n{buf.getvalue()}")
