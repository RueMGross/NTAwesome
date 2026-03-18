[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Path,
    [switch]$SkipSetup
)

$launcherArgs = @()
if ($SkipSetup) {
    $launcherArgs += "-SkipSetup"
}
if ($Path) {
    $launcherArgs += $Path
}

& "$PSScriptRoot\Run-NTAwesome.cmd" @launcherArgs
exit $LASTEXITCODE
