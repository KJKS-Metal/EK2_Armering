"""
ec2_rapport.py
Genererar berekningstillegg som PDF per NS-EN 1992-1-1:2004+A1:2014+NA:2024.
Krev:  pip install fpdf2
"""

import io
import math
import os
from datetime import date

import matplotlib
import numpy as np
from fpdf import FPDF
from PIL import Image

import ec2_boye
import ec2_omfar
import ec2_material as mat

_STD = "NS-EN 1992-1-1:2004+A1:2014+NA:2024"

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
        bredd = self.w - 2 * _LM
        hogre = f"{_STD}  |  {_DATO}"
        self.set_font("Arial", "", 8)
        wh = self.get_string_width(hogre) + 2
        self.set_font("Arial", "B", 9)
        self.cell(bredd - wh, 6, self._tittel,
                  new_x="RIGHT", new_y="TOP", align="L")
        self.set_font("Arial", "", 8)
        self.cell(wh, 6, hogre,
                  new_x="LMARGIN", new_y="NEXT", align="R")
        self.set_draw_color(80, 80, 80)
        self.line(_LM, self.get_y(), self.w - _LM, self.get_y())
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
    with Image.open(buf) as im:
        px_w, px_h = im.size
    buf.seek(0)
    tilgjengeleg_h = pdf.h - pdf.get_y() - 22
    w = min(width_mm, tilgjengeleg_h * px_w / px_h)
    pdf.image(buf, x=_LM + (width_mm - w) / 2, w=w)



def _kv(pdf: _PDF, rader: list, widths: list):
    """To-kolonnetabell med venstrejustert tekst."""
    for j, rad in enumerate(rader):
        pdf.set_font("Arial", "", 9)
        pdf.set_fill_color(240, 246, 252) if j % 2 == 0 else pdf.set_fill_color(255, 255, 255)
        for i, (v, w) in enumerate(zip(rad, widths)):
            last = i == len(rad) - 1
            pdf.cell(w, 6, str(v), border=1, fill=True, align="L",
                     new_x="LMARGIN" if last else "RIGHT",
                     new_y="NEXT" if last else "TOP")


# ══════════════════════════════════════════════════════════
# RAPPORT 1 – Bøyediameter
# ══════════════════════════════════════════════════════════

def lag_rapport_boye(fck, fcd, fck_brukt, avgrensa, situasjon, gamma_c, gamma_s,
                     ab_modus, ab, sigma_max, fig, custom_points=None) -> bytes:
    """Berekningstillegg for dordiameter (§8.3 og NA.8.3)."""
    pdf = _PDF("Berekningstillegg – Dordiameter")
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Berekningstillegg – Dordiameter ved bøying",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 7, "§8.3(3) uttrykk (8.1) og NA.8.3(2) tabell NA.8.1N.c)",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(6)

    _seksjon(pdf, "Inndata og materialparametrar", gap=0)
    rader = [
        ("Dimensjonerande situasjon (tabell NA.2.1N)", situasjon),
        ("Materialfaktor betong γC", f"{gamma_c:.2f}"),
        ("Materialfaktor armering γS", f"{gamma_s:.2f}"),
        ("αcc (NA.3.1.6(1)P)", f"{mat.ALPHA_CC}"),
        ("Betongfasthet fck", f"{fck} MPa"),
        ("fck brukt i (8.1), maks C55/67 jf. §8.3(3)",
         f"{fck_brukt} MPa" + ("  (avgrensa)" if avgrensa else "")),
        ("fcd = αcc · fck / γC",
         f"{mat.ALPHA_CC} · {fck_brukt} / {gamma_c:.2f} = {fcd:.2f} MPa"),
        ("Armering", "B500NC etter NS 3576"),
        ("Spenningsintervall", f"σ = 0 – {sigma_max} MPa"),
        ("Bestemming av ab", ab_modus),
    ]
    _kv(pdf, rader, [85, 85])

    _seksjon(pdf, "ab og minste dordiameter frå tabell NA.8.1N.c)")
    ws = [30, 30, 45]
    _th(pdf, ["ø (mm)", "ab (mm)", "øm,min tabell (mm)"], ws)
    for i, phi in enumerate(ec2_boye.PHI_LIST):
        _tr(pdf, [str(phi), f"{ab[phi]:.1f}", str(ec2_boye.MIN_BEND[phi])], ws, fill=(i % 2 == 0))

    _seksjon(pdf, "Formelgrunnlag")
    for linje in [
        "§8.3(3) uttrykk (8.1):",
        "   øm,min ≥ Fbt · (1/ab + 1/(2·ø)) / fcd",
        "der",
        "   Fbt = π · (ø/2)² · σ   [N]  strekkraft i stanga ved byrjinga av bøyen (ULS)",
        "   ab  = halve senteravstanden mellom stengene vinkelrett på bøyens plan.",
        "         For stang mot ytterkant: ab = overdekning + ø/2.",
        "   fcd = αcc · fck / γC, ikkje høgare enn for C55/67.",
        "",
        "NA.8.3(2): Dordiameteren skal ikkje vere mindre enn den største av verdien",
        "i tabell NA.8.1N og verdien frå uttrykk (8.1):",
        "   øm,dim = max(øm,min tabell ; øm frå (8.1))",
    ]:
        _txt(pdf, linje, h=5)

    _seksjon(pdf, "Resultat – dimensjonerande dordiameter øm,dim [mm]")
    _txt(pdf, "Verdi merka * er styrt av tabell NA.8.1N.c). Andre verdiar er styrt av (8.1).", h=5)
    pdf.ln(2)
    data = ec2_boye.berekn_kurvar(fcd, ab, sigma_max=sigma_max)
    ws = [20, 30, 30, 30, 30, 30]
    _th(pdf, ["σ [MPa]", "ø12", "ø16", "ø20", "ø25", "ø32"], ws)
    steg = list(range(0, sigma_max + 1, 25))
    if steg[-1] != sigma_max:
        steg.append(sigma_max)
    for i, s in enumerate(steg):
        row = [str(s)]
        for phi in ec2_boye.PHI_LIST:
            d81 = data["d_bend"][phi][s]
            mn = ec2_boye.MIN_BEND[phi]
            row.append(f"{mn}*" if d81 < mn else f"{d81:.0f}")
        _tr(pdf, row, ws, fill=(i % 2 == 0))

    if custom_points:
        _seksjon(pdf, "Eigendefinerte punkt")
        ws_e = [22, 25, 30, 30, 33, 30]
        _th(pdf, ["ø (mm)", "σ (MPa)", "ab (mm)", "(8.1) (mm)", "tabell (mm)", "øm,dim (mm)"], ws_e)
        for i, (phi, sig) in enumerate(custom_points):
            d, mn = ec2_boye.berekn_boeyediameter(phi, sig, fcd, ab[phi])
            _tr(pdf, [str(phi), f"{sig:.0f}", f"{ab[phi]:.1f}", f"{d:.1f}", str(mn),
                      f"{max(d, mn):.0f}"], ws_e, fill=(i % 2 == 0))

        # Fullt utrekna døme for første punkt
        phi, sig = custom_points[0]
        d, mn = ec2_boye.berekn_boeyediameter(phi, sig, fcd, ab[phi])
        Fbt = math.pi * (phi / 2) ** 2 * sig
        _seksjon(pdf, f"Dømeberekning – ø{phi}, σ = {sig:.0f} MPa")
        for linje in [
            f"Fbt = π · ({phi}/2)² · {sig:.0f} = {Fbt:.0f} N = {Fbt/1000:.1f} kN",
            f"1/ab + 1/(2ø) = 1/{ab[phi]:.1f} + 1/(2·{phi}) = {1/ab[phi] + 1/(2*phi):.5f} mm⁻¹",
            f"øm ≥ {Fbt:.0f} · {1/ab[phi] + 1/(2*phi):.5f} / {fcd:.2f} = {d:.1f} mm",
            f"Tabell NA.8.1N.c): øm,min = {mn} mm",
            f"Dimensjonerande: øm = max({mn} ; {d:.1f}) = {max(d, mn):.1f} mm",
        ]:
            _txt(pdf, linje, h=5)

    pdf.add_page(orientation="L")
    _seksjon(pdf, "Plott")
    _embed_plot(pdf, fig, width_mm=257)
    return bytes(pdf.output())


# ══════════════════════════════════════════════════════════
# RAPPORT 2 – Omfaring og forankring
# ══════════════════════════════════════════════════════════

def lag_rapport_omfar(felles: dict, situasjon: str, tilstand: str, sigma_s_max: int,
                      fig, kurvar: dict, custom_points=None) -> bytes:
    """Berekningstillegg for omfaring og forankring (§8.4, §8.7, §8.9)."""
    f = felles
    trykk = f["trykk"]
    pdf = _PDF("Berekningstillegg – Omfaring og forankring")
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Berekningstillegg – Omfaring og forankring",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 7, f"§8.4 forankring, §8.7 omfaring, §8.9 buntar – {tilstand.lower()}",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(6)

    _seksjon(pdf, "Inndata", gap=0)
    fyd = mat.fyd(f["gamma_s"])
    inndata = [
        ("Dimensjonerande situasjon (tabell NA.2.1N)",
         f"{situasjon}: γC = {f['gamma_c']:.2f}, γS = {f['gamma_s']:.2f}"),
        ("Spenningstilstand", tilstand),
        ("Betongfasthet fck", f"{f['fck']} MPa"),
        ("Heftforhold η1", f"{f['eta_01']}"),
        ("Antal stenger i bunt n", f"{f['n']}"),
        ("Senteravstand s", f"{f['s']} mm"),
        ("Overdekning c / sideoverdekning c1", f"{f['c']} mm / {f['c1']} mm"),
        ("Koblingstype (figur 8.3)",
         f"{f['type_kobling']} – {ec2_omfar.get_type_kobling_tekst(f['type_kobling'])}"),
        ("Prosentdel omfarte stenger ρ1", f"{f['rho_1']:.0f} %"),
        ("Sveist tverrarmering (α4 = 0.7)", "Ja" if f["sveist_tverrarmering"] else "Nei"),
    ]
    if not trykk:
        inndata += [
            ("Konstruksjonsdel (ΣAst,min forankring)", f["konstruksjon"]),
            ("Tverrarmering ΣAst", f"{f['sum_ast']:.0f} mm²"),
            ("Plassering av stang (figur 8.4)",
             f"{f['stangplassering']}  (K = {ec2_omfar.K_MAP[f['stangplassering']]})"),
            ("Trykk i tverretning p", f"{f['rho']} MPa"),
        ]
    if f["n"] > 1 and not trykk:
        inndata.append(("Forskyvd forankring i bunt (§8.9.2(2))",
                        "Ja" if f["forskyvd_forankring"] else "Nei"))
    inndata.append(("Maks. spenning i plott/tabell", f"σs,max = {sigma_s_max} MPa"))
    _kv(pdf, inndata, [78, 92])

    # ── Dømeberekning ø20 ved fyd
    ref_phi = 20
    ref_sig = round(fyd)
    d = ec2_omfar.beregn_detaljar(phi=ref_phi, sigma_sd=ref_sig, **f)
    fa, fo = d["forank"], d["omfar"]

    pdf.add_page()
    _seksjon(pdf, f"Dømeberekning – ø{ref_phi} mm, σsd = {ref_sig} MPa", gap=0)
    w2 = [95, 75]
    _th(pdf, ["Uttrykk", "Verdi"], w2)
    rader = [
        ("fck brukt for heft (maks C60/75, §8.4.2(2))", f"{d['fck_heft']} MPa"),
        ("fctm (tabell 3.1)", f"{d['fctm']:.2f} MPa"),
        ("fctk,0.05 = 0.7 · fctm", f"0.7 · {d['fctm']:.2f} = {d['fctk005']:.3f} MPa"),
        ("fctd = αct · fctk,0.05 / γC",
         f"{mat.ALPHA_CT} · {d['fctk005']:.3f} / {d['gamma_c']:.2f} = {d['fctd']:.3f} MPa"),
        ("φn = φ · √n", f"{ref_phi} · √{d['n']} = {d['phi_n']:.2f} mm"),
        ("a = s − " + ("φ" if d["n"] == 1 else "2φ"), f"{d['a']:.1f} mm"),
        ("cd (figur 8.3)", f"{d['cd']:.1f} mm"),
    ]
    _kv(pdf, rader, w2)

    def _blokk(tittel, x, er_omf):
        _seksjon(pdf, tittel)
        _th(pdf, ["Uttrykk", "Verdi"], w2)
        r = [
            ("Diameter brukt", f"{x['phi_x']:.2f} mm"),
            ("η2 (1.0 for ø ≤ 32, elles (132−ø)/100)", f"{x['eta_2']:.3f}"),
            ("fbd = 2.25 · η1 · η2 · fctd",
             f"2.25 · {f['eta_01']} · {x['eta_2']:.3f} · {d['fctd']:.3f} = {x['fbd']:.3f} MPa"),
            ("lb,rqd = (ø/4) · (σsd / fbd)",
             f"({x['phi_x']:.1f}/4) · ({ref_sig}/{x['fbd']:.3f}) = {x['lbrqd']:.1f} mm"),
            ("α1", f"{x['a1']:.3f}"),
            ("α2" + ("" if trykk else f"  (urekna {x['a2_raw']:.3f})"), f"{x['a2']:.3f}"),
            ("As = π/4 · ø²", f"{x['As']:.1f} mm²"),
            ("ΣAst,min" + ("  = As·σsd/fyd (§8.7.3)" if er_omf else ""), f"{x['sum_ast_min']:.1f} mm²"),
            ("α3 = 1 − K·(ΣAst − ΣAst,min)/As", f"{x['a3']:.3f}"),
        ]
        if not er_omf:
            r.append(("α4", f"{x['a4']:.2f}"))
        r.append(("α5", f"{x['a5']:.3f}"))
        if er_omf:
            r.append(("α6 = (ρ1/25)^0.5", f"{x['a6']:.3f}"))
        _kv(pdf, r, w2)

    _blokk("Forankring §8.4", fa, er_omf=False)
    if d["lbd"] is not None:
        lbmin_txt = "max(0.6·lb,rqd ; 10ø ; 100)  (8.7)" if trykk else "max(0.3·lb,rqd ; 10ø ; 100)  (8.6)"
        _kv(pdf, [
            ("α2·α3·α5 ≥ 0.7  (8.5)", f"{d['a235']:.3f}"),
            ("α1·α2α3α5·α4·lb,rqd", f"{d['lbd_raw']:.1f} mm"),
            ("lb,min = " + lbmin_txt, f"{d['lbmin']:.1f} mm"),
            ("lbd = max(…)", f"{d['lbd']:.0f} mm"),
        ], w2)
    else:
        _txt(pdf, "Forankring ikkje tillaten for denne kombinasjonen.", h=5, style="I")

    if fo is not None:
        _blokk("Omfaring §8.7.3", fo, er_omf=True)
        rows = [
            ("α1·α2·α3·α5·α6·lb,rqd  (8.10)", f"{d['l0_raw']:.1f} mm"),
            ("l0,min = max(0.3·α6·lb,rqd ; 15ø ; 200)  (8.11)", f"{d['l0min']:.1f} mm"),
            ("l0 = max(…)", f"{d['l0']:.1f} mm"),
            ("l0 avrunda opp til næraste 100 mm", f"{d['l0_rund']} mm"),
        ]
        if d["omfar_forskyving"]:
            rows.append(("Forskyving enkeltstenger ≥ 1.3·l0 (§8.9.3(3))", f"{d['forskyving']:.0f} mm"))
        _kv(pdf, rows, w2)
    else:
        _txt(pdf, "Omfaring ikkje tillaten for denne kombinasjonen (§8.9.3(3)).", h=5, style="I")

    if d["merknader"]:
        _seksjon(pdf, "Merknader")
        for m in d["merknader"]:
            _txt(pdf, "• " + m, h=5)

    # ── Formelgrunnlag
    pdf.add_page()
    _seksjon(pdf, "Formelgrunnlag", gap=0)
    for linje in [
        "§8.4.2 (8.2): fbd = 2.25 · η1 · η2 · fctd,  fctd = αct · fctk,0.05 / γC  (αct = 0.85, NA.3.1.6(2)P)",
        "   fctk,0.05 avgrensa til verdien for C60/75.",
        "§8.4.3 (8.3): lb,rqd = (ø/4) · (σsd / fbd)",
        "§8.4.4 (8.4): lbd = α1 · α2 · α3 · α4 · α5 · lb,rqd ≥ lb,min,   (8.5): α2·α3·α5 ≥ 0.7",
        "   (8.6) strekk: lb,min = max(0.3·lb,rqd ; 10ø ; 100 mm)",
        "   (8.7) trykk:  lb,min = max(0.6·lb,rqd ; 10ø ; 100 mm)",
        "§8.7.3 (8.10): l0 = α1 · α2 · α3 · α5 · α6 · lb,rqd ≥ l0,min",
        "§8.7.3 (8.11): l0,min = max(0.3·α6·lb,rqd ; 15ø ; 200 mm)",
        "",
        "Tabell 8.2 (strekk):",
        "   α1: rett = 1.0 ; ikkje rett = 0.7 viss cd > 3ø, elles 1.0",
        "   α2: rett 1 − 0.15(cd − ø)/ø ; ikkje rett 1 − 0.15(cd − 3ø)/ø ; 0.7 ≤ α2 ≤ 1.0",
        "   α3 = 1 − K·λ,  λ = (ΣAst − ΣAst,min)/As ; 0.7 ≤ α3 ≤ 1.0",
        "        ΣAst,min = 0.25·As (bjelkar) / 0 (plater) ; for omfaring As·σsd/fyd",
        "        K = 0.1 (i bøyen) / 0.05 (innanfor) / 0 (utanfor), figur 8.4",
        "   α4 = 0.7 ved sveist tverrarmering ;  α5 = 1 − 0.04p, 0.7 ≤ α5 ≤ 1.0",
        "   α6 = (ρ1/25)^0.5, 1.0 ≤ α6 ≤ 1.5 (tabell 8.3)",
        "Tabell 8.2 (trykk): α1 = α2 = α3 = 1.0 ; α4 = 0.7 ; α5 ikkje aktuell",
        "",
        "Figur 8.3: a) cd = min(a/2 ; c1 ; c)   b) cd = min(a/2 ; c1)   c) cd = c",
        "   a = fri avstand mellom stengene = s − ø (bunt: s − 2ø, konservativt).",
        "",
        "§8.9 Buntar: øn = ø·√nb ≤ 55 mm. nb ≤ 4 for vertikale stenger i trykk og",
        "   i omfaringsskøyt, elles nb ≤ 3.",
        "   §8.9.2(2): forankring med enkeltstenger forskyvd > 1.3·lb,rqd → ø, elles øn.",
        "   §8.9.3(2): 2 stenger, øn < 32 mm: omfaring utan forskyving, l0 med øn.",
        "   §8.9.3(3): 2 stenger med øn ≥ 32 mm eller 3 stenger: enkeltstenger forskyvast",
        "   ≥ 1.3·l0 med l0 rekna for éi stang. Maks fire stenger i eitt snitt.",
    ]:
        _txt(pdf, linje, h=5)

    # ── Resultattabellar
    ws_r = [20, 30, 30, 30, 30, 30]
    cols_r = ["σ [MPa]", "ø12", "ø16", "ø20", "ø25", "ø32"]
    steg = list(range(0, sigma_s_max + 1, 25))

    def _v(x, fmt):
        return "–" if x != x else fmt.format(x)   # NaN → «–»

    _seksjon(pdf, "Resultat – omfaringslengde l0 [mm] (avrunda opp til 100 mm)")
    if f["n"] > 1:
        _txt(pdf, "Bunt: sjå §8.9.3 for kva diameter som er brukt og krav til forskyving.", h=5, style="I")
    _th(pdf, cols_r, ws_r)
    for i, s in enumerate(steg):
        _tr(pdf, [str(s)] + [_v(kurvar["l0"][p][s], "{:.0f}") for p in ec2_omfar.PHI_LIST],
            ws_r, fill=(i % 2 == 0))

    _seksjon(pdf, "Resultat – forankringslengde lbd [mm]")
    _th(pdf, cols_r, ws_r)
    for i, s in enumerate(steg):
        _tr(pdf, [str(s)] + [_v(kurvar["lbd"][p][s], "{:.0f}") for p in ec2_omfar.PHI_LIST],
            ws_r, fill=(i % 2 == 0))
    _txt(pdf, "«–» = ikkje tillaten kombinasjon (sjå merknader).", h=5, style="I")

    if custom_points:
        _seksjon(pdf, "Eigendefinerte punkt")
        ws_e = [25, 30, 40, 40]
        _th(pdf, ["ø (mm)", "σ (MPa)", "l0 (mm)", "lbd (mm)"], ws_e)
        for i, (phi, sig) in enumerate(custom_points):
            l0c, lbdc = ec2_omfar.beregn_omfarOgForankring(phi=phi, sigma_sd=sig, **f)
            _tr(pdf, [str(phi), f"{sig:.0f}", "–" if l0c is None else str(l0c),
                      "–" if lbdc is None else f"{lbdc:.0f}"], ws_e, fill=(i % 2 == 0))

    pdf.add_page(orientation="L")
    _seksjon(pdf, "Plott")
    _embed_plot(pdf, fig, width_mm=257)
    return bytes(pdf.output())
