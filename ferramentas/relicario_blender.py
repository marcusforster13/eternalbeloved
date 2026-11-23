"""Transforma o chaveiro inteiro (eternal-beloved-chaveiro.stl) no relicário que abre ao meio.

Rode dentro do Blender (5.x, solver de booleana "Manifold"):  Scripting > Open > Run Script,
depois de ajustar STL e OUT abaixo. Cria uma cena "EternalBeloved" e não mexe nas outras.

Passos: une coração + flecha + argola num sólido só, corta no plano z = 0 (frente / trás),
abre o bolso da foto em forma de coração na metade de trás (0,8 mm), fura 3 furos de 1,95 mm
para pinos de filamento 1,75 mm, reforça a argola com uma placa de 1,6 mm em cada metade e
grava os dois STL já deitados com a face lisa na mesa.
"""
import bpy, bmesh, math, os, struct
from mathutils import Matrix

STL = r"eternal-beloved-chaveiro.stl"     # gerado por gerar_stl.py
OUT = r"."
S, K, CY = 16.0, 0.58, 0.05               # escala do site (mm/unidade), tamanho e posição do bolso
PINS = [(13.6, 10.5), (-13.6, 10.5), (0.0, -12.0)]
PIN_R, PIN_DEPTH, POCKET_DEPTH = 0.975, 3.0, 0.8
LOOP = dict(cx=0.0, cy=19.5, ro=5.0, ri=2.1, t=1.6)

def F(x, y, z): return x*x + 2.25*z*z + y*y - 1 - y*(x*x + 0.1125*z*z) ** (1/3)
def r_at(th):
    dx, dy = math.cos(th), math.sin(th); lo = hi = 0; r = .02
    while r < 2.5:
        if F(dx*r, dy*r, 0) > 0: hi, lo = r, r - .02; break
        r += .02
    for _ in range(40):
        m = (lo + hi) / 2
        if F(dx*m, dy*m, 0) > 0: hi = m
        else: lo = m
    return (lo + hi) / 2

sc = bpy.data.scenes.get("EternalBeloved") or bpy.data.scenes.new("EternalBeloved")
bpy.context.window.scene = sc
for o in list(sc.objects): bpy.data.objects.remove(o, do_unlink=True)

def prism(name, pts, z0, z1):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bot = [bm.verts.new((x, y, z0)) for x, y in pts]; top = [bm.verts.new((x, y, z1)) for x, y in pts]
    cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
    cb = bm.verts.new((cx, cy, z0)); ct = bm.verts.new((cx, cy, z1)); n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i])); bm.faces.new((cb, bot[j], bot[i])); bm.faces.new((ct, top[i], top[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o); return o
def cyl(name, x, y, r, z0, z1, seg=64):
    return prism(name, [(x + r*math.cos(2*math.pi*k/seg), y + r*math.sin(2*math.pi*k/seg)) for k in range(seg)], z0, z1)
def boolean(target, cutter, op):
    bpy.context.view_layer.objects.active = target
    m = target.modifiers.new("B", 'BOOLEAN'); m.operation = op; m.solver = 'MANIFOLD'; m.object = cutter
    bpy.ops.object.modifier_apply(modifier=m.name); bpy.data.objects.remove(cutter, do_unlink=True)
def dup(o, name):
    c = o.copy(); c.data = o.data.copy(); c.name = name; sc.collection.objects.link(c); return c

# 1) importa e une tudo
bpy.ops.wm.stl_import(filepath=STL, forward_axis='Y', up_axis='Z')
obj = bpy.context.selected_objects[0]; bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.separate(type='LOOSE'); bpy.ops.object.mode_set(mode='OBJECT')
parts = sorted([o for o in sc.objects if o.type == 'MESH'], key=lambda o: -len(o.data.polygons))
whole = parts[0]; whole.name = "Inteiro"
for o in parts[1:]: boolean(whole, o, 'UNION')

# 2) corta, bolso, furos, argola
outline = [((r_at(t)*math.cos(t))*K*S, (r_at(t)*math.sin(t) - .06)*K*S + CY*S) for t in (2*math.pi*k/180 for k in range(180))]
front, back = dup(whole, "Metade_frente"), dup(whole, "Metade_tras")
boolean(front, cyl("cx", 0, 0, 80, 0, 40, 8), 'INTERSECT'); boolean(back, cyl("cx", 0, 0, 80, -40, 0, 8), 'INTERSECT')
boolean(back, prism("bolso", outline, -POCKET_DEPTH, 0.5), 'DIFFERENCE')
for x, y in PINS:
    boolean(front, cyl("furo", x, y, PIN_R, -0.5, PIN_DEPTH), 'DIFFERENCE')
    boolean(back, cyl("furo", x, y, PIN_R, -PIN_DEPTH, 0.5), 'DIFFERENCE')
for o, z0, z1 in ((front, 0, LOOP['t']), (back, -LOOP['t'], 0)):
    boolean(o, cyl("disco", LOOP['cx'], LOOP['cy'], LOOP['ro'], z0, z1), 'UNION')
    boolean(o, cyl("argola", LOOP['cx'], LOOP['cy'], LOOP['ri'], -6, 6), 'DIFFERENCE')
whole.hide_set(True)

# 3) grava os STL deitados (face lisa na mesa)
def write(obj, name, M):
    me = obj.data; me.calc_loop_triangles(); vs = [M @ v.co for v in me.vertices]; zmin = min(v.z for v in vs)
    with open(os.path.join(OUT, name + ".stl"), 'wb') as f:
        f.write(b'Eternal Beloved relicario (mm)'.ljust(80, b' ')); f.write(struct.pack('<I', len(me.loop_triangles)))
        for t in me.loop_triangles:
            a, b, c = (vs[i].copy() for i in t.vertices)
            for v in (a, b, c): v.z -= zmin
            n = (b - a).cross(c - a)
            if n.length: n.normalize()
            f.write(struct.pack('<12fH', n.x, n.y, n.z, a.x, a.y, a.z, b.x, b.y, b.z, c.x, c.y, c.z, 0))
write(front, "eternal-beloved-relicario-frente", Matrix.Identity(4))
write(back, "eternal-beloved-relicario-tras", Matrix.Rotation(math.pi, 4, 'X'))
