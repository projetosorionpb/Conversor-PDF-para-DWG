import os
import glob
import ezdxf
import math
import blocos_simbolos

# Find latest dwg in uploads
dwg_files = glob.glob("uploads/*.dwg")
if not dwg_files:
    print("Nenhum arquivo DWG encontrado em uploads/")
    exit()

dwg_files.sort(key=os.path.getmtime, reverse=True)
latest_dwg = dwg_files[0]
print(f"Analisando: {latest_dwg}")

doc = ezdxf.readfile(latest_dwg)
msp = doc.modelspace()

NPF_AREA = 2.6437
NPF_TOL_AREA = 0.010
NPF_TOLERANCIA = 0.5

polys = []
hatches = []

for entity in msp:
    if not entity.is_alive:
        continue
    layer = entity.dxf.layer
    if not layer.endswith("COR_000000"):
        continue
        
    if entity.dxftype() == 'LWPOLYLINE':
        area = blocos_simbolos.get_area(entity)
        if abs(area - NPF_AREA) <= NPF_TOL_AREA:
            centro = blocos_simbolos.get_centro(entity)
            polys.append({"entity": entity, "centro": centro, "area": area})
    elif entity.dxftype() == 'HATCH':
        area = blocos_simbolos.get_area(entity)
        if abs(area - NPF_AREA) <= NPF_TOL_AREA:
            centro = blocos_simbolos.get_centro(entity)
            hatches.append({"entity": entity, "centro": centro, "area": area})

print(f"Polilinhs candidatas: {len(polys)}")
print(f"Hatches candidatos: {len(hatches)}")

# Vejamos as distâncias para algumas polilinhas
for i, poly in enumerate(polys[:10]):
    print(f"\nPolilinha {i}: centro={poly['centro']}, area={poly['area']:.4f}")
    dists = []
    for j, hatch in enumerate(hatches):
        d = math.dist(poly['centro'], hatch['centro'])
        dists.append((d, j, hatch['centro']))
    dists.sort()
    print("  Hatches mais próximos:")
    for d, idx, hc in dists[:3]:
        print(f"    Distância: {d:.6f} a Hatch {idx} no centro {hc}")

# Agora vamos simular o emparelhamento completo
hatches_usados = set()
pares = []
for poly_item in polys:
    poly_ent = poly_item["entity"]
    poly_center = poly_item["centro"]
    
    melhor_hatch = None
    melhor_dist = float('inf')
    
    for hatch_item in hatches:
        h_ent = hatch_item["entity"]
        h_center = hatch_item["centro"]
        
        if h_ent not in hatches_usados:
            d = math.dist(poly_center, h_center)
            if d < melhor_dist:
                melhor_dist = d
                melhor_hatch = h_ent
                
    if melhor_hatch and melhor_dist <= NPF_TOLERANCIA:
        hatches_usados.add(melhor_hatch)
        pares.append((poly_ent, melhor_hatch, melhor_dist))

print(f"\nTotal de pares formados com tolerância {NPF_TOLERANCIA}: {len(pares)}")
if pares:
    print("Exemplos de distâncias de pares formados:")
    for p, h, d in pares[:10]:
        print(f"  Distância: {d:.6f}")
else:
    # Ver menor distância absoluta encontrada
    menor_d = float('inf')
    for poly in polys:
        for hatch in hatches:
            d = math.dist(poly['centro'], hatch['centro'])
            if d < menor_d:
                menor_d = d
    print(f"Menor distância absoluta entre qualquer polyline e hatch candidato: {menor_d:.6f}")
