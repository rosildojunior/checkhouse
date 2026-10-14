"""
Proteus Circuit Builder
=======================
Lê um JSON de circuito gerado pelo Claude e cria o esquemático no Proteus via COM.

Uso:
    python builder.py circuito.json
    python builder.py circuito.json saida.pdsprj
    python builder.py --watch pasta/    # monitora pasta e executa automaticamente

Requisitos:
    pip install pywin32
    Proteus 8.x instalado no Windows
"""

import json
import sys
import os
import time
import math
import argparse
import traceback
from pathlib import Path
from typing import Optional, Tuple, Dict

# ── COM availability ──────────────────────────────────────────────────────────
try:
    import win32com.client
    import pywintypes
    COM_AVAILABLE = True
except ImportError:
    COM_AVAILABLE = False

# ── Mapeamento de componentes para biblioteca Proteus ──────────────────────────
# Formato: 'NOME_GENERICO': ('BIBLIOTECA', 'PARTE')
LIBRARY_MAP = {
    # Passivos
    'RES':          ('DEVICE', 'RES'),
    'RESISTOR':     ('DEVICE', 'RES'),
    'R':            ('DEVICE', 'RES'),
    'CAP':          ('DEVICE', 'CAP'),
    'CAPACITOR':    ('DEVICE', 'CAP'),
    'C':            ('DEVICE', 'CAP'),
    'CAP-ELEC':     ('DEVICE', 'CAP-ELEC'),
    'CAP_ELEC':     ('DEVICE', 'CAP-ELEC'),
    'INDUCTOR':     ('DEVICE', 'INDUCTOR'),
    'L':            ('DEVICE', 'INDUCTOR'),
    'XTAL':         ('DEVICE', 'CRYSTAL'),
    'CRYSTAL':      ('DEVICE', 'CRYSTAL'),
    'TRANSFORMER':  ('DEVICE', 'TRAN-2P2S'),

    # Diodos / LEDs
    'DIODE':        ('DEVICE', '1N4148'),
    '1N4148':       ('DEVICE', '1N4148'),
    '1N4007':       ('DEVICE', '1N4007'),
    '1N5408':       ('DEVICE', '1N5408'),
    'ZENER':        ('DEVICE', 'ZENER'),
    'LED':          ('DEVICE', 'LED'),
    'LED-RED':      ('OPTOELECTRONICS', 'LED-RED'),
    'LED-GREEN':    ('OPTOELECTRONICS', 'LED-GREEN'),
    'LED-BLUE':     ('OPTOELECTRONICS', 'LED-BLUE'),
    'LED-YELLOW':   ('OPTOELECTRONICS', 'LED-YELLOW'),

    # Transistores BJT
    'NPN':          ('DEVICE', 'NPN'),
    'PNP':          ('DEVICE', 'PNP'),
    'BC547':        ('TRANSISTORS', 'BC547'),
    'BC557':        ('TRANSISTORS', 'BC557'),
    'BC337':        ('TRANSISTORS', 'BC337'),
    'BC327':        ('TRANSISTORS', 'BC327'),
    '2N2222':       ('TRANSISTORS', '2N2222A'),
    '2N3904':       ('TRANSISTORS', '2N3904'),
    '2N3906':       ('TRANSISTORS', '2N3906'),
    'TIP31':        ('TRANSISTORS', 'TIP31C'),
    'TIP32':        ('TRANSISTORS', 'TIP32C'),
    'TIP41':        ('TRANSISTORS', 'TIP41C'),
    'BD135':        ('TRANSISTORS', 'BD135'),
    'BD136':        ('TRANSISTORS', 'BD136'),
    'BC639':        ('TRANSISTORS', 'BC639'),

    # MOSFETs
    'NMOS':         ('DEVICE', 'NMOS'),
    'PMOS':         ('DEVICE', 'PMOS'),
    'IRF540':       ('MOSFET', 'IRF540N'),
    'IRF9540':      ('MOSFET', 'IRF9540N'),

    # Temporizadores / analógicos
    '555':          ('DEVICE', '555'),
    'NE555':        ('DEVICE', '555'),
    'LM555':        ('DEVICE', '555'),
    'LM741':        ('ANALOG', 'LM741'),
    'LM358':        ('ANALOG', 'LM358'),
    'LM324':        ('ANALOG', 'LM324'),
    'LM393':        ('ANALOG', 'LM393'),
    'LM339':        ('ANALOG', 'LM339'),
    'TL071':        ('ANALOG', 'TL071'),
    'TL072':        ('ANALOG', 'TL072'),
    'TL082':        ('ANALOG', 'TL082'),
    'NE5532':       ('ANALOG', 'NE5532'),

    # Reguladores de tensão
    '7805':         ('DEVICE', '7805'),
    '7809':         ('DEVICE', '7809'),
    '7812':         ('DEVICE', '7812'),
    '7815':         ('DEVICE', '7815'),
    '7905':         ('DEVICE', '7905'),
    '7912':         ('DEVICE', '7912'),
    'LM317':        ('DEVICE', 'LM317'),
    'LM337':        ('DEVICE', 'LM337'),
    'LM7805':       ('DEVICE', '7805'),
    'LM7812':       ('DEVICE', '7812'),

    # Lógica TTL
    '74LS00':       ('74LS', '74LS00'),
    '74LS04':       ('74LS', '74LS04'),
    '74LS08':       ('74LS', '74LS08'),
    '74LS32':       ('74LS', '74LS32'),
    '74LS74':       ('74LS', '74LS74'),
    '74LS138':      ('74LS', '74LS138'),
    '74LS245':      ('74LS', '74LS245'),
    '74LS373':      ('74LS', '74LS373'),
    '74HC00':       ('74HC', '74HC00'),
    '74HC04':       ('74HC', '74HC04'),
    '74HC08':       ('74HC', '74HC08'),
    '74HC32':       ('74HC', '74HC32'),
    '74HC74':       ('74HC', '74HC74'),
    '74HC138':      ('74HC', '74HC138'),
    '74HC245':      ('74HC', '74HC245'),
    '74HC373':      ('74HC', '74HC373'),

    # Microcontroladores
    'ATMEGA328P':   ('AVR', 'ATMEGA328P-PU'),
    'ATMEGA328':    ('AVR', 'ATMEGA328P-PU'),
    'ATMEGA2560':   ('AVR', 'ATMEGA2560'),
    'ATTINY85':     ('AVR', 'ATTINY85-20PU'),
    'PIC16F877A':   ('PIC16', 'PIC16F877A'),
    'PIC16F628A':   ('PIC16', 'PIC16F628A'),
    'PIC18F4550':   ('PIC18', 'PIC18F4550'),
    'STM32F103':    ('STM32', 'STM32F103C8'),

    # Displays
    'LCD16X2':      ('DISPLAY', 'LM016L'),
    'LCD_16X2':     ('DISPLAY', 'LM016L'),
    '7SEG':         ('DISPLAY', '7SEG-MPX1-CC'),
    '7SEG_CA':      ('DISPLAY', '7SEG-MPX1-CA'),

    # Conectores / terminais
    'CONN1':        ('DEVICE', 'CONN-H1'),
    'CONN2':        ('DEVICE', 'CONN-H2'),
    'CONN3':        ('DEVICE', 'CONN-H3'),
    'CONN4':        ('DEVICE', 'CONN-H4'),
    'CONN5':        ('DEVICE', 'CONN-H5'),
    'CONN6':        ('DEVICE', 'CONN-H6'),
    'TERMINAL2':    ('DEVICE', 'TERMINAL'),
    'TERMINAL3':    ('DEVICE', 'TERMINAL'),

    # Chaves / botões
    'SW':           ('DEVICE', 'SW-SPST'),
    'PUSH':         ('ACTIVE', 'BUTTON'),
    'BUTTON':       ('ACTIVE', 'BUTTON'),
    'RELAY':        ('DEVICE', 'RELAY-SPDT'),

    # Transformadores / retificadores
    'BRIDGE':       ('DEVICE', 'BRIDGE'),
    'BRIDGE1':      ('DEVICE', 'BRIDGE'),

    # Medição (virtual instruments Proteus)
    'VOLTMETER':    ('ACTIVE', 'VOLTMETER'),
    'AMMETER':      ('ACTIVE', 'AMMETER'),
    'OSCILLOSCOPE': ('ACTIVE', 'OSCILLOSCOPE'),
    'LOGICANALYZER':('ACTIVE', 'LOGICANALYZER'),

    # Fontes
    'VSOURCE':      ('DEVICE', 'VSOURCE'),
    'ISOURCE':      ('DEVICE', 'ISOURCE'),
    'VSIN':         ('DEVICE', 'VSIN'),
    'BATTERY':      ('DEVICE', 'BATTERY'),
}

# ── COM ProgIDs do Proteus (tenta em ordem) ────────────────────────────────────
PROTEUS_PROGIDS = [
    "Labcenter.ProteusIDE",
    "Labcenter.Proteus",
    "ISIS.Application",
    "ProteusAutomate.Application",
    "Labcenter.Schematic",
]


# ── Auto-layout ────────────────────────────────────────────────────────────────

class AutoLayout:
    """
    Layout automático simples: distribui componentes em grade.
    Respeita posições explícitas no JSON; preenche o resto em grade.
    """
    COLS = 5
    STEP_X = 1500   # unidades Proteus (~1 inch = 1000 unis dependendo da versão)
    STEP_Y = 1200
    ORIGIN_X = 2000
    ORIGIN_Y = 2000

    def apply(self, components: list) -> list:
        col, row = 0, 0
        result = []
        for comp in components:
            c = dict(comp)
            if not c.get('position'):
                c['position'] = {
                    'x': self.ORIGIN_X + col * self.STEP_X,
                    'y': self.ORIGIN_Y + row * self.STEP_Y,
                }
                col += 1
                if col >= self.COLS:
                    col = 0
                    row += 1
            result.append(c)
        return result


# ── Proteus COM Builder ────────────────────────────────────────────────────────

class ProteusComBuilder:

    def __init__(self):
        self.app = None
        self.design = None
        self.sheet = None

    # ── Conexão ──────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        if not COM_AVAILABLE:
            _error("pywin32 não encontrado. Instale com: pip install pywin32")
            return False

        # Tenta conectar a instância em execução
        for progid in PROTEUS_PROGIDS:
            try:
                self.app = win32com.client.GetActiveObject(progid)
                _info(f"Conectado ao Proteus em execução ({progid})")
                return True
            except Exception:
                pass

        # Tenta iniciar nova instância
        for progid in PROTEUS_PROGIDS:
            try:
                self.app = win32com.client.Dispatch(progid)
                _info(f"Proteus iniciado ({progid})")
                return True
            except Exception:
                pass

        _error(
            "Não foi possível conectar ao Proteus.\n"
            "Verifique:\n"
            "  1. Proteus 8.x está instalado\n"
            "  2. Execute Proteus ao menos uma vez como Administrador\n"
            "  3. Registre o COM: 'cd C:\\Program Files (x86)\\Labcenter Electronics\\Proteus 8 Professional\\BIN'\n"
            "     depois: 'regsvr32 ISIS.EXE' (ou ProSPICE.EXE)"
        )
        return False

    # ── Build principal ───────────────────────────────────────────────────────

    def build(self, circuit: dict, output_path: Optional[str] = None) -> bool:
        if not self.connect():
            return False

        try:
            _info("Criando novo design...")
            self.design = self.app.NewDesign()
            self.sheet = self.design.RootSheet

            layout = AutoLayout()
            components = layout.apply(circuit['components'])

            # Coloca componentes
            placed: Dict[str, object] = {}
            for comp in components:
                obj = self._place_component(comp)
                if obj is not None:
                    placed[comp['ref']] = obj
                else:
                    _warn(f"  Pulando fios de {comp['ref']} (não foi colocado)")

            _info(f"Componentes colocados: {len(placed)}/{len(components)}")

            # Desenha fios
            wires_ok = 0
            for wire in circuit.get('wires', []):
                if self._draw_wire(wire, placed):
                    wires_ok += 1

            _info(f"Fios desenhados: {wires_ok}/{len(circuit.get('wires', []))}")

            # Salva
            if output_path:
                self.design.SaveAs(os.path.abspath(output_path))
                _info(f"Salvo em: {output_path}")
            else:
                self.design.Save()

            return True

        except Exception as e:
            _error(f"Erro ao construir circuito: {e}")
            traceback.print_exc()
            return False

    # ── Colocação de componente ───────────────────────────────────────────────

    def _place_component(self, comp: dict) -> Optional[object]:
        lib, part = self._resolve_part(comp)
        pos = comp['position']
        rot = comp.get('rotation', 0)

        try:
            # API do Proteus pode variar entre versões
            try:
                obj = self.sheet.PlaceComponent(lib, part, pos['x'], pos['y'], rot)
            except AttributeError:
                obj = self.sheet.AddComponent(lib, part, pos['x'], pos['y'], rot)

            # RefDes
            try:
                obj.RefDes = comp['ref']
            except AttributeError:
                obj.Reference = comp['ref']

            # Valor
            val = comp.get('value', '')
            if val:
                try:
                    obj.SetProperty('VALUE', str(val))
                except Exception:
                    try:
                        obj.Value = str(val)
                    except Exception:
                        pass

            _info(f"  + {comp['ref']} ({lib}:{part})  pos=({pos['x']},{pos['y']})")
            return obj

        except Exception as e:
            _warn(f"  ! Falha ao colocar {comp['ref']} ({lib}:{part}): {e}")
            return None

    # ── Fio ──────────────────────────────────────────────────────────────────

    def _draw_wire(self, wire: dict, placed: dict) -> bool:
        from_ref = wire['from']['ref']
        to_ref   = wire['to']['ref']
        from_pin = str(wire['from']['pin'])
        to_pin   = str(wire['to']['pin'])

        obj_from = placed.get(from_ref)
        obj_to   = placed.get(to_ref)

        if obj_from is None or obj_to is None:
            _warn(f"  ! Fio ignorado: {from_ref}.{from_pin} → {to_ref}.{to_pin} (componente ausente)")
            return False

        try:
            pin_from = obj_from.GetPin(from_pin)
            pin_to   = obj_to.GetPin(to_pin)

            if pin_from is None or pin_to is None:
                _warn(f"  ! Pin não encontrado: {from_ref}.{from_pin} ou {to_ref}.{to_pin}")
                return False

            self.sheet.DrawWire(pin_from.X, pin_from.Y, pin_to.X, pin_to.Y)
            return True

        except Exception as e:
            _warn(f"  ! Erro ao desenhar fio {from_ref}.{from_pin}→{to_ref}.{to_pin}: {e}")
            return False

    # ── Resolução de biblioteca ───────────────────────────────────────────────

    def _resolve_part(self, comp: dict) -> Tuple[str, str]:
        # Se veio explícito no JSON, usa direto
        if comp.get('library') and comp.get('part'):
            return comp['library'], comp['part']

        # Tenta resolver pelo campo 'part' ou 'type'
        key = comp.get('part', comp.get('type', '')).upper().strip()
        if key in LIBRARY_MAP:
            return LIBRARY_MAP[key]

        # Sem mapeamento: assume DEVICE
        _warn(f"  ? Componente '{key}' não mapeado — tentando biblioteca DEVICE")
        return ('DEVICE', key)


# ── Watcher de pasta ──────────────────────────────────────────────────────────

def watch_folder(folder: str, output_dir: Optional[str] = None):
    """Monitora uma pasta e executa o builder quando aparecer um novo .json"""
    path = Path(folder)
    if not path.exists():
        path.mkdir(parents=True)

    seen = set(path.glob('*.json'))
    _info(f"Monitorando '{folder}' — coloque arquivos .json aqui")
    _info("Pressione Ctrl+C para parar\n")

    try:
        while True:
            current = set(path.glob('*.json'))
            new_files = current - seen
            for f in sorted(new_files):
                _info(f"\nNovo arquivo: {f.name}")
                out = None
                if output_dir:
                    out = str(Path(output_dir) / f.stem) + '.pdsprj'
                run_build(str(f), out)
            seen = current
            time.sleep(1)
    except KeyboardInterrupt:
        _info("Monitoramento encerrado.")


# ── Entry point ───────────────────────────────────────────────────────────────

def run_build(json_path: str, output_path: Optional[str] = None) -> bool:
    if not os.path.exists(json_path):
        _error(f"Arquivo não encontrado: {json_path}")
        return False

    with open(json_path, 'r', encoding='utf-8') as f:
        try:
            circuit = json.load(f)
        except json.JSONDecodeError as e:
            _error(f"JSON inválido: {e}")
            return False

    _info(f"Circuito    : {circuit.get('name', 'Sem nome')}")
    _info(f"Descrição   : {circuit.get('description', '')}")
    _info(f"Componentes : {len(circuit.get('components', []))}")
    _info(f"Fios        : {len(circuit.get('wires', []))}")
    print()

    builder = ProteusComBuilder()
    return builder.build(circuit, output_path)


def main():
    parser = argparse.ArgumentParser(
        description='Proteus Circuit Builder — converte JSON em esquemático Proteus'
    )
    parser.add_argument('input', help='Arquivo .json do circuito OU pasta (com --watch)')
    parser.add_argument('output', nargs='?', help='Arquivo .pdsprj de saída (opcional)')
    parser.add_argument('--watch', action='store_true',
                        help='Monitorar pasta continuamente')
    args = parser.parse_args()

    if args.watch:
        watch_folder(args.input, args.output)
    else:
        ok = run_build(args.input, args.output)
        sys.exit(0 if ok else 1)


# ── Helpers de log ────────────────────────────────────────────────────────────

def _info(msg):  print(f"[OK] {msg}")
def _warn(msg):  print(f"[!!] {msg}")
def _error(msg): print(f"[XX] {msg}")


if __name__ == '__main__':
    main()
