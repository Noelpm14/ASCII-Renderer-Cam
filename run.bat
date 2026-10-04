@echo off
if "%1"=="go" goto run

rem open a new maximized cmd window and re-run this script
start /max "" cmd /c "%~f0 go"
exit

:run
rem set console to very large so it fills the maximized window
mode con cols=300 lines=80
cd /d "C:\Users\DELL\.gemini\antigravity\scratch\ascii-video-renderer"
py ascii_renderer.py
pause
