@echo off
pushd "%~dp0"
set REALFLARE_DEV=

..\venv\Scripts\python.exe -m realflare --frame-start 1 --frame-end 2 --project ..\benchmark\nikon_ai_50_135mm\project.json --arg "flare.light_position [-2.5,0.5] [2.5,1.0]" --output render.$F4.exr
popd .
cmd /k
