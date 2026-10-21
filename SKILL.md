---
name: origin-plotting
description: Create publication-ready Origin/OriginPro graphs from tabular data, save .opju projects, and export watermark-free PNG/PDF. Use when the user asks to 用 Origin 绘图, make an Origin graph, or plot data in Origin.
---

# Origin plotting

Deliver only a watermark-free formal figure. If Origin is demo/unlicensed, stop
and ask the user to activate it. Never ship a watermarked PNG or a screen capture
as the formal export.

## Standard path

For CSV → XY scatter + optional linear fit, run
[scripts/origin_plot.ps1](scripts/origin_plot.ps1). See
[README.md](README.md) for all options.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/origin_plot.ps1 `
  -Csv data.csv -X invT_K -Y ln_p_p0 -Title "Title" `
  -XLabel "1/T (K^-1)" -YLabel "ln(p/p0)" -Fit -Pdf
```

It saves `.opju`, exports PNG/PDF, and exits `3` without a figure in demo mode.
Batch the build, save, and export into one session; do not use GUI dialogs.

## Run as the desktop user

Run Origin COM in the interactive desktop session (escalated in Codex). Under a
sandbox account, Origin opens the "User Files Folder" dialog and COM fails with
`0x80080005`.

```powershell
$o = New-Object -ComObject Origin.ApplicationSI
$o.Visible = 1
```

Refuse to run if Origin is already open; `doc -n` prompts on a modified project.
Never kill an Origin instance you did not create.

## Paths and text

- Every path passed to Origin must be ASCII. Chinese paths can make save/export
  return success while writing nothing.
- Stage files in `%TEMP%` or the Origin User Files folder, then copy to the
  requested output folder with PowerShell.
- Keep `.ps1` files ASCII-only. Origin mangled Chinese passed through LabTalk
  even via a UTF-8 `.ogs`; use English graph text.

## Custom graph pattern

```labtalk
doc -n;
newbook name:="Data" sheet:=1 option:=lsname;
wks.ncols=3;
col(A)={0.00294,0.00288,0.00285};
col(B)={-1.30,-1.03,-0.83};
col(C)=13.834-5152.1*col(A);
wks.col1.type=4;
wks.col2.type=1;
wks.col1.lname$="1/T (K^-1)";   // axis titles come from long names
wks.col2.lname$="ln(p/p0)";
plotxy iy:=(1,2) plot:=201;      // 201 scatter, 200 line, 202 line+symbol
layer -i200 Data_C;              // add the fit as a line
page.zoom=80;
label -s -sa -d (0.5*page.width) (0.03*page.height) -n title "Title";
label -s -sa -d (0.15*page.width) (0.18*page.height) -n eq "y = 13.834 - 5152.1 x";
```

Useful facts:

- `layer -i200 %(1,3)` can return True without adding a plot. Use the dataset
  name `<book>_<column>`.
- `layer.x.label$ = ...` is unreliable; set column long names before plotting.
- Label position uses `-sa -d (x) (y)` with y from the page top. Avoid
  `-px/-py`; malformed options leak into the label text.
- `worksheet -p 201 scatter` can open a blocking dialog; use `plotxy`.

## Fit and export

`fitLR` is handy when licensed but not dependable. Compute slope, intercept and
R² outside Origin, write the fit values into a column, and add it with
`layer -i200`. For Clausius-Clapeyron, `ΔvapHm = -kR`.

```powershell
$o.Save("C:\Users\Public\plot.opju")  # reliable; avoid save -i
$o.Execute('expGraph type:=png path:="C:\Users\Public\plot.png" overwrite:=replace;')
$o.Execute('expGraph type:=pdf path:="C:\Users\Public\plot.pdf" overwrite:=replace;')
```

- `path` is the full file path including extension.
- `expGraph` false or no file means export is blocked (usually demo mode).
- Reopen the project (`$o.Load`, `FindWorksheet`, `FindGraphLayer`) and inspect
  the exported image at full size. Reject any tiled "demo" watermark.

## Quick diagnosis

| Symptom | Cause | Fix |
|---|---|---|
| COM `0x80080005`, UFF dialog | Sandbox account | Run in the desktop session |
| Export false, no file | Demo/unlicensed | Activate Origin; stop |
| Save true, file missing | `save -i` or non-ASCII path | `$o.Save()` to an ASCII path |
| Second plot missing | Wrong `layer -i` reference | `layer -i200 Book_Col` |
| Axis titles absent | `layer.x.label$` failed | Set column long names first |
| `doc -n` hangs | Modified project prompts save | Start clean |
