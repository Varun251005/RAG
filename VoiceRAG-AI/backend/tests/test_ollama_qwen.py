import json
import urllib.request
import subprocess
from pathlib import Path

def test_inspect_ollama():
    output = {}

    try:
        ver = subprocess.getoutput("ollama --version")
        output["version"] = ver
    except Exception as exc:
        output["version_error"] = str(exc)

    try:
        models = subprocess.getoutput("ollama list")
        output["models_cli"] = models
    except Exception as exc:
        output["models_cli_error"] = str(exc)

    try:
        req = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
        data = json.loads(req.read().decode())
        output["models_http"] = data
    except Exception as exc:
        output["models_http_error"] = str(exc)

    Path("ollama_status.json").write_text(json.dumps(output, indent=2))
    assert True
