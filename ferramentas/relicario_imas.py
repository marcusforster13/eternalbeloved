"""Relicário com ímãs: refaz as duas metades do coração com alojamentos para ímãs de 5x2 mm,
testa paredes, fechar/abrir pela argola e grava os STL de impressão.

Rodar:  blender -b --factory-startup --python relicario_imas.py
"""
import bpy, bmesh, math, os, struct, json
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
STL = os.path.join(HERE, "impressao", "eternal-beloved-chaveiro.stl")
PECAS = os.path.join(HERE, "impressao", "pecas")
REPORT = os.path.join(HERE, "impressao", "_relatorio_imas.json")

S, K, CY = 16.0, 0.58, 0.05
POCKET_D = 0.8
MAG_D, MAG_H = 5.0, 2.0                 # ímã de neodímio 5 x 2 mm
MAG_R = MAG_D / 2 + 0.12                # alojamento Ø5,24 (entra com uma gota de cola)
MAG_DEPTH = MAG_H + 0.1                 # fica 0,1 mm abaixo da face: as faces encostam, os ímãs não
CH = 0.3                                # chanfro na boca contra o pé de elefante
ADIR = Vector((1, .42, .32)).normalized()
T_OUT, T_IN, SOCK_R = 18.27, 13.79, 1.4

sc = bpy.context.scene
for o in list(sc.objects): bpy.data.objects.remove(o, do_unlink=True)

def Fh(x, y, z): return x*x + 2.25*z*z + y*y - 1 - y*(x*x + 0.1125*z*z) ** (1/3)
def r_at(th):
    dx, dy = math.cos(th), math.sin(th); lo = hi = 0; r = .02
    while r < 2.5:
        if Fh(dx*r, dy*r, 0) > 0: hi, lo = r, r-.02; break
        r += .02
    for _ in range(40):
        m = (lo+hi)/2
        if Fh(dx*m, dy*m, 0) > 0: hi = m
        else: lo = m
    return (lo+hi)/2
OUTLINE = [((r_at(t)*math.cos(t))*S, (r_at(t)*math.sin(t) - .06)*S) for t in (2*math.pi*k/360 for k in range(360))]
POCKET = [(x*K, y*K + CY*S + .06*S*K - .06*S*K) for x, y in OUTLINE]
POCKET = [((r_at(t)*math.cos(t))*K*S, (r_at(t)*math.sin(t) - .06)*K*S + CY*S) for t in (2*math.pi*k/360 for k in range(360))]

def seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p; dx, dy = bx-ax, by-ay; L = dx*dx + dy*dy
    t = 0 if L == 0 else max(0, min(1, ((px-ax)*dx + (py-ay)*dy) / L))
    return math.hypot(px - (ax + t*dx), py - (ay + t*dy))
def poly_dist(p, poly): return min(seg_dist(p, poly[i], poly[(i+1) % len(poly)]) for i in range(len(poly)))
def inside(p, poly):
    x, y = p; c = False
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[(i+1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1) + x1: c = not c
    return c

# ---------- posição dos ímãs: no lobo, o mais longe possível da borda e do bolso ----------
best = None
for xi in range(60, 200, 2):
    for yi in range(0, 180, 2):
        p = (xi / 10, yi / 10)
        if not inside(p, OUTLINE) or inside(p, POCKET): continue
        if math.hypot(p[0], p[1] - 19.5) < 5.0 + MAG_R + 1.0: continue          # longe da placa da argola
        w = min(poly_dist(p, OUTLINE), poly_dist(p, POCKET)) - MAG_R
        if best is None or w > best[0]: best = (w, p)
MAG_WALL_2D, (MX, MY) = best
MAGS = [(MX, MY), (-MX, MY)]

def link(name, me): o = bpy.data.objects.new(name, me); sc.collection.objects.link(o); return o
def prism(name, pts, z0, z1):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bot = [bm.verts.new((x, y, z0)) for x, y in pts]; top = [bm.verts.new((x, y, z1)) for x, y in pts]
    cx = sum(p[0] for p in pts)/len(pts); cy = sum(p[1] for p in pts)/len(pts)
    cb = bm.verts.new((cx, cy, z0)); ct = bm.verts.new((cx, cy, z1)); n = len(pts)
    for i in range(n):
        j = (i+1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i])); bm.faces.new((cb, bot[j], bot[i])); bm.faces.new((ct, top[i], top[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free(); return link(name, me)
def cyl(name, x, y, r, z0, z1, seg=64): return prism(name, [(x + r*math.cos(2*math.pi*k/seg), y + r*math.sin(2*math.pi*k/seg)) for k in range(seg)], z0, z1)
def cone_obj(name, r1, r2, h, M):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=64, radius1=r1, radius2=r2, depth=h); bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, h/2))
    bm.to_mesh(me); bm.free(); o = link(name, me); o.data.transform(M); return o
def boolean(target, cutter, op):
    m = target.modifiers.new("B", 'BOOLEAN'); m.operation = op; m.solver = 'MANIFOLD'; m.object = cutter
    with bpy.context.temp_override(object=target, active_object=target):
        bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
def dup(o, name): c = o.copy(); c.data = o.data.copy(); c.name = name; sc.collection.objects.link(c); return c
def along(t0, d): return Matrix.Translation(ADIR * t0) @ Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()

# ---------- 1) coração + toro da argola ----------
bpy.ops.wm.stl_import(filepath=STL, forward_axis='Y', up_axis='Z')
obj = bpy.context.selected_objects[0]
with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj], selected_editable_objects=[obj]):
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.separate(type='LOOSE'); bpy.ops.object.mode_set(mode='OBJECT')
parts = sorted([o for o in sc.objects if o.type == 'MESH'], key=lambda o: -len(o.data.polygons))
heart = parts[0]; torus = [o for o in parts if len(o.data.polygons) == 6144][0]
for o in parts:
    if o not in (heart, torus): bpy.data.objects.remove(o, do_unlink=True)
boolean(heart, torus, 'UNION')

# ---------- 2) metades, bolso, ímãs, argola, encaixes da flecha ----------
front, back = dup(heart, "Coracao_frente"), dup(heart, "Coracao_tras")
boolean(front, cyl("cx", 0, 0, 80, 0, 40, 8), 'INTERSECT'); boolean(back, cyl("cx", 0, 0, 80, -40, 0, 8), 'INTERSECT')
boolean(back, prism("bolso", POCKET, -POCKET_D, 0.5), 'DIFFERENCE')
for x, y in MAGS:
    boolean(front, cyl("ima", x, y, MAG_R, -0.5, MAG_DEPTH), 'DIFFERENCE')
    boolean(back, cyl("ima", x, y, MAG_R, -MAG_DEPTH, 0.5), 'DIFFERENCE')
    boolean(front, cone_obj("ch", MAG_R + CH + 0.3, MAG_R - 0.001, CH + 0.3, Matrix.Translation((x, y, -0.3))), 'DIFFERENCE')
    boolean(back, cone_obj("ch", MAG_R + CH + 0.3, MAG_R - 0.001, CH + 0.3, Matrix.Translation((x, y, 0.3)) @ Matrix.Rotation(math.pi, 4, 'X')), 'DIFFERENCE')
for o, z0, z1 in ((front, 0, 1.6), (back, -1.6, 0)):
    boolean(o, cyl("disco", 0, 19.5, 5.0, z0, z1), 'UNION'); boolean(o, cyl("argola", 0, 19.5, 2.1, -6, 6), 'DIFFERENCE')
boolean(front, cone_obj("enc", SOCK_R, SOCK_R, 10.0, along(T_OUT - 6.0, ADIR)), 'DIFFERENCE')
boolean(back, cone_obj("enc", SOCK_R, SOCK_R, 7.5, along(-(T_IN - 3.5), -ADIR)), 'DIFFERENCE')
bpy.data.objects.remove(heart, do_unlink=True)

def stats(o):
    bm = bmesh.new(); bm.from_mesh(o.data); n = sum(1 for e in bm.edges if not e.is_manifold); v = bm.calc_volume()
    seen, isl = set(), 0
    for f in bm.faces:
        if f.index in seen: continue
        isl += 1; st = [f]
        while st:
            g = st.pop()
            if g.index in seen: continue
            seen.add(g.index); st += [h for e in g.edges for h in e.link_faces if h.index not in seen]
    bm.free(); return {"bordas_abertas": n, "pecas": isl, "volume_mm3": round(v, 1)}
rep = {"ima_xy_mm": [round(MX, 2), round(MY, 2)], "parede_lateral_minima_mm": round(MAG_WALL_2D, 2),
       "frente": stats(front), "tras": stats(back)}

# espessura que sobra atrás de cada ímã (até a casca de fora do coração)
def surf(o, x, y, sgn):
    ok, loc, n, i = o.ray_cast(Vector((x, y, sgn * 40)), Vector((0, 0, -sgn)))
    return abs(loc.z) if ok else None
rep["sobra_atras_do_ima_mm"] = {"frente": round(min(surf(front, x + dx, y + dy, 1) for x, y in MAGS for dx, dy in ((MAG_R, 0), (-MAG_R, 0), (0, MAG_R), (0, -MAG_R))) - MAG_DEPTH, 2),
                                "tras": round(min(surf(back, x + dx, y + dy, -1) for x, y in MAGS for dx, dy in ((MAG_R, 0), (-MAG_R, 0), (0, MAG_R), (0, -MAG_R))) - MAG_DEPTH, 2)}
# distância do ímã até os encaixes da flecha (eixo do encaixe x cilindro do ímã)
def sock_gap(t0, t1, side):
    g = 99
    for i in range(41):
        c = ADIR * (t0 + (t1 - t0) * i / 40)
        for x, y in MAGS:
            dxy = math.hypot(c.x - x, c.y - y) - MAG_R
            dz = (abs(c.z) - MAG_DEPTH) if side * c.z > 0 else 9
            g = min(g, max(dxy, dz) - SOCK_R)
    return round(g, 2)
rep["folga_ima_encaixe_flecha_mm"] = {"frente": sock_gap(T_OUT - 6.0, T_OUT, 1), "tras": sock_gap(-(T_IN - 3.5), -T_IN, -1)}

# ---------- 3) testes de montagem: ímãs, foto, flecha, fechar, argola, abrir/fechar pela argola ----------
mags_f = [cyl(f"ima_f{i}", x, y, MAG_D/2, MAG_DEPTH - MAG_H, MAG_DEPTH) for i, (x, y) in enumerate(MAGS)]
mags_b = [cyl(f"ima_t{i}", x, y, MAG_D/2, -MAG_DEPTH, -MAG_DEPTH + MAG_H) for i, (x, y) in enumerate(MAGS)]
W = max(p[0] for p in POCKET) - min(p[0] for p in POCKET); cxp = (max(p[0] for p in POCKET) + min(p[0] for p in POCKET))/2; cyp = (max(p[1] for p in POCKET) + min(p[1] for p in POCKET))/2
fph = (W - 0.6) / W
photo = prism("foto", [(cxp + (x-cxp)*fph, cyp + (y-cyp)*fph) for x, y in POCKET], -0.8, -0.55)
def load_stl(path, M, name):
    bpy.ops.wm.stl_import(filepath=path, forward_axis='Y', up_axis='Z'); o = bpy.context.selected_objects[0]; o.name = name
    o.data.transform(o.matrix_world); o.matrix_world = Matrix.Identity(4); o.data.transform(M); return o
tip = load_stl(os.path.join(PECAS, "3-branco-ponta.stl"), along(30.9, ADIR), "ponta")
pen = load_stl(os.path.join(PECAS, "4-azul-penas.stl"), along(-31.2, ADIR), "penas")
shaft_f = cone_obj("haste_f", 1.25, 1.25, (30.9 + 3.0) - (T_OUT - 5.8), along(T_OUT - 5.8, ADIR))
shaft_b = cone_obj("haste_t", 1.25, 1.25, 31.2 - (T_IN - 3.3), along(-(T_IN - 3.3), -ADIR))
bpy.ops.mesh.primitive_torus_add(major_radius=12.5, minor_radius=0.6, major_segments=128, minor_segments=16, location=(0, 32.0, 0), rotation=(0, math.pi/2, 0))
ring = bpy.context.active_object; ring.data.transform(ring.matrix_world); ring.matrix_world = Matrix.Identity(4)

def bvh(o, M=Matrix.Identity(4)):
    vs = [M @ v.co for v in o.data.vertices]; return BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in o.data.polygons])
def vol(o):
    bm = bmesh.new(); bm.from_mesh(o.data); v = bm.calc_volume(); bm.free(); return v
def penetration(a, M, b):
    c = a.copy(); c.data = a.data.copy(); sc.collection.objects.link(c); c.data.transform(M); c.matrix_world = Matrix.Identity(4)
    m = c.modifiers.new("I", 'BOOLEAN'); m.operation = 'INTERSECT'; m.solver = 'MANIFOLD'; m.object = b
    with bpy.context.temp_override(object=c, active_object=c):
        bpy.ops.object.modifier_apply(modifier=m.name)
    v = vol(c) if len(c.data.polygons) else 0.0; bpy.data.objects.remove(c, do_unlink=True); return round(v, 3)
def sweep(movers, Ms, statics):
    worst = 0.0; bad = []; cache = {b.name: bvh(b) for b in statics}
    for M in Ms:
        for a in movers:
            ta = bvh(a, M)
            for b in statics:
                if ta.overlap(cache[b.name]):
                    p = penetration(a, M, b)
                    if p > 0: bad.append((a.name, b.name, p)); worst = max(worst, p)
    return {"passos": len(Ms), "max_penetracao_mm3": worst, "colisoes": bad[:4]}
T = lambda v: Matrix.Translation(v)
tests = {}
tests["imas_entram_na_frente"] = sweep(mags_f, [T((0, 0, -5 + 0.25*k)) for k in range(21)], [front])
tests["imas_entram_atras"] = sweep(mags_b, [T((0, 0, 5 - 0.25*k)) for k in range(21)], [back])
FRONT = [front, shaft_f, tip] + mags_f
BACK = [back, shaft_b, pen, photo] + mags_b
tests["fechar"] = sweep(FRONT, [T((0, 0, 6 - 0.25*k)) for k in range(25)], BACK)
tests["argola_no_fechado"] = sweep(FRONT + BACK, [Matrix.Identity(4)], [ring])
RC = Vector((0, 32.0, 0)); pose = lambda s, a: T(RC) @ Matrix.Rotation(math.radians(-a), 4, 'X') @ T(-RC) @ T((0, 0, s))
path = [(s * 0.5, 0) for s in range(0, 5)] + [(2.0, a) for a in range(5, 115, 5)]
tests["abrir_pela_argola"] = sweep(FRONT, [pose(s, a) for s, a in path], BACK + [ring])
tests["fechar_de_novo"] = sweep(FRONT, [pose(s, a) for s, a in reversed(path)], BACK + [ring])
gap = MAG_DEPTH - MAG_H
rep["vao_entre_imas_fechado_mm"] = round(2 * gap, 2)
rep["testes"] = tests

# ---------- 4) STL de impressão (face lisa na mesa) ----------
def write(o, fname, M):
    me = o.data; me.calc_loop_triangles(); vs = [M @ v.co for v in me.vertices]; zmin = min(v.z for v in vs)
    xs = [v.x for v in vs]; ys = [v.y for v in vs]; cx, cy = (max(xs)+min(xs))/2, (max(ys)+min(ys))/2
    with open(os.path.join(PECAS, fname), 'wb') as f:
        f.write(b'Eternal Beloved (mm)'.ljust(80, b' ')); f.write(struct.pack('<I', len(me.loop_triangles)))
        for t in me.loop_triangles:
            a, b, c = (vs[i].copy() for i in t.vertices)
            for v in (a, b, c): v.x -= cx; v.y -= cy; v.z -= zmin
            n = (b - a).cross(c - a)
            if n.length: n.normalize()
            f.write(struct.pack('<12fH', n.x, n.y, n.z, a.x, a.y, a.z, b.x, b.y, b.z, c.x, c.y, c.z, 0))
write(front, "1-rosa-coracao-frente.stl", Matrix.Identity(4))
write(back, "1-rosa-coracao-tras.stl", Matrix.Rotation(math.pi, 4, 'X'))
rep["stl"] = ["1-rosa-coracao-frente.stl", "1-rosa-coracao-tras.stl"]
json.dump(rep, open(REPORT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("RELATORIO", json.dumps(rep, ensure_ascii=False))
