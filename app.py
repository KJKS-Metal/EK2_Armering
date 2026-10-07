"""
app.py  –  EC2 Armering Verktøy
Streamlit-applikasjon for bøyediameter, omfarings- og forankringslengder
per NS-EN 1992-1-1:2004+A1:2014+NA:2024 (Eurokode 2).

Køyr med:  streamlit run app.py
"""

import io
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import streamlit as st

import ec2_material as mat
import ec2_boye
import ec2_omfar
import ec2_figur
import ec2_rapport

matplotlib.use("Agg")  # headless backend for Streamlit

STANDARD = "NS-EN 1992-1-1:2004+A1:2014+NA:2024"

# Symbol med senka skrift (LaTeX – vert vist med KaTeX i Streamlit og mathtext i matplotlib)
FCK, FCD, FCTM, FYD = r"$f_\mathrm{ck}$", r"$f_\mathrm{cd}$", r"$f_\mathrm{ctm}$", r"$f_\mathrm{yd}$"
FCTK = r"$f_\mathrm{ctk,0.05}$"
GC, GS = r"$\gamma_\mathrm{C}$", r"$\gamma_\mathrm{S}$"
ACC, ACT = r"$\alpha_\mathrm{cc}$", r"$\alpha_\mathrm{ct}$"
AB, PHIM = r"$a_\mathrm{b}$", r"$\phi_\mathrm{m,min}$"
LBRQD, LBD, L0, LBMIN = r"$l_\mathrm{b,rqd}$", r"$l_\mathrm{bd}$", r"$l_0$", r"$l_\mathrm{b,min}$"
SIGSD, SIGSMAX = r"$\sigma_\mathrm{sd}$", r"$\sigma_\mathrm{s,max}$"
AST, ASTMIN, AS = r"$\Sigma A_\mathrm{st}$", r"$\Sigma A_\mathrm{st,min}$", r"$A_\mathrm{s}$"
PHIN, C1, RHO1, ETA1 = r"$\phi_n$", r"$c_1$", r"$\rho_1$", r"$\eta_1$"
A1, A2, A3, A4, A5, A6 = (rf"$\alpha_{i}$" for i in range(1, 7))

# ──────────────────────────────────────────────────────────
# Sideoppsett
# ──────────────────────────────────────────────────────────
st.set_page_config(page_title="EC2 Armering Verktøy", page_icon="🔩", layout="wide")

st.title("EC2 Armering Verktøy")
st.caption(f"{STANDARD} – bøyediameter, omfaring og forankring")

# ── Globale val ──────────────────────────────────────────
g1, g2, g3 = st.columns([1.2, 1.2, 2])
with g1:
    situasjon = st.selectbox(
        "Dimensjonerande situasjon",
        list(mat.SITUASJONAR.keys()),
        help=f"Tabell NA.2.1N: ULS (vedvarande/forbigåande) {GC} = 1.50, {GS} = 1.15 · "
             f"ALS (ulykke) {GC} = 1.20, {GS} = 1.00. Forankring og omfaring vert ikkje kontrollert "
             f"i SLS ({SIGSD} og {FCTK}/{GC} i §8.4 er dimensjonerande verdiar).",
    )
with g2:
    tilstand = st.selectbox(
        "Spenningstilstand i armeringa",
        ["Strekk", "Trykk"],
        help=f"Gjeld fana «Omfaring og forankring». Tabell 8.2: i trykk er {A1} = {A2} = {A3} = 1.0 "
             f"og {A5} er ikkje aktuell. {LBMIN} etter (8.7). Bøyediameter vert alltid rekna for strekk.",
    )
gamma_c, gamma_s = mat.gamma(situasjon)
fyd = mat.fyd(gamma_s)
trykk = tilstand == "Trykk"
with g3:
    st.markdown(
        f"{GC} = **{gamma_c:.2f}** · {GS} = **{gamma_s:.2f}** · {FYD} = 500/{gamma_s:.2f} = **{fyd:.0f} MPa**  \n"
        f"{ACC} = {mat.ALPHA_CC} (NA.3.1.6(1)P) · {ACT} = {mat.ALPHA_CT} (NA.3.1.6(2)P)"
    )
if trykk:
    st.info("Trykk er valt. Kontroller òg §8.7.4.2 (tverrarmering ved omfaring i trykk) og "
            "§8.4.1(3): vinkelkroker og kroker bidreg ikkje til forankring av trykkarmering.")

tab1, tab2 = st.tabs(["🔄 Bøyediameter", "📏 Omfaring og forankring"])


def _fig_to_bytes(fig, fmt: str, dpi: int = 300) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    return buf.read()


def _punktliste(key: str, phi_sel, sig_max: float):
    if key not in st.session_state:
        st.session_state[key] = []
    ca, cb = st.columns(2)
    with ca:
        p = st.selectbox(r"Stangdiameter $\phi$ [mm]", phi_sel, key=f"{key}_phi")
    with cb:
        s = st.number_input(r"Spenning $\sigma$ [MPa]", min_value=0.0, max_value=float(sig_max),
                            value=min(200.0, float(sig_max)), step=5.0, key=f"{key}_sig")
    if st.button("Legg til punkt", key=f"{key}_add"):
        st.session_state[key].append((p, float(s)))
    if st.session_state[key]:
        st.markdown("**Lagde punkt:**")
        fjern = []
        for i, (pp, ss) in enumerate(st.session_state[key]):
            c1_, c2_ = st.columns([3, 1])
            c1_.write(f"φ{pp} mm,  {ss:.0f} MPa")
            if c2_.button("✕", key=f"{key}_rm_{i}"):
                fjern.append(i)
        for i in reversed(fjern):
            st.session_state[key].pop(i)
        if st.button("Nullstill alle punkt", key=f"{key}_clear"):
            st.session_state[key] = []


# ══════════════════════════════════════════════════════════
# TAB 1 – Bøyediameter
# ══════════════════════════════════════════════════════════
with tab1:
    st.header("Bøyediameter – §8.3 uttrykk (8.1) og NA.8.3(2)")

    with st.expander("📐 Formelreferansar"):
        st.markdown(r"""
**§8.3(3) uttrykk (8.1)**

$$
\phi_{m,min} \geq \frac{F_{bt}\left(\dfrac{1}{a_b} + \dfrac{1}{2\phi}\right)}{f_{cd}}
$$

| Symbol | Forklaring |
|--------|-----------|
| $F_{bt}$ | Strekkraft i stanga ved byrjinga av bøyen i bruddgrensetilstand: $F_{bt} = \pi(\phi/2)^2\cdot\sigma$ [N] |
| $a_b$ | Halve senteravstanden mellom stengene vinkelrett på bøyens plan. For stang mot ytterkant: $a_b = c + \phi/2$ [mm] |
| $f_{cd}$ | $\alpha_{cc} f_{ck}/\gamma_C$, men ikkje høgare enn for C55/67 [MPa] |

**NA.8.3(2):** Dordiameteren skal ikkje vere mindre enn den største av verdien i
tabell NA.8.1N og verdien frå uttrykk (8.1).

**Tabell NA.8.1N.c)** – B500NC etter NS 3576:

| φ (mm) | 12 | 16 | 20 | 25 | 32 |
|---|---|---|---|---|---|
| φm,min (mm) | 32 | 50 | 80 | 125 | 160 |
""")

    col_inp, col_plot = st.columns([1, 2.5])

    with col_inp:
        st.subheader("Inndata")

        fck_b = st.selectbox(
            f"Betongfasthet {FCK} [MPa]", mat.FCK_LISTE, index=mat.FCK_LISTE.index(45),
            key="boye_fck",
            help=f"{FCD} = {ACC} · {FCK} / {GC}. §8.3(3): «Verdien av fcd velges ikke høyere enn "
                 "verdien for fasthetsklasse C55/67.» Grunnen er at høgfast betong er "
                 "sprøare, og at (8.1) er ein modell for knusing/splitting av betongen "
                 "innanfor bøyen som ikkje er verifisert for høgare fastheiter.",
        )
        fcd, fck_brukt, avgrensa = ec2_boye.fcd_boey(fck_b, gamma_c)
        st.markdown(f"{FCD} = {mat.ALPHA_CC} · {fck_brukt} / {gamma_c:.2f} = **{fcd:.2f} MPa**")
        if avgrensa:
            st.warning(f"{FCK} = {fck_b} MPa er avgrensa til {mat.FCK_MAKS_BOEY} MPa (C55/67) "
                       "i uttrykk (8.1), jf. siste avsnitt i §8.3(3).")

        st.divider()
        ab_modus = st.radio(f"Bestemming av {AB}", ec2_boye.AB_MODUSAR, key="ab_modus",
                            format_func=lambda x: x.replace("a_b = c + φ/2", r"$a_\mathrm{b} = c + \phi/2$"))
        with st.expander("ℹ️ Kvar kjem $a_b$ frå?"):
            st.markdown(
                "Definisjonen står rett under uttrykk (8.1) i **§8.3(3)** "
                "(side 132 i NS-EN 1992-1-1):\n\n"
                "> *ab – for en gitt stang (eller armeringsbunt) er halve senteravstanden "
                "mellom stengene (eller armeringsbunt) vinkelrett på bøyens plan. For en stang "
                "eller gruppe av stenger mot ytterkant av en konstruksjonsdel bør ab antas å "
                "være overdekningen pluss φ/2.*\n\n"
                "Altså: $a_b$ er avstanden frå senter av stanga til nærmaste «frie» kant av den "
                "betongskiva som tek opp trykket frå bøyen – anten halve avstanden til nabostanga "
                "eller overdekninga til betongflata + φ/2."
            )
        if ab_modus == ec2_boye.AB_MODUSAR[0]:
            s_per_phi = {}
            cols = st.columns(len(ec2_boye.PHI_LIST))
            for col, phi in zip(cols, ec2_boye.PHI_LIST):
                s_per_phi[phi] = col.number_input(f"s ø{phi}", min_value=20, max_value=1000,
                                                  value=ec2_boye.S_STANDARD[phi], step=5,
                                                  key=f"s_boye_{phi}")
            ab = ec2_boye.ab_map(ab_modus, s_per_phi=s_per_phi)
        elif ab_modus == ec2_boye.AB_MODUSAR[1]:
            s_f = st.number_input("Senteravstand s [mm]", min_value=20, max_value=1000,
                                  value=150, step=5, key="s_boye_felles")
            ab = ec2_boye.ab_map(ab_modus, s_felles=s_f)
        else:
            c_b = st.number_input("Overdekning c [mm]", min_value=5, max_value=200,
                                  value=50, step=5, key="c_boye")
            ab = ec2_boye.ab_map(ab_modus, c=c_b)
        st.caption(f"{AB} [mm]:  " + "  |  ".join(f"ø{p}: {ab[p]:.1f}" for p in ec2_boye.PHI_LIST))

        st.divider()
        st.markdown("**Eige punkt å markere i plottet**")
        sigma_max_b = int(round(fyd))
        _punktliste("boye_custom", ec2_boye.PHI_LIST, sigma_max_b)

    with col_plot:
        data = ec2_boye.berekn_kurvar(fcd, ab, sigma_max=sigma_max_b)
        sigma = data["sigma"]
        fig, ax = plt.subplots(figsize=(10, 6))
        colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

        for idx, phi in enumerate(ec2_boye.PHI_LIST):
            clr = colors[idx % len(colors)]
            dm = data["d_bend_masked"][phi]
            ax.plot(sigma, dm, label=f"ø{phi} mm", color=clr)

            snap_sig = np.arange(0, sigma_max_b + 1, 25)
            snap = dm[snap_sig]
            valid = np.where(~np.isnan(snap))[0]
            if valid.size > 1:
                pidx = valid[1:]
                ax.scatter(snap_sig[pidx], snap[pidx], s=30, color=clr)
                for x, y in zip(snap_sig[pidx], snap[pidx]):
                    ax.annotate(f"{y:.0f}", (x, y), textcoords="offset points",
                                xytext=(0, 5), ha="center", fontsize=7)
            vi = np.where(~np.isnan(dm))[0]
            if vi.size > 0:
                for e in (vi[0], vi[-1]):
                    ax.scatter(sigma[e], dm[e], s=40, color="black", zorder=5)
                    ax.annotate(f"{dm[e]:.0f}", (sigma[e], dm[e]), textcoords="offset points",
                                xytext=(0, 9), ha="center", fontsize=8)

        for phi_c, sig_c in st.session_state.get("boye_custom", []):
            d, mn = ec2_boye.berekn_boeyediameter(phi_c, sig_c, fcd, ab[phi_c])
            if d >= mn:
                ax.scatter([sig_c], [d], color="red", s=100, marker="*", zorder=10,
                           label=f"ø{phi_c}, {sig_c:.0f} MPa")
                ax.annotate(f"{d:.0f}", (sig_c, d), textcoords="offset points",
                            xytext=(0, 10), ha="center", fontsize=10, color="red")
            else:
                st.info(f"ø{phi_c}, {sig_c:.0f} MPa: (8.1) gir {d:.1f} mm < {mn:.0f} mm frå "
                        f"tabell NA.8.1N.c) → tabellverdien {mn:.0f} mm er dimensjonerande.")

        ax.set_title(f"Naudsynt dordiameter etter uttrykk (8.1) – {situasjon}\n"
                     f"{FCD} = {fcd:.2f} MPa  (kurva vist der (8.1) gir meir enn tabell NA.8.1N.c)",
                     fontsize=11)
        ax.set_xlabel(r"Strekkspenning $\sigma$ [MPa]")
        ax.set_ylabel(f"Naudsynt dordiameter {PHIM} [mm]")
        ax.set_ylim(0, 400)
        ax.set_xlim(0, sigma_max_b)
        ax.legend(loc="upper left", fontsize=9)
        ax.grid(True, alpha=0.4)
        fig.tight_layout()
        st.pyplot(fig)

        rapport_bytes = ec2_rapport.lag_rapport_boye(
            fck_b, fcd, fck_brukt, avgrensa, situasjon, gamma_c, gamma_s,
            ab_modus, ab, sigma_max_b, fig,
            custom_points=st.session_state.get("boye_custom", []),
        )
        png_b, pdf_b = _fig_to_bytes(fig, "png"), _fig_to_bytes(fig, "pdf")
        plt.close(fig)

        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇️ Plott som PNG (300 dpi)", png_b, "boeyediameter_EC2.png", "image/png")
        d2.download_button("⬇️ Plott som PDF", pdf_b, "boeyediameter_EC2.pdf", "application/pdf")
        d3.download_button("📄 Berekningstillegg (PDF)", rapport_bytes,
                           "berekningstillegg_boeyediameter.pdf", "application/pdf")


# ══════════════════════════════════════════════════════════
# TAB 2 – Omfaring og forankring
# ══════════════════════════════════════════════════════════
with tab2:
    st.header(f"Omfaring og forankring – §8.4, §8.7 og §8.9  ({tilstand.lower()})")

    with st.expander("📐 Formelreferansar"):
        st.markdown(r"""
**§8.4.2 (8.2)** $f_{bd} = 2.25\,\eta_1\,\eta_2\,f_{ctd}$, der $f_{ctd} = \alpha_{ct} f_{ctk,0.05}/\gamma_C$
og $f_{ctk,0.05}$ er avgrensa til verdien for C60/75.

**§8.4.3 (8.3)** $l_{b,rqd} = \dfrac{\phi}{4}\cdot\dfrac{\sigma_{sd}}{f_{bd}}$

**§8.4.4 (8.4)** $l_{bd} = \alpha_1\alpha_2\alpha_3\alpha_4\alpha_5\,l_{b,rqd} \geq l_{b,min}$, med $\alpha_2\alpha_3\alpha_5 \geq 0.7$ (8.5)

- (8.6) strekk: $l_{b,min} = \max(0.3\,l_{b,rqd};\ 10\phi;\ 100\text{ mm})$
- (8.7) trykk: $l_{b,min} = \max(0.6\,l_{b,rqd};\ 10\phi;\ 100\text{ mm})$

**§8.7.3 (8.10)** $l_0 = \alpha_1\alpha_2\alpha_3\alpha_5\alpha_6\,l_{b,rqd} \geq l_{0,min}$

**§8.7.3 (8.11)** $l_{0,min} = \max(0.3\,\alpha_6\,l_{b,rqd};\ 15\phi;\ 200\text{ mm})$

**Tabell 8.2 (strekk)**
- $\alpha_1$: rett = 1.0; ikkje rett = 0.7 dersom $c_d > 3\phi$, elles 1.0
- $\alpha_2$: rett $1-0.15(c_d-\phi)/\phi$; ikkje rett $1-0.15(c_d-3\phi)/\phi$; $0.7 \le \alpha_2 \le 1.0$
- $\alpha_3 = 1 - K\lambda$, $\lambda = (\Sigma A_{st} - \Sigma A_{st,min})/A_s$; $0.7 \le \alpha_3 \le 1.0$
  - forankring: $\Sigma A_{st,min}$ = 0.25 $A_s$ (bjelkar) / 0 (plater)
  - omfaring §8.7.3(1): $\Sigma A_{st,min} = A_s\,\sigma_{sd}/f_{yd}$
- $\alpha_4$ = 0.7 ved sveist tverrarmering
- $\alpha_5 = 1-0.04p$; $0.7 \le \alpha_5 \le 1.0$
- $\alpha_6 = (\rho_1/25)^{0.5}$; $1.0 \le \alpha_6 \le 1.5$

**Tabell 8.2 (trykk):** $\alpha_1 = \alpha_2 = \alpha_3 = 1.0$, $\alpha_4 = 0.7$, $\alpha_5$ ikkje aktuell.

**Figur 8.3:** a) $c_d = \min(a/2;\ c_1;\ c)$ · b) $c_d = \min(a/2;\ c_1)$ · c) $c_d = c$,
der *a* er **fri** avstand mellom stengene.

**§8.9 Buntar:** $\phi_n = \phi\sqrt{n_b} \le 55$ mm. $n_b \le 4$ for vertikale stenger i trykk og i
omfaringsskøyt, elles $n_b \le 3$.
""")

    col_inp2, col_plot2 = st.columns([1, 2.5])

    with col_inp2:
        st.subheader("Inndata")
        fck = st.selectbox(f"Betongfasthet {FCK} [MPa]", mat.FCK_LISTE,
                           index=mat.FCK_LISTE.index(45), key="omfar_fck")
        fck_h = min(fck, mat.FCK_MAKS_HEFT)
        st.caption(f"{FCTM} = {mat.hent_fctm(fck_h):.1f} MPa (Tabell 3.1"
                   + (f", avgrensa til C60/75 jf. §8.4.2(2))" if fck > mat.FCK_MAKS_HEFT else ")"))
        if fck > mat.FCK_MAKS_HEFT:
            st.warning(f"§8.4.2(2): {FCTK} er avgrensa til verdien for C60/75 på grunn av "
                       "auka sprøheit i høgfast betong, med mindre auka heftfasthet kan påvisast.")

        eta_01 = st.selectbox(
            f"Heftforhold {ETA1}", [1.0, 0.7],
            format_func=lambda x: "Gode (η₁ = 1.0)" if x == 1.0 else "Dårlege (η₁ = 0.7)",
            help="§8.4.2(2) og figur 8.2.",
        )
        n = st.number_input("Antal stenger i bunt $n$", min_value=1, max_value=4, value=1, step=1)
        forskyvd = False
        if n > 1 and not trykk:
            forskyvd = st.checkbox(
                f"Enkeltstenger i bunten forankra forskyvd ≥ 1.3·{LBRQD}",
                help=f"§8.9.2(2): då kan stangdiameteren $\\phi$ brukast for {LBD}. Elles {PHIN}.",
            )

        s = st.number_input("Senteravstand mellom stenger $s$ [mm]", min_value=10,
                            max_value=1000, value=150, step=5)
        a_vis = {p: ec2_omfar.fri_avstand(s, p, n) for p in ec2_omfar.PHI_LIST}
        st.text_input("Fri avstand $a = s - " + ("\\phi" if n == 1 else "2\\phi") + "$ [mm]",
                      value="  |  ".join(f"ø{p}: {a_vis[p]:.0f}" for p in ec2_omfar.PHI_LIST),
                      disabled=True)
        cc1, cc2 = st.columns(2)
        c = cc1.number_input("Overdekning $c$ [mm]", min_value=5, max_value=200, value=65, step=5,
                             help="Overdekning vinkelrett på flata stanga ligg mot (figur 8.3).")
        c1 = cc2.number_input(f"Sideoverdekning {C1} [mm]", min_value=5, max_value=500, value=65,
                              step=5, help="Overdekning til sideflata (figur 8.3).")

        type_kobling = st.selectbox(
            "Koblingstype (figur 8.3)", ["a", "b", "c"],
            format_func=lambda x: f"{x} – {ec2_omfar.TYPE_TEKST[x]}",
        )
        with st.expander("🖼️ Skisse av $c$, $c_1$ og $a$ (figur 8.3)", expanded=True):
            phi_fig = st.selectbox(r"Vis for $\phi$ [mm]", ec2_omfar.PHI_LIST, index=2, key="fig_phi")
            a_fig = ec2_omfar.fri_avstand(s, phi_fig, int(n))
            cd_fig = ec2_omfar.get_cd(type_kobling, a_fig, c, c1)
            f_cd = ec2_figur.figur_cd(type_kobling, c, c1, s, phi_fig, a_fig, cd_fig)
            st.pyplot(f_cd)
            plt.close(f_cd)

        if not trykk:
            konstruksjon = st.selectbox(
                f"Konstruksjonsdel ({ASTMIN} for forankring)", ["Bjelke", "Plate"],
                help=f"Tabell 8.2: {ASTMIN} = 0.25·{AS} for bjelkar og 0 for plater. "
                     f"For omfaring vert {ASTMIN} = {AS}·{SIGSD}/{FYD} brukt, jf. §8.7.3(1).",
            )
            sum_ast = st.number_input(
                f"Tverrarmering langs {LBD}/{L0}, {AST} [mm²]", min_value=0.0, max_value=10000.0,
                value=0.0, step=50.0,
                help="Tverrsnittsareal av tverrarmering (ikkje sveist) langs lengda. "
                     f"0 gir {A3} = 1.0 (konservativt).",
            )
            stangplassering = st.selectbox(
                "Plassering av stang (K, figur 8.4)", list(ec2_omfar.K_MAP.keys()), index=1,
                help="Utanfor tverrarm.: K = 0 · Innanfor: K = 0.05 · I bøyen: K = 0.1",
            )
            rho = st.number_input("Trykk i tverretning $p$ [MPa]", min_value=0.0, max_value=100.0,
                                  value=0.0, step=1.0, help=f"{A5} = 1 − 0.04p, 0.7 ≤ {A5} ≤ 1.0")
        else:
            konstruksjon, sum_ast, stangplassering, rho = "Bjelke", 0.0, "Utanfor", 0.0

        rho_1 = st.number_input(f"Prosentdel omfarte stenger {RHO1} [%]", min_value=0.0,
                                max_value=100.0, value=50.0, step=5.0,
                                help=f"{A6} = ({RHO1}/25)^0.5, 1.0 ≤ {A6} ≤ 1.5 (Tabell 8.3)")
        sveist = st.checkbox(f"Sveist tverrarmering ({A4} = 0.7)", value=False,
                             help="Tabell 8.2 og §8.6. Gjeld berre forankring.")
        sigma_s_max = st.number_input(
            f"Maks. armeringsspenning i plott {SIGSMAX} [MPa]", min_value=100, max_value=600,
            value=500, step=25,
            help=f"Vert brukt for å vurdere ulykkessituasjon (ALS). Merk at {SIGSD} ikkje kan "
                 f"overstige {FYD} for valt situasjon.",
        )
        st.divider()
        st.markdown("**Eige punkt å markere i plottet**")
        _punktliste("omfar_custom", ec2_omfar.PHI_LIST, sigma_s_max)

    felles = dict(
        fck=fck, gamma_c=gamma_c, gamma_s=gamma_s, trykk=trykk, eta_01=eta_01, n=int(n),
        s=s, c=c, c1=c1, type_kobling=type_kobling, sum_ast=sum_ast,
        konstruksjon=konstruksjon, stangplassering=stangplassering, rho=rho, rho_1=rho_1,
        sveist_tverrarmering=sveist, forskyvd_forankring=forskyvd,
    )

    with col_plot2:
        kurvar = ec2_omfar.berekn_kurvar(sigma_s_max=int(sigma_s_max), **felles)
        sig_arr = kurvar["sigma_sd"]
        type_tekst = ec2_omfar.get_type_kobling_tekst(type_kobling)
        param_text = (
            f"{tilstand}, {situasjon}  |  {FCK} = {fck} MPa, {ETA1} = {eta_01}, n = {n}, s = {s} mm, "
            f"c = {c} mm, {C1} = {c1} mm, {type_tekst}, {RHO1} = {rho_1:.0f} %"
        )

        fig2, (ax_l0, ax_lbd) = plt.subplots(1, 2, figsize=(14, 6))
        colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        for idx, phi in enumerate(ec2_omfar.PHI_LIST):
            clr = colors[idx % len(colors)]
            ax_l0.plot(sig_arr, kurvar["l0"][phi], label=f"{L0}, ø{phi}", color=clr)
            ax_lbd.plot(sig_arr, kurvar["lbd"][phi], label=f"{LBD}, ø{phi}", color=clr)

        for phi_c, sig_c in st.session_state.get("omfar_custom", []):
            l0_c, lbd_c = ec2_omfar.beregn_omfarOgForankring(phi=phi_c, sigma_sd=sig_c, **felles)
            for ax_, v, t in ((ax_l0, l0_c, "omf."), (ax_lbd, lbd_c, "forankr.")):
                if v is None:
                    continue
                ax_.scatter([sig_c], [v], color="red", s=100, marker="*", zorder=10,
                            label=f"ø{phi_c}, {sig_c:.0f} MPa ({t})")
                ax_.annotate(f"{v:.0f}", (sig_c, v), textcoords="offset points",
                             xytext=(0, 10), ha="center", fontsize=10, color="red")

        l0_tittel = f"Naudsynt omfaringslengde {L0} (avrunda opp til 100 mm)"
        if n > 1:
            l0_tittel += "\nbunt: sjå §8.9.3 for diameter og forskyving"
        for ax_, title in ((ax_l0, l0_tittel), (ax_lbd, f"Naudsynt forankringslengde {LBD}")):
            ax_.axvline(fyd, color="grey", ls="--", lw=1)
            ax_.text(fyd, 0.98, f" {FYD} = {fyd:.0f}", transform=ax_.get_xaxis_transform(),
                     va="top", fontsize=8, color="grey")
            ax_.set_xlabel(f"Armeringsspenning {SIGSD} [MPa]")
            ax_.set_ylabel("Lengde [mm]")
            ax_.set_title(title, fontsize=11)
            ax_.set_xlim(0, sigma_s_max)
            ax_.set_ylim(bottom=0)
            ax_.legend(loc="upper left", fontsize=8)
            ax_.grid(True, alpha=0.4)
        fig2.suptitle(param_text, fontsize=10, y=1.01)
        fig2.tight_layout()
        st.pyplot(fig2)

        if sigma_s_max > fyd:
            st.caption(f"Kurvene over {FYD} = {fyd:.0f} MPa (stipla line) er berre informative for "
                       f"valt situasjon. For ALS: vel «ALS – Ulykkessituasjon» øvst ({FYD} = 500 MPa, {GC} = 1.20).")


        d_fig = ec2_omfar.beregn_detaljar(phi=phi_fig, sigma_sd=fyd, **felles)
        merk = []
        for p in ec2_omfar.PHI_LIST:
            for m in ec2_omfar.beregn_detaljar(phi=p, sigma_sd=fyd, **felles)["merknader"]:
                merk.append(f"ø{p}: {mat.til_latex(m)}")
        if merk:
            st.warning("**Merknader**  \n" + "  \n".join(f"• {m}" for m in merk))
        if n > 1:
            phi_n_fig = d_fig["phi_n"]
            if d_fig["omfar_forskyving"]:
                st.info(
                    f"**Omfaring av bunt (§8.9.3(3))** – ø{phi_fig}, n = {n}, {PHIN} = {phi_n_fig:.1f} mm:  \n"
                    f"Enkeltstengene skal forskyvast minst 1.3·{L0}, der {L0} er rekna for éi stang "
                    f"($\\phi$ = {phi_fig} mm). Ein ekstra (fjerde) omfaringsstang vert brukt, jf. figur 8.13. "
                    f"Maks fire stenger i eitt snitt.  \n"
                    f"{L0} (éi stang) = {d_fig['l0_rund']} mm → forskyving ≥ 1.3·{L0} = "
                    f"{d_fig['forskyving']:.0f} mm, total skøytsone ≈ {n + 1}·1.3·{L0} = "
                    f"{(n + 1) * d_fig['forskyving']:.0f} mm."
                )
            elif n == 2 and d_fig["omfar"] is not None:
                st.info(f"**Omfaring av bunt (§8.9.3(2))** – n = 2 og {PHIN} = {phi_n_fig:.1f} mm < 32 mm: "
                        f"stengene kan skøytast utan forskyving, {L0} vert rekna med {PHIN}.")


        rapport2 = ec2_rapport.lag_rapport_omfar(
            felles, situasjon, tilstand, int(sigma_s_max), fig2, kurvar,
            custom_points=st.session_state.get("omfar_custom", []),
        )
        png2, pdf2 = _fig_to_bytes(fig2, "png"), _fig_to_bytes(fig2, "pdf")
        plt.close(fig2)

        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇️ Plott som PNG (300 dpi)", png2, "omfaring_forankring_EC2.png", "image/png")
        d2.download_button("⬇️ Plott som PDF", pdf2, "omfaring_forankring_EC2.pdf", "application/pdf")
        d3.download_button("📄 Berekningstillegg (PDF)", rapport2,
                           "berekningstillegg_omfaring_forankring.pdf", "application/pdf")
