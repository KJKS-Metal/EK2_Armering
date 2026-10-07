"""
ec2_omfar.py
Forankrings- og omfaringslengder per NS-EN 1992-1-1:2004+A1:2014+NA:2024
§8.4 (forankring), §8.7 (omfaring) og §8.9 (bunta armering).
"""

# Merknader nyttar markering for senka skrift: φ_{n} (sjå ec2_material.til_latex)

import math

import ec2_material as mat

PHI_LIST = [12, 16, 20, 25, 32]

TYPE_TEKST = {"a": "Rette stenger", "b": "Vinkelkroker eller kroker", "c": "Sløyfer"}
K_MAP = {"Utanfor": 0.0, "Innanfor": 0.05, "I bøy": 0.1}   # Figur 8.4

PHI_N_MAKS = 55.0      # uttrykk (8.14)
PHI_LARGE_BUNT = 40.0  # NA.8.8(1)


def get_type_kobling_tekst(type_kobling: str) -> str:
    return TYPE_TEKST.get(type_kobling, "Ukjend")


def fri_avstand(s: float, phi: float, n: int) -> float:
    """
    Fri avstand a mellom stenger/buntar (figur 8.3).
    Enkeltstang: a = s − φ.
    Bunt (§8.9.1(3)): fri avstand målt frå faktisk utvendig omkrins.
    Konservativt er buntbreidda sett til 2φ for n ≥ 2 (stenger side om side).
    """
    b = phi if n == 1 else 2 * phi
    return s - b


def get_cd(type_kobling: str, a: float, c: float, c1: float) -> float:
    """Figur 8.3."""
    if type_kobling == "a":
        return min(a / 2, c1, c)
    if type_kobling == "b":
        return min(a / 2, c1)
    return c


def _eta_2(phi: float) -> float:
    return 1.0 if phi <= 32 else (132 - phi) / 100


def _alpha_1(trykk: bool, type_kobling: str, cd: float, phi: float) -> float:
    if trykk or type_kobling == "a":
        return 1.0
    return 0.7 if cd > 3 * phi else 1.0


def _alpha_2(trykk: bool, type_kobling: str, cd: float, phi: float) -> tuple[float, float]:
    """Returnerer (α2, urekna verdi før avgrensing)."""
    if trykk:
        return 1.0, 1.0
    if type_kobling == "a":
        raw = 1 - 0.15 * (cd - phi) / phi
    else:
        raw = 1 - 0.15 * (cd - 3 * phi) / phi
    return max(0.7, min(1.0, raw)), raw


def _alpha_3(trykk: bool, K: float, sum_ast: float, sum_ast_min: float, As: float) -> float:
    if trykk:
        return 1.0
    lam = (sum_ast - sum_ast_min) / As
    return max(0.7, min(1.0, 1 - K * lam))


def _alpha_5(trykk: bool, p: float) -> float:
    if trykk:
        return 1.0          # Tabell 8.2: «–» for trykk
    return max(0.7, min(1.0, 1 - 0.04 * p))


def _alpha_6(rho_1: float) -> float:
    return max(1.0, min(1.5, (rho_1 / 25) ** 0.5))


def beregn_detaljar(
    fck: float,
    gamma_c: float,
    gamma_s: float,
    trykk: bool,
    eta_01: float,
    phi: float,
    n: int,
    sigma_sd: float,
    s: float,
    c: float,
    c1: float,
    type_kobling: str,
    sum_ast: float,
    konstruksjon: str,
    stangplassering: str,
    rho: float,
    rho_1: float,
    sveist_tverrarmering: bool,
    forskyvd_forankring: bool = False,
) -> dict:
    """
    Full berekning med mellomresultat. sigma_sd er absoluttverdi [MPa].
    Returnerer dict; 'lbd' / 'l0' er None dersom kombinasjonen ikkje er tillaten.
    """
    sigma = abs(sigma_sd)
    fyd = mat.fyd(gamma_s)
    merknader = []

    # ── Heftfasthet §8.4.2 ────────────────────────────────
    fck_heft = min(fck, mat.FCK_MAKS_HEFT)
    fctm = mat.hent_fctm(fck_heft)
    fctk005 = 0.7 * fctm
    fctd = mat.ALPHA_CT * fctk005 / gamma_c

    phi_n = phi * math.sqrt(n)

    # ── Kva diameter skal brukast? §8.9.2 og §8.9.3 ───────
    if n == 1:
        phi_forank = phi
        phi_omfar = phi
        omfar_forskyving = False
    else:
        phi_forank = phi if forskyvd_forankring else phi_n
        if n == 2 and phi_n < 32:
            phi_omfar = phi_n                # §8.9.3(2)
            omfar_forskyving = False
        elif n in (2, 3):
            phi_omfar = phi                  # §8.9.3(3): enkeltstenger forskyvd 1.3·l0
            omfar_forskyving = True
        else:
            phi_omfar = None                 # §8.9.3(3): > 3 stenger skal ikkje omfarast
            omfar_forskyving = False

    # ── Gyldigheit ────────────────────────────────────────
    forank_ok = True
    omfar_ok = phi_omfar is not None
    if phi_n > PHI_N_MAKS:
        forank_ok = omfar_ok = False
        merknader.append(f"φ_{{n}} = {phi_n:.1f} mm > 55 mm – ikkje tillate, jf. (8.14).")
    if n == 4 and not trykk:
        forank_ok = False
        merknader.append("n_{b} = 4 er berre tillate for vertikale stenger i trykk, jf. §8.9.1(2).")
    if n >= 4:
        merknader.append("Buntar med meir enn tre stenger skal ikkje omfarast, jf. §8.9.3(3).")
    if n > 1 and phi_n >= 32 and not forskyvd_forankring and not trykk:
        merknader.append(
            f"φ_{{n}} = {phi_n:.1f} mm ≥ 32 mm: stengene i bunten bør forskyvast ved opplegg, jf. §8.9.2(1)."
        )
    if phi_n > PHI_LARGE_BUNT:
        merknader.append(
            f"φ_{{n}} = {phi_n:.1f} mm > φ_{{large}} = 40 mm for buntar (NA.8.8(1)): tilleggsreglar i §8.8 gjeld."
        )

    a = fri_avstand(s, phi, n)
    cd = get_cd(type_kobling, a, c, c1)

    def _ledd(phi_x: float, er_omfaring: bool) -> dict:
        eta_2 = _eta_2(phi_x)
        fbd = 2.25 * eta_01 * eta_2 * fctd
        As = math.pi / 4 * phi_x ** 2
        lbrqd = (phi_x / 4) * (sigma / fbd)
        a1 = _alpha_1(trykk, type_kobling, cd, phi_x)
        a2, a2_raw = _alpha_2(trykk, type_kobling, cd, phi_x)
        if er_omfaring:
            sum_ast_min = As * sigma / fyd                   # §8.7.3(1)
        else:
            sum_ast_min = 0.25 * As if konstruksjon == "Bjelke" else 0.0   # Tabell 8.2
        K = K_MAP.get(stangplassering, 0.05)
        a3 = _alpha_3(trykk, K, sum_ast, sum_ast_min, As)
        a4 = 0.7 if sveist_tverrarmering else 1.0
        a5 = _alpha_5(trykk, rho)
        a6 = _alpha_6(rho_1)
        return dict(phi_x=phi_x, eta_2=eta_2, fbd=fbd, As=As, lbrqd=lbrqd,
                    a1=a1, a2=a2, a2_raw=a2_raw, sum_ast_min=sum_ast_min, K=K,
                    a3=a3, a4=a4, a5=a5, a6=a6)

    # ── Forankring §8.4.4 ─────────────────────────────────
    fa = _ledd(phi_forank, er_omfaring=False)
    a235 = max(0.7, fa["a2"] * fa["a3"] * fa["a5"])               # (8.5)
    if trykk:
        lbmin = max(0.6 * fa["lbrqd"], 10 * phi_forank, 100)       # (8.7)
    else:
        lbmin = max(0.3 * fa["lbrqd"], 10 * phi_forank, 100)       # (8.6)
    lbd_raw = fa["a1"] * a235 * fa["a4"] * fa["lbrqd"]
    lbd = max(lbd_raw, lbmin) if forank_ok else None

    # ── Omfaring §8.7.3 ───────────────────────────────────
    if omfar_ok:
        fo = _ledd(phi_omfar, er_omfaring=True)
        l0min = max(0.3 * fo["a6"] * fo["lbrqd"], 15 * phi_omfar, 200)   # (8.11)
        l0_raw = fo["a1"] * fo["a2"] * fo["a3"] * fo["a5"] * fo["a6"] * fo["lbrqd"]
        l0 = max(l0_raw, l0min)
        l0_rund = math.ceil(l0 / 100) * 100
        forskyving = 1.3 * l0_rund if omfar_forskyving else None
    else:
        fo, l0min, l0_raw, l0, l0_rund, forskyving = None, None, None, None, None, None

    return dict(
        fck=fck, fck_heft=fck_heft, fctm=fctm, fctk005=fctk005, fctd=fctd,
        gamma_c=gamma_c, gamma_s=gamma_s, fyd=fyd, trykk=trykk,
        phi=phi, n=n, phi_n=phi_n, sigma=sigma, s=s, a=a, c=c, c1=c1, cd=cd,
        forank=fa, a235=a235, lbmin=lbmin, lbd_raw=lbd_raw, lbd=lbd,
        omfar=fo, l0min=l0min, l0_raw=l0_raw, l0=l0, l0_rund=l0_rund,
        omfar_forskyving=omfar_forskyving, forskyving=forskyving,
        merknader=merknader,
    )


def beregn_omfarOgForankring(**kw) -> tuple:
    """Kortform: returnerer (l0 avrunda opp til 100 mm, lbd) – None om ugyldig."""
    d = beregn_detaljar(**kw)
    return d["l0_rund"], d["lbd"]


def berekn_kurvar(sigma_s_max: int = 500, **kw) -> dict:
    """
    l0 og lbd for alle stangdiametrar over σsd = 0 … sigma_s_max.
    kw = alle argument til beregn_detaljar utanom phi og sigma_sd.
    Ugyldige kombinasjonar vert lagra som float('nan').
    """
    nan = float("nan")
    sig = list(range(0, sigma_s_max + 1, 1))
    l0_k = {phi: [] for phi in PHI_LIST}
    lbd_k = {phi: [] for phi in PHI_LIST}
    for phi in PHI_LIST:
        for s_ in sig:
            l0, lbd = beregn_omfarOgForankring(phi=phi, sigma_sd=s_, **kw)
            l0_k[phi].append(nan if l0 is None else l0)
            lbd_k[phi].append(nan if lbd is None else lbd)
    return {"sigma_sd": sig, "l0": l0_k, "lbd": lbd_k}
