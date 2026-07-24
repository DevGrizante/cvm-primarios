@echo off
title CVM Monitor Pro - Servidor
color 0B

echo ========================================================
echo         CVM MONITOR PRO - INICIANDO O SISTEMA           
echo ========================================================
echo.

:: 1. Verifica se o Python esta instalado
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    color 0C
    echo [ERRO] O Python nao foi encontrado neste computador!
    echo.
    echo Por favor, instale o Python abrindo a Microsoft Store
    echo e pesquisando por "Python 3.11" ou superior.
    echo.
    pause
    exit /b
)

:: Volta para a raiz caso o script seja executado de outro lugar, 
:: e entra na pasta backend
cd /d "%~dp0"
cd backend

:: 2. Verifica se o ambiente virtual (venv) existe
IF NOT EXIST "venv\Scripts\activate.bat" (
    echo [INFO] Primeira execucao detectada neste PC!
    echo [INFO] Criando o ambiente virtual isolado... (Isso pode levar um minuto)
    python -m venv venv
)

:: 3. Ativa o ambiente e instala dependencias
echo [INFO] Preparando as dependencias...
call venv\Scripts\activate.bat
pip install -r requirements.txt -q

:: 4. Finaliza e abre
echo.
echo ========================================================
echo [SUCESSO] Tudo pronto! O servidor sera iniciado agora.
echo.
echo 1. O seu navegador padrao abrira automaticamente.
echo 2. Mantenha ESTA JANELA PRETA ABERTA enquanto usa o painel.
echo 3. Para desligar, basta fechar esta janela.
echo ========================================================
echo.

:: Aguarda 2 segundos e manda abrir o navegador no Windows
start "" "http://localhost:8000"

:: Roda o servidor do backend (o Uvicorn ou o run_server se houver)
python main.py

pause
