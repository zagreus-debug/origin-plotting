# origin-plotting

Create publication-ready Origin/OriginPro graphs from tabular data on Windows:
XY scatter, optional linear fit, a reusable `.opju` project, and watermark-free
PNG/PDF export.

This repository is also a Codex skill. Copy the folder to
`%USERPROFILE%\.codex\skills\origin-plotting` and ask Codex to
"用 Origin 绘图".

## Features

- Reads a CSV with headers; chooses X and Y columns by name.
- Sorts by X and plots a scatter graph in Origin.
- Optional linear fit with slope, intercept, R², and equation labels.
- Saves a reusable `.opju` project.
- Exports PNG/PDF and refuses to deliver a demo-watermarked image.
- Uses ASCII staging paths, so Unicode output folders are safe.

## Requirements

- Windows 10/11 with Origin or OriginPro installed and **activated**
- Origin COM automation available (normally true after a normal install)
- PowerShell 5.1 or later
- Origin closed before running the script

The script starts and closes its own Origin instance. In Codex, run it in the
interactive desktop session (escalated if the sandbox account differs from your
desktop account).

## Usage

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\origin_plot.ps1 `
  -Csv .\examples\clausius_clapeyron.csv `
  -X invT_K -Y ln_p_p0 `
  -Title "Saturated Vapor Pressure of Water" `
  -XLabel "1/T (K^-1)" -YLabel "ln(p/p0)" `
  -OutDir .\origin_output -Name vapor_pressure -Fit -Pdf
```

This produces:

```text
origin_output/
  vapor_pressure.opju
  vapor_pressure.png
  vapor_pressure.pdf
```

The example data are the 10 water-vapor-pressure points from the original
worksheet. The fit gives k = -5152.1 K, b = 13.834, R² = 0.99978, and
ΔvapHm = 42.83 kJ/mol using `ΔvapHm = -kR`.

## Options

| Option | Required | Meaning |
|---|---|---|
| `-Csv` | yes | Input CSV with a header row |
| `-X` | yes | X column name |
| `-Y` | yes | Y column name |
| `-Title` | no | Graph title (ASCII) |
| `-XLabel` / `-YLabel` | no | Axis labels (ASCII); default to column names |
| `-OutDir` | no | Output folder; default `.\origin_output` |
| `-Name` | no | Output base name; default `origin_plot` |
| `-Fit` | no | Add a linear fit line and equation/R² labels |
| `-Pdf` | no | Also export PDF |
| `-NoExport` | no | Build/save the project only; no PNG/PDF |
| `-DryRun` | no | Validate data, compute the fit, and write the LabTalk script; no Origin launch |

Labels and names must be ASCII. Origin mangles non-ASCII text passed through
LabTalk; use English labels in the Origin graph.

## Behavior and safety

The script refuses to run if Origin is already open, then creates a clean
project, writes the data and computed fit column, saves the `.opju`, exports,
and closes the instance it started.

If Origin is in demo/unlicensed mode, `expGraph` fails or the exported PNG
contains Origin's tiled "demo" watermark. In either case the script exits with
code `3` and produces **no formal figure**. Activate Origin and rerun.

Exit codes:

- `0` — success
- `1` — input, path, or Origin automation error
- `3` — demo/unlicensed origin; no formal figure produced

## Install as a Codex skill

```powershell
Copy-Item -Recurse . "$env:USERPROFILE\.codex\skills\origin-plotting"
```

Restart Codex, then ask: `用 Origin 绘图，数据在 data.csv，X 列是 ...`.

## Testing

Close Origin, then:

```powershell
# Works without Origin (also runs in GitHub Actions)
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\smoke_test.ps1

# Full check on a Windows desktop with activated Origin
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\smoke_test.ps1 -WithOrigin
```

The default test validates the CSV, fit, LabTalk generation, and input errors.
`-WithOrigin` additionally builds and reloads the `.opju`, checks the worksheet
and graph, and verifies the export path. On an unlicensed Origin it confirms
that demo mode produces no formal figure instead of shipping a watermarked PNG.

## Troubleshooting

| Symptom | Fix |
|---|---|
| COM error `0x80080005` or a "User Files Folder" dialog | Run as the interactive desktop user; complete Origin's first-launch setup once |
| "Origin is already running" | Close Origin, or use a machine where the automation instance can be dedicated |
| Export returns false / no PNG | Activate Origin; demo mode blocks export |
| Save reports success but no file | Use this script (it calls `$o.Save()`), not `save -i`, and keep Origin paths ASCII |
| Second plot missing | Use `layer -i200 PlotData_C`; `%(1,3)` can silently do nothing |
| Axis titles missing | Set column long names before plotting; `layer.x.label$` is unreliable |

## Scope

This tool intentionally covers one job: CSV → XY scatter + optional linear fit
→ Origin project + PNG/PDF. Multi-panel layouts, 3D plots, error bars, and
nonlinear fitting are out of scope.

## License

MIT. See [LICENSE](LICENSE).
