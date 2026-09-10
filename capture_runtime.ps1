param(
    [string]$TmlInstallPath = 'D:\software\Steam\steamapps\common\tModLoader',
    [string]$ModPath = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'My Games\Terraria\tModLoader\Mods\TerraBridge.tmod'),
    [string]$OutputPath = (Join-Path $PSScriptRoot 'runtime-manifest.json')
)
$ErrorActionPreference = 'Stop'
$assembly = Get-Item -LiteralPath (Join-Path $TmlInstallPath 'tModLoader.dll')
$runtime = Join-Path $TmlInstallPath 'dotnet\dotnet.exe'
$runtimes = @(& $runtime --list-runtimes)
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect bundled runtimes' }
$artifacts = [ordered]@{}
foreach ($entry in @(
    @{Name='tmodloader'; Path=$assembly.FullName},
    @{Name='bridge_package'; Path=$ModPath}
)) {
    $file = Get-Item -LiteralPath $entry.Path
    $artifacts[$entry.Name] = [ordered]@{
        path=$file.FullName
        sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        bytes=$file.Length
    }
}
$sourceHashes = [ordered]@{}
Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'TerraBridge') -File | Where-Object {
    $_.Extension -eq '.cs' -or $_.Name -eq 'build.txt'
} | Sort-Object Name | ForEach-Object {
    $sourceHashes[$_.Name] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
}
$manifest = [ordered]@{
    schema=1
    capturedAt=[DateTime]::UtcNow.ToString('o')
    terrariaVersion=$assembly.VersionInfo.FileVersion
    tmodloaderProductVersion=$assembly.VersionInfo.ProductVersion
    bundledRuntimes=$runtimes
    runtimeConfig=(Get-Content -LiteralPath (Join-Path $TmlInstallPath 'tModLoader.runtimeconfig.json') -Raw | ConvertFrom-Json)
    expectedBridgeVersion='0.3'
    protocol=1
    buildCommand='.\build_bridge.ps1'
    artifacts=$artifacts
    sourceSha256=$sourceHashes
    provenance='Installed files sampled, not rebuilt. Source/package correspondence and loaded package hash are not attested by protocol 1.'
    referenceSourceIsBuildDependency=$false
    trainingProfile=$null
    synchronization='unverified'
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Output "Runtime manifest saved: $OutputPath"
