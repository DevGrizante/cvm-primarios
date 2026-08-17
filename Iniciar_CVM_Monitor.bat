@echo off
setlocal EnableDelayedExpansion
title CVM Monitor Pro - Servidor
color 0B
cd /d "%~dp0"

rem ===========================================================================
rem  CVM MONITOR PRO - inicializador autossuficiente
rem
rem  Exigencia unica: Python 3.10+ instalado. O resto (ambiente virtual,
rem  dependencias, porta) este script resolve sozinho. O frontend ja vem
rem  compilado em frontend\dist e e servido pelo proprio backend, entao nao ha
rem  Node.js nem npm no caminho.
rem
rem  CONVIVENCIA COM O CAPTACAO E RESGATE
rem  Os dois projetos rodam juntos na mesma maquina. As portas padrao nao se
rem  cruzam (aqui 8080, la 8000/5500) e, se a 8080 estiver ocupada, o script
rem  procura a proxima livre em vez de subir por cima de um servidor alheio.
rem  Cada projeto tem o seu proprio ambiente virtual, dentro da sua pasta.
rem ===========================================================================

rem O servidor roda na janela principal, entao quem abre o navegador tem que
rem ser outro processo. Em vez de um segundo arquivo .bat so para isso, o
rem script se reinvoca com esta flag numa janela minimizada.
if /i "%~1"=="--abrir-navegador" goto :abrir_navegador

set "PORTA=8080"

echo ========================================================
echo         CVM MONITOR PRO - INICIANDO O SISTEMA
echo ========================================================
echo.

rem --- 1) Encontrar um Python utilizavel -------------------------------------
rem O "python" do PATH pode ser o atalho da Microsoft Store, que nao executa
rem nada e so abre a loja. Por isso testamos rodando de fato, e caimos no
rem lancador "py -3" quando o primeiro nao serve.
set "PY="
call :testar_python "python" && set "PY=python"
if not defined PY call :testar_python "py -3" && set "PY=py -3"

if not defined PY (
    color 0C
    echo [ERRO] Nao encontrei um Python 3.10 ou superior neste computador.
    echo.
    echo Instale pelo site oficial ^(python.org/downloads^) e marque a opcao
    echo "Add python.exe to PATH" durante a instalacao. Depois rode este
    echo arquivo de novo.
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%v in ('%PY% -c "import sys;print(sys.version.split()[0])"') do set "PYVER=%%v"
echo [INFO] Python %PYVER% encontrado.

rem --- 2) Ambiente virtual ---------------------------------------------------
cd /d "%~dp0backend"

if not exist "venv\Scripts\python.exe" (
    echo [INFO] Primeira execucao: criando o ambiente virtual isolado...
    echo        ^(pode levar um minuto; acontece so uma vez^)
    %PY% -m venv venv
    if errorlevel 1 (
        color 0C
        echo [ERRO] Falhei ao criar o ambiente virtual em backend\venv
        pause
        exit /b 1
    )
)
set "VENV_PY=%~dp0backend\venv\Scripts\python.exe"

rem --- 3) Dependencias -------------------------------------------------------
rem Instalar a cada clique custaria uns 10 segundos por nada. Guardamos uma
rem copia do requirements.txt dentro do venv: enquanto os dois forem iguais,
rem o ambiente ja esta correto e o pip nem e chamado.
set "PRECISA_INSTALAR=1"
if exist "venv\requirements.lock" (
    fc /b "requirements.txt" "venv\requirements.lock" >nul 2>&1 && set "PRECISA_INSTALAR=0"
)

if "!PRECISA_INSTALAR!"=="1" (
    echo [INFO] Instalando as dependencias...
    "%VENV_PY%" -m pip install --upgrade pip --quiet --disable-pip-version-check
    "%VENV_PY%" -m pip install -r requirements.txt --quiet --disable-pip-version-check
    if errorlevel 1 (
        color 0C
        echo [ERRO] Falhei ao instalar as dependencias.
        echo        Verifique a conexao com a internet e tente de novo.
        pause
        exit /b 1
    )
    copy /y "requirements.txt" "venv\requirements.lock" >nul
    echo [INFO] Dependencias instaladas.
) else (
    echo [INFO] Dependencias ja instaladas.
)

rem --- 4) Porta --------------------------------------------------------------
call :porta_livre %PORTA% PORTA
if "!PORTA!"=="" (
    color 0C
    echo [ERRO] Nao achei nenhuma porta livre para o servidor.
    pause
    exit /b 1
)
echo [INFO] Servidor na porta !PORTA!
rem O main.py le a porta desta variavel.
set "PORT=!PORTA!"

rem --- 5) Subir o servidor ---------------------------------------------------
rem O servidor roda NESTA janela (fechar a janela desliga o sistema, que e o
rem que o usuario espera). O navegador entao precisa ser aberto por outra: uma
rem janela auxiliar espera o servidor comecar a ouvir e so entao abre, porque
rem o carregamento inicial dos dados da CVM leva alguns segundos e abrir antes
rem mostraria "nao foi possivel conectar" sem que nada estivesse errado.
start /min "Abrir CVM Monitor" cmd /c ""%~f0" --abrir-navegador !PORTA!"

echo.
echo ========================================================
echo [SUCESSO] Tudo pronto^^! O servidor sera iniciado agora.
echo.
echo   Painel ....... http://localhost:!PORTA!
echo   API / docs ... http://localhost:!PORTA!/docs
echo.
echo 1. O seu navegador padrao abrira automaticamente.
echo 2. Mantenha ESTA JANELA PRETA ABERTA enquanto usa o painel.
echo 3. Para desligar, basta fechar esta janela.
echo ========================================================
echo.

"%VENV_PY%" main.py

echo.
echo [INFO] O servidor foi encerrado.
pause
exit /b 0


rem ===========================================================================
rem  Sub-rotinas
rem ===========================================================================

rem :abrir_navegador - modo auxiliar, chamado pelo proprio script.
rem Espera o servidor comecar a ouvir na porta e so entao abre o navegador. O
rem teto de 60s evita uma janela pendurada para sempre se o servidor nao subir.
:abrir_navegador
for /l %%i in (1,1,30) do (
    ping -n 3 127.0.0.1 >nul
    netstat -an -p TCP | findstr /c:":%~2 " | findstr /i /c:"LISTENING" >nul 2>&1
    if not errorlevel 1 (
        start "" "http://localhost:%~2"
        exit /b 0
    )
)
exit /b 0

rem Roda o interpretador candidato e confere a versao. Retorna 0 se serve.
:testar_python
%~1 -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
exit /b %errorlevel%

rem :porta_livre <porta inicial> <nome da variavel de saida>
rem Anda para cima ate achar uma porta sem ninguem ouvindo. Devolve vazio se
rem as 20 seguintes tambem estiverem ocupadas - nesse caso a maquina tem outro
rem problema, e insistir so esconderia isso.
:porta_livre
set /a "_p=%~1"
set /a "_teto=%~1+20"
:_proxima_porta
netstat -an -p TCP | findstr /c:":!_p! " | findstr /i /c:"LISTENING" >nul 2>&1
if errorlevel 1 (
    set "%~2=!_p!"
    exit /b 0
)
echo [INFO] Porta !_p! ocupada, tentando a proxima...
set /a "_p+=1"
if !_p! gtr !_teto! (
    set "%~2="
    exit /b 1
)
goto :_proxima_porta
