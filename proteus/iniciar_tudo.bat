@echo off
title Proteus Builder - Iniciando...
echo ============================================
echo  Proteus Circuit Builder - Inicio Completo
echo ============================================
echo.
echo Iniciando os dois monitores:
echo   1. Clipboard Watcher  (copia JSON do Claude)
echo   2. Circuit Builder    (cria no Proteus)
echo.
echo Abra o Proteus antes de continuar.
echo.
pause

REM Abre o clipboard watcher em uma janela separada
start "Clipboard Watcher" cmd /k "cd /d %~dp0 && python clipboard_watcher.py"

REM Aguarda 2 segundos
timeout /t 2 /nobreak >nul

REM Abre o builder (modo watch) em outra janela
start "Proteus Builder" cmd /k "cd /d %~dp0 && python builder.py --watch "H:\Meu Drive\R&F CASA E ESTILO\RF - ARDUINO\PROTEUS - PROJETOS DE CIRCUITOS""

echo.
echo [OK] Dois monitores iniciados em janelas separadas.
echo.
echo Fluxo de uso:
echo   1. Peca o circuito ao Claude
echo   2. Clique em "Copiar" no JSON gerado
echo   3. O Clipboard Watcher salva o arquivo automaticamente
echo   4. O Builder detecta e cria o circuito no Proteus
echo.
echo Pode fechar esta janela.
pause
