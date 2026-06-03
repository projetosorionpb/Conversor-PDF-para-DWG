import os
import glob
import ezdxf
import blocos_simbolos

# Find latest dwg in uploads
dwg_files = glob.glob("uploads/*.dwg")
if not dwg_files:
    print("Nenhum arquivo DWG encontrado em uploads/")
    exit()

# Sort by modification time to get the latest
dwg_files.sort(key=os.path.getmtime, reverse=True)
latest_dwg = dwg_files[0]
print(f"Analisando o DWG mais recente: {latest_dwg}")

try:
    doc = ezdxf.readfile(latest_dwg)
except Exception as e:
    print(f"Erro ao ler arquivo: {e}")
    exit()

msp = doc.modelspace()
print(f"Total de entidades no Model Space: {len(msp)}")

# Contar por tipo e listar layers
counts = {}
layers = set()
for entity in msp:
    t = entity.dxftype()
    counts[t] = counts.get(t, 0) + 1
    layers.add(entity.dxf.layer)

print("\nContagem por tipo de entidade:")
for t, count in counts.items():
    print(f"  {t}: {count}")

print(f"\nTotal de layers: {len(layers)}")
print("Alguns layers de exemplo:")
for l in list(layers)[:15]:
    print(f"  {l}")

# Investigar polilinhas e hatches na layer COR_000000 ou similares
print("\n--- Investigando Polilinhas e Hatches com layers terminando em 'COR_000000' ---")
polys = []
hatches = []
for entity in msp:
    if entity.dxf.layer.endswith("COR_000000"):
        if entity.dxftype() == 'LWPOLYLINE':
            area = blocos_simbolos.get_area(entity)
            polys.append((entity, area))
        elif entity.dxftype() == 'HATCH':
            area = blocos_simbolos.get_area(entity)
            hatches.append((entity, area))

print(f"Total LWPOLYLINES terminando em COR_000000: {len(polys)}")
if polys:
    print("Áreas das polilinhas (primeiras 20):")
    for i, (poly, area) in enumerate(polys[:20]):
        print(f"  Area: {area:.6f}, Pontos: {len(poly.get_points())}, Fechada: {poly.is_closed}")

print(f"\nTotal HATCHES terminando em COR_000000: {len(hatches)}")
if hatches:
    print("Áreas dos hatches (primeiros 20):")
    for i, (hatch, area) in enumerate(hatches[:20]):
        print(f"  Area: {area:.6f}")

# Rodando detecções teste
print("\n--- Rodando Rotinas de Detecção em Modo Simulação ---")
print(f"  NO_PERTO_FORMADO candidatos: ...")
npf_count = 0
for poly, area in polys:
    if abs(area - 2.6437) <= 0.010:
        npf_count += 1
print(f"  Polilinhas com área próxima a 2.6437: {npf_count}")

hatch_npf_count = 0
for hatch, area in hatches:
    if abs(area - 2.6437) <= 0.010:
        hatch_npf_count += 1
print(f"  Hatches com área próxima a 2.6437: {hatch_npf_count}")
