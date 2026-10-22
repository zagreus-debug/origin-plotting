#!/usr/bin/env python3
"""Smoke tests for the no-Origin chemistry plotter."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "plot_chem.py"
OUT = ROOT / "tests" / "_out_py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def report(name: str) -> str:
    return (OUT / f"{name}_fit.txt").read_text(encoding="utf-8")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        old.unlink()

    base = ["--x", "invT_K", "--y", "ln_p_p0", "--outdir", str(OUT)]
    result = run("--input", "examples/clausius_clapeyron.csv", *base,
                 "--fit", "auto", "--title", "Vapor pressure", "--name", "linear_auto")
    check(result.returncode == 0, f"linear auto exits 0 ({result.stderr.strip()})")
    text = report("linear_auto")
    check("model: linear" in text, "auto selects linear for the linearized data")
    check("-5152.1" in text, "linear slope matches the reference")
    with Image.open(OUT / "linear_auto.png") as im:
        check(im.width >= 2000 and im.height >= 1400, "300 dpi PNG has publication size")
    check((OUT / "linear_auto.pdf").exists(), "PDF is produced")

    result = run("--input", "examples/first_order_kinetics.csv", "--x", "t_s", "--y", "A_abs",
                 "--fit", "auto", "--outdir", str(OUT), "--name", "kinetics_auto")
    check(result.returncode == 0, "kinetics auto exits 0")
    text = report("kinetics_auto")
    check("model: exp" in text, "auto selects exponential for first-order decay")
    check("0.799" in text and "-0.0498" in text, "exponential parameters match")

    result = run("--input", "examples/clausius_clapeyron.csv", *base,
                 "--fit", "quad", "--outdir", str(OUT), "--name", "quad")
    check(result.returncode == 0, "explicit quadratic fit exits 0")
    check("model: quad" in report("quad"), "explicit model is honored")

    result = run("--input", "examples/clausius_clapeyron.csv", *base,
                 "--fit", "none", "--outdir", str(OUT), "--name", "none")
    check(result.returncode == 0, "no-fit mode exits 0")
    check("model: none" in report("none"), "no-fit report is written")

    result = run("--input", "examples/clausius_clapeyron.csv", "--x", "missing", "--y", "ln_p_p0",
                 "--outdir", str(OUT), "--name", "bad")
    check(result.returncode != 0, "missing column is rejected")

    xlsx = OUT / "input.xlsx"
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["x", "y"])
    for i in range(1, 7):
        ws.append([i, 2 * i + 1])
    wb.save(xlsx)
    result = run("--input", str(xlsx), "--x", "x", "--y", "y", "--fit", "linear",
                 "--outdir", str(OUT), "--name", "xlsx")
    check(result.returncode == 0, "xlsx input exits 0")
    check("model: linear" in report("xlsx"), "xlsx input is fitted")

    print("ALL PYTHON CHECKS DONE")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
