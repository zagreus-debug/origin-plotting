#!/usr/bin/env python3
"""End-to-end tests for the advanced matplotlib/scipy renderer."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "plot_advanced.py"
OUT = ROOT / "tests" / "_out_adv"
EX = ROOT / "examples" / "advanced"


def run(spec: Path, name: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--spec", str(spec), "--outdir", str(OUT), "--name", name],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    result = run(EX / "advanced_xy.json", "adv_xy")
    check(result.returncode == 0, f"multi-panel XY exits 0 ({result.stderr.strip()})")
    report = (OUT / "adv_xy_fit.txt").read_text(encoding="utf-8")
    a = float(re.search(r"^a = (\S+)", report, re.M).group(1))
    b = float(re.search(r"^b = (\S+)", report, re.M).group(1))
    c = float(re.search(r"^c = (\S+)", report, re.M).group(1))
    check(abs(a - 0.7) < 0.03 and abs(b - 0.05) < 0.003 and abs(c - 0.1) < 0.03,
          "nonlinear fit recovers a*exp(-b*x)+c")
    pdf = (OUT / "adv_xy.pdf").read_bytes()
    check(b"/Subtype /Image" not in pdf, "XY PDF is vector (no embedded image)")
    check((OUT / "adv_xy.png").stat().st_size > 100000, "multi-panel PNG is non-trivial")

    result = run(EX / "advanced_gallery.json", "gallery")
    check(result.returncode == 0, f"gallery exits 0 ({result.stderr.strip()})")
    check((OUT / "gallery.png").stat().st_size > 200000, "gallery PNG is non-trivial")
    check((OUT / "gallery.pdf").exists(), "gallery PDF is produced")

    broken = {
        "data": str((EX / "xy.csv").resolve()),
        "figsize": [6, 4],
        "panels": [{
            "type": "xy",
            "series": [{"label": "A", "x": "time", "y": "A", "line": True}],
            "broken": {"x": [4, 7]},
            "xlabel": "time", "ylabel": "A",
        }],
    }
    broken_path = OUT / "broken_x.json"
    broken_path.write_text(json.dumps(broken), encoding="utf-8")
    result = run(broken_path, "broken_x")
    check(result.returncode == 0, "x-broken axis exits 0")

    custom = {
        "data": str((EX / "xy.csv").resolve()),
        "panels": [{
            "type": "xy",
            "series": [{
                "label": "A", "x": "time", "y": "A", "color": "#ff0000",
                "line": True, "alpha": 0.6,
                "fit": {
                    "formula": "a*exp(-b*x)+c",
                    "params": ["a", "b", "c"],
                    "p0": [0.7, 0.05, 0.1],
                },
            }],
            "xlabel": "time", "ylabel": "A",
            "xlim": [0, 10], "xticks": [0, 5, 10],
            "legend": {"loc": "upper right"},
        }],
    }
    custom_path = OUT / "custom_formula.json"
    custom_path.write_text(json.dumps(custom), encoding="utf-8")
    result = run(custom_path, "custom_formula")
    check(result.returncode == 0, "custom formula fit exits 0")
    check("a*exp(-b*x)+c" in (OUT / "custom_formula_fit.txt").read_text(encoding="utf-8"),
          "custom formula is reported")

    scatter3d = {
        "data": str((EX / "surface.csv").resolve()),
        "panels": [{
            "type": "3d", "x": "x", "y": "y", "z": "z", "kind": "scatter",
            "color": "#ff0000", "alpha": 0.7, "title": "3D scatter",
        }],
    }
    scatter_path = OUT / "scatter3d.json"
    scatter_path.write_text(json.dumps(scatter3d), encoding="utf-8")
    result = run(scatter_path, "scatter3d")
    check(result.returncode == 0, "3D scatter exits 0")

    print("ALL ADVANCED CHECKS DONE")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
