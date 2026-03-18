@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "RUNTIME_DIR=%SCRIPT_DIR%python"
set "READY_MARKER=%RUNTIME_DIR%\.ntawesome-runtime-ready"
set "REQUIREMENTS_FILE=%SCRIPT_DIR%requirements-windows.txt"
set "BOOTSTRAP_DIR=%SCRIPT_DIR%bootstrap"
set "PYTHON_ARCHIVE_PATH=%BOOTSTRAP_DIR%\python-portable.zip"
set "PYTHON_ARCHIVE_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.zip"
set "PYTHON_VERSION=3.11.9"
set "FORCE_REINSTALL="
set "SKIP_SYSTEM_PYTHON="
set "PYTHON_COMMAND="
set "BUNDLED_PYTHON="

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--force-reinstall" (
    set "FORCE_REINSTALL=1"
    shift
    goto parse_args
)
if /I "%~1"=="-ForceReinstall" (
    set "FORCE_REINSTALL=1"
    shift
    goto parse_args
)
if /I "%~1"=="--skip-system-python" (
    set "SKIP_SYSTEM_PYTHON=1"
    shift
    goto parse_args
)
if /I "%~1"=="-SkipSystemPython" (
    set "SKIP_SYSTEM_PYTHON=1"
    shift
    goto parse_args
)
if /I "%~1"=="-PythonCommand" (
    if "%~2"=="" goto missing_value
    set "PYTHON_COMMAND=%~2"
    shift
    shift
    goto parse_args
)
if /I "%~1"=="-PythonVersion" (
    if "%~2"=="" goto missing_value
    set "PYTHON_VERSION=%~2"
    shift
    shift
    goto parse_args
)
if /I "%~1"=="-PythonArchiveUrl" (
    if "%~2"=="" goto missing_value
    set "PYTHON_ARCHIVE_URL=%~2"
    shift
    shift
    goto parse_args
)
if /I "%~1"=="-PythonInstallerUrl" (
    if "%~2"=="" goto missing_value
    set "PYTHON_ARCHIVE_URL=%~2"
    shift
    shift
    goto parse_args
)

echo Unknown option: %~1
echo Supported options:
echo   --force-reinstall
echo   --skip-system-python
echo   -PythonCommand ^<ignored_for_compatibility^>
echo   -PythonVersion ^<display_only^>
echo   -PythonArchiveUrl ^<url^>
echo   -PythonInstallerUrl ^<url^>
exit /b 2

:missing_value
echo Missing value for option: %~1
exit /b 2

:args_done
if not exist "%REQUIREMENTS_FILE%" (
    echo Requirements file not found:
    echo   %REQUIREMENTS_FILE%
    exit /b 1
)

if defined PYTHON_COMMAND (
    echo.
    echo Note: -PythonCommand is ignored for the portable Windows bundle.
)

if defined SKIP_SYSTEM_PYTHON (
    echo.
    echo Note: --skip-system-python is no longer needed.
    echo The portable Windows bundle never builds a venv from system Python.
)

call :find_bundled_python

if defined FORCE_REINSTALL (
    call :remove_existing_runtime
    if errorlevel 1 exit /b 1
    set "BUNDLED_PYTHON="
) else if defined BUNDLED_PYTHON (
    echo.
    echo Bundled portable runtime already exists at:
    echo   %BUNDLED_PYTHON%
    call :install_requirements "%BUNDLED_PYTHON%"
    if errorlevel 1 exit /b 1
    goto setup_ready
)

if exist "%RUNTIME_DIR%" (
    call :remove_existing_runtime
    if errorlevel 1 exit /b 1
)

call :ensure_python_archive
if errorlevel 1 exit /b 1

call :extract_runtime
if errorlevel 1 exit /b 1

call :find_bundled_python
if not defined BUNDLED_PYTHON (
    echo Extracted runtime does not contain python.exe:
    echo   %RUNTIME_DIR%
    exit /b 1
)

call :install_requirements "%BUNDLED_PYTHON%"
if errorlevel 1 exit /b 1

:setup_ready
call :find_bundled_python
if not defined BUNDLED_PYTHON (
    echo Setup finished without a usable bundled Python runtime.
    exit /b 1
)

echo.
echo Bundled runtime is ready.
echo Run the processor with:
echo   Run-NTAwesome.cmd
echo.
exit /b 0

:find_bundled_python
set "BUNDLED_PYTHON="
if exist "%RUNTIME_DIR%\python.exe" set "BUNDLED_PYTHON=%RUNTIME_DIR%\python.exe"
if not defined BUNDLED_PYTHON if exist "%RUNTIME_DIR%\Scripts\python.exe" set "BUNDLED_PYTHON=%RUNTIME_DIR%\Scripts\python.exe"
exit /b 0

:remove_existing_runtime
if exist "%RUNTIME_DIR%" (
    echo.
    echo Removing existing bundled runtime...
    rmdir /s /q "%RUNTIME_DIR%"
    if exist "%RUNTIME_DIR%" (
        echo Failed to remove:
        echo   %RUNTIME_DIR%
        exit /b 1
    )
)
exit /b 0

:ensure_python_archive
if exist "%PYTHON_ARCHIVE_PATH%" exit /b 0

if not exist "%BOOTSTRAP_DIR%" md "%BOOTSTRAP_DIR%"

echo.
echo Downloading portable Python %PYTHON_VERSION% runtime...
echo   %PYTHON_ARCHIVE_URL%

curl.exe -L --fail --output "%PYTHON_ARCHIVE_PATH%" "%PYTHON_ARCHIVE_URL%"
if errorlevel 1 (
    echo Failed to download the portable Python runtime.
    echo Keep bootstrap\python-portable.zip with the app folder for offline rebuilds.
    exit /b 1
)

if not exist "%PYTHON_ARCHIVE_PATH%" (
    echo Portable Python archive not found after download:
    echo   %PYTHON_ARCHIVE_PATH%
    exit /b 1
)

exit /b 0

:extract_runtime
echo.
echo Extracting portable Python runtime...
echo   %PYTHON_ARCHIVE_PATH%

md "%RUNTIME_DIR%" >nul 2>&1
tar -xf "%PYTHON_ARCHIVE_PATH%" -C "%RUNTIME_DIR%"
if errorlevel 1 (
    echo Failed to extract the portable Python runtime.
    exit /b 1
)

exit /b 0

:install_requirements
set "TARGET_PYTHON=%~1"
if not exist "%TARGET_PYTHON%" (
    echo Python executable not found:
    echo   %TARGET_PYTHON%
    exit /b 1
)

echo.
echo Installing required packages into the bundled runtime...
echo.

if exist "%READY_MARKER%" del "%READY_MARKER%" >nul 2>&1

"%TARGET_PYTHON%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo Bootstrapping pip in the bundled runtime...
    "%TARGET_PYTHON%" -m ensurepip --upgrade
    if errorlevel 1 (
        echo Failed to bootstrap pip in the bundled runtime.
        exit /b 1
    )
)

"%TARGET_PYTHON%" -m pip install --disable-pip-version-check -r "%REQUIREMENTS_FILE%"
if errorlevel 1 (
    echo Failed to install required packages into the bundled runtime.
    exit /b 1
)

type nul > "%READY_MARKER%"
exit /b 0
