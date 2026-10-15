#!/usr/bin/env python3
"""
builder.py — Cria circuitos Proteus automaticamente a partir de um arquivo JSON.
Usa o servidor MCP nativo do Proteus ProPilot via JSON-RPC 2.0.

Uso:
    python builder.py caminho/para/circuito.json
"""

import sys
import json
import time
import urllib.request
import urllib.error
import argparse

MCP_URL = "http://localhost:8001"

# Mapeamento: nome do part -> (keyword de busca, índice de categoria)
# Índice 0 = (All Categories), 26 = Simulator Primitives, 3 = Analog ICs
PART_SEARCH_CONFIG = {
    "RES":      ("Generic resistor symbol",   0),
    "CAP":      ("Generic capacitor",         0),
    "CAP-ELEC": ("Electrolytic capacitor",    0),
    "LED":      ("Light emitting diode",      0),
    "BATTERY":  ("DC Voltage Source",        26),
    "NE555":    ("NE555",                     0),
}


# ---------------------------------------------------------------------------
# Utilitário JSON-RPC
# ---------------------------------------------------------------------------

def call(tool_name, args, timeout=15):
    """Chama uma ferramenta MCP e retorna o resultado como dict Python."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": args},
        "id": 1,
    }).encode()
    req = urllib.request.Request(
        MCP_URL, data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
    except urllib.error.URLError as e:
        raise RuntimeError(f"Erro ao conectar ao MCP (localhost:8001): {e}") from e

    if "error" in result:
        raise RuntimeError(f"MCP erro: {result['error']}")

    content = result["result"]["content"][0]
    text = content.get("text", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


# ---------------------------------------------------------------------------
# Helpers Proteus
# ---------------------------------------------------------------------------

def get_status():
    """Retorna (design_id, sheet_id) do projeto aberto."""
    r = call("get_current_status", {})
    s = r["data"]["status"]["schematic"]
    return s["current_design_id"], s["current_sheet_id"]


def list_parts_bin(design_id):
    """Retorna set de nomes de partes no parts bin."""
    r = call("schematic_list_parts_bin", {"id": design_id})
    return {item["name"] for item in r["data"]["contents"]}


# ---------------------------------------------------------------------------
# Adicionar partes ao parts bin via Pick Devices
# ---------------------------------------------------------------------------

def _open_pick_devices():
    """Abre o diálogo Pick Devices e retorna seu id."""
    call("command_invoke", {"cmd_id": 336913})
    time.sleep(1.5)
    r = call("ui_last_dialog", {})
    return r["data"]["active_modal"]["id"]


def _find_control_in_tree(node, obj_name):
    """Busca recursivamente um controle pelo objectName (usa 'children' do Proteus MCP)."""
    if not isinstance(node, dict):
        return None
    if node.get("object_name") == obj_name:
        return node
    # O Proteus MCP usa a chave "children" para filhos de widgets
    for child in node.get("children", []):
        found = _find_control_in_tree(child, obj_name)
        if found:
            return found
    return None


def add_to_parts_bin(part_name, design_id):
    """
    Adiciona um componente ao parts bin via diálogo Pick Devices.
    Usa window+objectName (sem IDs hardcoded) para máxima robustez.
    """
    if part_name in list_parts_bin(design_id):
        print(f"  ✓ {part_name} já está no parts bin")
        return True

    search_keyword, cat_idx = PART_SEARCH_CONFIG.get(part_name, (part_name, 0))
    print(f"  → Adicionando '{part_name}' (busca: '{search_keyword}')...")

    dlg_id = _open_pick_devices()

    try:
        # Desabilita filtros restritivos
        call("ui_act", {"window": dlg_id, "name": "wholeWordsCheck", "value": "false"})
        call("ui_act", {"window": dlg_id, "name": "managedCheck",    "value": "false"})

        # Define categoria (se != All Categories)
        if cat_idx > 0:
            call("ui_act", {"window": dlg_id, "name": "catList",
                            "property": "currentRow", "value": str(cat_idx)})
            time.sleep(0.4)

        # Define keyword de busca
        call("ui_act", {"window": dlg_id, "name": "keywordsEdit", "value": search_keyword})
        time.sleep(1.0)  # aguarda tabela atualizar

        # Obtém a tabela de resultados via describe
        r = call("ui_describe", {"id": dlg_id, "depth": "full"})
        res_ctrl = _find_control_in_tree(r.get("data", {}), "resList")

        if res_ctrl is None:
            raise RuntimeError(f"Controle 'resList' não encontrado no dialog {dlg_id}")

        iv = res_ctrl.get("item_view", {})
        rows = iv.get("rows", 0)
        if rows == 0:
            raise RuntimeError(
                f"Nenhum resultado para '{search_keyword}'. "
                f"Verifique PART_SEARCH_CONFIG para '{part_name}'."
            )

        # Encontra a linha com device name == part_name (DEVICE library)
        target_row = 0
        for i, item in enumerate(iv.get("items", [])):
            cells = item.get("cells", [])
            if cells and cells[0] == part_name:
                target_row = i
                break

        print(f"    {rows} resultado(s) — selecionando linha {target_row}: "
              f"{iv.get('items', [{}])[target_row:target_row+1]}")

        call("ui_act", {"id": res_ctrl["id"], "property": "currentRow",
                        "value": str(target_row)})
        time.sleep(0.3)

        # Confirma
        call("ui_answer_dialog", {"id": dlg_id, "answer": "Ok"})
        time.sleep(0.5)

        # Verifica
        if part_name in list_parts_bin(design_id):
            print(f"  ✓ '{part_name}' adicionado com sucesso")
            return True

        print(f"  ✗ '{part_name}' não apareceu no parts bin após OK")
        return False

    except Exception as e:
        print(f"  ✗ Erro ao adicionar '{part_name}': {e}")
        try:
            call("ui_answer_dialog", {"id": dlg_id, "answer": "Cancel"})
        except Exception:
            pass
        return False


# ---------------------------------------------------------------------------
# Posicionamento de componentes
# ---------------------------------------------------------------------------

def place_components(design_id, sheet_id, components):
    """
    Posiciona todos os componentes em grade automática (4 colunas).
    Retorna dict ref -> {x, y}.
    """
    COL_W = 1100   # thou entre colunas
    ROW_H = 1100   # thou entre linhas
    COLS  = 4
    X0    = 1500   # origem X
    Y0    = 9000   # origem Y (Proteus: Y cresce para cima)

    placed = {}
    for i, comp in enumerate(components):
        col = i % COLS
        row = i // COLS
        x = X0 + col * COL_W
        y = Y0 - row * ROW_H

        ref   = comp["ref"]
        part  = comp["part"]
        value = comp.get("value", "")

        r = call("schematic_place_device", {
            "id":        design_id,
            "sheet":     sheet_id,
            "name":      part,
            "reference": ref,
            "value":     value,
            "x":         x,
            "y":         y,
        })
        placed[ref] = {"x": x, "y": y}

        data     = r.get("data", {})
        overlaps = data.get("overlaps", [])
        if overlaps:
            print(f"  ⚠  {ref} sobrepõe: {[o['ref'] for o in overlaps]}")
        else:
            print(f"  ✓  {ref} ({part}={value}) → ({x}, {y})")

    return placed


# ---------------------------------------------------------------------------
# Terminais de alimentação
# ---------------------------------------------------------------------------

def place_power_terminals(design_id, sheet_id, power_nets, components, wires):
    """
    Coloca terminais POWER/GROUND para cada pino de alimentação no circuito.
    Cada pino que participa de uma rede nomeada VCC ou GND recebe um terminal.
    """
    if not power_nets:
        return

    # Coleta pinos por rede
    net_pins = {}
    for wire in wires:
        net = wire.get("net")
        if not net or net not in power_nets:
            continue
        for endpoint in (wire["from"], wire["to"]):
            ref, pin = endpoint["ref"], endpoint["pin"]
            net_pins.setdefault(net, set()).add((ref, pin))

    # Posiciona terminais próximos a cada pino
    comp_positions = {}  # rough positions — reais disponíveis após place_components

    term_type = {"VCC": "POWER", "GND": "GROUND"}

    # Um terminal por rede, posição fixa
    TERM_X = {"VCC": 500, "GND": 500}
    TERM_Y = {"VCC": 9700, "GND": 7000}

    for net_name, voltage in power_nets.items():
        ttype = "POWER" if voltage != 0 else "GROUND"
        label = net_name
        tx = TERM_X.get(net_name, 500)
        ty = TERM_Y.get(net_name, 8000)

        try:
            call("schematic_place_terminal", {
                "id":       design_id,
                "sheet":    sheet_id,
                "terminal": ttype,
                "label":    label,
                "x":        tx,
                "y":        ty,
            })
            print(f"  ✓  Terminal {ttype}:{label} → ({tx}, {ty})")
        except Exception as e:
            print(f"  ⚠  Terminal {label}: {e}")


# ---------------------------------------------------------------------------
# Roteamento
# ---------------------------------------------------------------------------

def build_route_nets(wires, power_nets=None):
    """
    Converte wires do JSON em estrutura para schematic_route_nets.
    Agrupa por net name; wires sem net formam redes anônimas individuais.
    """
    net_map = {}  # net_name -> set of (ref, pin)
    anon_id = [0]

    def add_pin(net, ref, pin):
        net_map.setdefault(net, set()).add((ref, pin))

    for wire in wires:
        net = wire.get("net") or f"_anon_{anon_id[0]}"
        if not wire.get("net"):
            anon_id[0] += 1
        frm, to = wire["from"], wire["to"]
        add_pin(net, frm["ref"], frm["pin"])
        add_pin(net, to["ref"],  to["pin"])

    nets_out = []
    for name, pins in net_map.items():
        entry = {
            "name": name,
            "pins": [{"ref": r, "name": p} for r, p in pins],
        }
        # Adiciona terminais para redes de alimentação
        if power_nets and name in power_nets:
            ttype = "POWER" if power_nets[name] != 0 else "GROUND"
            entry["terminals"] = [{"ref": ttype, "name": name}]

        nets_out.append(entry)

    return nets_out


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def build_circuit(json_path):
    print(f"\n=== Construtor de Circuitos Proteus ===")
    print(f"Arquivo: {json_path}\n")

    with open(json_path, encoding="utf-8") as f:
        circuit = json.load(f)

    print(f"Circuito: {circuit['name']}")
    print(f"Descrição: {circuit.get('description', '')}\n")

    # 1. Conecta ao Proteus
    design_id, sheet_id = get_status()
    print(f"Design: {design_id}  Sheet: {sheet_id}\n")

    # 2. Parts bin
    print("--- Parts bin ---")
    needed  = {comp["part"] for comp in circuit["components"]}
    in_bin  = list_parts_bin(design_id)
    missing = needed - in_bin

    if missing:
        print(f"Faltando: {missing}")
        for part in sorted(missing):
            add_to_parts_bin(part, design_id)
    else:
        print("Todas as partes já estão no parts bin ✓")

    in_bin = list_parts_bin(design_id)
    still_missing = needed - in_bin
    if still_missing:
        print(f"\n✗ Partes ainda faltando: {still_missing}")
        print("  Adicione manualmente: Library → Pick Device")
        return False

    # 3. Transação de desenho
    print("\n--- Desenhando ---")
    call("schematic_begin_transaction", {"id": design_id})
    print("Transação iniciada\n")

    try:
        # 4. Componentes
        print("Posicionando componentes:")
        place_components(design_id, sheet_id, circuit["components"])

        # 5. Terminais de alimentação (ANTES do roteamento)
        print("\nTerminais de alimentação:")
        place_power_terminals(
            design_id, sheet_id,
            circuit.get("power_nets", {}),
            circuit["components"],
            circuit["wires"],
        )

        # 6. Roteia
        print("\nRoteando redes:")
        nets = build_route_nets(circuit["wires"], circuit.get("power_nets", {}))
        r = call("schematic_route_nets", {
            "id":          design_id,
            "sheet":       sheet_id,
            "max_corners": 2,
            "nets":        nets,
        })
        summary = r.get("data", {}).get("summary", {})
        print(f"  OK: {summary.get('routed',0)}  "
              f"Parcial: {summary.get('partial',0)}  "
              f"Falhou: {summary.get('failed',0)}")

        # 7. Commit
        r = call("schematic_end_transaction", {
            "id":        design_id,
            "auto_nudge": True,
        })
        fouls = r.get("data", {}).get("block_placement", {}).get("fouls", [])
        if fouls:
            print(f"  ⚠  Sobreposições: {[f['ref'] for f in fouls]}")
        print("Transação finalizada ✓")

        # 8. Salva
        call("file_save", {})
        print(f"\n✓ Circuito '{circuit['name']}' criado com sucesso!")
        return True

    except Exception as e:
        print(f"\n✗ Erro: {e}")
        print("Revertendo transação...")
        try:
            call("schematic_end_transaction", {"id": design_id, "abandon": True})
        except Exception:
            pass
        return False


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Cria circuitos Proteus automaticamente a partir de JSON"
    )
    parser.add_argument("json_file", help="Arquivo JSON do circuito")
    args = parser.parse_args()
    success = build_circuit(args.json_file)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
