"""
ec2_rapport.py
Genererer berekningstillegg som PDF per NS-EN 1992-1-1.
Krev:  pip install fpdf2
"""

import io
import math
import os
from datetime import date

import matplotlib
import numpy as np
from fpdf import FPDF

import ec2_boye
import ec2_omfar

_DATO = date.today().strftime("%d.%m.%Y")
_LM = 20        # left/right margin [mm]
_W  = 170       # brukbar sidebreidd (A4=210, marginar 2x20)

# DejaVu Sans er bundla med matplotlib og støttar full Unicode,
# inkludert subscript-siffer (₁₂₃₄₅₆ osb.) som Arial manglar.
_MPL_FONTS   = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
_FONT        = os.path.join(_MPL_FONTS, "DejaVuSans.ttf")
_FONT_BOLD   = os.path.join(_MPL_FONTS, "DejaVuSans-Bold.ttf")
_FONT_ITALIC = os.path.join(_MPL_FONTS, "DejaVuSans-Oblique.ttf")


# ══════════════════════════════════════════════════════════
# Basis PDF-klasse med header/footer
# ══════════════════════════════════════════════════════════

class _PDF(FPDF):
    def __init__(self, tittel: str):
        super().__init__(unit="mm", format="A4")
        self._tittel = tittel
        self.set_margins(_LM, 20, _LM)
        self.set_auto_page_break(auto=True, margin=20)
        self.add_font("Arial",  style="",  fname=_FONT)
        self.add_font("Arial",  style="B", fname=_FONT_BOLD)
        self.add_font("Arial",  style="I", fname=_FONT_ITALIC)

    def header(self):
        self.set_font("Arial", "B", 9)
        self.cell(_W / 2, 6, self._tittel,
                  new_x="RIGHT", new_y="TOP", align="L")
        self.cell(_W / 2, 6, f"NS-EN 1992-1-1  |  {_DATO}",
                  new_x="LMARGIN", new_y="NEXT", align="R")
        self.set_draw_color(80, 80, 80)
        self.line(_LM, self.get_y(), 210 - _LM, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 8, f"Side {self.page_no()}", align="C",
                  new_x="LMARGIN", new_y="NEXT")


# ══════════════════════════════════════════════════════════
# Hjelpe-funksjonar
# ══════════════════════════════════════════════════════════

def _seksjon(pdf: _PDF, tekst: str, gap: float = 4):
    if gap:
        pdf.ln(gap)
    pdf.set_font("Arial", "B", 11)
    pdf.set_fill_color(210, 225, 245)
    pdf.cell(0, 7, tekst, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def _th(pdf: _PDF, cols: list, widths: list):
    """Tabellhovud."""
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(160, 190, 220)
    for i, (c, w) in enumerate(zip(cols, widths)):
        is_last = i == len(cols) - 1
        pdf.cell(w, 7, c, border=1, fill=True, align="C",
                 new_x="LMARGIN" if is_last else "RIGHT",
                 new_y="NEXT"    if is_last else "TOP")


def _tr(pdf: _PDF, vals: list, widths: list, fill: bool = False):
    """Tabellrad."""
    pdf.set_font("Arial", "", 9)
    pdf.set_fill_color(240, 246, 252) if fill else pdf.set_fill_color(255, 255, 255)
    for i, (v, w) in enumerate(zip(vals, widths)):
        is_last = i == len(vals) - 1
        pdf.cell(w, 6, str(v), border=1, fill=True, align="R",
                 new_x="LMARGIN" if is_last else "RIGHT",
                 new_y="NEXT"    if is_last else "TOP")


def _txt(pdf: _PDF, tekst: str, h: float = 6, style: str = ""):
    pdf.set_font("Arial", style, 10)
    pdf.multi_cell(0, h, tekst, new_x="LMARGIN", new_y="NEXT")


def _embed_plot(pdf: _PDF, fig, width_mm: float = _W):
    """Legg inn matplotlib-figur som bilete."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    pdf.image(buf, x=_LM, w=width_mm)


# ══════════════════════════════════════════════════════════
# RAPPORT 1 – Bøyediameter
# ══════════════════════════════════════════════════════════

def lag_rapport_boye(fcd: float, fig, custom_points=None) -> bytes:
    """Berekningstillegg for bøyediameter (NS-EN 1992-1-1 §8.3)."""
    pdf = _PDF("Berekningstillegg – Bøyediameter")
    pdf.add_page()

    # ── Tittel
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Berekningstillegg – Bøyediameter",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 7, "NS-EN 1992-1-1  §8.3(3)  Formel (8.1)",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(6)

    # ── Inndata
    _seksjon(pdf, "Inndata", gap=0)
    _txt(pdf, f"Dimensjonerande trykkfasthet:  fcd = {fcd} MPa")
    _txt(pdf, "Stangdiametrar:  ø12, ø16, ø20, ø25, ø32 mm")
    _txt(pdf, "Spenningsintervall:  σ = 0 – 435 MPa")

    # ── Minstediameter
    _seksjon(pdf, "Minstediameter – Tabell NA.8.1N.c) i NS-EN 1992-1-1")
    _th(pdf, ["ø (mm)", "øm,min (mm)"], [30, 30])
    for i, (phi, mn) in enumerate(zip(ec2_boye.PHI_LIST, ec2_boye.LOW_LIM)):
        _tr(pdf, [str(phi), str(mn)], [30, 30], fill=(i % 2 == 0))

    # ── Formelreferanse
    _seksjon(pdf, "Formelreferanse – NS-EN 1992-1-1 §8.3(3)")
    for linje in [
        "Formel (8.1) – kravet for bøyediameter:",
        "  Fbt · (1/ab + 1/(2·ø)) / fcd  ≤  øm,min / ø",
        "",
        "der bøyediameteren er:",
        "  øm = Fbt / fcd  ·  1 / (1/ab + 1/(2·ø))",
        "",
        "der:",
        "  Fbt  =  π · (ø/2)² · σ      [N]",
        "         (strekkkraft i armering ved bøyepunktet)",
        "  ab   =  senteravstand / 2    [mm]",
        "  ø    =  stangdiameter        [mm]",
        "  fcd  =  dim. trykkfasthet    [MPa]",
        "  σ    =  strekkspenning       [MPa]",
        "",
        "ab-verdiar (halve senteravstand):",
        "  ø12 → ab = 50 mm  |  ø16 → ab = 62,5 mm  |  ø20 → ab = 75 mm",
        "  ø25 → ab = 87,5 mm  |  ø32 → ab = 100 mm",
    ]:
        _txt(pdf, linje, h=5)

    # ── Resultattabell
    _seksjon(pdf, "Resultat – Bøyediameter øm [mm] ved ulike spenningar")
    _txt(pdf, "Strek (–) tyder at verdien er under minstediameteren.", h=5)
    pdf.ln(2)

    data = ec2_boye.berekn_kurvar(fcd)
    ws = [20, 30, 30, 30, 30, 30]
    _th(pdf, ["σ [MPa]", "ø12", "ø16", "ø20", "ø25", "ø32"], ws)
    for i, s in enumerate(range(0, 436, 25)):
        row = [str(s)]
        for phi in ec2_boye.PHI_LIST:
            dm = data["d_bend_masked"][phi][s]
            row.append("–" if np.isnan(dm) else f"{dm:.0f}")
        _tr(pdf, row, ws, fill=(i % 2 == 0))

    # ── Eigendefinerte punkt
    if custom_points:
        _seksjon(pdf, "Egendefinerte punkt")
        ws_e = [25, 28, 38, 38, 20]
        _th(pdf, ["ø (mm)", "σ (MPa)", "øm (mm)", "øm,min (mm)", "OK?"], ws_e)
        for i, (phi, sig) in enumerate(custom_points):
            d, mn = ec2_boye.berekn_boeyediameter(phi, sig, fcd)
            ok = "Ja" if d >= mn else "NEI"
            _tr(pdf, [str(phi), f"{sig:.0f}", f"{d:.1f}", str(mn), ok],
                ws_e, fill=(i % 2 == 0))

    # ── Plott – landskapsside
    pdf.add_page(orientation="L")
    _seksjon(pdf, "Plott")
    _embed_plot(pdf, fig, width_mm=257)  # A4 landskap: 297 - 2*20 = 257 mm

    return bytes(pdf.output())


# ══════════════════════════════════════════════════════════
# RAPPORT 2 – Omfaring og forankring
# ══════════════════════════════════════════════════════════

def lag_rapport_omfar(
    fck: float, eta_01: float, n: int,
    c: float, a: float, type_kobling: str,
    stangplassering: str, rho: float, rho_1: float,
    sveist_tverrarmering: bool, sigma_s_max: int,
    fig, custom_points=None,
) -> bytes:
    """Berekningstillegg for omfaring og forankring (NS-EN 1992-1-1 §8.4 og §8.7)."""
    pdf = _PDF("Berekningstillegg – Omfaring og forankring")
    pdf.add_page()

    # ── Tittel
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Berekningstillegg – Omfaring og forankring",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 7, "NS-EN 1992-1-1  §8.4 (forankring)  og  §8.7 (omfaring)",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(6)

    # ── Inndata
    _seksjon(pdf, "Inndata", gap=0)
    fctm = ec2_omfar.hent_fctm(fck)
    type_tekst = ec2_omfar.get_type_kobling_tekst(type_kobling)
    eta_tekst = "Gode tilhøve (η₁ = 1,0)" if eta_01 == 1.0 else "Dårlege tilhøve (η₁ = 0,7)"
    inndata = [
        ("Karakteristisk trykkfasthet", f"fck = {fck} MPa"),
        ("Middelverdi strekkfasthet (Tabell 3.1)", f"fctm = {fctm:.1f} MPa"),
        ("Heftforhold", eta_tekst),
        ("Antal stenger i bunt", f"n = {n}"),
        ("Overdekning", f"c = {c} mm"),
        ("Senteravstand mellom stenger", f"a = {a} mm"),
        ("Koblingstype (figur 8.3 NS-EN 1992-1-1)", f"{type_kobling} – {type_tekst}"),
        ("Stangplassering (K-faktor)", stangplassering),
        ("Trykkspenning i tverretning", f"ρ = {rho} MPa"),
        ("Prosentdel omfarte stenger", f"ρ₁ = {rho_1:.0f} %"),
        ("Sveist tverrarmering (α₄ = 0,7)", "Ja" if sveist_tverrarmering else "Nei"),
        ("Maks. armeringsspenning", f"σs,max = {sigma_s_max} MPa"),
    ]
    ws_i = [95, 75]
    _th(pdf, ["Parameter", "Verdi"], ws_i)
    for j, (lab, val) in enumerate(inndata):
        pdf.set_font("Arial", "", 9)
        fill = j % 2 == 0
        pdf.set_fill_color(240, 246, 252) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.cell(ws_i[0], 6, lab,  border=1, fill=True, align="L",
                 new_x="RIGHT",   new_y="TOP")
        pdf.cell(ws_i[1], 6, val,  border=1, fill=True, align="L",
                 new_x="LMARGIN", new_y="NEXT")

    # ── Mellomrekningar (referansediameter ø20)
    ref_phi = 20
    ref_sig = sigma_s_max
    fctk005  = 0.7 * fctm
    fctd     = 0.85 * fctk005 / 1.5
    eta_02   = 1.0 if ref_phi <= 32 else (132 - ref_phi) / 100
    fbd      = 2.25 * eta_01 * eta_02 * fctd
    phi_n    = ref_phi * math.sqrt(n)
    As       = math.pi / 4 * phi_n ** 2
    lbrqd    = (phi_n / 4) * (abs(ref_sig) / fbd)
    cd       = min(a / 2, c) if type_kobling in ("a", "b") else c
    alpha_1  = 1.0 if type_kobling == "a" else (0.7 if cd > 3 * phi_n else 1.0)
    a2raw    = (1 - 0.15 * (cd - phi_n) / phi_n) if type_kobling == "a" \
               else (1 - 0.15 * (cd - 3 * phi_n) / phi_n)
    alpha_2  = max(0.7, min(1.0, a2raw))
    k_map    = {"Utenfor": 0, "Innenfor": 0.05, "I bøy": 0.1}
    k        = k_map.get(stangplassering, 0.05)
    sum_astmin = As if phi_n >= 20 else 0
    alpha_3  = max(0.7, min(1.0, 1 - k * (0 - sum_astmin) / As))
    alpha_5  = max(0.7, min(1.0, 1 - 0.04 * rho))
    alpha_6  = max(1.0, min(1.5, (rho_1 / 25) ** 0.5))
    alpha_235 = max(0.7, alpha_2 * alpha_3 * alpha_5)
    l0min    = max(0.3 * lbrqd * alpha_6, 15 * phi_n, 200)
    l0       = max(lbrqd * alpha_1 * alpha_2 * alpha_3 * alpha_5 * alpha_6, l0min)
    lbdmin   = max(0.3 * lbrqd, 10 * phi_n, 100)
    alpha_4  = 0.7
    lbd      = max(lbrqd * alpha_1 * alpha_235 * alpha_4, lbdmin) \
               if sveist_tverrarmering else max(lbrqd * alpha_1 * alpha_235, lbdmin)

    _seksjon(pdf, f"Mellomrekningar – ø{ref_phi} mm, σsd = {ref_sig} MPa")
    ws_m = [100, 70]
    _th(pdf, ["Uttrykk", "Verdi"], ws_m)
    mellom = [
        ("fctk,0.05 = 0,7 · fctm",
         f"= 0,7 · {fctm:.2f} = {fctk005:.3f} MPa"),
        ("fctd = 0,85 · fctk,0.05 / 1,5",
         f"= {fctd:.4f} MPa"),
        (f"η₂ = 1,0  (ø{ref_phi} ≤ 32 mm)",
         f"= {eta_02:.2f}"),
        ("fbd = 2,25 · η₁ · η₂ · fctd",
         f"= {fbd:.4f} MPa"),
        (f"øn = ø · √n = {ref_phi} · √{n}",
         f"= {phi_n:.2f} mm"),
        ("lb,rqd = (øn/4) · (σsd / fbd)",
         f"= {lbrqd:.1f} mm"),
        (f"cd = min(a/2 ; c) = min({a/2:.0f} ; {c})",
         f"= {cd:.1f} mm"),
        (f"α₁  (type {type_kobling})",
         f"= {alpha_1:.2f}"),
        ("α₂  (inneslutning)",
         f"= {alpha_2:.3f}"),
        ("α₃  (tverrarmering)",
         f"= {alpha_3:.3f}"),
        ("α₅  (trykkspenning tverretning)",
         f"= {alpha_5:.3f}"),
        ("α₆  (omfaringsprosent)",
         f"= {alpha_6:.3f}"),
    ]
    for j, (expr, res) in enumerate(mellom):
        pdf.set_font("Arial", "", 9)
        fill = j % 2 == 0
        pdf.set_fill_color(240, 246, 252) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.cell(ws_m[0], 6, expr, border=1, fill=True, align="L",
                 new_x="RIGHT",   new_y="TOP")
        pdf.cell(ws_m[1], 6, res,  border=1, fill=True, align="L",
                 new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    _txt(pdf, "Sjå resultattabellar nedanfor for l0 og lbd for alle stangdiametrar og spenningar.", h=5, style="I")

    # ── Formelreferansar – side 2
    pdf.add_page()
    _seksjon(pdf, "Formelreferansar – NS-EN 1992-1-1", gap=0)
    for linje in [
        "§8.4.2  Formel (8.2) – Dimensjonerande heftfasthet:",
        "   fbd = 2,25 · η₁ · η₂ · fctd",
        "   der: η₁ = heftforhold (1,0 / 0,7),  η₂ = stangfaktor,",
        "        fctd = 0,85 · 0,7 · fctm / 1,5",
        "",
        "§8.4.3  Formel (8.3) – Grunnleggjande forankringslengde:",
        "   lb,rqd = (øn / 4) · (σsd / fbd)   [mm]",
        "   der:  øn = ø · √n  (ekvivalent diameter for bunt)",
        "",
        "§8.4.4  Formel (8.4) – Dimensjonerande forankringslengde:",
        "   lbd = α₁ · α₂ · α₃ · α₄ · α₅ · lb,rqd  ≥  lb,min",
        "   lb,min (strekk) = max(0,3·lb,rqd ; 10·øn ; 100 mm)",
        "   lb,min (trykk)  = max(0,6·lb,rqd ; 10·øn ; 100 mm)",
        "",
        "§8.7.3  Formel (8.10) – Omfaringslengde:",
        "   l0 = α₁ · α₂ · α₃ · α₅ · α₆ · lb,rqd  ≥  l0,min",
        "",
        "§8.7.3  Formel (8.11) – Minste omfaringslengde:",
        "   l0,min = max(0,3 · α₆ · lb,rqd ; 15 · øn ; 200 mm)",
        "",
        "Alfakoeffisientar – Tabell 8.2 NS-EN 1992-1-1:",
        "   α₁ : koblingstype  (a = 1,0 ;  b/c = 0,7 viss cd > 3·øn, elles 1,0)",
        "   α₂ : inneslutning  (1 − 0,15·(cd − øn)/øn  for type a ;",
        "                       1 − 0,15·(cd − 3·øn)/øn  for type b/c,  gr. 0,7–1,0)",
        "   α₃ : tverrarmering  (1 − k·(Ast − Ast,min)/As,  gr. 0,7–1,0)",
        "         K = 0 (utanfor bøy)  /  0,05 (innanfor)  /  0,1 (i bøy)",
        "   α₄ : 0,7 ved sveist tverrarmering",
        "   α₅ : trykkspenning  (1 − 0,04·ρ,  gr. 0,7–1,0)",
        "   α₆ : omfaringsprosent  ((ρ₁/25)^0,5,  gr. 1,0–1,5)",
    ]:
        _txt(pdf, linje, h=5)

    # ── Resultattabellar
    kurvar = ec2_omfar.berekn_kurvar(
        fck, eta_01, n, c, a, type_kobling, 0,
        stangplassering, rho, rho_1, sveist_tverrarmering, sigma_s_max,
    )
    ws_r = [20, 30, 30, 30, 30, 30]
    cols_r = ["σ [MPa]", "ø12", "ø16", "ø20", "ø25", "ø32"]
    sig_steg = list(range(0, sigma_s_max + 1, 25))

    _seksjon(pdf, "Resultat – Omfaringslengde l0 [mm]  (avrunda til næraste 100 mm)")
    _th(pdf, cols_r, ws_r)
    for i, s in enumerate(sig_steg):
        row = [str(s)] + [str(kurvar["l0"][phi][s]) for phi in ec2_omfar.PHI_LIST]
        _tr(pdf, row, ws_r, fill=(i % 2 == 0))

    _seksjon(pdf, "Resultat – Forankringslengde lbd [mm]")
    _th(pdf, cols_r, ws_r)
    for i, s in enumerate(sig_steg):
        row = [str(s)] + [f"{kurvar['lbd'][phi][s]:.0f}" for phi in ec2_omfar.PHI_LIST]
        _tr(pdf, row, ws_r, fill=(i % 2 == 0))

    # ── Eigendefinerte punkt
    if custom_points:
        _seksjon(pdf, "Egendefinerte punkt")
        ws_e = [25, 30, 40, 40]
        _th(pdf, ["ø (mm)", "σ (MPa)", "l0 (mm)", "lbd (mm)"], ws_e)
        for i, (phi, sig) in enumerate(custom_points):
            l0c, lbdc = ec2_omfar.beregn_omfarOgForankring(
                fck, eta_01, phi, n, sig, c, a,
                type_kobling, 0, stangplassering, rho, rho_1, sveist_tverrarmering,
            )
            _tr(pdf, [str(phi), f"{sig:.0f}", str(l0c), f"{lbdc:.0f}"],
                ws_e, fill=(i % 2 == 0))

    # ── Plott – landskapsside
    pdf.add_page(orientation="L")
    _seksjon(pdf, "Plott")
    _embed_plot(pdf, fig, width_mm=257)  # A4 landskap: 297 - 2*20 = 257 mm

    return bytes(pdf.output())
