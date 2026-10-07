"""
ec2_boye.py
Bøyediameter for armering per NS-EN 1992-1-1:2004+A1:2014+NA:2024
§8.3(3) uttrykk (8.1) og NA.8.3(2) Tabell NA.8.1N.c).
"""

import math
import numpy as np

import ec2_material as mat

# Stangdiametrar [mm]
PHI_LIST = [12, 16, 20, 25, 32]

# Tabell NA.8.1N.c) – minste dordiameter for B500NC etter NS 3576 [mm]
LOW_LIM = [32, 50, 80, 125, 160]
MIN_BEND = dict(zip(PHI_LIST, LOW_LIM))

# Standard senteravstandar (tidlegare hardkoda verdiar) [mm]
S_STANDARD = {12: 100, 16: 125, 20: 150, 25: 175, 32: 200}

AB_MODUSAR = [
    "Indre stang – senteravstand per diameter",
    "Indre stang – lik senteravstand for alle",
    "Kantstang – a_b = c + φ/2",
]


def fcd_boey(fck: float, gamma_c: float) -> tuple[float, float, bool]:
    """
    fcd for bruk i uttrykk (8.1).
    §8.3(3): «Verdien av fcd velges ikke høyere enn verdien for fasthetsklasse C55/67.»

    Returnerer (fcd, fck_brukt, avgrensa)
    """
    fck_brukt = min(fck, mat.FCK_MAKS_BOEY)
    return mat.fcd(fck_brukt, gamma_c), fck_brukt, fck > mat.FCK_MAKS_BOEY


def ab_map(modus: str, s_per_phi: dict | None = None,
           s_felles: float | None = None, c: float | None = None) -> dict:
    """
    a_b per stangdiameter, jf. definisjonen under uttrykk (8.1) i §8.3(3):
      - indre stang: a_b = halve senteravstanden vinkelrett på bøyens plan
      - stang mot ytterkant: a_b = overdekning + φ/2
    """
    if modus == AB_MODUSAR[0]:
        return {phi: s_per_phi[phi] / 2 for phi in PHI_LIST}
    if modus == AB_MODUSAR[1]:
        return {phi: s_felles / 2 for phi in PHI_LIST}
    return {phi: c + phi / 2 for phi in PHI_LIST}


def berekn_boeyediameter(phi: float, sigma: float, fcd: float, ab: float) -> tuple[float, float]:
    """
    Uttrykk (8.1):  φm,min ≥ Fbt · (1/ab + 1/(2φ)) / fcd

    Returnerer (d_81, min_tabell) i mm. Dimensjonerande dordiameter er
    max(d_81, min_tabell) jf. NA.8.3(2).
    """
    Fbt = math.pi * (phi / 2) ** 2 * sigma          # [N]
    d_bend = Fbt * (1 / ab + 1 / (2 * phi)) / fcd   # [mm]
    return d_bend, MIN_BEND[phi]


def berekn_kurvar(fcd: float, ab: dict, sigma_max: int = 435) -> dict:
    """Kurver for alle stangdiametrar, σ = 0 … sigma_max MPa."""
    sigma = np.arange(0, sigma_max + 1, 1)
    d_bend, d_bend_masked, d_dim = {}, {}, {}

    for phi in PHI_LIST:
        Fbt = np.pi * (phi / 2) ** 2 * sigma
        db = Fbt * (1 / ab[phi] + 1 / (2 * phi)) / fcd
        d_bend[phi] = db
        d_bend_masked[phi] = np.where(db >= MIN_BEND[phi], db, np.nan)
        d_dim[phi] = np.maximum(db, MIN_BEND[phi])

    return {
        "sigma": sigma,
        "d_bend": d_bend,
        "d_bend_masked": d_bend_masked,
        "d_dim": d_dim,
        "min_bend": dict(MIN_BEND),
    }
