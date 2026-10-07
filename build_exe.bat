@echo off
rem ASCII-only launcher (cmd.exe mangles UTF-8 batch files).
rem All real logic and messages live in build_exe.py.
cd /d "%~dp0"
python "%~dp0build_exe.py"
if errorlevel 1 pause
