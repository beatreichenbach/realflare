@echo off


rem Check if Python 3.10 is installed
echo Finding Python 3.10

python --version 2>nul | findstr /B /C:"Python 3.10" >nul
if %errorlevel% equ 0 (
    set python=python
    goto run
)

py -3.10 --version 2>nul
if %errorlevel% equ 0 (
    set python=py -3.10
    goto run
)

where python3.10.exe 2>nul
if %errorlevel% equ 0 (
    set python=python3.10.exe
    goto run
)

@REM python not found
echo Python 3.10 is not installed. Please download and install it from https://www.python.org/ftp/python/3.10.10/python-3.10.10-amd64.exe
pause
exit /B 1

:run
echo Python 3.10 found: %python%

@REM create venv
set venv="%~dp0venv\Scripts\python.exe"
if not exist %venv% (
    echo Installing venv
    %python% -m venv venv
    if %errorlevel% neq 0 goto error
)

@REM install repo
%venv% -m pip install --upgrade pip
echo Installing Realflare
%venv% -m pip install --upgrade realflare@https://github.com/beatreichenbach/realflare/archive/refs/heads/main.zip
if %errorlevel% neq 0 goto error

@REM create run.bat
set run=run.bat
if not exist %run% (
    echo Creating run.bat
    echo @echo off >> %run%
    echo %venv% -m realflare --gui >> %run%
    echo if %%errorlevel%% neq 0 pause >> %run%
)

@REM success
echo Installation successful
pause
exit

@REM error
:error
echo Installation failed
pause
exit
