import VeraGridEngine.api as gce
import pandas as pd
import matplotlib.pyplot as plt

# construire un reseau definit une fonction, construire_reseau() donne le réseau sans PV, construire_reseau(p_pv=12) le réseau avec 12 MW.
def construire_reseau(p_pv=0.0, q_pv=0.0):
    grid = gce.MultiCircuit(name="Reseau niveau 2")
    poste = gce.Bus(name="poste source", Vnom=20, is_slack=True)
    village = gce.Bus(name="village", Vnom=20)
    zone = gce.Bus(name="zone artisanale", Vnom=20)
    for b in (poste, village, zone):
        grid.add_bus(b)
    grid.add_generator(poste, gce.Generator(name="reseau amont", vset=1.0))
    grid.add_load(village, gce.Load(name="conso village", P=4, Q=1.5))
    grid.add_load(zone, gce.Load(name="conso zone", P=3, Q=1.0))
    grid.add_line(gce.Line(bus_from=poste, bus_to=village, name="L1-2", r=0.5, x=0.8, rate=10))
    grid.add_line(gce.Line(bus_from=village, bus_to=zone, name="L2-3", r=0.75, x=1.2, rate=10))
    grid.add_line(gce.Line(bus_from=poste, bus_to=zone, name="L1-3", r=1.0, x=1.6, rate=10))
    if p_pv > 0 : 
        grid.add_static_generator(zone, gce.StaticGenerator(name="Centrale PV", P=p_pv, Q=q_pv)) # ondulateur PV qui convertir le DC en AC 
    return grid

# fonction qui resume les resultats
def resumer(res):
    bus = res.get_bus_df()
    lignes = res.get_branch_df()
    return {
        "V min (pu)": bus["Vm"].min(),
        "V max (pu)": bus["Vm"].max(),
        "V zone (pu)": bus.loc["zone artisanale", "Vm"],
        "Charge max (%)": lignes["loading"].abs().max(),
        "Pertes (MW)": lignes["Ploss"].sum(),
        "P slack (MW)": bus.loc["poste source", "P"],
    }
print("Sans PV   :", {k: round(float(v), 3) for k, v in resumer(gce.power_flow(construire_reseau())).items()})
print("12 MW PV  :", {k: round(float(v), 3) for k, v in resumer(gce.power_flow(construire_reseau(p_pv=12))).items()})


# une boucle sur la puissance PV , On teste 16 puissances PV, de 0 à 30 MW, et on range tout dans un tableau.
lignes_tableau = []
for p in range(0, 31, 2):
    res = gce.power_flow(construire_reseau(p_pv=p))
    ligne = resumer(res)
    ligne["P PV (MW)"] = p
    lignes_tableau.append(ligne)
tableau = pd.DataFrame(lignes_tableau).set_index("P PV (MW)")
print(tableau.round(3))

contrainte = tableau[(tableau["V max (pu)"] > 1.05) | (tableau["Charge max (%)"] > 100)]
print("Première contrainte à :", contrainte.index[0], "MW")

# le graphique 
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
ax1.plot(tableau.index, tableau["V max (pu)"], "o-")
ax1.axhline(1.05, color="red", linestyle="--", label="Limite 1,05 pu")
ax1.set_xlabel("Puissance PV (MW)"); ax1.set_ylabel("Tension max (pu)")
ax1.set_title("Tension maximale du réseau"); ax1.legend(); ax1.grid(alpha=0.3)
ax2.plot(tableau.index, tableau["Charge max (%)"], "s-", color="tab:orange")
ax2.axhline(100, color="red", linestyle="--", label="Limite 100 %")
ax2.set_xlabel("Puissance PV (MW)"); ax2.set_ylabel("Charge max (%)")
ax2.set_title("Ligne la plus chargée"); ax2.legend(); ax2.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("balayage_pv.png", dpi=150)

# on compare deux reglages de londulateur PV , On compare l'onduleur à cos φ = 1 (Q = 0) avec un onduleur à cos φ = 0,95 qui absorbe du réactif, soit environ Q = −0,33 × P.

def balayage_pv(q_par_mw):
    res_list = []
    for p in range(0, 31, 2):
        r = resumer(gce.power_flow(construire_reseau(p_pv=p, q_pv=q_par_mw * p)))
        r["P PV (MW)"] = p
        res_list.append(r)
    return pd.DataFrame(res_list).set_index("P PV (MW)")

sans_q = balayage_pv(0.0)
avec_q = balayage_pv(-0.33)
print(pd.DataFrame({"V zone sans Q": sans_q["V zone (pu)"], "V zone cos phi 0,95": avec_q["V zone (pu)"],
                    "Charge sans Q": sans_q["Charge max (%)"], "Charge cos phi 0,95": avec_q["Charge max (%)"]}).round(3))

# le N-1 automatique
# concretement le code simule des pannes une par une pour verifier que le reseau tient le coup quand on ligne tombe 
#La règle de base de tous les gestionnaires de réseau, le N-1, dit que si n'importe quelle ligne tombe, les clients doivent continuer à être alimentés correctement, avec une tension correcte et aucune autre ligne en surcharge.
def analyse_n_moins_1(grid, v_min_ok=0.9, v_max_ok=1.1, charge_ok=100):
    resultats = []
    for ligne in grid.lines: # on parcourt toutes les lignes du reseau 
       ligne.active = False # on met la ligne hors service comme si elle etait en panne 
       r = resumer(gce.power_flow(grid)) # lance un load flow sur le reseau avec la ligne hors service
       ligne.active = True # on remet la ligne en service pour le prochain test
       ok = (r["V min (pu)"] >= v_min_ok) and (r["V max (pu)"] <= v_max_ok) and (r["Charge max (%)"] <= charge_ok)
       resultats.append({"Ligne perdue": ligne.name,
                          "V min (pu)": round(r["V min (pu)"], 3),
                          "V max (pu)": round(r["V max (pu)"], 3),
                          "Charge max (%)": round(r["Charge max (%)"]),
                          "Verdict": "OK" if ok else "CONTRAINTE"})
       return pd.DataFrame(resultats).set_index("Ligne perdue")
print(analyse_n_moins_1(construire_reseau()))
print(analyse_n_moins_1(construire_reseau(p_pv=12)))