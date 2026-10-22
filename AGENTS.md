# Agent entrypoint

This repository is a cross-agent chemistry plotting skill.

For plotting or fitting tasks:

1. Read `SKILL.md` before acting.
2. Simple XY plots: `scripts/plot_chem.py` (Pillow only).
3. Multi-panel, dual Y, inset, broken axis, 3D, heatmap, contour, bar/pie/box,
   vector PDF, or arbitrary formula fitting: `scripts/plot_advanced.py`.
4. Real `.opju` or Origin export: `scripts/origin_plot.ps1`, only with a
   licensed Windows Origin installation.

Never deliver an Origin demo-watermarked image. If Origin is unlicensed, use
the no-Origin renderer or stop and ask the user to activate Origin.
