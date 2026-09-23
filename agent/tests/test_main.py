from pathlib import Path
import subprocess
import sys


def test_agent_starts() -> None:
    entrypoint = Path(__file__).parents[1] / "src" / "main.py"
    result = subprocess.run([sys.executable, str(entrypoint)], capture_output=True, text=True, check=True)
    assert result.stdout == "DingInvoice Agent\nstatus: ready\nmode: development\n"

