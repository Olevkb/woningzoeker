@echo off
rem Start de woningzoeker; hij blijft scannen zolang dit venster open is.
cd /d "%~dp0"
title Woningzoeker
python -m woningzoeker --loop
pause
