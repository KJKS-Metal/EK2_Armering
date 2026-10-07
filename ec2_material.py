"""
ec2_material.py
Felles materialparametrar per NS-EN 1992-1-1:2004+A1:2014+NA:2024.

Kjelder:
  NA.2.4.2.4  Tabell NA.2.1N  – materialfaktorar γC og γS
  NA.3.1.6(1)P αcc = 0.85
  NA.3.1.6(2)P αct = 0.85
  Tabell 3.1  – fctm
"""

import re

ALPHA_CC = 0.85   # NA.3.1.6(1)P
ALPHA_CT = 0.85   # NA.3.1.6(2)P
FYK = 500.0       # B500NC [MPa]

# Tabell NA.2.1N – materialfaktorar i bruddgrensetilstand
SITUASJONAR = {
    "ULS – Bruddgrensetilstand": {"gamma_c": 1.50, "gamma_s": 1.15},
    "ALS – Ulykkessituasjon":    {"gamma_c": 1.20, "gamma_s": 1.00},
}

# Tabell 3.1 NS-EN 1992-1-1 – middelverdi for aksial strekkfasthet fctm [MPa]
FCTM_TABELL = {
    12: 1.6, 16: 1.9, 20: 2.2, 25: 2.6, 30: 2.9,
    35: 3.2, 40: 3.5, 45: 3.8, 50: 4.1, 55: 4.2,
    60: 4.4, 70: 4.6, 80: 4.8, 90: 5.0,
}
FCK_LISTE = list(FCTM_TABELL.keys())

# §8.3(3): fcd i uttrykk (8.1) skal ikkje takast høgare enn for C55/67
FCK_MAKS_BOEY = 55
# §8.4.2(2): fctk,0.05 i uttrykk (8.2) skal avgrensast til verdien for C60/75
FCK_MAKS_HEFT = 60


def gamma(situasjon: str) -> tuple[float, float]:
    s = SITUASJONAR[situasjon]
    return s["gamma_c"], s["gamma_s"]


def hent_fctm(fck: float) -> float:
    """Middelverdi strekkfasthet frå Tabell 3.1."""
    if fck in FCTM_TABELL:
        return FCTM_TABELL[fck]
    naermast = min(FCTM_TABELL.keys(), key=lambda x: abs(x - fck))
    return FCTM_TABELL[naermast]


def fcd(fck: float, gamma_c: float) -> float:
    """fcd = αcc · fck / γC  (uttrykk 3.15)."""
    return ALPHA_CC * fck / gamma_c


def fyd(gamma_s: float) -> float:
    return FYK / gamma_s


# ── Markering for heva/senka skrift ─────────────────────────
# Tekst kan innehalde  x_{ab}  (senka) og  x^{2}  (heva).
# PDF-rapporten teiknar dette direkte; i Streamlit vert det gjort om til LaTeX.
_GRESK = {"α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "η": r"\eta", "λ": r"\lambda",
          "ρ": r"\rho", "σ": r"\sigma", "φ": r"\phi", "Σ": r"\Sigma"}
_RE_MARK = re.compile(r"(Σ?[A-Za-zα-ωΣ])([_^])\{([^{}]*)\}")


def til_latex(tekst: str) -> str:
    """φ_{n} → $\\phi_\\mathrm{n}$ osb. for visning i Streamlit."""
    def _erst(m):
        base = "".join(_GRESK.get(ch, ch) + (" " if ch == "Σ" else "") for ch in m.group(1))
        idx = m.group(3)
        idx = rf"\mathrm{{{idx}}}" if re.fullmatch(r"[A-Za-z][A-Za-z,.]+", idx) else idx
        return f"${base}{m.group(2)}{{{idx}}}$"
    return _RE_MARK.sub(_erst, tekst)
