@echo off
chcp 65001 >nul
title 女娲升级台 v2.0
echo.
echo  ╔══════════════════════════════════╗
echo  ║       女娲升级台 v2.0           ║
echo  ║    Skill Upgrade Station        ║
echo  ╚══════════════════════════════════╝
echo.
echo  启动中...
echo  打开浏览器访问: http://localhost:8866
echo.
cd /d "%~dp0"
py app.py
pause