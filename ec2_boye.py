"""
ec2_boye.py
Reinskalkulering av bøyediameter for armering per NS-EN 1992-1-1 formel (8.1).
"""

import math
import numpy as np

# Stangdiametrar og tilhøyrande konstantar
PHI_LIST   = [12, 16, 20, 25, 32]           # mm
AB_LIST    = [50, 62.5, 75, 87.5, 100]      # mm  (senteravstand/2)
LOW_LIM    = [32, 50, 80, 125, 160]         # mm  Tabell NA.8.1N.c) minstediameter

FCD_DEFAULT = 25.5  # MPa (tilsvarar t.d. C30/37)


def berekn_boeyediameter(phi: float, sigma: float, fcd: float) -> tuple[float, float | None]:
    """
    Bereknar bøyediameter per NS-EN 1992-1-1 formel (8.1).

    Parametrar
    ----------
    phi   : stangdiameter [mm], ein av 12/16/20/25/32
    sigma : strekkspenning i armering [MPa], 0–435
    fcd   : dimensjonerande trykkfasthet betong [MPa]

    Returverdi
    ----------
    (d_bend, min_bend)
        d_bend   : berekna bøyediameter [mm]
        min_bend : minstediameter frå Tabell NA.8.1N.c) [mm], eller None viss phi ikkje er i PHI_LIST
    """
    idx = PHI_LIST.index(phi)
    ab = AB_LIST[idx]
    min_bend = LOW_LIM[idx]
    Fbt = math.pi * (phi / 2) ** 2 * sigma          # [N]
    d_bend = Fbt * (1 / ab + 1 / (2 * phi)) / fcd   # [mm]
    return d_bend, min_bend


def berekn_kurvar(fcd: float) -> dict:
    """
    Bereknar kurvene for alle stangdiametrar over spenningsintervallet 0–435 MPa.

    Returverdi
    ----------
    dict med nøklar:
        'sigma'          : np.ndarray [0, 1, ..., 435]
        'd_bend'         : dict {phi: np.ndarray av bøyediametrar}
        'd_bend_masked'  : dict {phi: np.ndarray, verdiar under minstediameter sett til np.nan}
        'min_bend'       : dict {phi: float}
    """
    sigma = np.arange(0, 436, 1)
    d_bend = {}
    d_bend_masked = {}
    min_bend_map = {}

    for idx, phi in enumerate(PHI_LIST):
        ab = AB_LIST[idx]
        min_b = LOW_LIM[idx]
        Fbt = np.pi * (phi / 2) ** 2 * sigma
        db = Fbt * (1 / ab + 1 / (2 * phi)) / fcd
        d_bend[phi] = db
        d_bend_masked[phi] = np.where(db >= min_b, db, np.nan)
        min_bend_map[phi] = min_b

    return {
        'sigma': sigma,
        'd_bend': d_bend,
        'd_bend_masked': d_bend_masked,
        'min_bend': min_bend_map,
    }
