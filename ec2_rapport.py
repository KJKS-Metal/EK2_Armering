"""
ec2_rapport.py
Genererar berekningstillegg som PDF per NS-EN 1992-1-1:2004+A1:2014+NA:2024.
Krev:  pip install fpdf2
"""

import io
import math
import os
import re
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
# og gresk skrift. Heva/senka skrift vert laga med char_vpos (sjå _segs).
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
# Heva og senka skrift
#   Markering i tekst:  f_{ck}  → f med senka «ck»
#                       x^{0.5} → x med heva «0.5»
#   I f-strengar må klammene doblast:  f"f_{{ck}} = {fck}"
# ══════════════════════════════════════════════════════════

_RE_SKRIFT = re.compile(r"([_^])\{([^{}]*)\}")


def _segs(tekst: str) -> list[tuple[str, str]]:
    """Del tekst i (tekst, char_vpos)-bitar."""
    ut, pos = [], 0
    for m in _RE_SKRIFT.finditer(tekst):
        if m.start() > pos:
            ut.append((tekst[pos:m.start()], "LINE"))
        ut.append((m.group(2), "SUB" if m.group(1) == "_" else "SUP"))
        pos = m.end()
    if pos < len(tekst):
        ut.append((tekst[pos:], "LINE"))
    return ut


def _breidd(pdf: FPDF, segs) -> float:
    w = 0.0
    for s, v in segs:
        pdf.char_vpos = v
        w += pdf.get_string_width(s)
    pdf.char_vpos = "LINE"
    return w


def _rcell(pdf: FPDF, w: float, h: float, tekst, border=0, fill=False,
           align: str = "L", siste: bool = False):
    """Som pdf.cell(), men med støtte for heva/senka skrift."""
    if w == 0:
        w = pdf.w - pdf.r_margin - pdf.get_x()
    pdf.cell(w, h, "", border=border, fill=fill, new_x="RIGHT", new_y="TOP")
    x, y = pdf.get_x() - w, pdf.get_y()      # etter evt. sideskift
    segs = _segs(str(tekst))
    tw = _breidd(pdf, segs)
    if align == "R":
        xs = x + w - pdf.c_margin - tw
    elif align == "C":
        xs = x + (w - tw) / 2
    else:
        xs = x + pdf.c_margin
    pdf.set_xy(xs, y)
    for s, v in segs:
        pdf.char_vpos = v
        pdf.cell(pdf.get_string_width(s), h, s, new_x="RIGHT", new_y="TOP")
    pdf.char_vpos = "LINE"
    if siste:
        pdf.set_xy(pdf.l_margin, y + h)
    else:
        pdf.set_xy(x + w, y)


# ══════════════════════════════════════════════════════════
# Hjelpe-funksjonar
# ══════════════════════════════════════════════════════════

def _seksjon(pdf: _PDF, tekst: str, gap: float = 4):
    if gap:
        pdf.ln(gap)
    pdf.set_font("Arial", "B", 11)
    pdf.set_fill_color(210, 225, 245)
    _rcell(pdf, 0, 7, tekst, fill=True, siste=True)
    pdf.ln(2)


def _th(pdf: _PDF, cols: list, widths: list):
    """Tabellhovud."""
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(160, 190, 220)
    for i, (c, w) in enumerate(zip(cols, widths)):
        _rcell(pdf, w, 7, c, border=1, fill=True, align="C", siste=(i == len(cols) - 1))


def _tr(pdf: _PDF, vals: list, widths: list, fill: bool = False):
    """Tabellrad."""
    pdf.set_font("Arial", "", 9)
    pdf.set_fill_color(240, 246, 252) if fill else pdf.set_fill_color(255, 255, 255)
    for i, (v, w) in enumerate(zip(vals, widths)):
        _rcell(pdf, w, 6, v, border=1, fill=True, align="R", siste=(i == len(vals) - 1))


def _kv(pdf: _PDF, rader: list, widths: list):
    """Tabell med venstrejustert tekst."""
    for j, rad in enumerate(rader):
        pdf.set_font("Arial", "", 9)
        pdf.set_fill_color(240, 246, 252) if j % 2 == 0 else pdf.set_fill_color(255, 255, 255)
        for i, (v, w) in enumerate(zip(rad, widths)):
            _rcell(pdf, w, 6, v, border=1, fill=True, align="L", siste=(i == len(rad) - 1))


def _txt(pdf: _PDF, tekst: str, h: float = 6, style: str = ""):
    """Fritekst med linjebryting og heva/senka skrift."""
    pdf.set_font("Arial", style, 10)
    pdf.set_x(pdf.l_margin)
    for s, v in _segs(tekst):
        pdf.char_vpos = v
        pdf.write(h, s)
    pdf.char_vpos = "LINE"
    pdf.ln(h)


def _embed_plot(pdf: _PDF, fig, width_mm: float = _W):
    """Legg inn matplotlib-figur som bilete, skalert til ledig plass."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    with Image.open(buf) as im:
        px_w, px_h = im.size
    buf.seek(0)
    tilgjengeleg_h = pdf.h - pdf.get_y() - 22
    w = min(width_mm, tilgjengeleg_h * px_w / px_h)
    pdf.image(buf, x=_LM + (width_mm - w) / 2, w=w)


# ══════════════════════════════════════════════════════════
# RAPPORT 1 – Dordiameter
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

    ab_modus_md = ab_modus.replace("a_b", "a_{b}")
    _seksjon(pdf, "Inndata og materialparametrar", gap=0)
    rader = [
        ("Dimensjonerande situasjon, ULS (tabell NA.2.1N)", situasjon),
        ("Materialfaktor betong γ_{C}", f"{gamma_c:.2f}"),
        ("Materialfaktor armering γ_{S}", f"{gamma_s:.2f}"),
        ("α_{cc} (NA.3.1.6(1)P)", f"{mat.ALPHA_CC}"),
        ("Betongfasthet f_{ck}", f"{fck} MPa"),
        ("f_{ck} brukt i (8.1), maks C55/67 jf. §8.3(3)",
         f"{fck_brukt} MPa" + ("  (avgrensa)" if avgrensa else "")),
        ("f_{cd} = α_{cc} · f_{ck} / γ_{C}",
         f"{mat.ALPHA_CC} · {fck_brukt} / {gamma_c:.2f} = {fcd:.2f} MPa"),
        ("Armering", "B500NC etter NS 3576"),
        ("Spenningsintervall", f"σ = 0 – {sigma_max} MPa"),
        ("Bestemming av a_{b}", ab_modus_md),
    ]
    _kv(pdf, rader, [85, 85])

    _seksjon(pdf, "a_{b} og minste dordiameter frå tabell NA.8.1N.c)")
    ws = [30, 30, 45]
    _th(pdf, ["φ (mm)", "a_{b} (mm)", "φ_{m,min} tabell (mm)"], ws)
    for i, phi in enumerate(ec2_boye.PHI_LIST):
        _tr(pdf, [str(phi), f"{ab[phi]:.1f}", str(ec2_boye.MIN_BEND[phi])], ws, fill=(i % 2 == 0))

    _seksjon(pdf, "Formelgrunnlag")
    for linje in [
        "§8.3(3) uttrykk (8.1):",
        "   φ_{m,min} ≥ F_{bt} · (1/a_{b} + 1/(2φ)) / f_{cd}",
        "der",
        "   F_{bt} = π · (φ/2)^{2} · σ   [N]  strekkraft i stanga ved byrjinga av bøyen (ULS)",
        "   a_{b} = halve senteravstanden mellom stengene vinkelrett på bøyens plan.",
        "            For stang mot ytterkant: a_{b} = overdekning + φ/2.",
        "   f_{cd} = α_{cc} · f_{ck} / γ_{C}, ikkje høgare enn for C55/67.",
        "",
        "NA.8.3(2): Dordiameteren skal ikkje vere mindre enn den største av verdien",
        "i tabell NA.8.1N og verdien frå uttrykk (8.1):",
        "   φ_{m,dim} = max(φ_{m,min} tabell ; φ_{m} frå (8.1))",
    ]:
        _txt(pdf, linje, h=5)

    _seksjon(pdf, "Resultat – dimensjonerande dordiameter φ_{m,dim} [mm]")
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
        _th(pdf, ["φ (mm)", "σ (MPa)", "a_{b} (mm)", "(8.1) (mm)", "tabell (mm)", "φ_{m,dim} (mm)"], ws_e)
        for i, (phi, sig) in enumerate(custom_points):
            d, mn = ec2_boye.berekn_boeyediameter(phi, sig, fcd, ab[phi])
            _tr(pdf, [str(phi), f"{sig:.0f}", f"{ab[phi]:.1f}", f"{d:.1f}", str(mn),
                      f"{max(d, mn):.0f}"], ws_e, fill=(i % 2 == 0))

        # Fullt utrekna døme for første punkt
        phi, sig = custom_points[0]
        d, mn = ec2_boye.berekn_boeyediameter(phi, sig, fcd, ab[phi])
        Fbt = math.pi * (phi / 2) ** 2 * sig
        k = 1 / ab[phi] + 1 / (2 * phi)
        _seksjon(pdf, f"Dømeberekning – ø{phi}, σ = {sig:.0f} MPa")
        for linje in [
            f"F_{{bt}} = π · ({phi}/2)^{{2}} · {sig:.0f} = {Fbt:.0f} N = {Fbt/1000:.1f} kN",
            f"1/a_{{b}} + 1/(2φ) = 1/{ab[phi]:.1f} + 1/(2 · {phi}) = {k:.5f} mm^{{−1}}",
            f"φ_{{m}} ≥ {Fbt:.0f} · {k:.5f} / {fcd:.2f} = {d:.1f} mm",
            f"Tabell NA.8.1N.c): φ_{{m,min}} = {mn} mm",
            f"Dimensjonerande: φ_{{m,dim}} = max({mn} ; {d:.1f}) = {max(d, mn):.1f} mm",
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
        ("Dimensjonerande situasjon, ULS (tabell NA.2.1N)",
         f"{situasjon}: γ_{{C}} = {f['gamma_c']:.2f}, γ_{{S}} = {f['gamma_s']:.2f}"),
        ("Spenningstilstand", tilstand),
        ("Betongfasthet f_{ck}", f"{f['fck']} MPa"),
        ("Heftforhold η_{1}", f"{f['eta_01']}"),
        ("Antal stenger i bunt n", f"{f['n']}"),
        ("Senteravstand s", f"{f['s']} mm"),
        ("Overdekning c / sideoverdekning c_{1}", f"{f['c']} mm / {f['c1']} mm"),
        ("Koblingstype (figur 8.3)",
         f"{f['type_kobling']} – {ec2_omfar.get_type_kobling_tekst(f['type_kobling'])}"),
        ("Prosentdel omfarte stenger ρ_{1}", f"{f['rho_1']:.0f} %"),
        ("Sveist tverrarmering (α_{4} = 0.7)", "Ja" if f["sveist_tverrarmering"] else "Nei"),
    ]
    if not trykk:
        inndata += [
            ("Konstruksjonsdel (ΣA_{st,min} forankring)", f["konstruksjon"]),
            ("Tverrarmering ΣA_{st}", f"{f['sum_ast']:.0f} mm^{{2}}"),
            ("Plassering av stang (figur 8.4)",
             f"{f['stangplassering']}  (K = {ec2_omfar.K_MAP[f['stangplassering']]})"),
            ("Trykk i tverretning p", f"{f['rho']} MPa"),
        ]
    if f["n"] > 1 and not trykk:
        inndata.append(("Forskyvd forankring i bunt (§8.9.2(2))",
                        "Ja" if f["forskyvd_forankring"] else "Nei"))
    inndata.append(("Maks. spenning i plott/tabell", f"σ_{{s,max}} = {sigma_s_max} MPa"))
    _kv(pdf, inndata, [78, 92])

    # ── Dømeberekning ø20 ved fyd
    ref_phi = 20
    ref_sig = round(fyd)
    d = ec2_omfar.beregn_detaljar(phi=ref_phi, sigma_sd=ref_sig, **f)
    fa, fo = d["forank"], d["omfar"]

    pdf.add_page()
    _seksjon(pdf, f"Dømeberekning – ø{ref_phi} mm, σ_{{sd}} = {ref_sig} MPa", gap=0)
    w2 = [95, 75]
    _th(pdf, ["Uttrykk", "Verdi"], w2)
    rader = [
        ("f_{ck} brukt for heft (maks C60/75, §8.4.2(2))", f"{d['fck_heft']} MPa"),
        ("f_{ctm} (tabell 3.1)", f"{d['fctm']:.2f} MPa"),
        ("f_{ctk,0.05} = 0.7 · f_{ctm}", f"0.7 · {d['fctm']:.2f} = {d['fctk005']:.3f} MPa"),
        ("f_{ctd} = α_{ct} · f_{ctk,0.05} / γ_{C}",
         f"{mat.ALPHA_CT} · {d['fctk005']:.3f} / {d['gamma_c']:.2f} = {d['fctd']:.3f} MPa"),
        ("φ_{n} = φ · √n_{b}", f"{ref_phi} · √{d['n']} = {d['phi_n']:.2f} mm"),
        ("a = s − " + ("φ" if d["n"] == 1 else "2φ"), f"{d['a']:.1f} mm"),
        ("c_{d} (figur 8.3)", f"{d['cd']:.1f} mm"),
    ]
    _kv(pdf, rader, w2)

    def _blokk(tittel, x, er_omf):
        _seksjon(pdf, tittel)
        _th(pdf, ["Uttrykk", "Verdi"], w2)
        r = [
            ("Diameter brukt", f"{x['phi_x']:.2f} mm"),
            ("η_{2} (1.0 for φ ≤ 32, elles (132 − φ)/100)", f"{x['eta_2']:.3f}"),
            ("f_{bd} = 2.25 · η_{1} · η_{2} · f_{ctd}",
             f"2.25 · {f['eta_01']} · {x['eta_2']:.3f} · {d['fctd']:.3f} = {x['fbd']:.3f} MPa"),
            ("l_{b,rqd} = (φ/4) · (σ_{sd} / f_{bd})",
             f"({x['phi_x']:.1f}/4) · ({ref_sig}/{x['fbd']:.3f}) = {x['lbrqd']:.1f} mm"),
            ("α_{1}", f"{x['a1']:.3f}"),
            ("α_{2}" + ("" if trykk else f"  (urekna {x['a2_raw']:.3f})"), f"{x['a2']:.3f}"),
            ("A_{s} = π/4 · φ^{2}", f"{x['As']:.1f} mm^{{2}}"),
            ("ΣA_{st,min}" + ("  = A_{s} · σ_{sd}/f_{yd} (§8.7.3)" if er_omf else ""),
             f"{x['sum_ast_min']:.1f} mm^{{2}}"),
            ("α_{3} = 1 − K · (ΣA_{st} − ΣA_{st,min})/A_{s}", f"{x['a3']:.3f}"),
        ]
        if not er_omf:
            r.append(("α_{4}", f"{x['a4']:.2f}"))
        r.append(("α_{5}", f"{x['a5']:.3f}"))
        if er_omf:
            r.append(("α_{6} = (ρ_{1}/25)^{0.5}", f"{x['a6']:.3f}"))
        _kv(pdf, r, w2)

    _blokk("Forankring §8.4", fa, er_omf=False)
    if d["lbd"] is not None:
        lbmin_txt = ("max(0.6 · l_{b,rqd} ; 10φ ; 100)  (8.7)" if trykk
                     else "max(0.3 · l_{b,rqd} ; 10φ ; 100)  (8.6)")
        _kv(pdf, [
            ("α_{2} · α_{3} · α_{5} ≥ 0.7  (8.5)", f"{d['a235']:.3f}"),
            ("α_{1} · (α_{2}α_{3}α_{5}) · α_{4} · l_{b,rqd}", f"{d['lbd_raw']:.1f} mm"),
            ("l_{b,min} = " + lbmin_txt, f"{d['lbmin']:.1f} mm"),
            ("l_{bd} = max(…)", f"{d['lbd']:.0f} mm"),
        ], w2)
    else:
        _txt(pdf, "Forankring ikkje tillaten for denne kombinasjonen.", h=5, style="I")

    if fo is not None:
        _blokk("Omfaring §8.7.3", fo, er_omf=True)
        rows = [
            ("α_{1} · α_{2} · α_{3} · α_{5} · α_{6} · l_{b,rqd}  (8.10)", f"{d['l0_raw']:.1f} mm"),
            ("l_{0,min} = max(0.3 · α_{6} · l_{b,rqd} ; 15φ ; 200)  (8.11)", f"{d['l0min']:.1f} mm"),
            ("l_{0} = max(…)", f"{d['l0']:.1f} mm"),
            ("l_{0} avrunda opp til næraste 100 mm", f"{d['l0_rund']} mm"),
        ]
        if d["omfar_forskyving"]:
            rows.append(("Forskyving enkeltstenger ≥ 1.3 · l_{0} (§8.9.3(3))",
                         f"{d['forskyving']:.0f} mm"))
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
        "§8.4.2 (8.2): f_{bd} = 2.25 · η_{1} · η_{2} · f_{ctd},  f_{ctd} = α_{ct} · f_{ctk,0.05} / γ_{C}"
        "  (α_{ct} = 0.85, NA.3.1.6(2)P)",
        "   f_{ctk,0.05} avgrensa til verdien for C60/75.",
        "§8.4.3 (8.3): l_{b,rqd} = (φ/4) · (σ_{sd} / f_{bd})",
        "§8.4.4 (8.4): l_{bd} = α_{1} · α_{2} · α_{3} · α_{4} · α_{5} · l_{b,rqd} ≥ l_{b,min}, "
        "  (8.5): α_{2} · α_{3} · α_{5} ≥ 0.7",
        "   (8.6) strekk: l_{b,min} = max(0.3 · l_{b,rqd} ; 10φ ; 100 mm)",
        "   (8.7) trykk:  l_{b,min} = max(0.6 · l_{b,rqd} ; 10φ ; 100 mm)",
        "§8.7.3 (8.10): l_{0} = α_{1} · α_{2} · α_{3} · α_{5} · α_{6} · l_{b,rqd} ≥ l_{0,min}",
        "§8.7.3 (8.11): l_{0,min} = max(0.3 · α_{6} · l_{b,rqd} ; 15φ ; 200 mm)",
        "",
        "Tabell 8.2 (strekk):",
        "   α_{1}: rett = 1.0 ; ikkje rett = 0.7 viss c_{d} > 3φ, elles 1.0",
        "   α_{2}: rett 1 − 0.15(c_{d} − φ)/φ ; ikkje rett 1 − 0.15(c_{d} − 3φ)/φ ; 0.7 ≤ α_{2} ≤ 1.0",
        "   α_{3} = 1 − Kλ,  λ = (ΣA_{st} − ΣA_{st,min})/A_{s} ; 0.7 ≤ α_{3} ≤ 1.0",
        "        ΣA_{st,min} = 0.25 · A_{s} (bjelkar) / 0 (plater) ; for omfaring A_{s} · σ_{sd}/f_{yd}",
        "        K = 0.1 (i bøyen) / 0.05 (innanfor) / 0 (utanfor), figur 8.4",
        "   α_{4} = 0.7 ved sveist tverrarmering ;  α_{5} = 1 − 0.04p, 0.7 ≤ α_{5} ≤ 1.0",
        "   α_{6} = (ρ_{1}/25)^{0.5}, 1.0 ≤ α_{6} ≤ 1.5 (tabell 8.3)",
        "Tabell 8.2 (trykk): α_{1} = α_{2} = α_{3} = 1.0 ; α_{4} = 0.7 ; α_{5} ikkje aktuell",
        "",
        "Figur 8.3: a) c_{d} = min(a/2 ; c_{1} ; c)   b) c_{d} = min(a/2 ; c_{1})   c) c_{d} = c",
        "   a = fri avstand mellom stengene = s − φ (bunt: s − 2φ, konservativt).",
        "",
        "§8.9 Buntar: φ_{n} = φ · √n_{b} ≤ 55 mm. n_{b} ≤ 4 for vertikale stenger i trykk og",
        "   i omfaringsskøyt, elles n_{b} ≤ 3.",
        "   §8.9.2(2): forankring med enkeltstenger forskyvd > 1.3 · l_{b,rqd} → φ, elles φ_{n}.",
        "   §8.9.3(2): 2 stenger, φ_{n} < 32 mm: omfaring utan forskyving, l_{0} med φ_{n}.",
        "   §8.9.3(3): 2 stenger med φ_{n} ≥ 32 mm eller 3 stenger: enkeltstenger forskyvast",
        "   ≥ 1.3 · l_{0} med l_{0} rekna for éi stang. Maks fire stenger i eitt snitt.",
    ]:
        _txt(pdf, linje, h=5)

    # ── Resultattabellar
    ws_r = [20, 30, 30, 30, 30, 30]
    cols_r = ["σ [MPa]", "ø12", "ø16", "ø20", "ø25", "ø32"]
    steg = list(range(0, sigma_s_max + 1, 25))

    def _v(x, fmt):
        return "–" if x != x else fmt.format(x)   # NaN → «–»

    _seksjon(pdf, "Resultat – omfaringslengde l_{0} [mm] (avrunda opp til 100 mm)")
    if f["n"] > 1:
        _txt(pdf, "Bunt: sjå §8.9.3 for kva diameter som er brukt og krav til forskyving.", h=5, style="I")
    _th(pdf, cols_r, ws_r)
    for i, s in enumerate(steg):
        _tr(pdf, [str(s)] + [_v(kurvar["l0"][p][s], "{:.0f}") for p in ec2_omfar.PHI_LIST],
            ws_r, fill=(i % 2 == 0))

    _seksjon(pdf, "Resultat – forankringslengde l_{bd} [mm]")
    _th(pdf, cols_r, ws_r)
    for i, s in enumerate(steg):
        _tr(pdf, [str(s)] + [_v(kurvar["lbd"][p][s], "{:.0f}") for p in ec2_omfar.PHI_LIST],
            ws_r, fill=(i % 2 == 0))
    _txt(pdf, "«–» = ikkje tillaten kombinasjon (sjå merknader).", h=5, style="I")

    if custom_points:
        _seksjon(pdf, "Eigendefinerte punkt")
        ws_e = [25, 30, 40, 40]
        _th(pdf, ["φ (mm)", "σ (MPa)", "l_{0} (mm)", "l_{bd} (mm)"], ws_e)
        for i, (phi, sig) in enumerate(custom_points):
            l0c, lbdc = ec2_omfar.beregn_omfarOgForankring(phi=phi, sigma_sd=sig, **f)
            _tr(pdf, [str(phi), f"{sig:.0f}", "–" if l0c is None else str(l0c),
                      "–" if lbdc is None else f"{lbdc:.0f}"], ws_e, fill=(i % 2 == 0))

    pdf.add_page(orientation="L")
    _seksjon(pdf, "Plott")
    _embed_plot(pdf, fig, width_mm=257)
    return bytes(pdf.output())
