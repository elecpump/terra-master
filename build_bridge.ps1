param(
    [string]$TmlInstallPath = 'D:\software\Steam\steamapps\common\tModLoader',
    [string]$SavePath
)
$ErrorActionPreference = 'Stop'
$runtime = Join-Path $TmlInstallPath 'dotnet\dotnet.exe'
if (!(Test-Path -LiteralPath $runtime)) { throw "Bundled runtime not found: $runtime" }
if (!(Test-Path -LiteralPath (Join-Path $TmlInstallPath 'tModLoader.dll'))) { throw 'tModLoader.dll not found' }
Push-Location -LiteralPath $TmlInstallPath
try {
    $buildArgs = @('tModLoader.dll', '-server', '-build', (Join-Path $PSScriptRoot 'TerraBridge'))
    if ($SavePath) { $buildArgs += @('-tmlsavedirectory', [IO.Path]::GetFullPath($SavePath)) }
    & $runtime @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "Mod build failed: $LASTEXITCODE" }
} finally { Pop-Location }
