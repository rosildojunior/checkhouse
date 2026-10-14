@echo off
echo ============================================
echo  Proteus Circuit Builder - Instalacao
echo ============================================
echo.

REM Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [XX] Python nao encontrado. Instale em: https://python.org
    pause
    exit /b 1
)

echo [OK] Python encontrado
echo.

REM Instala dependencias
echo [..] Instalando pywin32...
pip install pywin32 --quiet

echo [..] Instalando pyperclip...
pip install pyperclip --quiet
if errorlevel 1 (
    echo [XX] Falha ao instalar pywin32
    pause
    exit /b 1
)

REM Post-install do pywin32 (registra DLLs)
echo [..] Registrando pywin32...
python -c "import sys; sys.path.insert(0, next(p for p in sys.path if 'site-packages' in p))" 2>nul
python Scripts\pywin32_postinstall.py -install 2>nul || python -m pywin32_postinstall -install 2>nul

echo.
echo [OK] Instalacao concluida!
echo.
echo Como usar:
echo   python builder.py examples\blink_led_555.json
echo   python builder.py meu_circuito.json saida.pdsprj
echo   python builder.py --watch pasta\
echo.

REM Testa conexao com Proteus
echo [..] Testando conexao com Proteus...
python -c "
import win32com.client
progids = ['Labcenter.ProteusIDE','Labcenter.Proteus','ISIS.Application']
connected = False
for p in progids:
    try:
        win32com.client.GetActiveObject(p)
        print(f'[OK] Proteus em execucao encontrado: {p}')
        connected = True
        break
    except: pass
if not connected:
    print('[!!] Proteus nao esta em execucao')
    print('     Abra o Proteus e execute o builder novamente')
    print('     OU execute o builder com o Proteus fechado (ele sera iniciado)')
"

echo.
pause
