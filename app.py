"""
app.py  –  EC2 Armering Verktøy
Streamlit-applikasjon for bøyediameter, omfarings- og forankringslengder
per NS-EN 1992-1-1 (Eurokode 2).

Køyr med:  streamlit run app.py
"""

import io
import math
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import streamlit as st

import ec2_boye
import ec2_omfar
import ec2_rapport

matplotlib.use("Agg")  # headless backend for Streamlit

# ──────────────────────────────────────────────────────────
# Sideoppsett
# ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EC2 Armering Verktøy",
    page_icon="🔩",
    layout="wide",
)

st.title("EC2 Armering Verktøy")
st.caption("NS-EN 1992-1-1 (Eurokode 2) – bøyediameter, omfaring og forankring")

tab1, tab2 = st.tabs(["🔄 Bøyediameter", "📏 Omfaring og forankring"])


# ══════════════════════════════════════════════════════════
# Hjelpe-funksjonar
# ══════════════════════════════════════════════════════════

def _fig_to_png_bytes(fig, dpi: int = 300) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    return buf.read()


def _fig_to_pdf_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="pdf", bbox_inches="tight")
    buf.seek(0)
    return buf.read()


# ══════════════════════════════════════════════════════════
# TAB 1 – Bøyediameter
# ══════════════════════════════════════════════════════════

with tab1:
    st.header("Bøyediameter – formel (8.1)")

    # ── Formelreferanse ────────────────────────────────────
    with st.expander("📐 Formelreferansar – NS-EN 1992-1-1"):
        st.markdown(r"""
**§ 8.3(3) Formel (8.1)**

$$
F_{bt} \left(\frac{1}{a_b} + \frac{1}{2\phi}\right) \leq f_{cd}
$$

der den naudsynte bøyediameteren vert

$$
\phi_{m} = \frac{F_{bt}}{f_{cd}} \left(\frac{1}{a_b} + \frac{1}{2\phi}\right)^{-1}
\quad \text{[mm]}
$$

| Symbol | Forklaring |
|--------|-----------|
| $F_{bt}$ | Strekkkraft i stangen ved bøyepunktet: $F_{bt} = \pi(\phi/2)^2 \cdot \sigma$ [N] |
| $a_b$ | Halve senteravstanden mellom stengene (eller kantavstand) [mm] |
| $\phi$ | Stangdiameter [mm] |
| $f_{cd}$ | Dimensjonerande trykkfasthet betong [MPa] |

**Minstediameter** – Tabell NA.8.1N.c) i NS-EN 1992-1-1:

| Stangdiameter φ (mm) | 12 | 16 | 20 | 25 | 32 |
|---|---|---|---|---|---|
| φ_m,min (mm) | 32 | 50 | 80 | 125 | 160 |
""")

    # ── Inndata ────────────────────────────────────────────
    col_inp, col_plot = st.columns([1, 2.5])

    with col_inp:
        st.subheader("Inndata")

        fcd = st.number_input(
            "Dimensjonerande trykkfasthet fcd [MPa]",
            min_value=1.0, max_value=100.0, value=25.5, step=0.5,
            help="Døme: C30/37 → fcd = 25.5 MPa,  C35/45 → fcd = 29.75 MPa",
        )

        st.divider()
        st.markdown("**Eige punkt å markere i plottet**")

        phi_options = [12, 16, 20, 25, 32]
        col_a, col_b = st.columns(2)
        with col_a:
            custom_phi = st.selectbox("Stangdiameter φ [mm]", phi_options, key="boye_phi")
        with col_b:
            custom_sig = st.number_input(
                "Spenning σ [MPa]", min_value=0.0, max_value=435.0,
                value=200.0, step=5.0, key="boye_sig",
            )

        if st.button("Legg til punkt", key="boye_add"):
            if "boye_custom" not in st.session_state:
                st.session_state["boye_custom"] = []
            st.session_state["boye_custom"].append((custom_phi, float(custom_sig)))

        # Vis og fjern eigendefinerte punkt
        if "boye_custom" not in st.session_state:
            st.session_state["boye_custom"] = []

        if st.session_state["boye_custom"]:
            st.markdown("**Lagde punkt:**")
            to_remove = []
            for i, (p, s) in enumerate(st.session_state["boye_custom"]):
                ccol1, ccol2 = st.columns([3, 1])
                ccol1.write(f"φ{p} mm,  {s:.0f} MPa")
                if ccol2.button("✕", key=f"boye_rm_{i}"):
                    to_remove.append(i)
            for i in reversed(to_remove):
                st.session_state["boye_custom"].pop(i)
            if st.button("Nullstill alle punkt", key="boye_clear"):
                st.session_state["boye_custom"] = []

    # ── Plot ───────────────────────────────────────────────
    with col_plot:
        data = ec2_boye.berekn_kurvar(fcd)
        sigma = data["sigma"]
        d_bend_masked = data["d_bend_masked"]
        min_bend = data["min_bend"]

        fig, ax = plt.subplots(figsize=(10, 6))

        colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        for idx, phi in enumerate(ec2_boye.PHI_LIST):
            dm = d_bend_masked[phi]
            ax.plot(sigma, dm, label=f"ø{phi} mm", color=colors[idx % len(colors)])

            # Snap-punkt kvar 25 MPa
            snap_sig = np.arange(0, 436, 25)
            snap_Fbt = np.pi * (phi / 2) ** 2 * snap_sig
            snap_db = snap_Fbt * (1 / ec2_boye.AB_LIST[idx] + 1 / (2 * phi)) / fcd
            snap_dm = np.where(snap_db >= min_bend[phi], snap_db, np.nan)
            valid_snaps = np.where(~np.isnan(snap_dm))[0]
            if valid_snaps.size > 1:
                pidx = valid_snaps[1:]
                ax.scatter(snap_sig[pidx], snap_dm[pidx], s=30, marker="o",
                           color=colors[idx % len(colors)])
                for x, y in zip(snap_sig[pidx], snap_dm[pidx]):
                    ax.annotate(f"{y:.0f}", (x, y), textcoords="offset points",
                                xytext=(0, 5), ha="center", fontsize=7)

            # Første og siste gyldige punkt
            valid_idx = np.where(~np.isnan(dm))[0]
            if valid_idx.size > 0:
                for end_i in [valid_idx[0], valid_idx[-1]]:
                    ax.scatter(sigma[end_i], dm[end_i], s=40, color="black", zorder=5)
                    ax.annotate(f"{dm[end_i]:.0f}", (sigma[end_i], dm[end_i]),
                                textcoords="offset points", xytext=(0, 9),
                                ha="center", fontsize=8)

        # Eigendefinerte punkt
        for phi_c, sig_c in st.session_state.get("boye_custom", []):
            d, min_b = ec2_boye.berekn_boeyediameter(phi_c, sig_c, fcd)
            if d >= min_b:
                ax.scatter([sig_c], [d], color="red", s=100, marker="*",
                           zorder=10, label=f"ø{phi_c}, {sig_c:.0f} MPa")
                ax.annotate(f"{d:.0f}", (sig_c, d), textcoords="offset points",
                            xytext=(0, 10), ha="center", fontsize=10, color="red")
            else:
                st.warning(
                    f"φ{phi_c}, {sig_c:.0f} MPa: berekna bøyediameter {d:.1f} mm "
                    f"er under minstediameter φm,min = {min_b:.0f} mm – vert ikkje plotta."
                )

        ax.set_title(
            f"Naudsynt bøyediameter per NS-EN 1992-1-1 formel (8.1)\n"
            f"fcd = {fcd} MPa",
            fontsize=12,
        )
        ax.set_xlabel("Strekkspenning σ [MPa]")
        ax.set_ylabel("Naudsynt bøyediameter [mm]")
        ax.set_ylim(0, 400)
        ax.set_xlim(0, 435)
        ax.legend(loc="upper left", fontsize=9)
        ax.grid(True, alpha=0.4)
        fig.tight_layout()

        st.pyplot(fig)

        png_bytes      = _fig_to_png_bytes(fig, dpi=300)
        pdf_plot_bytes = _fig_to_pdf_bytes(fig)
        rapport_bytes  = ec2_rapport.lag_rapport_boye(
            fcd, fig,
            custom_points=st.session_state.get("boye_custom", []),
        )
        plt.close(fig)

        dl1, dl2, dl3 = st.columns(3)
        dl1.download_button(
            "⬇️ Plott som PNG (300 dpi)",
            png_bytes,
            file_name="boeyediameter_EC2.png",
            mime="image/png",
        )
        dl2.download_button(
            "⬇️ Plott som PDF",
            pdf_plot_bytes,
            file_name="boeyediameter_EC2.pdf",
            mime="application/pdf",
        )
        dl3.download_button(
            "📄 Berekningstillegg (PDF)",
            rapport_bytes,
            file_name="berekningstillegg_boeyediameter.pdf",
            mime="application/pdf",
        )


# ══════════════════════════════════════════════════════════
# TAB 2 – Omfaring og forankring
# ══════════════════════════════════════════════════════════

with tab2:
    st.header("Omfaring og forankring – §8.4 og §8.7")

    # ── Formelreferanse ────────────────────────────────────
    with st.expander("📐 Formelreferansar – NS-EN 1992-1-1"):
        st.markdown(r"""
**§ 8.4.2 Formel (8.2)** – Dimensjonerande heftfasthet

$$
f_{bd} = 2{,}25 \cdot \eta_1 \cdot \eta_2 \cdot f_{ctd}
$$

**§ 8.4.3 Formel (8.3)** – Grunnleggjande forankringslengde

$$
l_{b,rqd} = \frac{\phi_n}{4} \cdot \frac{\sigma_{sd}}{f_{bd}}
$$

**§ 8.4.4 Formel (8.4)** – Dimensjonerande forankringslengde

$$
l_{bd} = \alpha_1 \cdot \alpha_2 \cdot \alpha_3 \cdot \alpha_4 \cdot \alpha_5 \cdot l_{b,rqd} \geq l_{b,min}
$$

**§ 8.7.3 Formel (8.10)** – Omfaringslengde

$$
l_0 = \alpha_1 \cdot \alpha_2 \cdot \alpha_3 \cdot \alpha_5 \cdot \alpha_6 \cdot l_{b,rqd} \geq l_{0,min}
$$

**§ 8.7.3 Formel (8.11)** – Minste omfaringslengde

$$
l_{0,min} = \max\!\left(0{,}3 \cdot \alpha_6 \cdot l_{b,rqd};\; 15\phi_n;\; 200\text{ mm}\right)
$$

| Symbol | Forklaring |
|--------|-----------|
| $\eta_1$ | Heftforhold: 1,0 (gode) / 0,7 (dårlege) |
| $\eta_2$ | Stangfaktor: 1,0 viss φ ≤ 32 mm, elles (132−φ)/100 |
| $f_{ctd}$ | Dimensjonerande strekkfasthet: $0{,}85 \cdot 0{,}7 \cdot f_{ctm} / 1{,}5$ |
| $\phi_n$ | Ekvivalent diameter for bunt: $\phi\sqrt{n}$ |
| $\alpha_{1..6}$ | Reduksjonskoeffisientar, sjå Tabell 8.2 |
| $\alpha_6$ | Funksjon av prosentdel omfarte stenger $\rho_1$ |
""")

    # ── Inndata ────────────────────────────────────────────
    col_inp2, col_plot2 = st.columns([1, 2.5])

    with col_inp2:
        st.subheader("Inndata")

        fck_options = [12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90]
        fck = st.selectbox(
            "Karakteristisk trykkfasthet fck [MPa]",
            fck_options, index=fck_options.index(45),
            help="Betongklasse per Tabell 3.1 NS-EN 1992-1-1",
        )
        fctm_val = ec2_omfar.hent_fctm(fck)
        st.caption(f"fctm = {fctm_val:.1f} MPa  (Tabell 3.1)")

        eta_01 = st.selectbox(
            "Heftforhold η₁",
            options=[1.0, 0.7],
            format_func=lambda x: "Gode tilhøve (η₁ = 1,0)" if x == 1.0 else "Dårlege tilhøve (η₁ = 0,7)",
            help="§8.4.2(2): gode tilhøve = botnarmering, øvre armering i h < 300 mm, skråarmering > 45°",
        )

        n = st.number_input("Antal stenger i bunt n", min_value=1, max_value=4, value=1, step=1)
        c = st.number_input("Overdekning c [mm]", min_value=5, max_value=200, value=65, step=5)
        a = st.number_input("Senteravstand mellom stenger a [mm]", min_value=10, max_value=500, value=85, step=5)

        type_kobling = st.selectbox(
            "Koblingstype (figur 8.3)",
            options=["a", "b", "c"],
            format_func=lambda x: {
                "a": "a – Rette stenger",
                "b": "b – Vinkelkroker eller kroker",
                "c": "c – Sløyfer",
            }[x],
        )

        stangplassering = st.selectbox(
            "Plassering av stang (K-faktor)",
            options=["Utenfor", "Innenfor", "I bøy"],
            index=1,
            help="Utenfor: K=0  |  Innenfor: K=0,05  |  I bøy: K=0,1",
        )

        rho = st.number_input(
            "Trykkspenning i tverretning ρ [MPa]",
            min_value=0.0, max_value=100.0, value=0.0, step=1.0,
            help="α₅ = max(0,7; min(1,0; 1 − 0,04·ρ))",
        )

        rho_1 = st.number_input(
            "Prosentdel omfarte stenger ρ₁ [%]",
            min_value=0.0, max_value=100.0, value=50.0, step=5.0,
            help="α₆ = max(1,0; min(1,5; (ρ₁/25)^0,5))",
        )

        sveist_tverrarmering = st.checkbox(
            "Sveist tverrarmering (α₄ = 0,7)", value=False,
            help="Kryssar NS-EN 1992-1-1 §8.4.4(2)",
        )

        sigma_s_max = st.number_input(
            "Maks. armeringsspenning σ_s,max [MPa]",
            min_value=100, max_value=600, value=500, step=25,
        )

        st.divider()
        st.markdown("**Eige punkt å markere i plottet**")

        col_c, col_d = st.columns(2)
        with col_c:
            custom_phi2 = st.selectbox("Stangdiameter φ [mm]", [12, 16, 20, 25, 32], key="omfar_phi")
        with col_d:
            custom_sig2 = st.number_input(
                "Spenning σsd [MPa]", min_value=0.0, max_value=float(sigma_s_max),
                value=min(200.0, float(sigma_s_max)), step=5.0, key="omfar_sig",
            )

        if st.button("Legg til punkt", key="omfar_add"):
            if "omfar_custom" not in st.session_state:
                st.session_state["omfar_custom"] = []
            st.session_state["omfar_custom"].append((custom_phi2, float(custom_sig2)))

        if "omfar_custom" not in st.session_state:
            st.session_state["omfar_custom"] = []

        if st.session_state["omfar_custom"]:
            st.markdown("**Lagde punkt:**")
            to_remove2 = []
            for i, (p, s) in enumerate(st.session_state["omfar_custom"]):
                ccol1, ccol2 = st.columns([3, 1])
                ccol1.write(f"φ{p} mm,  {s:.0f} MPa")
                if ccol2.button("✕", key=f"omfar_rm_{i}"):
                    to_remove2.append(i)
            for i in reversed(to_remove2):
                st.session_state["omfar_custom"].pop(i)
            if st.button("Nullstill alle punkt", key="omfar_clear"):
                st.session_state["omfar_custom"] = []

    # ── Plot ───────────────────────────────────────────────
    with col_plot2:
        kurvar = ec2_omfar.berekn_kurvar(
            fck=fck, eta_01=eta_01, n=n, c=c, a=a,
            type_kobling=type_kobling, sum_ast=0,
            stangplassering=stangplassering, rho=rho,
            rho_1=rho_1, sveist_tverrarmering=sveist_tverrarmering,
            sigma_s_max=sigma_s_max,
        )
        sigma_sd_arr = kurvar["sigma_sd"]
        l0_kurvar    = kurvar["l0"]
        lbd_kurvar   = kurvar["lbd"]

        type_tekst = ec2_omfar.get_type_kobling_tekst(type_kobling)
        param_text = (
            rf"$f_{{ck}}$={fck} MPa,  $\eta_1$={eta_01},  n={n},  "
            rf"c={c} mm,  a={a} mm,  {type_tekst},  "
            rf"Stangplassering: {stangplassering},  $\rho_1$={rho_1:.0f}%"
        )

        fig2, (ax_l0, ax_lbd) = plt.subplots(1, 2, figsize=(14, 6))
        colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

        for idx, phi in enumerate(ec2_omfar.PHI_LIST):
            clr = colors[idx % len(colors)]
            ax_l0.plot(sigma_sd_arr, l0_kurvar[phi],  label=rf"$l_{{0,ø{phi}}}$",  color=clr)
            ax_lbd.plot(sigma_sd_arr, lbd_kurvar[phi], label=rf"$l_{{bd,ø{phi}}}$", color=clr)

        # Eigendefinerte punkt
        for phi_c, sig_c in st.session_state.get("omfar_custom", []):
            l0_c, lbd_c = ec2_omfar.beregn_omfarOgForankring(
                fck, eta_01, phi_c, n, sig_c, c, a,
                type_kobling, 0, stangplassering, rho, rho_1, sveist_tverrarmering,
            )
            lbl_l0  = f"ø{phi_c}, {sig_c:.0f} MPa (omf.)"
            lbl_lbd = f"ø{phi_c}, {sig_c:.0f} MPa (forankr.)"
            ax_l0.scatter([sig_c], [l0_c],   color="red", s=100, marker="*", zorder=10, label=lbl_l0)
            ax_l0.annotate(f"{l0_c:.0f}",  (sig_c, l0_c),  textcoords="offset points",
                           xytext=(0, 10), ha="center", fontsize=10, color="red")
            ax_lbd.scatter([sig_c], [lbd_c], color="red", s=100, marker="*", zorder=10, label=lbl_lbd)
            ax_lbd.annotate(f"{lbd_c:.0f}", (sig_c, lbd_c), textcoords="offset points",
                            xytext=(0, 10), ha="center", fontsize=10, color="red")

        for ax, title in [
            (ax_l0,  r"Naudsynt omfaringslengde $l_0$"),
            (ax_lbd, r"Naudsynt forankringslengde $l_{bd}$"),
        ]:
            ax.set_xlabel(r"Armeringsspenning $\sigma_{sd}$ [MPa]")
            ax.set_ylabel("Lengde [mm]")
            ax.set_title(title)
            ax.set_xlim(0, sigma_s_max)
            ax.set_ylim(bottom=0)
            ax.legend(loc="upper left", fontsize=9)
            ax.grid(True, alpha=0.4)

        fig2.suptitle(param_text, fontsize=11, y=1.01)
        fig2.tight_layout()

        st.pyplot(fig2)

        png_bytes2      = _fig_to_png_bytes(fig2, dpi=300)
        pdf_plot_bytes2 = _fig_to_pdf_bytes(fig2)
        rapport_bytes2  = ec2_rapport.lag_rapport_omfar(
            fck, eta_01, n, c, a, type_kobling,
            stangplassering, rho, rho_1, sveist_tverrarmering, sigma_s_max,
            fig2,
            custom_points=st.session_state.get("omfar_custom", []),
        )
        plt.close(fig2)

        dl1, dl2, dl3 = st.columns(3)
        dl1.download_button(
            "⬇️ Plott som PNG (300 dpi)",
            png_bytes2,
            file_name="omfaring_forankring_EC2.png",
            mime="image/png",
        )
        dl2.download_button(
            "⬇️ Plott som PDF",
            pdf_plot_bytes2,
            file_name="omfaring_forankring_EC2.pdf",
            mime="application/pdf",
        )
        dl3.download_button(
            "📄 Berekningstillegg (PDF)",
            rapport_bytes2,
            file_name="berekningstillegg_omfaring_forankring.pdf",
            mime="application/pdf",
        )
