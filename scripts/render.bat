@echo off
pushd "%~dp0"
set REALFLARE_DEV=

..\venv39\Scripts\python.exe -m realflare --frame-start 1 --frame-end 2 --project ..\benchmark\nikon_ai_50_135mm\project.json --animation ..\benchmark\nikon_ai_50_135mm\project.animation.json --output ..\render\render.%%04d.exr --element FLARE_STARBURST
popd .
cmd /k
