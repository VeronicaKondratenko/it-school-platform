@echo off
setlocal EnableExtensions
title IT School - Start (run only)

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo =============================================
echo   IT School Platform - Start (RUN ONLY)
echo   (does NOT install or seed)
echo =============================================
echo.

if exist ".venv\Scripts\python.exe" goto :venv_ok
echo [ERROR] Virtual environment .venv was not found.
echo Run the setup-and-start Windows batch file first to install and seed the project.
goto :end
:venv_ok

echo Activating .venv...
call ".venv\Scripts\activate.bat"
if errorlevel 1 ( echo [ERROR] Failed to activate virtual environment. & goto :end )

echo Starting backend + frontend and opening browser...
set "FRONTEND_PORT="
for %%P in (8080 8081 8082) do call :try_port %%P
if not defined FRONTEND_PORT ( echo [ERROR] Frontend ports 8080-8082 are busy. & goto :end )
echo Using frontend port: %FRONTEND_PORT%

start "IT School - Backend" cmd /k "cd /d %ROOT%backend && call %ROOT%.venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
call :wait_for_port 8000 90
if errorlevel 1 ( echo [ERROR] Backend did not open port 8000 in time. Check its window. & goto :end )

start "IT School - Frontend" cmd /k "cd /d %ROOT%frontend && call %ROOT%.venv\Scripts\activate.bat && python -m http.server %FRONTEND_PORT%"
call :wait_for_port %FRONTEND_PORT% 25
if errorlevel 1 ( echo [ERROR] Frontend did not open port %FRONTEND_PORT% in time. Check its window. & goto :end )

start "" "http://localhost:%FRONTEND_PORT%/index.html"
echo.
echo Startup complete. Keep the Backend and Frontend windows open while using the app.
goto :end

:try_port
if defined FRONTEND_PORT exit /b 0
call :is_port_in_use %1
if errorlevel 1 set "FRONTEND_PORT=%1"
exit /b 0

:is_port_in_use
netstat -ano | findstr /R /C:":%~1 .*LISTENING" >nul 2>nul
exit /b %errorlevel%

:wait_for_port
set "WP=%~1"
set "WMAX=%~2"
set /a WE=0
:wfp_loop
call :is_port_in_use %WP%
if not errorlevel 1 exit /b 0
if %WE% GEQ %WMAX% exit /b 1
timeout /t 1 /nobreak >nul
set /a WE+=1
goto :wfp_loop

:end
echo.
echo ------------------------------------------------------------
echo Press any key to close this window...
pause >nul
endlocal
exit /b
