"""
Clipboard Watcher — Monitor de Área de Transferência
=====================================================
Fica rodando em segundo plano.
Quando você copiar um JSON de circuito gerado pelo Claude,
ele detecta, salva e chama o builder automaticamente no Proteus.

Fluxo:
    1. Claude gera o JSON do circuito
    2. Você copia o JSON (Ctrl+C)
    3. Este watcher detecta, salva e chama builder.py
    4. O circuito aparece no Proteus automaticamente

Uso:
    python clipboard_watcher.py

Requisitos:
    pip install pyperclip
"""

import json
import os
import re
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

try:
    import pyperclip
except ImportError:
    print("Instalando pyperclip...")
    os.system("pip install pyperclip -q")
    import pyperclip

# ── Configuração ──────────────────────────────────────────────────────────────
BASE = Path(r"H:\Meu Drive\R&F CASA E ESTILO\RF - ARDUINO\PROTEUS - PROJETOS DE CIRCUITOS")
BUILDER  = BASE / "proteus" / "builder.py"
DESTINO  = BASE / "proteus" / "examples"
INTERVALO = 1.5    # segundos entre verificações


# ── Extração e validação ──────────────────────────────────────────────────────

def extrair_json(texto: str) -> dict | None:
    """Tenta parsear JSON do texto, removendo blocos markdown se houver."""
    texto = texto.strip()
    texto = re.sub(r'^```(?:json)?\s*', '', texto, flags=re.MULTILINE)
    texto = re.sub(r'```\s*$', '', texto, flags=re.MULTILINE)
    texto = texto.strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r'\{[\s\S]+\}', texto)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return None


def eh_circuito_valido(d: dict) -> tuple[bool, str]:
    """
    Retorna (válido, motivo).
    Aceita tanto netlist[] (novo) quanto wires[] (antigo).
    """
    if not isinstance(d, dict):
        return False, "não é objeto"
    if 'components' not in d or not isinstance(d['components'], list):
        return False, "sem 'components'"
    if len(d['components']) == 0:
        return False, "lista de componentes vazia"

    if 'netlist' in d:
        nl = d['netlist']
        if not isinstance(nl, list) or len(nl) == 0:
            return False, "'netlist' vazio"
        row = nl[0]
        if not all(k in row for k in ('ref', 'pin', 'net')):
            return False, "'netlist' sem campos ref/pin/net"
        return True, "netlist"

    if 'wires' in d:
        if not isinstance(d['wires'], list):
            return False, "'wires' não é lista"
        return True, "wires"

    return False, "sem 'netlist' nem 'wires'"


def nome_arquivo(d: dict) -> str:
    nome = d.get('name', 'circuito')
    nome = re.sub(r'[\\/:*?"<>|\s]+', '_', nome).strip('_')
    ts   = datetime.now().strftime('%H%M%S')
    return f"{nome}_{ts}.json"


# ── Ação principal ────────────────────────────────────────────────────────────

def processar(dados: dict, formato: str):
    # 1. Salva o arquivo
    DESTINO.mkdir(parents=True, exist_ok=True)
    arquivo = DESTINO / nome_arquivo(dados)
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    comp  = len(dados.get('components', []))
    pinos = len(dados.get('netlist', dados.get('wires', [])))
    nome  = dados.get('name', 'Sem nome')

    print(f"\n{'='*52}")
    print(f"  Circuito detectado!")
    print(f"  Nome       : {nome}")
    print(f"  Formato    : {formato}")
    print(f"  Componentes: {comp}   Pinos/fios: {pinos}")
    print(f"  Arquivo    : {arquivo.name}")
    print(f"{'='*52}")
    print("  Chamando builder.py...\n")

    # 2. Chama o builder (mesmo processo Python, visível no terminal)
    ret = subprocess.run(
        [sys.executable, str(BUILDER), str(arquivo)],
        text=True
    )

    if ret.returncode == 0:
        print(f"\n  ✓ Circuito criado no Proteus!")
    else:
        print(f"\n  ✗ Builder retornou código {ret.returncode}")
        print(f"    Arquivo salvo em: {arquivo}")
        print(f"    Execute manualmente: python builder.py \"{arquivo}\"")

    print("-" * 52)


# ── Loop principal ────────────────────────────────────────────────────────────

def main():
    print("=" * 52)
    print("  Clipboard Watcher — Proteus Circuit Builder")
    print("=" * 52)
    print(f"\n  Destino : {DESTINO}")
    print(f"  Builder : {BUILDER}")
    print()
    print("  Copie um JSON de circuito gerado pelo Claude.")
    print("  O builder será chamado automaticamente.")
    print("  Ctrl+C para parar.\n")
    print("-" * 52)

    ultimo      = ""
    ultimo_hash = ""

    while True:
        try:
            atual = pyperclip.paste()

            if atual != ultimo:
                ultimo = atual
                dados  = extrair_json(atual)
                if dados:
                    ok, formato = eh_circuito_valido(dados)
                    if ok:
                        chave = json.dumps(dados, sort_keys=True)
                        if chave != ultimo_hash:
                            ultimo_hash = chave
                            processar(dados, formato)

            time.sleep(INTERVALO)

        except KeyboardInterrupt:
            print("\n  Monitor encerrado.")
            sys.exit(0)
        except Exception:
            time.sleep(INTERVALO)


if __name__ == '__main__':
    main()
