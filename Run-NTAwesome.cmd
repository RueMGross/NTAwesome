@echo off
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
set "PROCESSOR_SCRIPT=%SCRIPT_DIR%app\zetaview_plotter.py"
set "SETUP_SCRIPT=%SCRIPT_DIR%Setup-NTAwesome.cmd"
set "READY_MARKER=%SCRIPT_DIR%python\.ntawesome-runtime-ready"
set "PYTHON_EXE="
set "SKIP_SETUP="

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--skip-setup" (
    set "SKIP_SETUP=1"
    shift
    goto parse_args
)
if /I "%~1"=="-SkipSetup" (
    set "SKIP_SETUP=1"
    shift
    goto parse_args
)
goto args_done

:args_done
pushd "%SCRIPT_DIR%" >nul 2>&1
if errorlevel 1 (
    echo Could not access the script folder:
    echo   %SCRIPT_DIR%
    echo Keep the app bundle on a local Windows drive.
    echo.
    pause
    exit /b 1
)

chcp 65001 >nul 2>&1

call :find_bundled_python
if defined PYTHON_EXE if not exist "%READY_MARKER%" set "PYTHON_EXE="

if not exist "%PROCESSOR_SCRIPT%" (
    echo Processor script not found:
    echo   %PROCESSOR_SCRIPT%
    set "EXIT_CODE=1"
    goto finish
)

if not defined PYTHON_EXE (
    if defined SKIP_SETUP (
        echo Bundled Python runtime not found and setup was skipped.
        echo Run Setup-NTAwesome.cmd first, or launch without -SkipSetup.
        set "EXIT_CODE=1"
        goto finish
    )

    if not exist "%SETUP_SCRIPT%" (
        echo Setup script not found:
        echo   %SETUP_SCRIPT%
        set "EXIT_CODE=1"
        goto finish
    )

    echo Bundled Python runtime not found.
    echo Starting first-time setup...
    echo.
    call "%SETUP_SCRIPT%"
    if errorlevel 1 (
        set "EXIT_CODE=1"
        goto finish
    )

    call :find_bundled_python
    if defined PYTHON_EXE if not exist "%READY_MARKER%" set "PYTHON_EXE="
    if not defined PYTHON_EXE (
        echo Setup completed, but bundled Python is still missing.
        set "EXIT_CODE=1"
        goto finish
    )
)

echo Starting NTAwesome...
echo.
"%PYTHON_EXE%" "%PROCESSOR_SCRIPT%" %*
set "EXIT_CODE=%ERRORLEVEL%"

:finish
popd

if not "%EXIT_CODE%"=="0" (
    echo.
    echo NTAwesome stopped with error code %EXIT_CODE%.
    echo Press any key to close this window.
    pause >nul
)

exit /b %EXIT_CODE%

:find_bundled_python
set "PYTHON_EXE="
if exist "%SCRIPT_DIR%python\python.exe" set "PYTHON_EXE=%SCRIPT_DIR%python\python.exe"
if not defined PYTHON_EXE if exist "%SCRIPT_DIR%python\Scripts\python.exe" set "PYTHON_EXE=%SCRIPT_DIR%python\Scripts\python.exe"
exit /b 0
