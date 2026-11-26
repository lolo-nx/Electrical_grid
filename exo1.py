"""
Petit cours VeraGrid — tous les exercices dans un seul fichier.
Lancer avec :  python cours.py
Testé avec VeraGridEngine 6.8.6.
"""
import VeraGridEngine.api as gce
import matplotlib.pyplot as plt


# =============================================================================
# Le réseau de base : 3 bus à 20 kV reliés en boucle
# =============================================================================
def construire_reseau():
    grid = gce.MultiCircuit(name="Mon premier réseau")

    # 1) Trois bus à 20 kV (moyenne tension)
    b1 = gce.Bus(name="Poste source", Vnom=20, is_slack=True)
    b2 = gce.Bus(name="Village", Vnom=20)
    b3 = gce.Bus(name="Zone artisanale", Vnom=20)
    for b in (b1, b2, b3):
        grid.add_bus(b)

    # 2) Le réseau amont, qui tient la tension à 1,0 pu au poste source
    grid.add_generator(b1, gce.Generator(name="Réseau amont", vset=1.0))

    # 3) Deux charges : P en MW, Q en Mvar
    grid.add_load(b2, gce.Load(name="Conso village", P=4.0, Q=1.5))
    grid.add_load(b3, gce.Load(name="Conso artisans", P=3.0, Q=1.0))

    # 4) Trois lignes : r et x en pu (base 100 MVA), capacité 10 MVA
    grid.add_line(gce.Line(bus_from=b1, bus_to=b2, name="L1-2", r=0.50, x=0.80, rate=10))
    grid.add_line(gce.Line(bus_from=b2, bus_to=b3, name="L2-3", r=0.75, x=1.20, rate=10))
    grid.add_line(gce.Line(bus_from=b1, bus_to=b3, name="L1-3", r=1.00, x=1.60, rate=10))
    return grid, b3


def reseau_avec_pv(p_pv=12.0, q_pv=0.0):
    """Le réseau de base + une centrale PV dans la zone artisanale."""
    grid, b3 = construire_reseau()
    grid.add_static_generator(b3, gce.StaticGenerator(name="Centrale PV", P=p_pv, Q=q_pv))
    return grid


# =============================================================================
# Exercice 1 : load flow sur le réseau de base
# =============================================================================
print("\n========== EXERCICE 1 : réseau de base ==========")
grid, _ = construire_reseau()
res = gce.power_flow(grid)
print("Convergé :", bool(res.converged))
print("\nBus :")
print(res.get_bus_df().round(3))
print("\nLignes :")
print(res.get_branch_df().round(3))


# =============================================================================
# Exercice 2 : 12 MW de PV dans la zone artisanale
# =============================================================================
print("\n========== EXERCICE 2 : avec 12 MW de PV ==========")
grid_pv = reseau_avec_pv(p_pv=12.0, q_pv=0.0)   # essaie q_pv=-4.0
res_pv = gce.power_flow(grid_pv)
print("\nBus :")
print(res_pv.get_bus_df().round(3))
print("\nLignes :")
print(res_pv.get_branch_df().round(3))


# =============================================================================
# Exercice 3 : N-1, on perd chaque ligne une par une
# =============================================================================
print("\n========== EXERCICE 3 : analyse N-1 ==========")
grid, _ = construire_reseau()
for ligne in grid.lines:
    ligne.active = False                      # on déclenche la ligne
    r = gce.power_flow(grid)
    bus, branches = r.get_bus_df(), r.get_branch_df()
    print(f"--- Perte de {ligne.name} ---")
    print(f"Tension min : {bus['Vm'].min():.3f} pu ({bus['Vm'].idxmin()})")
    print(f"Charge max  : {branches['loading'].abs().max():.0f} % ({branches['loading'].abs().idxmax()})")
    ligne.active = True                       # on la remet en service


# =============================================================================
# Graphiques
# =============================================================================
grid, _ = construire_reseau()
res_sans = gce.power_flow(grid)
res_avec = gce.power_flow(reseau_avec_pv(12.0))

# --- Graphique 1 : tension à chaque bus, avec et sans PV
v_sans = res_sans.get_bus_df()["Vm"]
v_avec = res_avec.get_bus_df()["Vm"]
x = range(len(v_sans))
plt.figure(figsize=(7, 4))
plt.bar([i - 0.2 for i in x], v_sans, width=0.4, label="Sans PV")
plt.bar([i + 0.2 for i in x], v_avec, width=0.4, label="Avec 12 MW de PV")
plt.axhline(1.1, color="red", linestyle="--", label="Limites 0,9 / 1,1 pu")
plt.axhline(0.9, color="red", linestyle="--")
plt.xticks(list(x), v_sans.index)
plt.ylim(0.85, 1.15)
plt.ylabel("Tension (pu)")
plt.title("Tension aux bus")
plt.legend()
plt.tight_layout()
plt.savefig("tensions_bus.png", dpi=150)

# --- Graphique 2 : taux de charge des lignes, avec et sans PV
ch_sans = res_sans.get_branch_df()["loading"].abs()
ch_avec = res_avec.get_branch_df()["loading"].abs()
x = range(len(ch_sans))
plt.figure(figsize=(7, 4))
plt.bar([i - 0.2 for i in x], ch_sans, width=0.4, label="Sans PV")
plt.bar([i + 0.2 for i in x], ch_avec, width=0.4, label="Avec 12 MW de PV")
plt.axhline(100, color="red", linestyle="--", label="Capacité max (100 %)")
plt.xticks(list(x), ch_sans.index)
plt.ylabel("Taux de charge (%)")
plt.title("Charge des lignes")
plt.legend()
plt.tight_layout()
plt.savefig("charge_lignes.png", dpi=150)

# --- Graphique 3 : montée de tension quand la puissance PV augmente
puissances = range(0, 31, 2)
v_zone, charge_max = [], []
for p in puissances:
    r = gce.power_flow(reseau_avec_pv(float(p)))
    v_zone.append(r.get_bus_df().loc["Zone artisanale", "Vm"])
    charge_max.append(r.get_branch_df()["loading"].abs().max())

fig, ax1 = plt.subplots(figsize=(7, 4))
ax1.plot(puissances, v_zone, "o-", color="tab:blue")
ax1.axhline(1.1, color="tab:blue", linestyle="--")
ax1.set_xlabel("Puissance PV injectée (MW)")
ax1.set_ylabel("Tension zone artisanale (pu)", color="tab:blue")
ax2 = ax1.twinx()
ax2.plot(puissances, charge_max, "s-", color="tab:orange")
ax2.axhline(100, color="tab:orange", linestyle="--")
ax2.set_ylabel("Charge de la ligne la plus chargée (%)", color="tab:orange")
plt.title("Que se passe-t-il quand on ajoute du PV ?")
fig.tight_layout()
plt.savefig("montee_tension.png", dpi=150)

print("\nGraphiques enregistrés : tensions_bus.png, charge_lignes.png, montee_tension.png")
plt.show()