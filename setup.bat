@echo off

rem Check if Python 3.10 is installed
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
@REM create venv
%python% -m venv venv
set venv=%~dp0venv\Scripts\python.exe
if not exist %venv% (
    %venv% -m pip install --upgrade pip
    %venv% -m flare --gui
)

@REM install repo
%venv% -m pip install --upgrade flare@https://github.com/beatreichenbach/realflare/archive/refs/heads/main.zip

@REM create run.bat
set run=run.bat
if not exist %run% (
    echo @echo off > %run%
    echo %venv% -m flare --gui >> %run%
    echo if %%errorlevel%% neq 0 pause >> %run%
)

@REM success
echo Installation successful
pause
