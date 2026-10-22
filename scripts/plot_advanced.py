#!/usr/bin/env python3
"""Spec-driven advanced chemistry figures (matplotlib + scipy).

The JSON spec supports multi-series XY plots, multi-panel layouts, dual Y axes,
insets, broken axes, bars, pies, boxes, heatmaps, contours, 3D plots, error
bands, custom axes/styles, vector PDF, and arbitrary formula fitting.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

_mpl_dir = Path.cwd() / ".mplconfig"
try:
    _mpl_dir.mkdir(parents=True, exist_ok=True)
except OSError:
    _mpl_dir = Path(os.environ.get("TEMP", ".")) / "origin_plotting_mpl"
    _mpl_dir.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(_mpl_dir)
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors as mcolors
from matplotlib.lines import Line2D
from matplotlib.ticker import AutoMinorLocator
from scipy.interpolate import griddata
from scipy.optimize import curve_fit

from plot_chem import parse_float, read_table


FUNCS = {
    "exp": np.exp, "log": np.log, "ln": np.log, "log10": np.log10,
    "sin": np.sin, "cos": np.cos, "tan": np.tan, "sqrt": np.sqrt,
    "abs": np.abs,
}
CONSTS = {"pi": np.pi, "e": np.e}
NAMED_MODELS = {
    "linear": ("a*x+b", ["a", "b"]),
    "quad": ("a*x**2+b*x+c", ["a", "b", "c"]),
    "exp": ("a*exp(b*x)", ["a", "b"]),
    "exp_offset": ("a*exp(-b*x)+c", ["a", "b", "c"]),
    "power": ("a*x**b", ["a", "b"]),
    "log": ("a+b*log(x)", ["a", "b"]),
    "langmuir": ("a*x/(b+x)", ["a", "b"]),
}


def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def compile_formula(expr: str, params: list[str]):
    tree = ast.parse(expr, mode="eval")
    allowed_names = set(params) | {"x"} | set(FUNCS) | set(CONSTS)
    for node in ast.walk(tree):
        if isinstance(node, ast.Expression):
            continue
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            continue
        if isinstance(node, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.UAdd, ast.USub, ast.Load)):
            continue
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS:
            continue
        if isinstance(node, ast.Name) and node.id in allowed_names:
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            continue
        raise ValueError(f"Unsafe or unsupported token in formula: {ast.dump(node)}")
    code = compile(tree, "<formula>", "eval")

    def func(x, *values):
        env = {"x": np.asarray(x, dtype=float), **FUNCS, **CONSTS}
        env.update(dict(zip(params, values)))
        return np.asarray(eval(code, {"__builtins__": {}}, env), dtype=float)

    return func


def fit_series(x: np.ndarray, y: np.ndarray, spec: dict) -> dict:
    model = spec.get("model")
    if model:
        if model not in NAMED_MODELS:
            raise ValueError(f"Unknown fit model '{model}'.")
        formula, params = NAMED_MODELS[model]
        formula = spec.get("formula", formula)
        params = spec.get("params", params)
    else:
        formula = spec.get("formula")
        params = spec.get("params")
        if not formula or not params:
            raise ValueError("Fit needs 'model' or both 'formula' and 'params'.")
    func = compile_formula(formula, params)
    p0 = spec.get("p0") or [1.0] * len(params)
    bounds = spec.get("bounds") or (-np.inf, np.inf)
    popt, pcov = curve_fit(func, x, y, p0=p0, bounds=bounds, maxfev=40000)
    perr = np.sqrt(np.diag(pcov))
    yhat = func(x, *popt)
    sst = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - float(np.sum((y - yhat) ** 2)) / sst if sst > 0 else 1.0
    return {
        "formula": formula, "params": params, "popt": popt.tolist(),
        "perr": perr.tolist(), "r2": r2, "func": func,
    }


def get_rows(spec: dict, panel: dict, cache: dict) -> tuple[list[str], list[dict]]:
    path = panel.get("data") or spec.get("data")
    if not path:
        raise ValueError("Spec needs a top-level 'data' file or per-panel 'data'.")
    sheet = panel.get("sheet") or spec.get("sheet")
    base = Path(spec.get("_base", "."))
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = base / resolved
    key = (str(resolved), sheet)
    if key not in cache:
        cache[key] = read_table(str(resolved), sheet)
    return cache[key]


def column(rows: list[dict], name: str) -> np.ndarray:
    out = []
    for row in rows:
        value = parse_float(row.get(name))
        out.append(np.nan if value is None else value)
    return np.asarray(out, dtype=float)


def pair_arrays(rows: list[dict], xname: str, yname: str):
    x = column(rows, xname)
    y = column(rows, yname)
    mask = np.isfinite(x) & np.isfinite(y)
    return x[mask], y[mask], mask


def style_axis(ax, panel: dict, skip_lims: bool = False) -> None:
    ax.set_xlabel(panel.get("xlabel", ""), fontsize=11)
    ax.set_ylabel(panel.get("ylabel", ""), fontsize=11)
    if panel.get("title"):
        ax.set_title(panel["title"], fontsize=12)
    if panel.get("xlim") and not skip_lims:
        ax.set_xlim(panel["xlim"])
    if panel.get("ylim") and not skip_lims:
        ax.set_ylim(panel["ylim"])
    if panel.get("xticks") is not None:
        ax.set_xticks(panel["xticks"])
    if panel.get("yticks") is not None:
        ax.set_yticks(panel["yticks"])
    if panel.get("xscale"):
        ax.set_xscale(panel["xscale"])
    if panel.get("yscale"):
        ax.set_yscale(panel["yscale"])
    ax.tick_params(direction="in", top=True, right=True, width=1.0, length=5)
    ax.xaxis.set_minor_locator(AutoMinorLocator())
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    for spine in ax.spines.values():
        spine.set_linewidth(1.1)


def series_xy(rows, series, ax):
    x, y, mask = pair_arrays(rows, series["x"], series["y"])
    if len(x) == 0:
        raise ValueError(f"Series '{series.get('label')}' has no valid rows.")
    color = series.get("color", "#d62728")
    alpha = float(series.get("alpha", 1.0))
    marker = series.get("marker", "o")
    line = bool(series.get("line", False))
    label = series.get("label", series["y"])
    if series.get("band"):
        lo, hi = series["band"]
        lo_y = column(rows, lo)[mask]
        hi_y = column(rows, hi)[mask]
        band_mask = np.isfinite(lo_y) & np.isfinite(hi_y)
        if band_mask.any():
            ax.fill_between(x[band_mask], lo_y[band_mask], hi_y[band_mask],
                            color=color, alpha=float(series.get("band_alpha", 0.2)), linewidth=0)
    if series.get("yerr"):
        err = column(rows, series["yerr"])[mask]
        ax.errorbar(x, y, yerr=err, fmt="none", ecolor=color, elinewidth=1.0, capsize=3, alpha=alpha)
    if line:
        ax.plot(x, y, "-", color=color, lw=float(series.get("lw", 1.6)),
                marker=marker, ms=float(series.get("ms", 6)), alpha=alpha, label=label)
    else:
        ax.plot(x, y, marker, color=color, ms=float(series.get("ms", 6)),
                mec=series.get("edge", color), alpha=alpha, label=label)
    return x, y, color


def add_fit(ax, x, y, color, fit_spec, report, panel_name, record=True):
    fit = fit_series(x, y, fit_spec)
    xs = np.linspace(float(x.min()), float(x.max()), 400)
    ax.plot(xs, fit["func"](xs, *fit["popt"]), "-", color=fit_spec.get("color", color),
            lw=float(fit_spec.get("lw", 1.8)), label=fit_spec.get("label", "Fit"))
    if fit_spec.get("annotate", True):
        text = fit["formula"] + "\nR2 = " + f"{fit['r2']:.6f}"
        ax.text(float(fit_spec.get("x", 0.04)), float(fit_spec.get("y", 0.04)), text,
                transform=ax.transAxes, fontsize=8, va="bottom", ha="left")
    if record:
        report.append({
            "panel": panel_name, "formula": fit["formula"], "params": fit["params"],
            "popt": fit["popt"], "perr": fit["perr"], "r2": fit["r2"],
        })


def break_axes(fig, ax, panel):
    ss = ax.get_subplotspec()
    ax.set_visible(False)
    full_xlim = panel.get("xlim") or ax.get_xlim()
    full_ylim = panel.get("ylim") or ax.get_ylim()
    if panel["broken"].get("y"):
        y1, y2 = panel["broken"]["y"]
        gs = ss.subgridspec(2, 1, height_ratios=[1, 1], hspace=0.06)
        hi = fig.add_subplot(gs[0])
        lo = fig.add_subplot(gs[1])
        for a in (lo, hi):
            a.set_xlim(full_xlim)
        lo.set_ylim(full_ylim[0], y1)
        hi.set_ylim(y2, full_ylim[1])
        lo.spines["top"].set_visible(False)
        hi.spines["bottom"].set_visible(False)
        lo.tick_params(top=False, labeltop=False)
        hi.tick_params(bottom=False, labelbottom=False)
        d = 0.012
        for x0 in (0, 1):
            for a, y0 in ((lo, 1), (hi, 0)):
                a.plot((x0 - d, x0 + d), (y0 - d, y0 + d), transform=a.transAxes,
                       color="k", clip_on=False, lw=1)
        return [lo, hi], "y"
    x1, x2 = panel["broken"]["x"]
    gs = ss.subgridspec(1, 2, width_ratios=[1, 1], wspace=0.06)
    left = fig.add_subplot(gs[0])
    right = fig.add_subplot(gs[1])
    left.set_xlim(full_xlim[0], x1)
    right.set_xlim(x2, full_xlim[1])
    for a in (left, right):
        a.set_ylim(full_ylim)
    left.spines["right"].set_visible(False)
    right.spines["left"].set_visible(False)
    left.tick_params(right=False, labelright=False)
    right.tick_params(left=False, labelleft=False)
    d = 0.012
    for y0 in (0, 1):
        for a, x0 in ((left, 1), (right, 0)):
            a.plot((x0 - d, x0 + d), (y0 - d, y0 + d), transform=a.transAxes,
                   color="k", clip_on=False, lw=1)
    return [left, right], "x"


def render_xy(fig, ax, panel, rows, report, panel_name, small=False):
    series_list = panel.get("series") or []
    if not series_list:
        raise ValueError("XY panel needs at least one series.")
    broken = bool(panel.get("broken")) and not small
    if broken and any(s.get("axis") == "right" for s in series_list):
        raise ValueError("Dual Y axis combined with a broken axis is not supported.")
    if broken:
        for series in series_list:
            series_xy(rows, series, ax)
    axes = [ax]
    mode = None
    if broken:
        axes, mode = break_axes(fig, ax, panel)

    right = None
    handles = []
    for idx, series in enumerate(series_list):
        if series.get("axis") == "right":
            if right is None:
                right = axes[0].twinx()
            targets = [right]
        else:
            targets = axes
        first = True
        for target in targets:
            x, y, color = series_xy(rows, series, target)
            if series.get("fit"):
                add_fit(target, x, y, color, series["fit"], report,
                        f"{panel_name}/{series.get('label', idx)}", record=first)
            first = False
        handles.append(Line2D([], [], color=color, marker=series.get("marker", "o"),
                              linestyle="-" if series.get("line") else "None",
                              label=series.get("label", series["y"])))
        if series.get("fit"):
            handles.append(Line2D([], [], color=series["fit"].get("color", color),
                                  linestyle="-", label=series["fit"].get("label", "Fit")))

    for a in axes:
        style_axis(a, panel, skip_lims=broken)
    if broken:
        for a in axes:
            a.set_xlabel("")
            a.set_ylabel("")
            a.set_title("")
        if mode == "y":
            axes[0].tick_params(axis="x", which="both", top=False)
            axes[1].tick_params(axis="x", which="both", bottom=False, labelbottom=False)
        else:
            axes[0].tick_params(axis="y", which="both", right=False)
            axes[1].tick_params(axis="y", which="both", left=False, labelleft=False)
        axes[0].set_xlabel(panel.get("xlabel", ""), fontsize=11)
        axes[0].set_ylabel(panel.get("ylabel", ""), fontsize=11)
        if panel.get("title"):
            axes[0].set_title(panel["title"], fontsize=12)
    if right is not None:
        right.set_ylabel(panel.get("right_ylabel", ""), fontsize=11)
        if panel.get("right_ylim"):
            right.set_ylim(panel["right_ylim"])
        if panel.get("right_yticks") is not None:
            right.set_yticks(panel["right_yticks"])
        right.tick_params(direction="in", right=True, width=1.0, length=5)
    if panel.get("legend", {}).get("show", True) and handles:
        loc = panel.get("legend", {}).get("loc", "upper right")
        axes[0].legend(handles=handles, loc=loc,
                       frameon=panel.get("legend", {}).get("frame", True),
                       fontsize=8 if small else 9)
    if panel.get("inset") and not small:
        bounds = panel["inset"].get("bounds", [0.62, 0.62, 0.3, 0.3])
        parent = axes[-1] if broken else ax
        iax = parent.inset_axes(bounds)
        render_xy(fig, iax, panel["inset"], rows, report, panel_name + "/inset", small=True)
    return axes[0]


def render_bar(ax, rows, panel):
    xcol, ycol = panel["x"], panel["y"]
    labels = [str(r.get(xcol, "")) for r in rows]
    y = column(rows, ycol)
    mask = np.isfinite(y)
    labels = [l for l, m in zip(labels, mask) if m]
    y = y[mask]
    idx = np.arange(len(y))
    err = column(rows, panel["yerr"])[mask] if panel.get("yerr") else None
    colors = panel.get("colors")
    ax.bar(idx, y, yerr=err, color=colors, alpha=float(panel.get("alpha", 0.85)),
           edgecolor=panel.get("edge", "black"), width=float(panel.get("width", 0.7)))
    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=float(panel.get("rotate", 0)))
    style_axis(ax, panel)


def render_pie(ax, rows, panel):
    labels = [str(r.get(panel["labels"], "")) for r in rows]
    values = column(rows, panel["values"])
    mask = np.isfinite(values) & (values > 0)
    ax.pie(values[mask], labels=[l for l, m in zip(labels, mask) if m],
           colors=panel.get("colors"), autopct=panel.get("autopct", "%1.1f%%"),
           startangle=float(panel.get("startangle", 90)),
           wedgeprops={"alpha": float(panel.get("alpha", 1.0))})
    if panel.get("title"):
        ax.set_title(panel["title"])


def render_box(ax, rows, panel):
    data, labels = [], []
    for s in panel.get("series", []):
        values = column(rows, s["y"])
        values = values[np.isfinite(values)]
        data.append(values)
        labels.append(s.get("label", s["y"]))
    try:
        bp = ax.boxplot(data, tick_labels=labels, patch_artist=True, widths=0.6)
    except TypeError:
        bp = ax.boxplot(data, labels=labels, patch_artist=True, widths=0.6)
    for i, patch in enumerate(bp["boxes"]):
        color = (panel.get("colors") or ["#4c72b0"])[i % len(panel.get("colors") or ["#4c72b0"])]
        patch.set_facecolor(color)
        patch.set_alpha(float(panel.get("alpha", 0.8)))
    if panel.get("rotate"):
        ax.tick_params(axis="x", labelrotation=float(panel["rotate"]))
    style_axis(ax, panel)


def grid_data(rows, panel):
    x, y, z = column(rows, panel["x"]), column(rows, panel["y"]), column(rows, panel["z"])
    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    x, y, z = x[mask], y[mask], z[mask]
    xi = np.linspace(x.min(), x.max(), int(panel.get("nx", 120)))
    yi = np.linspace(y.min(), y.max(), int(panel.get("ny", 120)))
    X, Y = np.meshgrid(xi, yi)
    Z = griddata((x, y), z, (X, Y), method=panel.get("interp", "cubic"))
    if np.isnan(Z).all():
        Z = griddata((x, y), z, (X, Y), method="nearest")
    return X, Y, Z


def render_heatmap(ax, rows, panel):
    X, Y, Z = grid_data(rows, panel)
    mesh = ax.pcolormesh(X, Y, Z, shading="auto", cmap=panel.get("cmap", "viridis"),
                         vmin=panel.get("vmin"), vmax=panel.get("vmax"))
    cbar = ax.figure.colorbar(mesh, ax=ax)
    cbar.set_label(panel.get("cbar_label", ""))
    style_axis(ax, panel)


def render_contour(ax, rows, panel):
    X, Y, Z = grid_data(rows, panel)
    cmap = panel.get("cmap", "viridis")
    levels = int(panel.get("levels", 12))
    cf = ax.contourf(X, Y, Z, levels=levels, cmap=cmap,
                     vmin=panel.get("vmin"), vmax=panel.get("vmax"))
    if panel.get("lines", True):
        ax.contour(X, Y, Z, levels=levels, colors="black", linewidths=0.4)
    cbar = ax.figure.colorbar(cf, ax=ax)
    cbar.set_label(panel.get("cbar_label", ""))
    style_axis(ax, panel)


def render_3d(fig, ax, rows, panel):
    ss = ax.get_subplotspec()
    ax.set_visible(False)
    ax3 = fig.add_subplot(ss, projection="3d")
    x, y, z = column(rows, panel["x"]), column(rows, panel["y"]), column(rows, panel["z"])
    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    x, y, z = x[mask], y[mask], z[mask]
    if panel.get("kind", "scatter") == "surface":
        X, Y, Z = grid_data(rows, panel)
        ax3.plot_surface(X, Y, Z, cmap=panel.get("cmap", "viridis"), alpha=float(panel.get("alpha", 1.0)))
    else:
        ax3.scatter(x, y, z, c=panel.get("color", "#d62728"), s=float(panel.get("size", 20)),
                    alpha=float(panel.get("alpha", 1.0)))
    ax3.set_xlabel(panel.get("xlabel", panel["x"]))
    ax3.set_ylabel(panel.get("ylabel", panel["y"]))
    ax3.set_zlabel(panel.get("zlabel", panel["z"]))
    if panel.get("title"):
        ax3.set_title(panel["title"])
    return ax3


def render_panel(fig, ax, panel, spec, cache, report, name):
    ptype = panel.get("type", "xy")
    headers, rows = get_rows(spec, panel, cache)
    if ptype == "xy":
        render_xy(fig, ax, panel, rows, report, name)
    elif ptype == "bar":
        render_bar(ax, rows, panel)
    elif ptype == "pie":
        render_pie(ax, rows, panel)
    elif ptype == "box":
        render_box(ax, rows, panel)
    elif ptype == "heatmap":
        render_heatmap(ax, rows, panel)
    elif ptype == "contour":
        render_contour(ax, rows, panel)
    elif ptype == "3d":
        render_3d(fig, ax, rows, panel)
    else:
        raise ValueError(f"Unknown panel type '{ptype}'.")


def build(spec: dict, outdir: Path, name: str, dpi: int) -> tuple[Path, Path, Path]:
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "SimSun", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "axes.linewidth": 1.1,
        "figure.facecolor": "white",
    })
    layout = spec.get("layout", {"rows": 1, "cols": 1})
    rows_n, cols_n = int(layout["rows"]), int(layout["cols"])
    figsize = spec.get("figsize", [10, 7.5])
    fig, axes = plt.subplots(rows_n, cols_n, figsize=figsize, squeeze=False)
    report = []
    cache = {}
    panels = spec.get("panels", [])
    for i, panel in enumerate(panels):
        if i >= rows_n * cols_n:
            raise ValueError("More panels than layout cells.")
        ax = axes.flat[i]
        render_panel(fig, ax, panel, spec, cache, report, f"panel{i + 1}")
    for j in range(len(panels), rows_n * cols_n):
        axes.flat[j].set_visible(False)
    if spec.get("suptitle"):
        fig.suptitle(spec["suptitle"], fontsize=14)
    fig.tight_layout()
    outdir.mkdir(parents=True, exist_ok=True)
    png = outdir / f"{name}.png"
    pdf = outdir / f"{name}.pdf"
    txt = outdir / f"{name}_fit.txt"
    fig.savefig(png, dpi=dpi, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    lines = []
    for item in report:
        lines.append(f"[{item['panel']}] {item['formula']}  R2={item['r2']:.8f}")
        for p, v, e in zip(item["params"], item["popt"], item["perr"]):
            lines.append(f"{p} = {v:.8g} +/- {e:.3g}")
    txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return png, pdf, txt


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--spec", required=True)
    p.add_argument("--outdir", default="advanced_output")
    p.add_argument("--name", default="advanced_figure")
    p.add_argument("--dpi", type=int, default=300)
    args = p.parse_args()
    with open(args.spec, "r", encoding="utf-8") as handle:
        spec = json.load(handle)
    spec["_base"] = str(Path(args.spec).resolve().parent)
    png, pdf, txt = build(spec, Path(args.outdir), args.name, args.dpi)
    print(f"Saved: {png}")
    print(f"Saved: {pdf}")
    print(f"Saved: {txt}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        die(str(exc))
