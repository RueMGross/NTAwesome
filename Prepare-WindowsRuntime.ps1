[CmdletBinding()]
param(
    [string]$PythonCommand = "",
    [string]$PythonVersion = "3.11.9",
    [string]$PythonArchiveUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.zip",
    [string]$PythonInstallerUrl = "",
    [switch]$ForceReinstall,
    [switch]$SkipSystemPython
)

$setupArgs = @()
if ($PythonCommand) {
    $setupArgs += @("-PythonCommand", $PythonCommand)
}
if ($PythonVersion) {
    $setupArgs += @("-PythonVersion", $PythonVersion)
}
if ($PythonArchiveUrl) {
    $setupArgs += @("-PythonArchiveUrl", $PythonArchiveUrl)
} elseif ($PythonInstallerUrl) {
    $setupArgs += @("-PythonInstallerUrl", $PythonInstallerUrl)
}
if ($ForceReinstall) {
    $setupArgs += "-ForceReinstall"
}
if ($SkipSystemPython) {
    $setupArgs += "-SkipSystemPython"
}

& "$PSScriptRoot\Setup-NTAwesome.cmd" @setupArgs
exit $LASTEXITCODE
