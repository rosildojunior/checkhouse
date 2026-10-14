# Proteus Circuit Builder

Crie qualquer circuito eletrônico no Proteus a partir de uma descrição em JSON.

**Fluxo:**
```
Claude (gasta tokens) → JSON do circuito → builder.py → Circuito no Proteus (0 tokens)
```

---

## Instalação (Windows)

```
cd proteus
setup.bat
```

Ou manualmente:
```
pip install pywin32
python Scripts\pywin32_postinstall.py -install
```

---

## Uso básico

```bash
# Construir um circuito
python builder.py meu_circuito.json

# Construir e salvar arquivo Proteus
python builder.py meu_circuito.json saida.pdsprj

# Monitorar pasta (executa automaticamente ao detectar novo .json)
python builder.py --watch C:\Circuitos\fila\
```

---

## Como gerar o JSON com o Claude

1. Abra o Claude (claude.ai ou API)
2. Cole o System Prompt em `CLAUDE_PROMPT.md` no campo de sistema
3. Descreva o circuito que quer criar:
   - *"Piscador de LED com NE555 a 1Hz com alimentação 5V"*
   - *"Amplificador não-inversor com LM741 ganho 10x"*
   - *"Fonte regulada 5V a partir de 12V usando 7805"*
4. Claude retorna o JSON — copie e salve como `.json`
5. Execute `python builder.py seu_arquivo.json`

---

## Exemplos incluídos

| Arquivo | Circuito |
|---------|----------|
| `examples/blink_led_555.json` | Piscador de LED com NE555 (~1Hz) |
| `examples/amplificador_bc547.json` | Amplificador emissor-comum BC547 |

---

## Estrutura do JSON

```json
{
  "name": "Nome do circuito",
  "description": "Como funciona",
  "supply_voltage": 5,
  "components": [
    { "ref": "U1", "part": "NE555", "value": "NE555" },
    { "ref": "R1", "part": "RES",   "value": "47k"   },
    { "ref": "LED1","part": "LED",  "value": "LED-RED"}
  ],
  "wires": [
    { "from": {"ref": "U1",   "pin": "OUT"}, "to": {"ref": "R1",   "pin": "1"} },
    { "from": {"ref": "R1",   "pin": "2"},   "to": {"ref": "LED1", "pin": "A"} },
    { "from": {"ref": "LED1", "pin": "K"},   "to": {"ref": "GND1", "pin": "1"} }
  ]
}
```

Sem `"position"` → auto-layout automático.

---

## Solução de problemas

**"Não foi possível conectar ao Proteus"**
- Instale o Proteus e execute-o ao menos uma vez
- Execute como Administrador na primeira vez
- Registre o COM: vá em `C:\Program Files (x86)\Labcenter Electronics\Proteus 8 Professional\BIN` e execute `regsvr32 ISIS.EXE`

**"pywin32 não encontrado"**
- `pip install pywin32`
- `python Scripts\pywin32_postinstall.py -install`

**Componente não encontrado**
- Verifique o nome em `LIBRARY_MAP` dentro de `builder.py`
- Adicione mapeamentos novos na seção `LIBRARY_MAP` conforme necessário
- Ou especifique `"library"` e `"part"` explicitamente no JSON
