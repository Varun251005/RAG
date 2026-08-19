import json
import urllib.request
import subprocess
from pathlib import Path

def test_check_ollama():
    ver = subprocess.getoutput("ollama --version")
    models_output = subprocess.getoutput("ollama list")

    http_output = ""
    try:
        req = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
        data = json.loads(req.read().decode())
        http_output = json.dumps(data, indent=2)
    except Exception as exc:
        http_output = f"Error: {exc}"

    res = f"VERSION:\n{ver}\n\nMODELS:\n{models_output}\n\nHTTP API:\n{http_output}\n"
    Path("ollama_info.txt").write_text(res)
    assert True
