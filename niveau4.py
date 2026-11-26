# on construit un vrai départ de distribution : le réseau 63 kV, un transformateur, 
# puis une ligne 20 kV de 18 km qui dessert 9 villages en série, comme une route de campagne.

# convertir une ligne en pu 
import VeraGridEngine.api as gce
import pandas as pd
import matplotlib.pyplot as plt

S_BASE = 100 # MVA

def ligne_en_pu(r_ohm_km, x_ohm_km, longueur_km, U_kv=20):
    Z_base = (U_kv**2) / S_BASE
    return r_ohm_km * longueur_km / Z_base, x_ohm_km * longueur_km / Z_base

r, x = ligne_en_pu(0.3, 0.35, 2)
print(f"Tronçon de 2 km : r = {r:.3f} pu, x = {x:.3f} pu")

# construire le depart avec une boucle 

N_BUS = 9
LONGUEUR_TRONCON = 2 

N_BUS = 9                 # nombre de bus (villages) le long du départ
LONGUEUR_TRONCON = 2      # longueur de chaque tronçon entre deux bus, en km

def construire_depart(conso_mw=0.4, pv_mw=None, q_pv_par_mw=0.0, tap=1.0):
    # conso_mw    : consommation de CHAQUE bus, en MW (0.4 par défaut)
    # pv_mw       : dictionnaire {numéro de bus: MW de PV}, par ex. {7: 2.0, 9: 3.0}
    # q_pv_par_mw : réactif des onduleurs par MW de PV (0 = aucun, -0.33 = cos phi 0.95 en absorption)
    # tap         : position du régleur du transfo (1.0 = neutre, < 1 = tension côté 20 kV plus haute)

    pv_mw = pv_mw or {}   # si aucun PV n'est donné (None), on prend un dictionnaire vide

    grid = gce.MultiCircuit(name="Départ 20 kV")   # on crée le réseau vide

    # ---------- Réseau amont et poste source ----------
    amont = gce.Bus(name="Réseau 63 kV", Vnom=63, is_slack=True)   # bus 63 kV = nœud bilan (slack)
    poste = gce.Bus(name="Poste 20 kV", Vnom=20)                    # bus 20 kV à la sortie du transfo
    grid.add_bus(amont)                                             # on ajoute le bus 63 kV au réseau
    grid.add_bus(poste)                                             # on ajoute le bus 20 kV au réseau
    grid.add_generator(amont, gce.Generator(name="Réseau amont", vset=1.0))  # le réseau amont tient 1.0 pu

    # ---------- Transformateur 63/20 kV ----------
    # 20 MVA, ucc = 12 %  ->  x = 0.12 * 100 / 20 = 0.6 pu (base 100 MVA)
    grid.add_transformer2w(gce.Transformer2W(
        bus_from=amont,       # côté haute tension : relié au bus 63 kV
        bus_to=poste,         # côté basse tension : relié au bus 20 kV
        name="TR 63/20",      # nom du transfo
        HV=63,                # tension côté haut, en kV
        LV=20,                # tension côté bas, en kV
        nominal_power=20,     # puissance nominale, en MVA
        r=0.02,               # résistance en pu (pertes)
        x=0.6,                # réactance en pu (calculée depuis l'ucc)
        rate=20,              # limite de puissance, en MVA
        tap_module=tap))      # position du régleur, reprise du paramètre de la fonction

    # ---------- Le départ : une chaîne de 9 bus ----------
    r, x = ligne_en_pu(0.3, 0.35, LONGUEUR_TRONCON)   # r et x en pu d'un tronçon de 2 km (0.15 et 0.175)

    precedent = poste     # "le bout de la chaîne" : au départ, c'est le poste 20 kV

    for i in range(1, N_BUS + 1):          # on répète pour i = 1, 2, ..., 9 (un tour par village)

        bus = gce.Bus(name=f"N{i}", Vnom=20)   # on crée un nouveau bus : N1, puis N2, ... N9
        grid.add_bus(bus)                      # on l'ajoute au réseau

        grid.add_line(gce.Line(                # on crée le tronçon de ligne :
            bus_from=precedent,                #   il part du bout actuel de la chaîne
            bus_to=bus,                        #   et arrive au nouveau bus
            name=f"T{i}",                      #   il s'appelle T1, T2, ... T9
            r=r, x=x,                          #   avec les r et x calculés avant la boucle
            rate=10))                          #   et une limite de 10 MVA

        grid.add_load(bus, gce.Load(           # on ajoute la consommation du village sur ce bus :
            name=f"Conso N{i}",                #   nom : Conso N1, Conso N2, ...
            P=conso_mw,                        #   puissance active, en MW
            Q=conso_mw * 0.33))                #   réactive = 0.33 x P (cos phi ~ 0.95)

        if i in pv_mw:                         # ce bus a-t-il du PV dans le dictionnaire ?
            p = pv_mw[i]                       #   si oui, on récupère sa puissance (en MW)
            grid.add_static_generator(bus, gce.StaticGenerator(   # on ajoute la centrale PV :
                name=f"PV N{i}",               #   nom : PV N7, PV N9, ...
                P=p,                           #   puissance injectée, en MW
                Q=q_pv_par_mw * p))            #   réactif de l'onduleur (négatif = absorbe)

        precedent = bus                        # le nouveau bus devient le bout de la chaîne
                                               # -> au tour suivant, le tronçon partira de lui

    return grid           # après la boucle (4 espaces) : on renvoie le réseau complet


# ---------- Hors de la fonction : on l'utilise ----------
grid = construire_depart()     # on construit le cas de base : 0.4 MW par bus, pas de PV, régleur neutre
print("Bus :", len(grid.buses),               # 11 bus  : 63 kV + poste + N1 à N9
      "| lignes :", len(grid.lines),          # 9 lignes : T1 à T9
      "| transfos :", len(grid.transformers2w))  # 1 transfo


# profil de tension 
def profil(grid):
    res = gce.power_flow(grid)                    # on lance le load flow sur le réseau donné
    bus = res.get_bus_df()                        # tableau des résultats par bus

    noms = ["Poste 20 kV"] + [f"N{i}" for i in range(1, N_BUS + 1)]
    # la liste des bus du départ, dans l'ordre : ["Poste 20 kV", "N1", "N2", ..., "N9"]

    v = bus.loc[noms, "Vm"]                       # on récupère la tension (Vm) de ces bus, dans cet ordre

    distances = [0] + [i * LONGUEUR_TRONCON for i in range(1, N_BUS + 1)]
    # la distance de chaque bus au poste : [0, 2, 4, ..., 18] km

    return pd.Series(v.values, index=distances, name="Vm"), res
    # on renvoie deux choses : les tensions rangées par distance, et les résultats complets


v_soir, res_soir = profil(construire_depart(conso_mw=0.4))   # cas du soir : 0.4 MW par bus, pas de PV
print(v_soir.round(3))                                        # on affiche le profil