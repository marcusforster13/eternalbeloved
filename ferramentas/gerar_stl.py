"""Gera o STL do chaveiro Eternal Beloved (coração atravessado por flecha, com argola).

Mesma equação do coração usada no site. Unidades de saída: milímetros.
Uso:  python gerar_stl.py   ->  cria a pasta impressao/ e o zip para o site.
"""
import math, struct, zipfile, os

S = 16.0               # 1 unidade da cena = 16 mm  (coração ~ 36 mm de largura: chaveiro)
ARROW_L = 3.9          # comprimento do cabo, em unidades da cena (igual ao site)
SHAFT_R = 0.078        # cabo ~ 2,5 mm de diâmetro (resistente no tamanho de chaveiro)
FLETCH_T = 0.075       # penas ~ 1,2 mm de espessura
LOOP_R, LOOP_T, LOOP_Y = 0.2, 0.07, 1.14   # argola: furo ~4 mm, espessura ~2,2 mm
ROD_R = 4.0 / S        # haste de 8 mm (cabe no furo de um rolamento 608)
ADIR = (1.0, 0.42, 0.32)

# ---------------- utilidades de malha ----------------
def norm(v):
    l = math.sqrt(sum(c * c for c in v)); return tuple(c / l for c in v)
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

class Mesh:
    def __init__(self): self.v, self.t = [], []
    def add(self, other):
        o = len(self.v); self.v += other.v; self.t += [(a+o, b+o, c+o) for a, b, c in other.t]; return self
    def transform(self, M, T=(0, 0, 0)):
        self.v = [(M[0][0]*x+M[0][1]*y+M[0][2]*z+T[0], M[1][0]*x+M[1][1]*y+M[1][2]*z+T[1], M[2][0]*x+M[2][1]*y+M[2][2]*z+T[2]) for x, y, z in self.v]; return self
    def volume(self):
        s = 0.0
        for a, b, c in self.t:
            A, B, C = self.v[a], self.v[b], self.v[c]
            s += A[0]*(B[1]*C[2]-B[2]*C[1]) - A[1]*(B[0]*C[2]-B[2]*C[0]) + A[2]*(B[0]*C[1]-B[1]*C[0])
        return s / 6
    def outward(self):
        if self.volume() < 0: self.t = [(a, c, b) for a, b, c in self.t]
        return self
    def watertight(self):
        e = {}
        for a, b, c in self.t:
            for u, w in ((a, b), (b, c), (c, a)):
                k = (min(u, w), max(u, w)); e[k] = e.get(k, 0) + 1
        return all(n == 2 for n in e.values())

def rot_x(a): c, s = math.cos(a), math.sin(a); return ((1, 0, 0), (0, c, -s), (0, s, c))
def rot_z(a): c, s = math.cos(a), math.sin(a); return ((c, -s, 0), (s, c, 0), (0, 0, 1))
def scale(x, y, z): return ((x, 0, 0), (0, y, 0), (0, 0, z))
def mul(A, B): return tuple(tuple(sum(A[i][k]*B[k][j] for k in range(3)) for j in range(3)) for i in range(3))
def rot_from_x(d):
    d = norm(d); x = (1.0, 0.0, 0.0); v = cross(x, d); c = d[0]; s = math.sqrt(sum(k*k for k in v))
    if s < 1e-9: return ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    k = tuple(q / s for q in v); K = ((0, -k[2], k[1]), (k[2], 0, -k[0]), (-k[1], k[0], 0)); K2 = mul(K, K)
    return tuple(tuple((1 if i == j else 0) + s*K[i][j] + (1-c)*K2[i][j] for j in range(3)) for i in range(3))

def cylinder(r0, r1, h, n=48):           # ao longo de +y, de 0 a h, fechado
    m = Mesh()
    for y, r in ((0, r0), (h, r1)):
        for j in range(n): a = 2*math.pi*j/n; m.v.append((r*math.cos(a), y, r*math.sin(a)))
    m.v += [(0, 0, 0), (0, h, 0)]; cb, ct = 2*n, 2*n+1
    for j in range(n):
        a, b = j, (j+1) % n
        m.t += [(a, b, n+b), (a, n+b, n+a), (cb, b, a), (ct, n+a, n+b)]
    return m.outward()
def cone(r, h, n=4):
    m = Mesh()
    for j in range(n): a = 2*math.pi*j/n; m.v.append((r*math.cos(a), 0, r*math.sin(a)))
    m.v += [(0, 0, 0), (0, h, 0)]; cb, ap = n, n+1
    for j in range(n): a, b = j, (j+1) % n; m.t += [(cb, b, a), (a, b, ap)]
    return m.outward()
def prism(poly, t):
    m = Mesh(); n = len(poly)
    for z in (-t/2, t/2):
        for x, y in poly: m.v.append((x, y, z))
    cx = sum(p[0] for p in poly)/n; cy = sum(p[1] for p in poly)/n
    m.v += [(cx, cy, -t/2), (cx, cy, t/2)]; c0, c1 = 2*n, 2*n+1
    for j in range(n):
        a, b = j, (j+1) % n
        m.t += [(a, b, n+b), (a, n+b, n+a), (c0, b, a), (c1, n+a, n+b)]
    return m.outward()
def lathe(profile, n=128):                # perfil fechado (r, y) girado em torno de y
    m = Mesh(); k = len(profile)
    for j in range(n):
        a = 2*math.pi*j/n
        for r, y in profile: m.v.append((r*math.cos(a), y, r*math.sin(a)))
    for j in range(n):
        for i in range(k):
            a = j*k+i; b = j*k+(i+1) % k; c = ((j+1) % n)*k+i; d = ((j+1) % n)*k+(i+1) % k
            m.t += [(a, c, d), (a, d, b)]
    return m.outward()

def torus(R, r, nu=96, nv=32):                 # no plano XY (furo atravessa de frente para trás)
    m = Mesh()
    for i in range(nu):
        u = 2*math.pi*i/nu
        for j in range(nv):
            v = 2*math.pi*j/nv; m.v.append(((R + r*math.cos(v))*math.cos(u), (R + r*math.cos(v))*math.sin(u), r*math.sin(v)))
    for i in range(nu):
        for j in range(nv):
            a = i*nv+j; b = i*nv+(j+1) % nv; c = ((i+1) % nu)*nv+j; d = ((i+1) % nu)*nv+(j+1) % nv; m.t += [(a, c, d), (a, d, b)]
    return m.outward()

# ---------------- o coração (superfície implícita de Taubin) ----------------
def F(x, y, z): return x*x + 2.25*z*z + y*y - 1 - y*(x*x + 0.1125*z*z) ** (1/3)
def surf(dx, dy, dz):
    lo = hi = 0.0; r = 0.02
    while r < 2.5:
        if F(dx*r, dy*r, dz*r) > 0: hi, lo = r, r - 0.02; break
        r += 0.02
    if hi == 0: lo = hi = 1.0
    for _ in range(30):
        m = (lo+hi)/2
        if F(dx*m, dy*m, dz*m) > 0: hi = m
        else: lo = m
    r = (lo+hi)/2; return (dx*r, dy*r - 0.06, dz*r)
def heart(nlat=150, nlon=240):
    m = Mesh(); m.v.append(surf(0, 1, 0))
    for i in range(1, nlat):
        th = math.pi*i/nlat
        for j in range(nlon):
            ph = 2*math.pi*j/nlon; m.v.append(surf(math.sin(th)*math.cos(ph), math.cos(th), math.sin(th)*math.sin(ph)))
    m.v.append(surf(0, -1, 0)); bot = len(m.v)-1
    idx = lambda i, j: 1 + (i-1)*nlon + (j % nlon)
    for j in range(nlon): m.t.append((0, idx(1, j+1), idx(1, j)))
    for i in range(1, nlat-1):
        for j in range(nlon):
            a, b, c, d = idx(i, j), idx(i, j+1), idx(i+1, j), idx(i+1, j+1); m.t += [(a, b, d), (a, d, c)]
    for j in range(nlon): m.t.append((bot, idx(nlat-1, j), idx(nlat-1, j+1)))
    return m.outward()

# ---------------- a flecha (mesmas medidas do site) ----------------
def arrow():
    parts = []
    to_x = rot_z(-math.pi/2)                                     # +y -> +x
    parts.append(cylinder(SHAFT_R, SHAFT_R, ARROW_L).transform(to_x, (-ARROW_L/2, 0, 0)))
    head = cone(0.12, 0.44, 4).transform(scale(1, 1, 0.6)).transform(to_x, (ARROW_L/2 - 0.02, 0, 0))
    parts.append(head)
    parts.append(cylinder(0.09, 0.09, 0.1, 24).transform(to_x, (-ARROW_L/2 - 0.05, 0, 0)))
    # pena: alta atrás (junto ao encaixe), descendo em curva até a frente
    pts = [(0.08, 0.0), (0.0, 0.22)]
    for i in range(1, 12):
        t = i/11; pts.append((2*(1-t)*t*0.3 + t*t*0.62, (1-t)**2*0.22 + 2*(1-t)*t*0.22))
    for k in range(3):
        f = prism(pts, FLETCH_T).transform(((1, 0, 0), (0, 1, 0), (0, 0, 1)), (-ARROW_L/2, 0, 0)).transform(rot_x(k*2*math.pi/3))
        parts.append(f)
    m = Mesh()
    for p in parts: m.add(p)
    return m.transform(rot_from_x(ADIR))

# ---------------- montagem ----------------
def write_stl(path, m, title):
    with open(path, 'wb') as f:
        f.write(title.encode('ascii', 'replace')[:80].ljust(80, b' ')); f.write(struct.pack('<I', len(m.t)))
        for a, b, c in m.t:
            A, B, C = m.v[a], m.v[b], m.v[c]; n = cross(sub(B, A), sub(C, A)); l = math.sqrt(sum(k*k for k in n)) or 1
            f.write(struct.pack('<12fH', n[0]/l, n[1]/l, n[2]/l, *A, *B, *C, 0))

if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__)); out = os.path.join(here, 'impressao'); os.makedirs(out, exist_ok=True)
    for old in ('eternal-beloved-coracao-flecha.stl', 'eternal-beloved-base.stl'):
        if os.path.exists(os.path.join(out, old)): os.remove(os.path.join(out, old))
    H = heart(); A = arrow()
    L = torus(LOOP_R, LOOP_T).transform(((1, 0, 0), (0, 1, 0), (0, 0, 1)), (0, LOOP_Y, 0))
    shells = [('coracao', H), ('flecha', A), ('argola', L)]
    for name, m in shells: print(name, 'fechada' if m.watertight() else 'ABERTA', len(m.t), 'triângulos')
    piece = Mesh()
    for _, m in shells: piece.add(m)
    piece.transform(scale(S, S, S))
    p1 = os.path.join(out, 'eternal-beloved-chaveiro.stl')
    write_stl(p1, piece, 'Eternal Beloved - chaveiro (mm)')
    xs = [v[0] for v in piece.v]; ys = [v[1] for v in piece.v]; zs = [v[2] for v in piece.v]
    dims = (max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)); print('chaveiro (mm): %.0f x %.0f x %.0f' % dims)
    leia = f"""ETERNAL BELOVED - chaveiro para impressão 3D (unidades em milímetros)

eternal-beloved-chaveiro.stl
   Coração atravessado pela flecha (penas atrás, ponta na frente), com argola no topo.
   Tamanho aproximado: {dims[0]:.0f} x {dims[1]:.0f} x {dims[2]:.0f} mm.
   São três sólidos fechados que se cruzam (coração, flecha, argola); o fatiador junta tudo numa peça só.

COMO IMPRIMIR
   - Resina (melhor detalhe) ou FDM com bico 0,4 mm e camada 0,12-0,16 mm.
   - Use suportes em árvore: a flecha fica em balanço dos dois lados.
   - Preenchimento 20-30% e 3 paredes, para a argola e o cabo da flecha aguentarem o uso.
   - Furo da argola: ~4 mm. Passe uma argola de chaveiro de metal (25-30 mm).

CORES
   No site: coração rosa, cabo preto, ponta cromada, penas azuis.
   Em FDM dá para pintar depois, ou pausar a impressão e trocar o filamento.

ESCALA
   1 unidade do site = {S:.0f} mm. Para aumentar, escale no fatiador; abaixo de 90% o cabo fica frágil.
"""
    with open(os.path.join(out, 'LEIA-ME.txt'), 'w', encoding='utf-8') as fh: fh.write(leia)
    z = os.path.join(here, 'eternal-beloved-stl.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in (p1, os.path.join(out, 'LEIA-ME.txt')): zf.write(p, os.path.basename(p))
    import base64
    open(os.path.join(here, 'eternal-beloved-stl.b64.txt'), 'w').write(base64.b64encode(open(z, 'rb').read()).decode())
    print('zip', os.path.getsize(z) // 1024, 'KB')
