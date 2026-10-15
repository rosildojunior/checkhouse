"""
Diagnóstico completo do Proteus Circuit Builder
================================================
Executa e mostra o resultado de cada etapa do sistema.
Copie e cole o resultado aqui para análise.
"""

import os
import sys
import json
import winreg
import glob
from pathlib import Path

PASTA_DESTINO = r"H:\Meu Drive\R&F CASA E ESTILO\RF - ARDUINO\PROTEUS - PROJETOS DE CIRCUITOS"
SEP = "-" * 55

def titulo(t):
    print(f"\n{SEP}")
    print(f"  {t}")
    print(SEP)

def ok(msg):   print(f"  [OK] {msg}")
def erro(msg): print(f"  [XX] {msg}")
def info(msg): print(f"  [..] {msg}")

# ── 1. Python ─────────────────────────────────────────────────────────────────
titulo("1. Python")
ok(f"Versão: {sys.version}")

# ── 2. Dependências ───────────────────────────────────────────────────────────
titulo("2. Dependências")
try:
    import win32com.client
    ok("pywin32 instalado")
except ImportError:
    erro("pywin32 NÃO encontrado  →  pip install pywin32")

try:
    import pyperclip
    ok("pyperclip instalado")
except ImportError:
    erro("pyperclip NÃO encontrado  →  pip install pyperclip")

# ── 3. Pasta de destino ───────────────────────────────────────────────────────
titulo("3. Pasta de destino")
if os.path.exists(PASTA_DESTINO):
    ok(f"Pasta existe")
    teste = os.path.join(PASTA_DESTINO, "__teste_builder__.tmp")
    try:
        with open(teste, 'w') as f: f.write("ok")
        os.remove(teste)
        ok("Permissão de escrita: OK")
    except Exception as e:
        erro(f"Sem permissão de escrita: {e}")
else:
    erro(f"Pasta NÃO encontrada: {PASTA_DESTINO}")

# ── 4. Localização do Proteus ─────────────────────────────────────────────────
titulo("4. Instalação do Proteus")

PASTAS_POSSIVEIS = [
    r"C:\Program Files (x86)\Labcenter Electronics",
    r"C:\Program Files\Labcenter Electronics",
    r"C:\Labcenter Electronics",
    r"D:\Program Files (x86)\Labcenter Electronics",
    r"D:\Labcenter Electronics",
]

pasta_proteus = None
exe_proteus   = None

for base in PASTAS_POSSIVEIS:
    if os.path.exists(base):
        ok(f"Encontrado em: {base}")
        pasta_proteus = base
        # Procura o executável ISIS.EXE
        for exe in glob.glob(os.path.join(base, "**", "ISIS.EXE"), recursive=True):
            exe_proteus = exe
            ok(f"ISIS.EXE: {exe}")
            break
        # Procura type library
        for tlb in glob.glob(os.path.join(base, "**", "*.TLB"), recursive=True):
            ok(f"Type library: {tlb}")
        # Procura SAMPLES de automação
        for s in glob.glob(os.path.join(base, "**", "Automation"), recursive=True):
            ok(f"Pasta Automation: {s}")
        break

if not pasta_proteus:
    erro("Pasta Labcenter Electronics não encontrada")
    info("Verifique onde o Proteus está instalado")

# Também verifica o registro para caminho de instalação
try:
    for root in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        for sub in [
            r"SOFTWARE\Labcenter Electronics\Proteus 8 Professional",
            r"SOFTWARE\WOW6432Node\Labcenter Electronics\Proteus 8 Professional",
            r"SOFTWARE\Labcenter Electronics",
        ]:
            try:
                key = winreg.OpenKey(root, sub)
                i = 0
                while True:
                    try:
                        name, val, _ = winreg.EnumValue(key, i)
                        info(f"Registro [{sub}] {name} = {val}")
                        i += 1
                    except OSError:
                        break
            except Exception:
                pass
except Exception as e:
    info(f"Registro: {e}")

# ── 5. COM — PDS.ImportServer ─────────────────────────────────────────────────
titulo("5. COM — PDS.ImportServer")
try:
    import win32com.client

    for progid in ["PDS.ImportServer.1", "PDS.ImportServer"]:
        try:
            srv = win32com.client.Dispatch(progid)
            ok(f"Conectado: {progid}")
            metodos = [m for m in dir(srv) if not m.startswith('_')]
            info(f"Métodos/propriedades: {metodos}")
            break
        except Exception as e:
            info(f"  Falhou {progid}: {e}")
except Exception as e:
    erro(f"Erro ao testar PDS.ImportServer: {e}")

# ── 6. COM — busca TODOS os ProgIDs que têm CLSID ────────────────────────────
titulo("6. ProgIDs COM completos do Proteus")
try:
    encontrados = []
    for hive, nome_hive in [(winreg.HKEY_CLASSES_ROOT, "HKCR"),
                            (winreg.HKEY_LOCAL_MACHINE, "HKLM")]:
        try:
            chave = winreg.OpenKey(hive, "")
            i = 0
            while True:
                try:
                    nome = winreg.EnumKey(chave, i)
                    if any(p in nome.lower() for p in ['proteus','labcenter','isis','ares','pds']):
                        # Verifica se tem CLSID (é um ProgID real)
                        try:
                            sub = winreg.OpenKey(hive, nome + "\\CLSID")
                            clsid = winreg.QueryValue(sub, "")
                            encontrados.append(f"{nome_hive}\\{nome}  →  CLSID={clsid}")
                        except Exception:
                            encontrados.append(f"{nome_hive}\\{nome}  (sem CLSID)")
                    i += 1
                except OSError:
                    break
        except Exception:
            pass

    if encontrados:
        ok(f"{len(encontrados)} entradas:")
        for e in encontrados:
            print(f"       {e}")
    else:
        erro("Nenhuma encontrada")
except Exception as e:
    erro(f"Erro: {e}")

# ── 7. Proteus em execução — janela ativa ─────────────────────────────────────
titulo("7. Processos Proteus em execução")
try:
    import subprocess
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq ISIS.EXE"],
        capture_output=True, text=True
    )
    if "ISIS.EXE" in result.stdout:
        ok("ISIS.EXE está em execução")
        print(f"       {result.stdout.strip()}")
    else:
        info("ISIS.EXE não está em execução")

    result2 = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Proteus.exe"],
        capture_output=True, text=True
    )
    if "Proteus.exe" in result2.stdout:
        ok("Proteus.exe está em execução")
    else:
        info("Proteus.exe não está em execução")
except Exception as e:
    info(f"Não foi possível listar processos: {e}")

# ── 8. Teste de salvamento de JSON ────────────────────────────────────────────
titulo("8. Teste de salvamento de JSON na pasta")
if os.path.exists(PASTA_DESTINO):
    circuito_teste = {
        "name": "Teste Diagnóstico",
        "description": "Arquivo de teste",
        "supply_voltage": 5,
        "components": [{"ref": "R1", "part": "RES", "value": "1k"}],
        "wires": []
    }
    arquivo_teste = os.path.join(PASTA_DESTINO, "__teste_diagnostico__.json")
    try:
        with open(arquivo_teste, 'w', encoding='utf-8') as f:
            json.dump(circuito_teste, f, ensure_ascii=False, indent=2)
        ok(f"JSON salvo com sucesso")
    except Exception as e:
        erro(f"Falha: {e}")

# ── Resumo ────────────────────────────────────────────────────────────────────
titulo("RESUMO — Cole tudo acima e envie para análise")
print()
input("Pressione Enter para fechar...")
