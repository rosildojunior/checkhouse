# Contexto da Sessão — Proteus Circuit Builder

## Objetivo

Criar uma pipeline para gerar circuitos eletrônicos no Proteus automaticamente:
- **Com tokens:** Claude gera o JSON com a lista de conexões
- **Sem tokens:** script local lê o JSON e cria o circuito no Proteus

---

## Repositório

- **URL:** https://github.com/rosildojunior/checkhouse
- **Branch:** `ccr-5c70d27c-fgmkcw`
- **Pasta do projeto:** `proteus/`
- **Download ZIP:** https://github.com/rosildojunior/checkhouse/archive/refs/heads/ccr-5c70d27c-fgmkcw.zip

---

## Arquivos criados

| Arquivo | Função |
|---|---|
| `builder.py` | Lê JSON e cria circuito no Proteus via COM |
| `clipboard_watcher.py` | Monitora clipboard, salva JSON automaticamente |
| `diagnostico.py` | Testa todas as etapas e reporta erros |
| `diagnostico.bat` | Executa o diagnóstico |
| `CLAUDE_PROMPT.md` | System prompt para o Claude gerar JSONs |
| `iniciar_tudo.bat` | Liga clipboard watcher + builder juntos |
| `rodar.bat` | Liga só o builder em modo watch |
| `setup.bat` | Instala pywin32 + pyperclip |
| `schema.json` | Especificação do formato JSON |
| `examples/` | Exemplos: NE555 blink + amplificador BC547 |

---

## Pasta de destino dos circuitos

```
H:\Meu Drive\R&F CASA E ESTILO\RF - ARDUINO\PROTEUS - PROJETOS DE CIRCUITOS
```

---

## Status atual — problema identificado

O `builder.py` tenta conectar ao Proteus via COM automation, mas os ProgIDs
estão errados para esta instalação.

### ProgIDs tentados (todos falharam)
```
Labcenter.ProteusIDE
Labcenter.Proteus
ISIS.Application
ProteusAutomate.Application
Labcenter.Schematic
```

### ProgIDs encontrados no registro do Windows do usuário
```
PDS.ImportServer
PDS.ImportServer.1
Labcenter Electronics.Proteus.pdsprj
Labcenter Electronics.Proteus.pdspnl
Labcenter Electronics.Proteus.lxk
```

---

## Próximo passo — o que precisa ser feito

1. Rodar `diagnostico.bat` no PC do usuário (versão atualizada já no repo)
2. O diagnóstico vai revelar:
   - Onde o Proteus está instalado
   - Métodos disponíveis no `PDS.ImportServer.1`
   - CLSID exato de cada objeto COM registrado
   - Se ISIS.EXE está em execução
3. Com o resultado, reescrever `builder.py` com o ProgID e API corretos

---

## Fluxo desejado (quando estiver funcionando)

```
1. Usuário pede circuito ao Claude
        ↓  (tokens gastos aqui)
2. Claude retorna JSON estruturado
        ↓
3. Usuário clica "Copiar" no JSON
        ↓  (0 tokens daqui em diante)
4. clipboard_watcher.py detecta → salva .json na pasta do Drive
        ↓
5. builder.py detecta o arquivo → cria circuito no Proteus
        ↓
6. Proteus abre com o circuito completo
```

---

## Dependências necessárias no PC

```
pip install pywin32
pip install pyperclip
python Scripts\pywin32_postinstall.py -install
```

---

## Formato JSON dos circuitos

```json
{
  "name": "Nome do circuito",
  "description": "Como funciona",
  "supply_voltage": 5,
  "components": [
    { "ref": "U1",   "part": "NE555",   "value": "NE555" },
    { "ref": "R1",   "part": "RES",     "value": "47k"   },
    { "ref": "LED1", "part": "LED-RED", "value": "LED"   }
  ],
  "wires": [
    { "from": {"ref": "U1",   "pin": "OUT"}, "to": {"ref": "R1",   "pin": "1"} },
    { "from": {"ref": "R1",   "pin": "2"},   "to": {"ref": "LED1", "pin": "A"} },
    { "from": {"ref": "LED1", "pin": "K"},   "to": {"ref": "BAT1", "pin": "-"} }
  ],
  "power_nets": { "VCC": 5, "GND": 0 }
}
```

---

## Instrução para nova sessão local

Cole este contexto e diga:

> "Preciso que você rode o `diagnostico.py` que está na pasta `proteus/`
> e use o resultado para corrigir o `builder.py`, substituindo os ProgIDs
> errados pelos corretos encontrados no registro do Windows.
> Depois teste criando o circuito do arquivo `examples/blink_led_555.json`."
