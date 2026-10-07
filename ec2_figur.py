"""
ec2_figur.py
Skisse av c, c1 og a for valt koblingstype (jf. figur 8.3 i NS-EN 1992-1-1).
Teikna med dei faktiske inndataverdiane.
"""

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch


def _maal(ax, p1, p2, tekst, offset=(0, 0), farge="#1f4e79"):
    ax.annotate("", xy=p2, xytext=p1,
                arrowprops=dict(arrowstyle="<->", color=farge, lw=1.1,
                                shrinkA=0, shrinkB=0))
    xm = (p1[0] + p2[0]) / 2 + offset[0]
    ym = (p1[1] + p2[1]) / 2 + offset[1]
    ax.text(xm, ym, tekst, color=farge, ha="center", va="center", fontsize=9,
            bbox=dict(fc="white", ec="none", pad=0.5))


def figur_cd(type_kobling: str, c: float, c1: float, s: float, phi: float,
             a: float, cd: float):
    fig, ax = plt.subplots(figsize=(4.2, 3.2))
    r = phi / 2
    x1 = c1 + r
    y1 = c + r
    x2 = x1 + s
    W = x2 + max(2.2 * phi, 60)
    H = y1 + max(5 * phi, 120)

    # Betongkant: venstre og botn heiltrekte, resten stipla
    ax.plot([0, 0], [0, H], color="black", lw=2)
    ax.plot([0, W], [0, 0], color="black", lw=2)
    ax.plot([0, W, W], [H, H, 0], color="grey", lw=1, ls="--")

    # Stenger
    for x in (x1, x2):
        ax.add_patch(Circle((x, y1), r, color="#a00000", zorder=5))

    if type_kobling == "b":
        # krok/vinkelkrok går opp i planet – vist stipla
        for x in (x1, x2):
            ax.plot([x - r, x - r, x + r, x + r], [y1, y1 + 3 * phi, y1 + 3 * phi, y1],
                    color="#a00000", ls="--", lw=1)
    if type_kobling == "c":
        ax.add_patch(FancyBboxPatch((x1, y1 - r), s, 2 * r,
                                    boxstyle=f"round,pad=0,rounding_size={r}",
                                    fill=False, ec="#a00000", ls="--", lw=1))

    # Mål med hjelpeliner (forlenging frå stang/kant til målelina)
    hl = dict(color="#4f6378", lw=0.9, zorder=3)
    ov = 6  # overheng forbi målelina [mm]
    if type_kobling in ("a", "c"):
        xd = x1 - 1.6 * r - 8
        ax.plot([xd - ov, x1], [y1 - r, y1 - r], **hl)            # horisontal frå underkant stang
        _maal(ax, (xd, 0), (xd, y1 - r), f"$c$ = {c:.0f}", offset=(-22, 0))
    if type_kobling in ("a", "b"):
        ym = y1 + (3 * phi + 15 if type_kobling == "b" else 2.2 * r + 10)
        y0 = y1 + (3 * phi if type_kobling == "b" else 0)
        for xv in (x1 - r, x1 + r, x2 - r):                         # vertikale frå stangkantane
            ax.plot([xv, xv], [y0, ym + ov], **hl)
        _maal(ax, (0, ym), (x1 - r, ym), f"$c_1$ = {c1:.0f}", offset=(0, 10))
        _maal(ax, (x1 + r, ym), (x2 - r, ym), f"$a$ = {a:.0f}", offset=(0, 10))

    formel = {"a": r"$c_\mathrm{d} = \min(a/2,\ c_1,\ c)$",
              "b": r"$c_\mathrm{d} = \min(a/2,\ c_1)$",
              "c": r"$c_\mathrm{d} = c$"}[type_kobling]
    ax.set_title(f"{formel} = {cd:.1f} mm", fontsize=10)
    ax.set_xlim(-45, W + 5)
    ax.set_ylim(-10, H + 5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    return fig
