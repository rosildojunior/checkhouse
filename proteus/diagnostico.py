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
    ok(f"Pasta existe: {PASTA_DESTINO}")
    # Testa escrita
    teste = os.path.join(PASTA_DESTINO, "__teste_builder__.tmp")
    try:
        with open(teste, 'w') as f:
            f.write("ok")
        os.remove(teste)
        ok("Permissão de escrita: OK")
    except Exception as e:
        erro(f"Sem permissão de escrita: {e}")
else:
    erro(f"Pasta NÃO encontrada: {PASTA_DESTINO}")
    info("Verifique se o Google Drive está sincronizado e a letra H: está ativa")

# ── 4. Registro COM — busca entradas do Proteus ───────────────────────────────
titulo("4. COM — Entradas do Proteus no Registro")

encontrados = []
prefixos = ['proteus', 'labcenter', 'isis', 'ares', 'pds']

try:
    chave = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "")
    i = 0
    while True:
        try:
            nome = winreg.EnumKey(chave, i)
            if any(p in nome.lower() for p in prefixos):
                encontrados.append(nome)
            i += 1
        except OSError:
            break
except Exception as e:
    erro(f"Não foi possível ler o registro: {e}")

if encontrados:
    ok(f"{len(encontrados)} entrada(s) encontrada(s):")
    for e in encontrados:
        print(f"       {e}")
else:
    erro("Nenhuma entrada COM do Proteus encontrada no registro")
    info("O Proteus pode não estar instalado ou o COM não foi registrado")

# ── 5. Tenta conectar ao Proteus via COM ──────────────────────────────────────
titulo("5. Conexão COM com o Proteus")

PROGIDS = [
    "Labcenter.ProteusIDE",
    "Labcenter.Proteus",
    "ISIS.Application",
    "ProteusAutomate.Application",
    "Labcenter.Schematic",
]

conectou = False
try:
    import win32com.client
    for progid in PROGIDS:
        try:
            win32com.client.GetActiveObject(progid)
            ok(f"Proteus em execução encontrado: {progid}")
            conectou = True
            break
        except Exception:
            pass

    if not conectou:
        info("Proteus não está em execução. Tentando iniciar...")
        for progid in PROGIDS:
            try:
                win32com.client.Dispatch(progid)
                ok(f"Proteus iniciado via COM: {progid}")
                conectou = True
                break
            except Exception as e:
                info(f"  Falhou {progid}: {e}")

    if not conectou:
        erro("Não foi possível conectar via nenhum ProgID conhecido")

except Exception as e:
    erro(f"Erro na tentativa COM: {e}")

# ── 6. Clipboard ──────────────────────────────────────────────────────────────
titulo("6. Área de Transferência")
try:
    import pyperclip
    conteudo = pyperclip.paste()
    if conteudo:
        preview = conteudo[:80].replace('\n', ' ')
        ok(f"Leitura OK. Conteúdo atual: {preview}...")
    else:
        info("Área de transferência vazia")
except Exception as e:
    erro(f"Erro ao ler clipboard: {e}")

# ── 7. Arquivo de teste na pasta ──────────────────────────────────────────────
titulo("7. Teste de salvamento de JSON na pasta")
if os.path.exists(PASTA_DESTINO):
    circuito_teste = {
        "name": "Teste Diagnóstico",
        "description": "Arquivo de teste gerado pelo diagnóstico",
        "supply_voltage": 5,
        "components": [
            {"ref": "R1", "part": "RES", "value": "1k"}
        ],
        "wires": []
    }
    arquivo_teste = os.path.join(PASTA_DESTINO, "__teste_diagnostico__.json")
    try:
        with open(arquivo_teste, 'w', encoding='utf-8') as f:
            json.dump(circuito_teste, f, ensure_ascii=False, indent=2)
        ok(f"JSON de teste salvo em: {arquivo_teste}")
        info("Se o builder estiver rodando, ele deve processar este arquivo agora")
    except Exception as e:
        erro(f"Falha ao salvar JSON de teste: {e}")

# ── Resumo ────────────────────────────────────────────────────────────────────
titulo("RESUMO")
if not conectou:
    print("""
  O principal problema é a conexão COM com o Proteus.

  Soluções para tentar:

  1. Execute o Proteus como ADMINISTRADOR e deixe aberto
     depois rode este diagnóstico novamente

  2. Registre o COM manualmente:
     - Abra o CMD como Administrador
     - Vá até a pasta de instalação do Proteus, ex:
       cd "C:\\Program Files (x86)\\Labcenter Electronics\\Proteus 8 Professional\\BIN"
     - Execute: regsvr32 ISIS.EXE

  3. Informe a versão exata do Proteus instalada
     (Help → About no menu do Proteus)
""")
else:
    ok("Sistema pronto para uso!")

print(SEP)
print()
input("Pressione Enter para fechar...")
