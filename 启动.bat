@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 --version >nul 2>&1
if errorlevel 1 (
  echo 请先安装 Python 3.10 或以上版本，再运行本文件。
  echo 下载地址：https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8765"
py -3 app.py
pause
