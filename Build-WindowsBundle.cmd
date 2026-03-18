@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
set "DIST_DIR=%ROOT_DIR%dist\NTAAwesome"
set "DIST_ZIP=%ROOT_DIR%dist\NTAAwesome-win.zip"

echo.
echo Building Windows release bundle...
echo.

if exist "%DIST_DIR%" (
    echo Removing previous bundle folder...
    rmdir /s /q "%DIST_DIR%"
    if exist "%DIST_DIR%" (
        echo Failed to remove:
        echo   %DIST_DIR%
        exit /b 1
    )
)

if exist "%DIST_ZIP%" del "%DIST_ZIP%" >nul 2>&1

if not exist "%ROOT_DIR%dist" md "%ROOT_DIR%dist"
if not exist "%DIST_DIR%" md "%DIST_DIR%"
if not exist "%DIST_DIR%\bootstrap" md "%DIST_DIR%\bootstrap"

echo Copying app files...
xcopy "%ROOT_DIR%app" "%DIST_DIR%\app" /E /I /Y /Q >nul
if errorlevel 1 exit /b 1

copy /Y "%ROOT_DIR%Run-NTAwesome.cmd" "%DIST_DIR%\Run-NTAwesome.cmd" >nul || exit /b 1
copy /Y "%ROOT_DIR%Run-NTAwesome.ps1" "%DIST_DIR%\Run-NTAwesome.ps1" >nul || exit /b 1
copy /Y "%ROOT_DIR%Setup-NTAwesome.cmd" "%DIST_DIR%\Setup-NTAwesome.cmd" >nul || exit /b 1
copy /Y "%ROOT_DIR%Setup-NTAwesome.ps1" "%DIST_DIR%\Setup-NTAwesome.ps1" >nul || exit /b 1
copy /Y "%ROOT_DIR%Prepare-WindowsRuntime.ps1" "%DIST_DIR%\Prepare-WindowsRuntime.ps1" >nul || exit /b 1
copy /Y "%ROOT_DIR%requirements-windows.txt" "%DIST_DIR%\requirements-windows.txt" >nul || exit /b 1
copy /Y "%ROOT_DIR%README-Bundle.md" "%DIST_DIR%\README.md" >nul || exit /b 1

if exist "%ROOT_DIR%bootstrap\python-portable.zip" (
    echo Copying cached portable Python archive...
    copy /Y "%ROOT_DIR%bootstrap\python-portable.zip" "%DIST_DIR%\bootstrap\python-portable.zip" >nul || exit /b 1
)

echo.
echo Building bundled Python runtime inside the release folder...
pushd "%DIST_DIR%" >nul
call "%DIST_DIR%\Setup-NTAwesome.cmd" --force-reinstall
if errorlevel 1 (
    popd >nul
    exit /b 1
)
popd >nul

echo.
echo Creating release zip...
pushd "%ROOT_DIR%dist" >nul
tar -a -cf "NTAAwesome-win.zip" "NTAAwesome"
if errorlevel 1 (
    popd >nul
    exit /b 1
)
popd >nul

echo.
echo Windows release bundle ready:
echo   %DIST_DIR%
echo   %DIST_ZIP%
echo.
exit /b 0
