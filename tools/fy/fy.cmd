@echo off
rem fy launcher: uses the repo virtual environment when it exists, else whatever python is on PATH.
set "FY_PY=%~dp0..\..\.venv\Scripts\python.exe"
if not exist "%FY_PY%" set "FY_PY=python"
"%FY_PY%" "%~dp0" %*
