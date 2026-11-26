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
    """resolve a cadeia de 'inherits' dos perfis de sistema e os 'include' (é neles que ficam o
    G-code oficial de início/fim/troca de camada da P1S: nivelamento, aquecimento, linha de purga)"""
    d = load(kind, name); chain = [d]
    while d.get("inherits"):
        d = load(kind, d["inherits"]); chain.append(d)
    out = {}
    for d in reversed(chain):
        for inc in d.get("include", []):
            out.update({k: v for k, v in load(kind, inc).items() if k not in ("name", "instantiation", "from", "type")})
        out.update(d)
    for k in ("inherits", "include"): out.pop(k, None)
    out["from"] = "system"; out["name"] = name
    return out

machine = flatten("machine", "Bambu Lab P1S 0.4 nozzle")
filament = flatten("filament", "Generic PLA High Speed @BBL P1P")   # PLA de alta velocidade (o perfil da P1P serve na P1S)
filament["compatible_printers"] = ["Bambu Lab P1S 0.4 nozzle"]
# caixa do filamento: bico 195-220 °C, mesa 50-65 °C. No perfil lento de qualidade máxima o fluxo é baixo,
# então 210 °C dá detalhe mais nítido e menos fiapo; a primeira camada fica em 220 °C para grudar bem.
filament["nozzle_temperature"] = ["210"]
filament["nozzle_temperature_initial_layer"] = ["220"]
base_process = flatten("process", "0.08mm High Quality @BBL P1P")   # qualidade máxima: camada 0,08, parede externa a 60 mm/s
base_process["compatible_printers"] = ["Bambu Lab P1S 0.4 nozzle"]

COMMON = {
    "wall_loops": "3",
    "sparse_infill_density": "25%",
    "elefant_foot_compensation": "0.15",      # (grafia do próprio Bambu Studio)
    "elephant_foot_compensation": "0.15",
    "seam_position": "back",
    "curr_bed_type": "Textured PEI Plate",   # a placa que vem com a P1S
}
PLATES = [
    # peças pequenas saem em dobro: uma de reserva (e a ponta esfria melhor entre uma camada e outra)
    # nome, cor, arquivos, ajustes
    ("1-ROSA-coracao", "rosa", ["1-rosa-coracao-frente.stl", "1-rosa-coracao-tras.stl"],
     # sem suporte: o domo cresce para dentro e os bolsos (foto e ímãs) ficam virados para a mesa, onde
     # o suporte ficaria preso lá dentro; o teto deles é feito em ponte
     {"enable_support": "0", "brim_type": "no_brim"}),
    ("2-PRETO-hastes", "preto", ["2-preto-haste-frente.stl", "2-preto-haste-tras.stl"] * 2,
     {"enable_support": "0", "brim_type": "outer_only", "brim_width": "3"}),
    ("3-BRANCO-ponta", "branco", ["3-branco-ponta.stl"] * 2,
     {"enable_support": "0", "brim_type": "outer_only", "brim_width": "3"}),
    ("4-AZUL-penas", "azul", ["4-azul-penas.stl"] * 2,
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
    if ok:  # o CLI deixa o código do modelo vazio; o Bambu Studio grava "C12" para a P1S. Igual ao fatiado na tela.
        tmp = out3mf + ".tmp"
        with zipfile.ZipFile(out3mf) as zi, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
            for it in zi.infolist():
                data = zi.read(it.filename)
                if it.filename == "Metadata/slice_info.config":
                    data = data.replace(b'key="printer_model_id" value=""', b'key="printer_model_id" value="C12"')
                zo.writestr(it, data)
        os.replace(tmp, out3mf)
    results[name] = {"ok": ok, "codigo": r.returncode, **(summary(out3mf) if ok else {}),
                     "erro": "" if ok else (r.stdout[-1500:] + r.stderr[-1500:])}
print(json.dumps(results, indent=1, ensure_ascii=False))
