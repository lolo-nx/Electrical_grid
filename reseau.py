import VeraGridEngine.api as gce

grid = gce.MultiCircuit(name= "Mon premier reseau")
print("reseau cree:", grid.name)



# creation des 3 bus

poste = gce.Bus(name="poste source", Vnom=20, is_slack=True)
village= gce.Bus(name="village", Vnom=20)
zone = gce.Bus(name="zone artisanale", Vnom=20)

grid.add_bus(poste)
grid.add_bus(village)
grid.add_bus(zone)
print("Nombre de bus:", len(grid.buses))


# ajout dun generateur sur le bus poste
grid.add_generator(poste, gce.Generator(name="reseau amont", vset=1.0))
print("Nombre de generateurs:", len(grid.generators))

# ajout de deux charges
grid.add_load(village, gce.Load(name="conso village", P=4, Q=1.5))
grid.add_load(zone, gce.Load(name="conso zone", P=3, Q=1.0))
print("Nombre de charges:", len(grid.loads))

# tracer les 3 lignes
grid.add_line(gce.Line(bus_from=poste, bus_to=village, name="L1-2", r=0.5, x=0.8, rate=10))
grid.add_line(gce.Line(bus_from=village, bus_to=zone, name="L2-3", r=0.75, x=1.2, rate=10))
grid.add_line(gce.Line(bus_from=poste, bus_to=zone, name="L1-3", r=1.0, x=1.6, rate=10))
print("Nombre de lignes:", len(grid.lines))

#lancer le load flow
res = gce.power_flow(grid)
print("Load flow converged:", bool(res.converged))

# affichage des resultats
print(res.get_bus_df().round(3))   #tableau des bus
print(res.get_branch_df().round(3)) # tableau des lignes


gce.save_file(grid, "mon_reseau.veragrid")
print("Réseau enregistré dans mon_reseau.veragrid")