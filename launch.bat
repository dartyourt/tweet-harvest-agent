@echo off
echo Starting Twitter Scraper Agent...
python launch.py
if %ERRORLEVEL% NEQ 0 (
    echo Error launching Twitter Scraper Agent
    echo Please check if Python is installed and dependencies are available
    pause
)
