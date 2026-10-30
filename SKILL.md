---
name: origin-plotting
description: Create publication-ready chemistry figures from tabular data with optional automatic model fitting, including Origin-style PNG/PDF for users without Origin and real .opju projects when Origin is available. Use when the user asks to 用 Origin 绘图, 画化学实验图, or fit and plot lab data.
---

# Chemistry plotting

This is an agent-neutral skill. `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`,
`.cursor/rules/`, `.windsurf/rules/`, `.github/copilot-instructions.md`, and
`CONVENTIONS.md` are thin entrypoints to this file.

Choose the renderer before doing anything else:

1. **No Origin, or a general chemistry plot** → [scripts/plot_chem.py](scripts/plot_chem.py).
   This is the default. It produces a clean 300 dpi PNG/PDF with Pillow and
   works without Origin, NumPy, SciPy, pandas, or matplotlib. Its PDF is raster.
2. **Multi-panel, dual Y, inset, broken axis, 3D, heatmap, contour, bar/pie/
   box, error band, vector PDF, or arbitrary formula fit** →
   [scripts/plot_advanced.py](scripts/plot_advanced.py) with a JSON spec.
   Requires `pip install -r requirements-advanced.txt` (matplotlib + scipy).
   This is also the path for vector PDF output.
3. **User explicitly needs a `.opju` or a real Origin export** →
   [scripts/origin_plot.ps1](scripts/origin_plot.ps1), only on a licensed
   Windows Origin installation.

Never deliver an image with Origin's "demo" watermark. A Pillow-rendered figure
is always watermark-free; call it "Origin-style" rather than an Origin export.

## Fit choice

Use the model the user names. Map common Chinese/English names:

- 线性 → `linear`
- 二次 → `quad`
- 指数 → `exp`
- 幂 → `power`
- 对数 → `log`
- 饱和/Langmuir → `langmuir`
- 不拟合 → `none`

If the user does not specify, use `auto`. The script fits every valid model and
selects by AICc, preferring linear when it is within 2 AICc of the best. Report
the selected model, equation and R². If the physical law is known, pass that
model explicitly instead of relying on auto.

## No-Origin workflow

```powershell
python scripts/plot_chem.py --input data.csv --x invT_K --y ln_p_p0 --fit auto `
  --title "Saturated Vapor Pressure" --xlabel "1/T (K^-1)" --ylabel "ln(p/p0)" `
  --outdir output --name figure
```

Common chemistry transforms belong in the table, not hidden in the model:

- Clausius-Clapeyron / Arrhenius: `1/T`, `ln(p/p0)`, `ln(k)`
- First-order kinetics: concentration vs time, `exp`
- Beer-Lambert: absorbance vs concentration, `linear`
- Adsorption: amount vs concentration, `langmuir`

Supports CSV/TSV/XLSX, optional error bars, scatter/line styles, Chinese labels,
and PNG/PDF plus a `*_fit.txt` report.

## Advanced JSON figures

```powershell
pip install -r requirements-advanced.txt
python scripts/plot_advanced.py --spec examples/advanced/advanced_xy.json `
  --outdir advanced_output --name figure
```

Use `examples/advanced/advanced_gallery.json` for bar, pie, box, heatmap,
contour and 3D panels. XY panels support multiple series, `axis: "right"`,
error bands, insets, `broken: {"x": [...]}` or `{"y": [...]}`, custom limits,
ticks, colors, alpha and legend placement.

For a custom nonlinear fit, put a safe formula and parameter list in the spec:

```json
"fit": {
  "formula": "a*exp(-b*x)+c",
  "params": ["a", "b", "c"],
  "p0": [0.7, 0.05, 0.1]
}
```

The formula evaluator is AST-whitelisted; it never executes arbitrary Python.
Advanced line/text PDFs are vector; heatmaps and surfaces embed raster layers.

## Origin workflow

```powershell
powershell -File scripts/origin_plot.ps1 `
  -Csv data.csv -X invT_K -Y ln_p_p0 -Fit `
  -Title "Saturated Vapor Pressure" `
  -XLabel "1/T (K^-1)" -YLabel "ln(p/p0)" `
  -OutDir output -Name figure -Pdf
```

This path is scatter + linear fit only. Labels and paths must be ASCII.

Hard-won Origin rules:

- Run `powershell -File scripts/origin_plot.ps1 -DetectOnly` first. The script
  finds `Origin64.exe` from the Windows uninstall registry and standard
  `OriginLab` folders; use `-OriginExe` for portable/custom installations.
- Run COM in the interactive desktop session. Under a sandbox account Origin
  shows the "User Files Folder" dialog and COM fails with `0x80080005`. The
  script now exits `2` before that dialog when the Windows identity does not
  match the desktop profile. Rerun under the desktop user; do not click through
  the dialog.
- If the COM ProgID exists but its CLSID registration is stale, the script
  repairs only the current user's `HKCU\Software\Classes` entries from the
  discovered executable and retries.
- Stage files in `%TEMP%` or the Origin User Files folder, then copy to the
  final output folder. Non-ASCII paths break LabTalk file commands.
- `$o.Save(path)` is reliable; `save -i` can return True and write nothing.
- Add a line plot with `layer -i200 Book_Col`; `%(1,3)` can silently do nothing.
- Axis titles come from column long names; `layer.x.label$` is unreliable.
- Label position uses `label -s -sa -d (x) (y)`, y from the page top.
- `expGraph` returning False or no file means export is blocked, usually demo
  mode. Stop; do not deliver a watermarked image.

## Verify before replying

- Open the PNG and check axes, labels, data, fit line, equation and R².
- Confirm the fit report and the stated model match the user's request.
- For Origin, reload the `.opju` (`FindWorksheet`, `FindGraphLayer`) and confirm
  the PNG/PDF exists and has no tiled "demo" watermark.

## Quick diagnosis

| Symptom | Cause | Fix |
|---|---|---|
| `Pillow is required` | Missing dependency | `pip install pillow` |
| `.xlsx` fails | Missing openpyxl | `pip install openpyxl` |
| Advanced spec imports fail | Missing matplotlib/scipy | `pip install -r requirements-advanced.txt` |
| Auto picks a surprising model | AICc preference | Pass `--fit` explicitly |
| `Origin64.exe was not found` | Install is custom/portable | Run `-DetectOnly`; pass `-OriginExe` |
| COM `0x80080005`, UFF dialog | Sandbox account | Run in the desktop session |
| Exit code `2`, desktop context false | Sandbox identity | Rerun from the desktop user's terminal |
| Origin export false, no file | Demo/unlicensed | Activate Origin; stop |
| Origin save true, file missing | `save -i` or non-ASCII path | `$o.Save()` to ASCII path |
