#!/usr/bin/env python3
"""
builder.py — Cria circuitos Proteus a partir de um JSON com netlist tabular.

Formato de entrada (schema.json):
  components[]  — lista de componentes { ref, part, value }
  netlist[]     — tabela pino→net:  { ref, pin, net }
  power_nets{}  — { "VCC": 5, "GND": 0 }

Fluxo:
  1. Parts bin via Pick Devices (ui_act)
  2. Placement topológico (BFS do componente mais conectado)
  3. Terminais POWER/GROUND nas nets de alimentação
  4. Terminais DEFAULT (net labels) em cada pino de sinal
  5. schematic_route_nets para desenhar os stubs pino→label
  6. Salva

Uso:
    python builder.py circuito.json
"""

import sys, json, time, urllib.request, urllib.error, argparse

MCP_URL = "http://localhost:8001"

# ---------------------------------------------------------------------------
# Configuração de busca no Pick Devices
# ---------------------------------------------------------------------------
PART_SEARCH_CONFIG = {
    "RES":       ("Generic resistor symbol",   0),
    "CAP":       ("Generic capacitor",         0),
    "CAP-ELEC":  ("Electrolytic capacitor",    0),
    "LED":       ("Light emitting diode",      0),
    "BATTERY":   ("DC Voltage Source",        26),
    "NE555":     ("NE555",                     0),
    "BC547":     ("BC547",                     0),
    "BC557":     ("BC557",                     0),
    "LM741":     ("LM741",                     0),
    "LM358":     ("LM358",                     0),
    "DIODE":     ("Generic signal diode",      0),
    "ZENER":     ("Generic zener diode",       0),
    "SW-SPST":   ("Single pole single throw",  0),
    "POT-HG":        ("Variable resistor",         0),
    "INDUCTOR":      ("Generic inductor",          0),
    "ARDUINO-UNO":   ("ARDUINO UNO",               0),
    "ARDUINO-MINI":  ("ARDUINO MINI",              0),
    "ARDUINO-MEGA":  ("ARDUINO MEGA 2560",         0),
}

# ---------------------------------------------------------------------------
# Geometria dos símbolos Proteus (thou)
# Usada para:
#   · Calcular espaçamento no placement (cell = maior dim + gap)
#   · Estimar posição dos net labels relativos ao centro do componente
#
# pin_side:  "h" = pinos nas laterais esq/dir (ICs, resistores horizontais)
#            "v" = pinos em cima/baixo (capacitores, LEDs, baterias)
# ---------------------------------------------------------------------------
PART_GEOM = {
    "NE555":    {"w": 700,  "h": 1100, "side": "h"},
    "LM741":    {"w": 700,  "h": 1100, "side": "h"},
    "LM358":    {"w": 700,  "h": 900,  "side": "h"},
    "BC547":    {"w": 400,  "h": 600,  "side": "h"},
    "BC557":    {"w": 400,  "h": 600,  "side": "h"},
    "RES":      {"w": 500,  "h": 100,  "side": "h"},
    "INDUCTOR": {"w": 500,  "h": 100,  "side": "h"},
    "CAP":      {"w": 100,  "h": 400,  "side": "v"},
    "CAP-ELEC": {"w": 100,  "h": 400,  "side": "v"},
    "LED":      {"w": 200,  "h": 500,  "side": "v"},
    "DIODE":    {"w": 200,  "h": 400,  "side": "v"},
    "ZENER":    {"w": 200,  "h": 400,  "side": "v"},
    "BATTERY":  {"w": 200,  "h": 600,  "side": "v"},
    "SW-SPST":       {"w": 500,  "h": 200,  "side": "h"},
    "POT-HG":        {"w": 300,  "h": 500,  "side": "h"},
    "ARDUINO-UNO":   {"w": 900,  "h": 1400, "side": "h"},
    "ARDUINO-MINI":  {"w": 500,  "h": 1200, "side": "h"},
    "ARDUINO-MEGA":  {"w": 900,  "h": 2200, "side": "h"},
}
_GEOM_DEFAULT = {"w": 400, "h": 300, "side": "h"}

_LABEL_GAP = 120   # thou do bounding-box até o label


# ---------------------------------------------------------------------------
# Utilitário JSON-RPC
# ---------------------------------------------------------------------------
def call(tool_name, args, timeout=20):
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method":  "tools/call",
        "params":  {"name": tool_name, "arguments": args},
        "id": 1,
    }).encode()
    req = urllib.request.Request(
        MCP_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
    except urllib.error.URLError as e:
        raise RuntimeError(f"MCP inacessível (localhost:8001): {e}") from e
    if "error" in result:
        raise RuntimeError(f"MCP erro: {result['error']}")
    text = result["result"]["content"][0].get("text", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def get_status():
    r = call("get_current_status", {})
    s = r["data"]["status"]["schematic"]
    return s["current_design_id"], s["current_sheet_id"]


def list_parts_bin(design_id):
    r = call("schematic_list_parts_bin", {"id": design_id})
    return {item["name"] for item in r["data"]["contents"]}


# ---------------------------------------------------------------------------
# Parts bin via Pick Devices
# ---------------------------------------------------------------------------
def _find_in_tree(node, obj_name):
    if not isinstance(node, dict):
        return None
    if node.get("object_name") == obj_name:
        return node
    for child in node.get("children", []):
        found = _find_in_tree(child, obj_name)
        if found:
            return found
    return None


def add_to_parts_bin(part_name, design_id):
    if part_name in list_parts_bin(design_id):
        print(f"  ✓ {part_name} já no parts bin")
        return True

    kw, cat = PART_SEARCH_CONFIG.get(part_name, (part_name, 0))
    print(f"  → Adicionando '{part_name}' (busca: '{kw}')...")

    call("command_invoke", {"cmd_id": 336913})
    time.sleep(1.5)
    dlg_id = call("ui_last_dialog", {})["data"]["active_modal"]["id"]

    try:
        call("ui_act", {"window": dlg_id, "name": "wholeWordsCheck", "value": "false"})
        call("ui_act", {"window": dlg_id, "name": "managedCheck",    "value": "false"})
        if cat > 0:
            call("ui_act", {"window": dlg_id, "name": "catList",
                            "property": "currentRow", "value": str(cat)})
            time.sleep(0.4)
        call("ui_act", {"window": dlg_id, "name": "keywordsEdit", "value": kw})
        time.sleep(1.0)

        r   = call("ui_describe", {"id": dlg_id, "depth": "full"})
        ctrl = _find_in_tree(r.get("data", {}), "resList")
        if ctrl is None:
            raise RuntimeError("'resList' não encontrado")

        iv   = ctrl.get("item_view", {})
        rows = iv.get("rows", 0)
        if rows == 0:
            raise RuntimeError(f"Sem resultados para '{kw}'")

        target = 0
        for i, item in enumerate(iv.get("items", [])):
            if item.get("cells", [None])[0] == part_name:
                target = i
                break

        print(f"    {rows} resultado(s) → linha {target}")
        call("ui_act", {"id": ctrl["id"], "property": "currentRow", "value": str(target)})
        time.sleep(0.3)
        call("ui_answer_dialog", {"id": dlg_id, "answer": "Ok"})
        time.sleep(0.5)

        if part_name in list_parts_bin(design_id):
            print(f"  ✓ '{part_name}' adicionado")
            return True
        print(f"  ✗ '{part_name}' não apareceu no parts bin")
        return False

    except Exception as e:
        print(f"  ✗ Erro: {e}")
        try:
            call("ui_answer_dialog", {"id": dlg_id, "answer": "Cancel"})
        except Exception:
            pass
        return False


# ---------------------------------------------------------------------------
# Placement topológico
# ---------------------------------------------------------------------------
def build_topology(components, net_map):
    """
    net_map: dict net_name -> list[(ref, pin)]

    Retorna dict ref -> (x, y) com placement BFS a partir do componente
    de maior grau de conectividade.
    """
    refs   = [c["ref"]  for c in components]
    parts  = {c["ref"]: c["part"] for c in components}

    # Grau: pares de refs que compartilham uma net
    pair_w: dict[tuple, int] = {}
    for pins in net_map.values():
        refs_in_net = list({r for r, _ in pins})
        for i in range(len(refs_in_net)):
            for j in range(i + 1, len(refs_in_net)):
                key = (min(refs_in_net[i], refs_in_net[j]),
                       max(refs_in_net[i], refs_in_net[j]))
                pair_w[key] = pair_w.get(key, 0) + 1

    degree = {r: 0 for r in refs}
    for (a, b), w in pair_w.items():
        degree[a] += w
        degree[b] += w

    def cell(ref):
        g = PART_GEOM.get(parts.get(ref, ""), _GEOM_DEFAULT)
        return max(g["w"], g["h"]) + 700   # espaçamento mínimo

    DIRS = [(1,0),(0,-1),(-1,0),(0,1),(1,-1),(-1,-1),(1,1),(-1,1)]
    X0, Y0 = 4000, 9000
    pos: dict[str, tuple] = {}
    visited: set[str] = set()

    anchor = max(refs, key=lambda r: degree.get(r, 0))
    pos[anchor] = (X0, Y0)
    visited.add(anchor)

    queue = [anchor]
    dir_idx = 0
    while queue:
        cur = queue.pop(0)
        cx, cy = pos[cur]
        cs = cell(cur)

        # Vizinhos não visitados, ordenados por peso
        nbrs = sorted(
            [(r, pair_w.get((min(cur,r), max(cur,r)), 0))
             for r in refs if r not in visited],
            key=lambda x: -x[1]
        )
        nbrs = [r for r, w in nbrs if w > 0]

        for nbr in nbrs:
            if nbr in visited:
                continue
            ns   = cell(nbr)
            step = max(cs, ns)
            placed = False
            for attempt in range(len(DIRS)):
                dx, dy = DIRS[(dir_idx + attempt) % len(DIRS)]
                nx, ny = cx + dx * step, cy + dy * step
                if not any(
                    abs(px - nx) < step * 0.75 and abs(py - ny) < step * 0.75
                    for px, py in pos.values()
                ):
                    pos[nbr] = (nx, ny)
                    visited.add(nbr)
                    queue.append(nbr)
                    dir_idx = (dir_idx + 1) % len(DIRS)
                    placed = True
                    break
            if not placed:
                fx = max(px for px, _ in pos.values()) + cs
                pos[nbr] = (fx, Y0)
                visited.add(nbr)
                queue.append(nbr)

    # Componentes sem conexão
    x_cur = X0
    for ref in refs:
        if ref not in pos:
            x_cur += 1200
            pos[ref] = (x_cur, Y0 - 2500)

    return pos


def place_components(design_id, sheet_id, components, positions):
    print("Posicionando componentes:")
    for comp in components:
        ref  = comp["ref"]
        part = comp["part"]
        val  = comp.get("value", "")
        x, y = positions[ref]
        r = call("schematic_place_device", {
            "id": design_id, "sheet": sheet_id,
            "name": part, "reference": ref, "value": val,
            "x": int(x), "y": int(y),
        })
        overlaps = r.get("data", {}).get("overlaps", [])
        if overlaps:
            print(f"  ⚠  {ref} ({part}) → ({int(x)},{int(y)})  "
                  f"sobrepõe {[o['ref'] for o in overlaps]}")
        else:
            print(f"  ✓  {ref} ({part}={val}) → ({int(x)},{int(y)})")


# ---------------------------------------------------------------------------
# Net labels
# ---------------------------------------------------------------------------
def _label_xy(cx, cy, part, idx, total, side_hint=None):
    """
    Calcula (lx, ly) para o net label do pino `idx` de um componente em (cx, cy).
    Distribui os labels ao redor do símbolo evitando sobreposição.
    """
    g    = PART_GEOM.get(part, _GEOM_DEFAULT)
    side = side_hint or g["side"]
    hw   = g["w"] // 2 + _LABEL_GAP
    hh   = g["h"] // 2 + _LABEL_GAP

    # Alternamos entre dois lados (esq/dir para "h", cima/baixo para "v")
    # e deslocamos verticalmente (ou horizontalmente) para espalhar
    spacing = 150
    half    = max(total // 2, 1)
    offset  = (idx // 2 - (half - 1) / 2) * spacing

    if side == "h":
        dx = -hw if idx % 2 == 0 else hw
        dy = int(offset)
    else:
        dy = -hh if idx % 2 == 0 else hh
        dx = int(offset)

    return int(cx + dx), int(cy + dy)


def place_net_labels(design_id, sheet_id, netlist, components, positions, power_nets):
    """
    Para cada pino na tabela netlist, coloca um terminal com o nome da rede.
      · POWER  → redes de alimentação positiva
      · GROUND → redes de terra
      · DEFAULT → sinais
    Não precisa de fio — pinos com o mesmo nome de rede ficam conectados.
    """
    parts_map = {c["ref"]: c["part"] for c in components}

    # Conta quantos pinos cada componente tem para distribuir offsets
    pin_count: dict[str, int] = {}
    for row in netlist:
        pin_count[row["ref"]] = pin_count.get(row["ref"], 0) + 1

    # Índice sequencial por componente (para o offset)
    pin_idx: dict[str, int] = {}

    ok = 0
    fail = 0
    print("Colocando net labels:")
    for row in netlist:
        ref  = row["ref"]
        pin  = row["pin"]
        net  = row["net"]
        cx, cy = positions.get(ref, (4000, 9000))
        part   = parts_map.get(ref, "")
        idx    = pin_idx.get(ref, 0)
        total  = pin_count.get(ref, 1)
        pin_idx[ref] = idx + 1

        if net in power_nets:
            term = "POWER" if power_nets[net] != 0 else "GROUND"
        else:
            term = "DEFAULT"

        lx, ly = _label_xy(cx, cy, part, idx, total)

        try:
            call("schematic_place_terminal", {
                "id": design_id, "sheet": sheet_id,
                "terminal": term, "label": net,
                "x": lx, "y": ly,
            })
            ok += 1
            print(f"  ✓  {ref}.{pin} [{net}] ({term}) → ({lx},{ly})")
        except Exception as e:
            fail += 1
            print(f"  ✗  {ref}.{pin} [{net}]: {e}")

    # Âncoras de alimentação (símbolo central de VCC/GND)
    anchors = {"VCC": (1800, 10600), "GND": (1800, 7400)}
    for net, voltage in power_nets.items():
        if net not in anchors:
            continue
        ax, ay = anchors[net]
        ttype  = "POWER" if voltage != 0 else "GROUND"
        try:
            call("schematic_place_terminal", {
                "id": design_id, "sheet": sheet_id,
                "terminal": ttype, "label": net,
                "x": ax, "y": ay,
            })
            print(f"  ✓  Âncora {ttype}:{net} → ({ax},{ay})")
        except Exception as e:
            print(f"  ⚠  Âncora {net}: {e}")

    print(f"\n  Totais: {ok} OK  {fail} falhou")
    return ok, fail


# ---------------------------------------------------------------------------
# Roteamento (conecta pinos aos labels próximos)
# ---------------------------------------------------------------------------
def route_all_nets(design_id, sheet_id, net_map, power_nets):
    """
    Chama schematic_route_nets para todas as redes.
    · Redes de alimentação: rota pino → terminal POWER/GROUND (funciona sempre)
    · Redes de sinal: rota pino → pino direto (funciona se placement é compacto)
      Se falhar, o net label DEFAULT garante a conectividade no simulador.
    """
    nets_out = []
    for net_name, pins in net_map.items():
        unique_pins = list({(r, p) for r, p in pins})
        if net_name in power_nets:
            ttype = "POWER" if power_nets[net_name] != 0 else "GROUND"
            entry = {
                "name": net_name,
                "pins": [{"ref": r, "name": p} for r, p in unique_pins],
                "terminals": [{"ref": ttype, "name": net_name}],
            }
        else:
            # Direto pino-a-pino; se falhar o DEFAULT label já está no schematic
            entry = {
                "name": net_name,
                "pins": [{"ref": r, "name": p} for r, p in unique_pins],
            }
        nets_out.append(entry)

    if not nets_out:
        return

    r = call("schematic_route_nets", {
        "id": design_id, "sheet": sheet_id,
        "max_corners": 4, "nets": nets_out,
    })
    s = r.get("data", {}).get("summary", {})
    print(f"  Roteamento — OK: {s.get('routed',0)}  "
          f"Parcial: {s.get('partial',0)}  Falhou: {s.get('failed',0)}")

    failed = r.get("data", {}).get("failed_nets", [])
    if failed:
        names = [n.get("name","?") for n in failed]
        print(f"  ⚠  Não roteadas (serão conectadas via net label): {names}")


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------
def build_circuit(json_path):
    print(f"\n{'='*52}")
    print(f" MCP Builder — Proteus Circuit Builder")
    print(f"{'='*52}")
    print(f" Arquivo: {json_path}\n")

    with open(json_path, encoding="utf-8") as f:
        circuit = json.load(f)

    # Aceita tanto o formato novo (netlist[]) quanto o antigo (wires[])
    if "netlist" in circuit:
        netlist = circuit["netlist"]
        # Constrói net_map a partir da tabela
        net_map: dict[str, list] = {}
        for row in netlist:
            net_map.setdefault(row["net"], []).append((row["ref"], row["pin"]))
    elif "wires" in circuit:
        # Compatibilidade retroativa com wires[]
        wires   = circuit["wires"]
        netlist = []
        net_map = {}
        seen: set[tuple] = set()
        for wire in wires:
            net = wire.get("net")
            if not net:
                continue
            for ep in (wire["from"], wire["to"]):
                key = (ep["ref"], ep["pin"])
                if key not in seen:
                    seen.add(key)
                    netlist.append({"ref": ep["ref"], "pin": ep["pin"], "net": net})
                net_map.setdefault(net, []).append((ep["ref"], ep["pin"]))
    else:
        print("✗ JSON não tem 'netlist' nem 'wires'")
        return False

    power_nets = circuit.get("power_nets", {})
    components = circuit["components"]

    print(f" Circuito: {circuit['name']}")
    print(f" Desc: {circuit.get('description','')}")
    print(f" Componentes: {len(components)}  "
          f"Pinos: {len(netlist)}  Nets: {len(net_map)}\n")

    design_id, sheet_id = get_status()
    print(f" Design: {design_id}  Sheet: {sheet_id}\n")

    # ── 1. Parts bin ──────────────────────────────────────────────────────
    print("─── 1. Parts bin ───")
    needed  = {c["part"] for c in components}
    missing = needed - list_parts_bin(design_id)
    if missing:
        print(f"Faltando: {missing}")
        for part in sorted(missing):
            add_to_parts_bin(part, design_id)
    else:
        print("Todas as partes já estão no parts bin ✓")

    still_missing = needed - list_parts_bin(design_id)
    if still_missing:
        print(f"\n✗ Ainda faltam: {still_missing}  — abortando")
        return False

    # ── 2. Placement topológico ───────────────────────────────────────────
    print("\n─── 2. Placement topológico ───")
    positions = build_topology(components, net_map)

    print(" Layout:")
    for ref, (x, y) in sorted(positions.items()):
        print(f"   {ref}: ({int(x)},{int(y)})")

    call("schematic_begin_transaction", {"id": design_id})
    print("\nTransação iniciada")

    try:
        place_components(design_id, sheet_id, components, positions)

        # ── 3. Net labels ─────────────────────────────────────────────────
        print("\n─── 3. Net labels (conectores virtuais) ───")
        place_net_labels(
            design_id, sheet_id,
            netlist, components, positions, power_nets,
        )

        # ── 4. Roteamento ─────────────────────────────────────────────────
        print("\n─── 4. Roteamento ───")
        route_all_nets(design_id, sheet_id, net_map, power_nets)

        # ── 5. Commit ─────────────────────────────────────────────────────
        r = call("schematic_end_transaction", {"id": design_id, "auto_nudge": True})
        fouls = r.get("data", {}).get("block_placement", {}).get("fouls", [])
        if fouls:
            print(f"\n⚠  Sobreposições: {[f['ref'] for f in fouls]}")
        print("\nTransação finalizada ✓")

        call("file_save", {})
        print(f"\n✓ '{circuit['name']}' criado com sucesso!")
        return True

    except Exception as e:
        print(f"\n✗ Erro: {e}")
        try:
            call("schematic_end_transaction", {"id": design_id, "abandon": True})
        except Exception:
            pass
        return False


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Cria circuitos Proteus a partir de JSON (netlist tabular)"
    )
    ap.add_argument("json_file", help="Arquivo JSON do circuito")
    args = ap.parse_args()
    sys.exit(0 if build_circuit(args.json_file) else 1)


if __name__ == "__main__":
    main()
