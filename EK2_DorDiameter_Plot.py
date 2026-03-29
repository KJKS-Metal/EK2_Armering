import numpy as np
import matplotlib.pyplot as plt
import math
import tkinter as tk
from tkinter import simpledialog, messagebox

# Bar diameters (mm)
phi_list = [12, 16, 20, 25, 32]
# ab values (mm) for each diameter (as given)
ab_list = [100/2, 125/2, 150/2, 175/2, 200/2]
# Design compressive strength of concrete (MPa)
fcd = 25.5
low_lim = [32,50,80,125,160]  # Minimum bend diameters (mm) from table NA.8.1N.c) in EC2-1-1
# Tension stress in concrete (MPa)
sig = np.arange(0, 436, 1)  # 0 to 435 MPa

plt.figure(figsize=(8, 6))

for idx, phi in enumerate(phi_list):
    ab = ab_list[idx]
    min_bend = low_lim[idx]
    Fbt = np.pi * (phi / 2) ** 2 * sig  # mm² * MPa = N
    telj = Fbt * (1/ab + 1/(2*phi))
    nemn = fcd
    d_bend = telj / nemn

    # Apply lower limit: set values below min_bend to np.nan so they are not plotted
    d_bend_masked = np.where(d_bend >= min_bend, d_bend, np.nan)

    # Plot the continuous line
    plt.plot(sig, d_bend_masked, label=f"ø{phi} mm")

    # Plot snappable points every 25 MPa, also applying the lower limit
    snap_sig = np.arange(0, 436, 25)
    snap_Fbt = np.pi * (phi / 2) ** 2 * snap_sig
    snap_d_bend = snap_Fbt * (1/ab + 1/(2*phi)) / nemn
    snap_d_bend_masked = np.where(snap_d_bend >= min_bend, snap_d_bend, np.nan)
    
    # Find the first valid (not NaN) scatter point
    valid_snap_indices = np.where(~np.isnan(snap_d_bend_masked))[0]
    if valid_snap_indices.size > 1:
        # Exclude the first valid point
        plot_indices = valid_snap_indices[1:]
        plt.scatter(snap_sig[plot_indices], snap_d_bend_masked[plot_indices], s=40, marker='o')
        for x, y in zip(snap_sig[plot_indices], snap_d_bend_masked[plot_indices]):
            plt.annotate(f"{y:.0f}", (x, y), textcoords="offset points", xytext=(0,5), ha='center', fontsize=8)


    # --- Add dots and values for the first and last valid points of the line ---
    valid_indices = np.where(~np.isnan(d_bend_masked))[0]
    if valid_indices.size > 0:
        # First valid point
        first_idx = valid_indices[0]
        plt.scatter(sig[first_idx], d_bend_masked[first_idx], s=40, color='black', zorder=5)
        plt.annotate(f"{d_bend_masked[first_idx]:.0f}", (sig[first_idx], d_bend_masked[first_idx]),
                     textcoords="offset points", xytext=(0,10), ha='center', fontsize=9)
        # Last valid point
        last_idx = valid_indices[-1]
        plt.scatter(sig[last_idx], d_bend_masked[last_idx], s=40, color='black', zorder=5)
        plt.annotate(f"{d_bend_masked[last_idx]:.0f}", (sig[last_idx], d_bend_masked[last_idx]),
                     textcoords="offset points", xytext=(0,10), ha='center', fontsize=9)

# --- Tkinter dialog for user input ---
root = tk.Tk()
root.withdraw()

custom_labels = set()  # To avoid duplicate legend entries

while messagebox.askyesno("Custom Value", "Do you want to plot a custom value?"):
    # Diameter selection
    while True:
        user_phi = simpledialog.askinteger(
            "Diameter",
            "Choose diameter (mm): 12, 16, 20, 25, or 32",
            minvalue=12, maxvalue=32
        )
        if user_phi in phi_list:
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
                "Enter tension force (MPa) between 0 and 435:",
                minvalue=0, maxvalue=435
            )
            if user_sig is None:
                break
            if 0 <= user_sig <= 435:
                break
            else:
                messagebox.showerror("Invalid input", "Please enter a value between 0 and 435.")
                

    if user_phi is not None and user_sig is not None:
        idx = phi_list.index(user_phi)
        ab = ab_list[idx]
        min_bend = low_lim[idx]
        Fbt = np.pi * (user_phi / 2) ** 2 * user_sig
        d_bend = Fbt * (1/ab + 1/(2*user_phi)) / fcd
        custom_label = f"ø{user_phi}, {user_sig:.0f}MPa"
        if d_bend >= min_bend:
            # Only add label if not already used
            if custom_label not in custom_labels:
                plt.scatter([user_sig], [d_bend], color='red', s=80, marker='*', zorder=10, label=custom_label)
                custom_labels.add(custom_label)
            else:
                plt.scatter([user_sig], [d_bend], color='red', s=80, marker='*', zorder=10)
            plt.annotate(f"{d_bend:.0f}", (user_sig, d_bend), textcoords="offset points", xytext=(0,10), ha='center', fontsize=10, color='red')
        else:
            messagebox.showinfo("Below minimum", f"Calculated bend diameter {d_bend:.1f} mm is below phim,min={min_bend:.0f} mm and will not be plotted.")

plt.title('Required Bend Diameter (mm) per EC2-1-1 Formula (8.1)')
plt.xlabel('Tension Stress σ [MPa]')
plt.ylabel('Required Bend Diameter [mm]')
plt.ylim(0, 400)
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()