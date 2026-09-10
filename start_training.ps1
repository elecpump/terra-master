param(
    [ValidatePattern('^[a-z0-9][a-z0-9_-]{0,39}$')][string]$Name = 'training-m0',
    [string]$TmlInstallPath = 'D:\software\Steam\steamapps\common\tModLoader'
)
$ErrorActionPreference = 'Stop'
$profileRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "profiles\$Name"))
$marker = Get-Content -LiteralPath (Join-Path $profileRoot 'terramaster-training.json') -Raw | ConvertFrom-Json
if ($marker.schema -ne 1 -or $marker.purpose -ne 'training' -or $marker.saveRoot -ne $profileRoot) {
    throw 'Training profile marker does not match its directory'
}
for ($checkPath = $profileRoot; $checkPath; $checkPath = [IO.Path]::GetDirectoryName($checkPath)) {
    if ((Get-Item -LiteralPath $checkPath).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Redirected profile directory is not supported'
    }
}
if (!(Test-Path -LiteralPath (Join-Path $profileRoot 'Mods\TerraBridge.tmod'))) { throw 'Build TerraBridge into the profile first' }
# Port ownership is checked without contacting or stopping another game instance.
if (Get-NetTCPConnection -LocalPort 17655 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 17655 is occupied. Save and exit the existing game before launching.'
}
$launcher = Join-Path $TmlInstallPath 'start-tModLoader.bat'
if ($profileRoot.Contains('"')) { throw 'Invalid quote in profile path' }
$launchProcess = Start-Process -FilePath $launcher -ArgumentList @('-tmlsavedirectory', ('"' + $profileRoot + '"')) -WorkingDirectory $TmlInstallPath -WindowStyle Hidden -PassThru
@{
    launchedAt=[DateTime]::UtcNow.ToString('o'); launcherPid=$launchProcess.Id;
    launcher=$launcher; saveRoot=$profileRoot; profileId=$marker.profileId;
    note='Launcher PID is not proof of game process ownership. This script never terminates processes.'
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $profileRoot 'launch.json') -Encoding utf8
Write-Output "Started isolated profile: $profileRoot. Create LOCAL character/world names beginning TM-Training-."
