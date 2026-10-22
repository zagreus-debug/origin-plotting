# origin-plotting

Publication-quality chemistry figures from tabular data, **with or without
Origin**.

- **No Origin?** `scripts/plot_chem.py` renders a clean 300 dpi PNG/PDF with
  Pillow. No license, watermark, network, NumPy, pandas, or matplotlib needed.
- **Have Origin?** `scripts/origin_plot.ps1` builds a real `.opju`, exports
  PNG/PDF, and refuses to deliver a demo-watermarked image.

This repository is also a Codex skill. Copy it to
`%USERPROFILE%\.codex\skills\origin-plotting` and ask Codex to
"用 Origin 绘图" or "画化学实验图".

## Features

- CSV/TSV/XLSX input; choose X and Y columns by header.
- Optional Y error bars and scatter/line/line+symbol styles.
- Fitting: automatic, linear, quadratic, exponential, power, logarithmic,
  Langmuir (saturation), or none.
- Auto mode fits every valid model and selects by AICc, preferring the simpler
  linear model when it is statistically close.
- 300 dpi PNG/PDF plus a plain-text fit report.
- Chinese or English labels in the no-Origin renderer.

## Install

```powershell
pip install -r requirements.txt
```

Only `Pillow` is needed for plotting; `openpyxl` adds `.xlsx` input. Origin is
optional. Python 3.9 or later.

As a Codex skill:

```powershell
Copy-Item -Recurse . "$env:USERPROFILE\.codex\skills\origin-plotting"
```

## Quick start without Origin

Clausius-Clapeyron example:

```powershell
python scripts/plot_chem.py `
  --input examples/clausius_clapeyron.csv `
  --x invT_K --y ln_p_p0 --fit auto `
  --title "Saturated Vapor Pressure of Water" `
  --xlabel "1/T (K^-1)" --ylabel "ln(p/p0)" `
  --outdir origin_output --name vapor_pressure
```

The selected model is `linear`:

```text
y = -5152 x + 13.83
R2 = 0.999778
```

First-order kinetics example:

```powershell
python scripts/plot_chem.py `
  --input examples/first_order_kinetics.csv `
  --x t_s --y A_abs --fit auto `
  --title "First-order kinetics" --xlabel "t / s" --ylabel "A" `
  --outdir origin_output --name kinetics
```

Auto mode selects `exp`:

```text
y = 0.7997 exp(-0.04984 x)
R2 = 0.999999
```

## Fit models

| `--fit` | Model |
|---|---|
| `auto` (default) | Fit all valid models, choose by AICc |
| `none` | Scatter only |
| `linear` / `线性` | `y = a x + b` |
| `quad` / `二次` | `y = a x^2 + b x + c` |
| `exp` / `指数` | `y = a exp(b x)` |
| `power` / `幂` | `y = a x^b` |
| `log` / `对数` | `y = a + b ln(x)` |
| `langmuir` / `饱和` | `y = a x / (b + x)` |

If the user names a model, pass it explicitly. If not, use `auto` and state the
selected model and constraints in the result.

## Chemistry recipes

| Experiment | Plot |
|---|---|
| Clausius-Clapeyron | `ln(p/p0)` vs `1/T`, linear |
| Arrhenius | `ln(k)` vs `1/T`, linear |
| First-order kinetics | concentration/absorbance vs time, exponential |
| Beer-Lambert | absorbance vs concentration, linear |
| Adsorption saturation | amount adsorbed vs concentration, Langmuir |

Do the physical transform in the data table (for example `1/T` and
`ln(p/p0)`) so the axes and fitted parameters stay interpretable.

## Main options

| Option | Meaning |
|---|---|
| `--input` | CSV/TSV/TXT/XLSX |
| `--x`, `--y` | Column names |
| `--yerr` | Optional error column |
| `--sheet` | XLSX sheet name |
| `--fit` | Model or `auto` |
| `--title`, `--xlabel`, `--ylabel` | Labels (Unicode supported) |
| `--style` | `scatter`, `line`, `line+symbol` |
| `--data-label`, `--fit-label` | Legend text |
| `--outdir`, `--name` | Output folder/base name |
| `--dpi` | 300 by default |

Outputs:

```text
origin_output/
  vapor_pressure.png
  vapor_pressure.pdf
  vapor_pressure_fit.txt
```

## Origin project path

Use this only when the user asks for `.opju` or an actual Origin export, and
Origin is installed and activated:

```powershell
powershell -File scripts/origin_plot.ps1 `
  -Csv examples/clausius_clapeyron.csv `
  -X invT_K -Y ln_p_p0 -Fit `
  -Title "Saturated Vapor Pressure of Water" `
  -XLabel "1/T (K^-1)" -YLabel "ln(p/p0)" `
  -OutDir origin_output -Name vapor_pressure -Pdf
```

This path supports scatter + linear fit only. Labels and paths must be ASCII
because Origin mangles non-ASCII LabTalk text. If Origin is in demo mode, the
script exits `3` and produces no formal figure.

## Testing

```powershell
# No Origin required
python tests/test_plot_chem.py
powershell -File tests/smoke_test.ps1

# Full Origin integration on an activated Windows desktop
powershell -File tests/smoke_test.ps1 -WithOrigin
```

GitHub Actions runs the no-Origin Python test and the PowerShell dry-run test.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Pillow is required` | `pip install pillow` |
| `.xlsx` input fails | `pip install openpyxl` |
| Chinese labels show boxes | Install a CJK font (SimHei/Noto Sans CJK); Windows fonts are auto-detected |
| Auto picks a surprising model | Pass `--fit linear` (or another model) explicitly |
| Origin COM error / demo watermark | See [SKILL.md](SKILL.md); activate Origin or use the no-Origin plotter |

## Scope

One X/Y series per figure; multi-panel layouts, 3D plots, and arbitrary
user-supplied formulas are out of scope. Named models cover common chemistry
labs.

## License

MIT. See [LICENSE](LICENSE).
