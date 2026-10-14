"""
Clipboard Watcher — Monitor de Área de Transferência
=====================================================
Fica rodando em segundo plano.
Quando você copiar um JSON de circuito gerado pelo Claude,
ele detecta, valida e salva automaticamente na pasta de projetos.

Uso:
    python clipboard_watcher.py

Requisitos:
    pip install pyperclip
"""

import json
import os
import re
import time
import sys
from datetime import datetime
from pathlib import Path

try:
    import pyperclip
except ImportError:
    print("[XX] pyperclip não encontrado. Instalando...")
    os.system("pip install pyperclip -q")
    import pyperclip

# ── Pasta de destino ──────────────────────────────────────────────────────────
PASTA_DESTINO = r"H:\Meu Drive\R&F CASA E ESTILO\RF - ARDUINO\PROTEUS - PROJETOS DE CIRCUITOS"

# ── Intervalo de verificação (segundos) ───────────────────────────────────────
INTERVALO = 1.5


def extrair_json(texto: str) -> dict | None:
    """Tenta extrair um JSON válido do texto copiado."""
    texto = texto.strip()

    # Remove bloco de código markdown se houver (```json ... ```)
    texto = re.sub(r'^```(?:json)?\s*', '', texto, flags=re.MULTILINE)
    texto = re.sub(r'```\s*$', '', texto, flags=re.MULTILINE)
    texto = texto.strip()

    try:
        dados = json.loads(texto)
        return dados
    except json.JSONDecodeError:
        # Tenta encontrar o primeiro bloco { ... } válido
        match = re.search(r'\{[\s\S]+\}', texto)
        if match:
            try:
                dados = json.loads(match.group())
                return dados
            except Exception:
                pass
    return None


def eh_circuito_valido(dados: dict) -> bool:
    """Verifica se o JSON tem a estrutura mínima de um circuito."""
    return (
        isinstance(dados, dict)
        and 'components' in dados
        and 'wires' in dados
        and isinstance(dados['components'], list)
        and isinstance(dados['wires'], list)
        and len(dados['components']) > 0
    )


def nome_arquivo(dados: dict) -> str:
    """Gera um nome de arquivo a partir do nome do circuito."""
    nome = dados.get('name', 'circuito')
    # Remove caracteres inválidos para nome de arquivo
    nome = re.sub(r'[\\/:*?"<>|]', '', nome)
    nome = nome.strip().replace(' ', '_')
    timestamp = datetime.now().strftime('%H%M%S')
    return f"{nome}_{timestamp}.json"


def salvar(dados: dict, pasta: str) -> str:
    """Salva o JSON na pasta de destino e retorna o caminho."""
    Path(pasta).mkdir(parents=True, exist_ok=True)
    arquivo = os.path.join(pasta, nome_arquivo(dados))
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    return arquivo


def main():
    print("=" * 52)
    print("  Clipboard Watcher — Proteus Circuit Builder")
    print("=" * 52)
    print(f"\nDestino: {PASTA_DESTINO}")
    print("\nCopie o JSON gerado pelo Claude.")
    print("O arquivo será salvo automaticamente.")
    print("Pressione Ctrl+C para parar.\n")
    print("-" * 52)

    ultimo = ""
    ultimo_salvo = ""

    while True:
        try:
            atual = pyperclip.paste()

            # Só processa se o conteúdo mudou
            if atual != ultimo:
                ultimo = atual

                dados = extrair_json(atual)
                if dados and eh_circuito_valido(dados):
                    # Evita salvar o mesmo circuito duas vezes seguidas
                    chave = json.dumps(dados, sort_keys=True)
                    if chave != ultimo_salvo:
                        ultimo_salvo = chave
                        caminho = salvar(dados, PASTA_DESTINO)
                        nome = dados.get('name', 'Sem nome')
                        comp = len(dados.get('components', []))
                        fios = len(dados.get('wires', []))
                        print(f"\n[OK] Circuito detectado e salvo!")
                        print(f"     Nome       : {nome}")
                        print(f"     Componentes: {comp}")
                        print(f"     Fios       : {fios}")
                        print(f"     Arquivo    : {os.path.basename(caminho)}")
                        print(f"\n     O Proteus deve abrir o circuito em instantes...")
                        print("-" * 52)

            time.sleep(INTERVALO)

        except KeyboardInterrupt:
            print("\n\nMonitor encerrado.")
            sys.exit(0)
        except Exception as e:
            # Erro de leitura de clipboard (comum no Windows em alguns contextos)
            time.sleep(INTERVALO)


if __name__ == '__main__':
    main()
