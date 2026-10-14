@echo off
title Proteus Circuit Builder - Aguardando circuitos...
echo ============================================
echo  Proteus Circuit Builder - Modo Automatico
echo ============================================
echo.
echo Monitorando:
echo H:\Meu Drive\R^&F CASA E ESTILO\RF - ARDUINO\PROTEUS - PROJETOS DE CIRCUITOS
echo.
echo Salve qualquer .json nessa pasta e o circuito
echo sera criado no Proteus automaticamente.
echo.
echo Pressione Ctrl+C para parar.
echo ============================================
echo.

python builder.py --watch "H:\Meu Drive\R&F CASA E ESTILO\RF - ARDUINO\PROTEUS - PROJETOS DE CIRCUITOS"

pause
