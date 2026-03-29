# Forankring og omfaringslengde for enkle stenger og buntar
import math
import matplotlib.pyplot as plt
import sys
import tkinter as tk
from tkinter import simpledialog, messagebox

def hent_fctm(fck):
    # Verdier fra tabell 3.1 EN 1992-1-1
    tabell = {
        12: 1.6,
        16: 1.9,
        20: 2.2,
        25: 2.6,
        30: 2.9,
        35: 3.2,
        40: 3.5,
        45: 3.8,
        50: 4.1,
        55: 4.2,
        60: 4.4,
        70: 4.6,
        80: 4.8,
        90: 5.0
    }
    # Returner nærmeste verdi hvis fck ikke finnes direkte
    if fck in tabell:
        return tabell[fck]
    else:
        # Finn nærmeste fck-verdi
        nærmest = min(tabell.keys(), key=lambda x: abs(x - fck))
        return tabell[nærmest]

def get_type_kobling_description(type_kobling):
    if type_kobling == "a":
        return "Rette stenger"
    elif type_kobling == "b":
        return "Vinkelkroker eller kroker"
    elif type_kobling == "c":
        return "Sløyfer"
    else:
        raise ValueError("Ugyldig type_kobling. Velg mellom 'a', 'b', eller 'c'.")

def get_cd(type_kobling, a, c):
    # Bestemmer cd basert på type_kobling
    if type_kobling == "a": 
        cd = min(a/2,c)
    elif type_kobling == "b":
        cd = min(a/2,c)
    elif type_kobling == "c":
        cd = c  
    return cd
def get_alpha_1(type_kobling, cd, øn):
    # Velg alpha_1 basert på type_kobling
    if type_kobling == "a":
        alpha_1 = 1.0
    elif type_kobling == "b":
        if cd > 3*øn:
            alpha_1 = 0.7
        else:
            alpha_1 = 1
    elif type_kobling == "c":
        if cd > 3*øn:
            alpha_1 = 0.7
        else:
            alpha_1 = 1
    else:
        raise ValueError("Ugyldig type_kobling. Velg mellom 'Rette stenger == a', 'Vinkelkroker eller kroker == b', eller 'Sløyfer == c'.")
    return alpha_1

def get_alpha_2(type_kobling, cd, øn):
    if type_kobling == "a":
        alpha_2 = 1-0.15*(cd-øn)/øn
        if alpha_2 >= 1:
            alpha_2 = 1.0
        elif alpha_2 <= 0.7:
            alpha_2 = 0.7
        else:
            alpha_2 = alpha_2
    elif type_kobling != "a":
        alpha_2 = 1-0.15*(cd-3*øn)/øn
        if alpha_2 >= 1:
            alpha_2 = 1.0
        elif alpha_2 <= 0.7:
            alpha_2 = 0.7
        else:
            alpha_2 = alpha_2
    return alpha_2

def beregn_omfarOgForankring(fck, eta_01, ø, n, sigma_sd, c, a, type_kobling, sum_ast, stangplassering, rho, rho_1, sveist_tverrarmering):

    # Input parameters
    # fck         = 45            # karakteristisk trykkfasthet betong [MPa]
    # fyk         = 500           # karakteristisk flytespenning armering [MPa]
    # ø           = 20            # diameter of rebar [mm]
    # n           = 1             # number of bars
    # sigma_sd    = 435           # design value of steel stress [MPa]
    # c           = 75            # concrete cover [mm]
    # a           = 150           # distanse mellom armeringsstenger [mm]
    # type_kob    = "Rette stenger"  # type of rebar coupling
    # sigma_ast   = 0             # Sum av faktisk tverrarmering langs forankring-/omfaringslengde [MPa]
    # rho         = 0             # Trykkspenning i tverretning
    # rho_1       = 50            # Prosentandel av stenger som omfares

    fctm        = hent_fctm(fck)                    # middelverdi for karakteristisk strekkfasthet betong [MPa]
    fctk005     = 0.7*fctm                          # nedre karakteristisk verdi for strekkfasthet betong [MPa]
    alpha_ct    = 0.85                              # Koeffisient for langtidslast og ugunstige virkningar
    gamma_c     = 1.5                               # partial safety factor for concrete
    fctd        = alpha_ct * fctk005 / gamma_c      # design value of tensile strength of concrete [MPa]
    eta_02      = 1.0 if ø <= 32 else (132-ø)/100   # Faktor avhengig av stangdiameter
    fbd         = 2.25 * eta_01 * eta_02 * fctd     # bond stress for good bond conditions [MPa]   
    øn          = ø*math.sqrt(n)                    # total diameter of bars [mm]
    As          = (math.pi/4) * øn**2               # totalt armeringsareal i stang/bunt [mm²]
    lbrqd       = (øn/4) * (abs(sigma_sd) / fbd)    # naudsynt forankringslengde [mm]

    # Bestemmer cd (dimensjonerande kantavstand ved brudd) basert på type_kobling
    cd = get_cd(type_kobling, a, c)
    # Velg alpha_1 basert på type_kobling
    alpha_1 = get_alpha_1(type_kobling, cd, øn)
    alpha_2 = get_alpha_2(type_kobling, cd, øn)
        
    sum_ast = 0 # Sum av faktisk tverrarmering langs forankring-/omfaringslengde [MPa]
    sum_astmin = As if øn >= 20 else 0
    # Velg K basert på plassering av stang
    if stangplassering == "Utenfor":
        k = 0
    elif stangplassering == "Innenfor":
        k = 0.05
    elif stangplassering == "I bøy":
        k = 0.1
    else:
        raise ValueError("Ugyldig plassering av stang. Velg mellom 'Utenfor', 'Innenfor' eller 'I bøy'.")

    alpha_3 = min(1,max(0.7,1 - k * (sum_ast - sum_astmin)/As)) # Koeffisient for tverrarmering (ikkje sveist)
    alpha_4 = 0.7                                               # Koeffisient for sveist tverrarmering
    rho     = rho                                               # Trykkspenning i tverretning
    alpha_5 = min(1,max(0.7,1-0.04*rho))                        # Koeffisient for trykkspenning i tverretning
    rho_1   = rho_1                                             # Prosentandel av stenger som omfares
    alpha_6 = min(1.5,max((rho_1/25)**0.5,1.0))                 # Koeffisient for prosentandel av stenger som omfares
    l0min   = max(0.3 * lbrqd * alpha_6, 15*øn, 200)            # minimum bond length [mm]
    l0      = max(lbrqd * alpha_1 * alpha_2 * alpha_3 * alpha_5 * alpha_6, l0min)  # bond length [mm]
    l0n400  = math.ceil(l0/100)*100
    

    lbdmin      = max(0.3 * lbrqd, 10*øn, 100) if sigma_sd > 0 else max(0.6 * lbrqd,10*øn,100)  # minste forankringslengde [mm]
    alpha_235   = max(alpha_2 * alpha_3 * alpha_5, 0.7)
    if sveist_tverrarmering == False:
        lbd         = max(lbrqd * alpha_1 * alpha_235, lbdmin)  # forankringslengde [mm]
    else:
        lbd         = max(lbrqd * alpha_1 * alpha_235 * alpha_4, lbdmin)  # forankringslengde [mm]
    return l0n400, lbd

def plot_omfaring_forankring(sigma_sd, l0_12, l0_16, l0_20, l0_25, l0_32,
                             lbd_12, lbd_16, lbd_20, lbd_25, lbd_32,
                             fck, eta_01, c, a, type_kobling, stangplassering, n, rho_1,
                             custom_values, sigma_s_max):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))

    type_kobling_desc = get_type_kobling_description(type_kobling)
    # Samlende tekst med parametre
    param_text = (
    r"$f_{ck}$=" + f"{fck} MPa, "
    r"$\eta_{1}$=" + f"{eta_01}, n={n}, "
    f"c={c} mm, a={a} mm, {type_kobling_desc}, "
    f"Stangplassering={stangplassering}, "
    r"$\rho_1$=" + f"{rho_1}%"
    )

    # Plot omfaringslengde
    ax1.plot(sigma_sd, l0_12, label=r'$l_{0,ø12}$')
    ax1.plot(sigma_sd, l0_16, label=r'$l_{0,ø16}$')
    ax1.plot(sigma_sd, l0_20, label=r'$l_{0,ø20}$')
    ax1.plot(sigma_sd, l0_25, label=r'$l_{0,ø25}$')
    ax1.plot(sigma_sd, l0_32, label=r'$l_{0,ø32}$')
    ax1.set_xlabel(r'Armeringsspenning ($\sigma_{sd}$) [MPa]')
    ax1.set_ylabel('Lengde [mm]')
    ax1.legend()
    ax1.grid(True)
    ax1.set_title('Nødvendig omfaringslengde, $l_{0}$')
    ax1.set_ylim(bottom=0)
    ax1.set_xlim(left=0,right=sigma_s_max)

    # Plot forankringslengde
    ax2.plot(sigma_sd, lbd_12, label=r'$l_{bd,ø12}$')
    ax2.plot(sigma_sd, lbd_16, label=r'$l_{bd,ø16}$')
    ax2.plot(sigma_sd, lbd_20, label=r'$l_{bd,ø20}$')
    ax2.plot(sigma_sd, lbd_25, label=r'$l_{bd,ø25}$')
    ax2.plot(sigma_sd, lbd_32, label=r'$l_{bd,ø32}$')
    ax2.set_xlabel(r'Armeringsspenning ($\sigma_{sd}$) [MPa]')
    ax2.set_ylabel('Lengde [mm]')
    ax2.legend()
    ax2.grid(True)
    ax2.set_title('Nødvendig forankringslengde, $l_{bd}$')
    ax2.set_ylim(bottom=0)
    ax2.set_xlim(left=0,right=sigma_s_max)

    # Samlet tittel for figuren
    fig.suptitle(param_text, fontsize=14)
    # --- Plot custom values if provided ---
    if custom_values:
        for user_phi, user_sig in custom_values:
            l0_custom, lbd_custom = beregn_omfarOgForankring(
                fck, eta_01, user_phi, n, user_sig, c, a, type_kobling, sum_ast, stangplassering, rho, rho_1, sveist_tverrarmering
            )
            custom_label_l0 = f"ø{user_phi}, {user_sig:.0f}MPa (omf.)"
            custom_label_lbd = f"ø{user_phi}, {user_sig:.0f}MPa (forankr.)"
            ax1.scatter([user_sig], [l0_custom], color='red', s=80, marker='*', zorder=10, label=custom_label_l0)
            ax1.annotate(f"{l0_custom:.0f}", (user_sig, l0_custom), textcoords="offset points", xytext=(0,10), ha='center', fontsize=10, color='red')
            ax2.scatter([user_sig], [lbd_custom], color='red', s=80, marker='*', zorder=10, label=custom_label_lbd)
            ax2.annotate(f"{lbd_custom:.0f}", (user_sig, lbd_custom), textcoords="offset points", xytext=(0,10), ha='center', fontsize=10, color='red')
        ax1.legend()
        ax2.legend()
    plt.tight_layout()
    plt.show()

fck             = 45                    # Karakteristisk trykkfasthet betong [MPa]
eta_01          = 1                     # Gode forhold = 1, Dårlige forhold = 0.7
n               = 1                     # Antal stenger i bunt
c               = 65                    # Overdekning [mm]
type_kobling    = "a"                   # "a", "b", "c", sjå figur 8.3 i Eurokode 2
a               = 85                   # Avstand mellom armeringsstenger [mm]
sum_ast         = 0                     # Sum av faktisk tverrarmering langs forankring-/omfaringslengde [mm2]
stangplassering = "Innenfor"            # "Utenfor", "Innenfor", "I bøy"
rho             = 0                     # Trykkspenning i tverretning
rho_1           = 50                    # Prosentandel av stenger som omfarast
sveist_tverrarmering = False            # Er tverrarmering sveist?
sigma_s_max     = 500                 # maksimal tillatt armeringsspenning

#module_dir = r"D:\OneDrive\OneDrive - Multiconsult\Jobb\Python\Dynamo"  # Update with your actual path
#if module_dir not in sys.path:
#    sys.path.append(module_dir)
#import __python_utils
#ec2_props = __python_utils.ec2_table_3_1(fck)
#fctm = ec2_props["fctm"]

sigma_sd_values = list(range(0, sigma_s_max+1, 1))
l0_values_12, l0_values_16, l0_values_20, l0_values_25, l0_values_32        = [],[],[],[],[]
lbd_values_12, lbd_values_16, lbd_values_20, lbd_values_25, lbd_values_32   = [],[],[],[],[]
for i in sigma_sd_values:
    # For ø = 12 mm, gode forhold
    l0, lbd = beregn_omfarOgForankring(fck,eta_01, 12, n,i, c,a,type_kobling, sum_ast, stangplassering, rho, rho_1, sveist_tverrarmering)
    l0_values_12.append(l0)
    lbd_values_12.append(lbd)
    # For ø = 16 mm, gode forhold
    l0, lbd = beregn_omfarOgForankring(fck,eta_01, 16, n,i, c,a,type_kobling, sum_ast, stangplassering, rho, rho_1, sveist_tverrarmering)
    l0_values_16.append(l0)
    lbd_values_16.append(lbd)
    # For ø = 20 mm, gode forhold
    l0, lbd = beregn_omfarOgForankring(fck,eta_01, 20, n,i, c,a,type_kobling, sum_ast, stangplassering, rho, rho_1, sveist_tverrarmering)
    l0_values_20.append(l0)
    lbd_values_20.append(lbd)
    # For ø = 25 mm, gode forhold
    l0, lbd = beregn_omfarOgForankring(fck,eta_01, 25, n,i, c,a,type_kobling, sum_ast, stangplassering, rho, rho_1, sveist_tverrarmering)
    l0_values_25.append(l0)
    lbd_values_25.append(lbd)
    # For ø = 32 mm, gode forhold
    l0, lbd = beregn_omfarOgForankring(fck,eta_01, 32, n,i, c,a,type_kobling, sum_ast, stangplassering, rho, rho_1, sveist_tverrarmering)
    l0_values_32.append(l0)
    lbd_values_32.append(lbd)

# Interaktiv del for å legge til egne verdiar
custom_values = []

root = tk.Tk()
root.withdraw()

while messagebox.askyesno("Custom Value", "Do you want to plot a custom value?"):
    # Diameter selection
    while True:
        user_phi = simpledialog.askinteger(
            "Diameter",
            "Choose diameter (mm): 12, 16, 20, 25, or 32",
            minvalue=12, maxvalue=32
        )
        if user_phi in [12, 16, 20, 25, 32]:
            break
        elif user_phi is None:
            user_phi = None
            break
        else:
            messagebox.showerror("Invalid input", "Please choose one of: 12, 16, 20, 25, 32.")

    # Tension force selection
    user_sig = None
    if user_phi is not None:
        while True:
            user_sig = simpledialog.askfloat(
                "Tension force",
                "Enter tension force (MPa) between 0 and sigma_s_max:",
                minvalue=0, maxvalue=sigma_s_max
            )
            if user_sig is None:
                break
            if 0 <= user_sig <= sigma_s_max:
                break
            else:
                messagebox.showerror("Invalid input", "Please enter a value between 0 and sigma_s_max.")

    if user_phi is not None and user_sig is not None:
        custom_values.append((user_phi, user_sig))

# Plot "utenfor" for gode forhold
fig = plot_omfaring_forankring(
    sigma_sd_values, l0_values_12, l0_values_16, l0_values_20, l0_values_25, l0_values_32,
    lbd_values_12, lbd_values_16, lbd_values_20, lbd_values_25, lbd_values_32,
    fck, eta_01, c, a, type_kobling, stangplassering, n, rho_1,
    custom_values=custom_values, sigma_s_max=sigma_s_max
)

