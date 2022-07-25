@echo off
pushd "%~dp0"
set REALFLARE_DEV=

venv\Scripts\python.exe -m flare --frame-start 1 --frame-end 400 --project C:\Users\Beat\nikon.json --arg "flare.light_position [-2.5,0.5] [2.5,1.0]" --output D:/files/dev/027_flare/render/nikon_v006/render.$F4.exr
popd .
cmd /k
