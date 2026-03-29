"""
ec2_omfar.py
Bereknar omfarings- og forankringslengder per NS-EN 1992-1-1 §8.4 og §8.7.
"""

import math

PHI_LIST = [12, 16, 20, 25, 32]

# Tabell 3.1 NS-EN 1992-1-1 – middelverdi for strekkfasthet fctm [MPa]
_FCTM_TABELL = {
    12: 1.6, 16: 1.9, 20: 2.2, 25: 2.6, 30: 2.9,
    35: 3.2, 40: 3.5, 45: 3.8, 50: 4.1, 55: 4.2,
    60: 4.4, 70: 4.6, 80: 4.8, 90: 5.0,
}


def hent_fctm(fck: float) -> float:
    """Middelverdi for karakteristisk strekkfasthet frå Tabell 3.1 NS-EN 1992-1-1."""
    if fck in _FCTM_TABELL:
        return _FCTM_TABELL[fck]
    naermast = min(_FCTM_TABELL.keys(), key=lambda x: abs(x - fck))
    return _FCTM_TABELL[naermast]


def get_type_kobling_tekst(type_kobling: str) -> str:
    tekst = {"a": "Rette stenger", "b": "Vinkelkroker eller kroker", "c": "Sløyfer"}
    return tekst.get(type_kobling, "Ukjend")


def _get_cd(type_kobling: str, a: float, c: float) -> float:
    """Dimensjonerande kantavstand ved brudd, §8.4.4."""
    if type_kobling in ("a", "b"):
        return min(a / 2, c)
    return c  # type c


def _get_alpha_1(type_kobling: str, cd: float, phi_n: float) -> float:
    """α₁ – koeffisient for koblingstype, Tabell 8.2 NS-EN 1992-1-1."""
    if type_kobling == "a":
        return 1.0
    return 0.7 if cd > 3 * phi_n else 1.0


def _get_alpha_2(type_kobling: str, cd: float, phi_n: float) -> float:
    """α₂ – koeffisient for inneslutningsverknad, Tabell 8.2 NS-EN 1992-1-1."""
    if type_kobling == "a":
        alpha = 1 - 0.15 * (cd - phi_n) / phi_n
    else:
        alpha = 1 - 0.15 * (cd - 3 * phi_n) / phi_n
    return max(0.7, min(1.0, alpha))


def beregn_omfarOgForankring(
    fck: float,
    eta_01: float,
    phi: float,
    n: int,
    sigma_sd: float,
    c: float,
    a: float,
    type_kobling: str,
    sum_ast: float,
    stangplassering: str,
    rho: float,
    rho_1: float,
    sveist_tverrarmering: bool,
) -> tuple[float, float]:
    """
    Bereknar omfarings- og forankringslengde per NS-EN 1992-1-1.

    Returnerer (l0n400, lbd) i mm.
    """
    fctm    = hent_fctm(fck)
    fctk005 = 0.7 * fctm
    alpha_ct = 0.85
    gamma_c  = 1.5
    fctd    = alpha_ct * fctk005 / gamma_c          # §3.1.6(2) formel (3.19)
    eta_02  = 1.0 if phi <= 32 else (132 - phi) / 100
    fbd     = 2.25 * eta_01 * eta_02 * fctd         # §8.4.2 formel (8.2)
    phi_n   = phi * math.sqrt(n)                     # ekvivalent diameter for bunt
    As      = (math.pi / 4) * phi_n ** 2
    lbrqd   = (phi_n / 4) * (abs(sigma_sd) / fbd)   # §8.4.3 formel (8.3)

    cd      = _get_cd(type_kobling, a, c)
    alpha_1 = _get_alpha_1(type_kobling, cd, phi_n)
    alpha_2 = _get_alpha_2(type_kobling, cd, phi_n)

    sum_astmin = As if phi_n >= 20 else 0
    if stangplassering == "Utenfor":
        k = 0
    elif stangplassering == "Innenfor":
        k = 0.05
    else:  # I bøy
        k = 0.1

    alpha_3 = max(0.7, min(1.0, 1 - k * (sum_ast - sum_astmin) / As))
    alpha_4 = 0.7
    alpha_5 = max(0.7, min(1.0, 1 - 0.04 * rho))
    alpha_6 = max(1.0, min(1.5, (rho_1 / 25) ** 0.5))

    # Omfaringslengde §8.7.3 formel (8.10) og (8.11)
    l0min = max(0.3 * lbrqd * alpha_6, 15 * phi_n, 200)
    l0    = max(lbrqd * alpha_1 * alpha_2 * alpha_3 * alpha_5 * alpha_6, l0min)
    l0n400 = math.ceil(l0 / 100) * 100

    # Forankringslengde §8.4.4 formel (8.4)
    lbdmin   = max(0.3 * lbrqd, 10 * phi_n, 100) if sigma_sd > 0 else max(0.6 * lbrqd, 10 * phi_n, 100)
    alpha_235 = max(0.7, alpha_2 * alpha_3 * alpha_5)
    if sveist_tverrarmering:
        lbd = max(lbrqd * alpha_1 * alpha_235 * alpha_4, lbdmin)
    else:
        lbd = max(lbrqd * alpha_1 * alpha_235, lbdmin)

    return l0n400, lbd


def berekn_kurvar(
    fck: float,
    eta_01: float,
    n: int,
    c: float,
    a: float,
    type_kobling: str,
    sum_ast: float,
    stangplassering: str,
    rho: float,
    rho_1: float,
    sveist_tverrarmering: bool,
    sigma_s_max: int = 500,
) -> dict:
    """
    Bereknar l0 og lbd for alle stangdiametrar over spenningsintervallet.

    Returnerer dict med nøklar 'sigma_sd', 'l0', 'lbd' (begge som {phi: list}).
    """
    sigma_sd_values = list(range(0, sigma_s_max + 1, 1))
    l0_kurvar  = {phi: [] for phi in PHI_LIST}
    lbd_kurvar = {phi: [] for phi in PHI_LIST}

    for sigma in sigma_sd_values:
        for phi in PHI_LIST:
            l0, lbd = beregn_omfarOgForankring(
                fck, eta_01, phi, n, sigma, c, a,
                type_kobling, sum_ast, stangplassering,
                rho, rho_1, sveist_tverrarmering,
            )
            l0_kurvar[phi].append(l0)
            lbd_kurvar[phi].append(lbd)

    return {
        'sigma_sd': sigma_sd_values,
        'l0':  l0_kurvar,
        'lbd': lbd_kurvar,
    }
