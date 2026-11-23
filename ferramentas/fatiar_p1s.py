"""Fatia as peças do Eternal Beloved para a Bambu Lab P1S (bico 0,4) usando o Bambu Studio instalado.

Gera um .gcode.3mf por cor, pronto para mandar imprimir (Wi-Fi pelo Bambu Studio ou cartão microSD).
Uso:  python fatiar_p1s.py
"""
import json, os, subprocess, sys, zipfile, re

STUDIO = r"C:\Program Files\Bambu Studio\bambu-studio.exe"
BBL = r"C:\Program Files\Bambu Studio\resources\profiles\BBL"
HERE = os.path.dirname(os.path.abspath(__file__))
PECAS = os.path.join(HERE, "impressao", "pecas")
OUT = os.path.join(HERE, "impressao", "pronto-para-imprimir")
TMP = os.path.join(HERE, "impressao", "_perfis")
os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)

def load(kind, name):
    with open(os.path.join(BBL, kind, name + ".json"), encoding="utf-8") as f: return json.load(f)

def flatten(kind, name):
    """resolve a cadeia de 'inherits' dos perfis de sistema"""
    d = load(kind, name); chain = [d]
    while d.get("inherits"):
        d = load(kind, d["inherits"]); chain.append(d)
    out = {}
    for d in reversed(chain): out.update(d)
    out.pop("inherits", None); out["from"] = "system"; out["name"] = name
    return out

machine = flatten("machine", "Bambu Lab P1S 0.4 nozzle")
filament = flatten("filament", "Bambu PLA Basic @BBL P1S 0.4 nozzle")
base_process = flatten("process", "0.12mm Fine @BBL P1P")
base_process["compatible_printers"] = ["Bambu Lab P1S 0.4 nozzle"]

COMMON = {
    "wall_loops": "3",
    "sparse_infill_density": "25%",
    "elefant_foot_compensation": "0.15",      # (grafia do próprio Bambu Studio)
    "elephant_foot_compensation": "0.15",
    "seam_position": "back",
}
PLATES = [
    # nome, cor, arquivos, ajustes
    ("1-ROSA-coracao", "rosa", ["1-rosa-coracao-frente.stl", "1-rosa-coracao-tras.stl"],
     {"enable_support": "1", "support_type": "tree(auto)", "support_on_build_plate_only": "1", "support_threshold_angle": "40"}),
    ("2-PRETO-hastes", "preto", ["2-preto-haste-frente.stl", "2-preto-haste-tras.stl"],
     {"enable_support": "0", "brim_type": "outer_only", "brim_width": "3"}),
    ("3-BRANCO-ponta", "branco", ["3-branco-ponta.stl"],
     {"enable_support": "0", "brim_type": "outer_only", "brim_width": "3"}),
    ("4-AZUL-penas", "azul", ["4-azul-penas.stl"],
     {"enable_support": "0", "brim_type": "outer_only", "brim_width": "3"}),
]

def write(path, d):
    with open(path, "w", encoding="utf-8") as f: json.dump(d, f, indent=1, ensure_ascii=False)

def summary(gcode3mf):
    """lê tempo e filamento do gcode dentro do .gcode.3mf"""
    info = {}
    with zipfile.ZipFile(gcode3mf) as z:
        g = [n for n in z.namelist() if n.endswith(".gcode")]
        if not g: return info
        head = z.read(g[0])[:200000].decode("utf-8", "ignore")
        for key, pat in (("tempo", r"model printing time: ([^;\n]+)"), ("tempo_total", r"total estimated time: ([^;\n]+)"),
                         ("filamento_g", r"total filament weight \[g\] : ([\d.]+)"), ("filamento_m", r"total filament length \[mm\] : ([\d.]+)"),
                         ("camadas", r"total layer number: (\d+)")):
            m = re.search(pat, head)
            if m: info[key] = m.group(1).strip()
        info["linhas_de_suporte"] = head.count("; FEATURE: Support") + z.read(g[0]).decode("utf-8", "ignore").count("; FEATURE: Support")
    return info

machine_path = os.path.join(TMP, "maquina.json"); write(machine_path, machine)
filament_path = os.path.join(TMP, "filamento.json"); write(filament_path, filament)
results = {}
HEX = {"rosa": "#FF5FA2", "preto": "#1A1A1A", "branco": "#F5F5F2", "azul": "#1F5BFF"}
for name, color, files, tweaks in PLATES:
    fil = dict(filament); fil["filament_colour"] = [HEX[color]]
    filament_path = os.path.join(TMP, f"filamento-{color}.json"); write(filament_path, fil)
    proc = dict(base_process); proc.update(COMMON); proc.update(tweaks); proc["name"] = "Eternal Beloved " + color
    proc_path = os.path.join(TMP, f"processo-{color}.json"); write(proc_path, proc)
    out3mf = os.path.join(OUT, name + ".gcode.3mf")
    if os.path.exists(out3mf): os.remove(out3mf)
    cmd = [STUDIO, "--debug", "2", "--orient", "0", "--arrange", "1", "--slice", "0",
           "--load-settings", f"{machine_path};{proc_path}", "--load-filaments", filament_path,
           "--export-3mf", out3mf] + [os.path.join(PECAS, f) for f in files]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    ok = os.path.exists(out3mf)
    results[name] = {"ok": ok, "codigo": r.returncode, **(summary(out3mf) if ok else {}),
                     "erro": "" if ok else (r.stdout[-1500:] + r.stderr[-1500:])}
print(json.dumps(results, indent=1, ensure_ascii=False))
