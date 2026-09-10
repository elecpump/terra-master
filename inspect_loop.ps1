param(
    [string]$TmlInstallPath = 'D:\software\Steam\steamapps\common\tModLoader',
    [string]$OutputPath = (Join-Path $PSScriptRoot 'runs\loop-inspection.json')
)
$ErrorActionPreference = 'Stop'
$assemblyPath = Join-Path $TmlInstallPath 'tModLoader.dll'
$cecilFiles = @(Get-ChildItem -LiteralPath (Join-Path $TmlInstallPath 'Libraries\mono.cecil') -Recurse -Filter Mono.Cecil.dll)
if ($cecilFiles.Count -ne 1) { throw 'Expected one installed Mono.Cecil assembly' }
Add-Type -Path $cecilFiles[0].FullName
$assembly = [Mono.Cecil.AssemblyDefinition]::ReadAssembly($assemblyPath)
try {
    $methods = [ordered]@{}
    foreach ($spec in @(
        @{Type='Terraria.Main'; Method='DoUpdate'; Pattern='CanPauseGame|DoUpdate_WhilePaused|UpdateWeather|PreUpdateEntities|DoUpdateInWorld|DoUpdate_AutoSave|hasFocus'},
        @{Type='Terraria.Main'; Method='DoUpdateInWorld'; Pattern='Player::Update\(|NPC::UpdateNPC|Projectile::Update|Main::UpdateTime|WorldGen::UpdateWorld|PostUpdateEverything'},
        @{Type='Terraria.Main'; Method='CanPauseGame'; Pattern='.*'},
        @{Type='Terraria.Player'; Method='Update'; Pattern='ResetControls|hasFocus|PlayerLoader::SetControls'}
    )) {
        $type = $assembly.MainModule.Types | Where-Object FullName -eq $spec.Type
        $method = @($type.Methods | Where-Object { $_.Name -eq $spec.Method -and $_.Parameters.Count -eq $(if ($spec.Method -eq 'CanPauseGame') {0} else {1}) })
        if ($method.Count -ne 1 -or !$method[0].HasBody) { throw "Cannot identify $($spec.Type)::$($spec.Method)" }
        $instructions = $method[0].Body.Instructions
        $rows = [System.Collections.Generic.List[string]]::new()
        for ($index = 0; $index -lt $instructions.Count; $index++) {
            if ($instructions[$index].Operand -match $spec.Pattern -and $instructions[$index].OpCode.FlowControl.ToString() -ne 'Branch') {
                $rows.Add($instructions[$index].ToString())
            }
        }
        $methods[$method[0].FullName] = $rows.ToArray()
    }
    $report = [ordered]@{
        schema=1; generatedAtUtc=[DateTime]::UtcNow.ToString('o')
        assemblyPath=$assemblyPath; assemblySha256=(Get-FileHash -LiteralPath $assemblyPath -Algorithm SHA256).Hash.ToLowerInvariant()
        productVersion=(Get-Item -LiteralPath $assemblyPath).VersionInfo.ProductVersion
        methods=$methods
        limitation='Static IL inspection only. Does not prove whole-world freeze, determinism, acceleration or runtime hook behavior.'
    }
    $fullOutput = [IO.Path]::GetFullPath($OutputPath)
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($fullOutput)) | Out-Null
    $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $fullOutput -Encoding utf8
    Write-Output "Loop inspection saved: $fullOutput"
} finally { $assembly.Dispose() }
