"""R1 — gated 60s Tier-2 receipt script (examples/tier2_receipt.sh)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "tier2_receipt.sh"


def test_r1_tier2_receipt_script_green() -> None:
    assert SCRIPT.is_file()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "TIER-2 RECEIPT GREEN" in proc.stdout
