@echo off
setlocal EnableExtensions
title IT School - Setup + Seed + Start (Windows)

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo ==================================================
echo   IT School Platform - SETUP + SEED + START
echo   Creates venv, installs deps, seeds the database
echo   with realistic data, then launches the system.
echo ==================================================
echo.

echo [1/7] Checking Python...
set "PYTHON_CMD="
where py >nul 2>nul
if %errorlevel%==0 set "PYTHON_CMD=py -3"
if defined PYTHON_CMD goto :py_ok
where python >nul 2>nul
if %errorlevel%==0 set "PYTHON_CMD=python"
:py_ok
if not defined PYTHON_CMD (
    echo [ERROR] Python was not found in PATH.
    echo Install Python 3.10+ and enable "Add Python to PATH".
    goto :end
)
echo Using: %PYTHON_CMD%

echo [2/7] Checking virtual environment (.venv)...
if not exist ".venv\Scripts\python.exe" (
    echo Creating .venv...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 ( echo [ERROR] Failed to create virtual environment. & goto :end )
) else (
    echo .venv already exists.
)

echo Activating .venv...
call ".venv\Scripts\activate.bat"
if errorlevel 1 ( echo [ERROR] Failed to activate virtual environment. & goto :end )

echo [3/7] Installing dependencies (may take a few minutes)...
python -m pip install --upgrade pip
if errorlevel 1 ( echo [ERROR] Failed to upgrade pip. & goto :end )
pip install -r "backend\requirements.txt"
if errorlevel 1 ( echo [ERROR] Failed to install backend dependencies. & goto :end )

echo [4/7] Checking backend\.env ...
if exist "backend\.env" goto :env_exists
echo backend\.env not found. Creating it from backend\.env.example...
copy /Y "backend\.env.example" "backend\.env" >nul
echo.
echo [ACTION REQUIRED] Edit backend\.env: set DATABASE_URL and SECRET_KEY.
echo PostgreSQL must be running and the database must exist. Then run this file again.
echo Opening backend\.env in Notepad...
notepad "backend\.env"
goto :end
:env_exists
findstr /C:"user:password@localhost:5432/dbname" "backend\.env" >nul 2>nul
if errorlevel 1 goto :env_ok
echo.
echo [ACTION REQUIRED] backend\.env still contains the EXAMPLE DATABASE_URL.
echo Edit it and set your real PostgreSQL connection, then run this file again.
echo Opening backend\.env in Notepad...
notepad "backend\.env"
goto :end
:env_ok

echo [5/7] Applying Alembic migrations (base tables)...
alembic -c "backend\alembic.ini" upgrade head
echo (If Alembic printed an error above, it is OK - the seed step creates missing tables.)

echo [6/7] Seeding REALISTIC data...
echo WARNING: this DELETES all existing courses and users EXCEPT the test accounts
echo (admin@school.com, teacher@example.com, student@example.com).
python -m backend.seed_realistic
if errorlevel 1 (
    echo.
    echo [ERROR] Realistic seed failed.
    echo Most likely causes:
    echo   - PostgreSQL is not running, or
    echo   - DATABASE_URL in backend\.env is wrong, or the database does not exist.
    goto :end
)

echo [7/7] Starting backend + frontend and opening browser...
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
echo Setup + seed + startup complete.
echo Account table: backend\accounts.csv  (all new passwords = password)
echo Keep the Backend and Frontend windows open while using the app.
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
